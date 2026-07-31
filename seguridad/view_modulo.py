"""Módulos (URLs del sistema) y secciones del menú lateral."""
import sys

from django.db import transaction
from django.http import JsonResponse

from core.crud import ConfigCrud, vista_crud
from core.funciones import log, secure_module

from .forms import ModuloForm, SeccionMenuForm
from .models import Modulo, ModuloGrupo
from .sincronizacion import sincronizar_modulos


def _contexto_modulo(request, data):
    data['sin_seccion'] = Modulo.objects.filter(status=True, grupos_menu__isnull=True).count()
    data['total_secciones'] = ModuloGrupo.objects.filter(status=True).count()


@secure_module
def modulo_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'sincronizar':
        try:
            with transaction.atomic():
                creados, existentes = sincronizar_modulos()
            log(f'Sincronizó módulos del sistema: {creados} nuevos', request, 'change')
            return JsonResponse({
                'error': False,
                'message': (f'{creados} módulo{"s" if creados != 1 else ""} nuevo'
                            f'{"s" if creados != 1 else ""} · {existentes} ya existían.'),
                'creados': creados,
            })
        except Exception as ex:
            linea = sys.exc_info()[-1].tb_lineno
            return JsonResponse({'error': True, 'message': f'{ex} - Línea {linea}'}, status=400)

    return vista_crud(request, ConfigCrud(
        modelo=Modulo,
        formulario=ModuloForm,
        titulo='Módulos del sistema',
        modulo='Seguridad',
        plantilla_listado='seguridad/modulo_listado.html',
        plantilla_formulario='seguridad/modulo_form.html',
        campos_busqueda=('nombre', 'url', 'descripcion'),
        orden=('orden', 'nombre'),
        singular='un módulo',
        prefetch_related=('grupos_menu', 'roles_asignados'),
        contexto_extra=_contexto_modulo,
        por_pagina=50,
    ))


@secure_module
def seccion_menu_view(request):
    return vista_crud(request, ConfigCrud(
        modelo=ModuloGrupo,
        formulario=SeccionMenuForm,
        titulo='Secciones del menú',
        modulo='Seguridad',
        plantilla_listado='seguridad/seccion_listado.html',
        plantilla_formulario='seguridad/seccion_form.html',
        campos_busqueda=('nombre',),
        orden=('prioridad', 'nombre'),
        singular='una sección del menú',
        prefetch_related=('modulos',),
    ))
