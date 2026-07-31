"""CRUD genérico con el patrón de vistas basadas en funciones del proyecto.

Cada módulo del panel declara un `ConfigCrud` y llama a `vista_crud`. Se
mantiene el contrato del sistema original:

  GET  sin `action`      → listado paginado (plantilla `<plantilla_listado>`)
  GET  ?action=add       → JSON con el HTML del formulario
  GET  ?action=change    → JSON con el HTML del formulario cargado
  GET  ?action=ver       → plantilla de detalle
  POST action=add        → crea
  POST action=change     → edita
  POST action=delete     → borrado lógico (`status = False`)
"""
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import get_template

from clientes.contexto import cliente_actual, es_compartible, filtro_cliente, modelo_por_cliente
from core.custom_models import FormError
from core.funciones import addData, log, paginador


@dataclass
class ConfigCrud:
    modelo: type
    formulario: type
    titulo: str
    modulo: str
    plantilla_listado: str
    plantilla_formulario: str
    plantilla_detalle: str = ''
    campos_busqueda: tuple = ('nombre',)
    orden: tuple = ('-id',)
    singular: str = 'registro'
    filtros_extra: Optional[Callable] = None
    select_related: tuple = ()
    prefetch_related: tuple = ()
    contexto_extra: Optional[Callable] = None
    al_guardar: Optional[Callable] = None
    por_pagina: int = 25
    permitir_eliminar: bool = True
    contexto: dict = field(default_factory=dict)


def vista_crud(request, config: ConfigCrud):
    data = {'titulo': config.titulo, 'modulo': config.modulo, **config.contexto}
    modelo, Formulario = config.modelo, config.formulario

    if request.method == 'POST':
        return _procesar_post(request, config, modelo, Formulario)

    addData(request, data)
    if 'action' in request.GET:
        return _procesar_get_accion(request, config, data, modelo, Formulario)

    criterio = (request.GET.get('criterio') or '').strip()
    filtros = Q(status=True) & filtro_cliente(request, modelo)
    url_vars = ''
    if criterio and config.campos_busqueda:
        busqueda = Q()
        for campo in config.campos_busqueda:
            busqueda |= Q(**{f'{campo}__icontains': criterio})
        filtros &= busqueda
        data['criterio'] = criterio
        url_vars += f'&criterio={criterio}'

    if config.filtros_extra is not None:
        filtros, url_vars = config.filtros_extra(request, filtros, url_vars, data)

    listado = modelo.objects.filter(filtros)
    if config.select_related:
        listado = listado.select_related(*config.select_related)
    if config.prefetch_related:
        listado = listado.prefetch_related(*config.prefetch_related)
    listado = listado.order_by(*config.orden)

    paginador(request, listado, data, config.por_pagina, url_vars)
    if config.contexto_extra is not None:
        config.contexto_extra(request, data)
    return render(request, config.plantilla_listado, data)


def _obtener(request, modelo, pk):
    """Trae el registro solo si pertenece al cliente activo."""
    return modelo.objects.filter(filtro_cliente(request, modelo)).get(pk=int(pk))


def _procesar_post(request, config, modelo, Formulario):
    respuesta = []
    accion = request.POST.get('action', '')
    try:
        with transaction.atomic():
            if accion == 'add':
                formulario = Formulario(request.POST, request.FILES)
                if not formulario.is_valid():
                    raise FormError(formulario)
                instancia = formulario.save(commit=False)
                # Los modelos compartibles deciden en su formulario si la fila
                # es de un cliente o del operador; al resto se les impone el activo.
                if (modelo_por_cliente(modelo) and not es_compartible(modelo)
                        and instancia.cliente_id is None):
                    instancia.cliente = cliente_actual(request)
                instancia.save(request)
                formulario.save_m2m()
                if config.al_guardar is not None:
                    config.al_guardar(request, instancia, 'add')
                log(f'Registró {config.singular}: {instancia}', request, 'add', obj=instancia.id)
                respuesta.append({'error': False, 'reload': True})

            elif accion == 'change':
                instancia = _obtener(request, modelo, request.POST['pk'])
                formulario = Formulario(request.POST, request.FILES, instance=instancia)
                if not formulario.is_valid():
                    raise FormError(formulario)
                instancia = formulario.save(commit=False)
                instancia.save(request)
                formulario.save_m2m()
                if config.al_guardar is not None:
                    config.al_guardar(request, instancia, 'change')
                log(f'Editó {config.singular}: {instancia}', request, 'change', obj=instancia.id)
                respuesta.append({'error': False, 'reload': True})

            elif accion == 'delete' and config.permitir_eliminar:
                instancia = _obtener(request, modelo, request.POST['id'])
                instancia.status = False
                instancia.save(request)
                log(f'Eliminó {config.singular}: {instancia}', request, 'del', obj=instancia.id)
                messages.success(request, 'Registro eliminado.')
                return JsonResponse({'error': False})

            else:
                respuesta.append({'error': True, 'message': f'Acción no soportada: {accion}'})

    except FormError as ex:
        respuesta = [ex.dict_error]
    except modelo.DoesNotExist:
        respuesta = [{'error': True, 'message': 'El registro no existe.'}]
    except Exception as ex:
        linea = sys.exc_info()[-1].tb_lineno
        respuesta = [{'error': True, 'message': f'{ex} - Línea {linea}'}]
    return JsonResponse(respuesta, safe=False)


def _procesar_get_accion(request, config, data, modelo, Formulario):
    accion = request.GET['action']
    data['action'] = accion
    try:
        if accion == 'add':
            data['form'] = Formulario()
            plantilla = get_template(config.plantilla_formulario)
            return JsonResponse({'result': True, 'data': plantilla.render(data, request)})

        if accion == 'change':
            instancia = _obtener(request, modelo, request.GET['id'])
            data['filtro'] = instancia
            data['form'] = Formulario(instance=instancia)
            plantilla = get_template(config.plantilla_formulario)
            return JsonResponse({'result': True, 'data': plantilla.render(data, request)})

        if accion == 'ver' and config.plantilla_detalle:
            instancia = _obtener(request, modelo, request.GET['id'])
            data['filtro'] = instancia
            if config.contexto_extra is not None:
                config.contexto_extra(request, data)
            return render(request, config.plantilla_detalle, data)

        return JsonResponse({'result': False, 'message': f'Acción no soportada: {accion}'})
    except modelo.DoesNotExist:
        return JsonResponse({'result': False, 'message': 'El registro no existe.'})
    except Exception as ex:
        return JsonResponse({'result': False, 'message': str(ex)})
