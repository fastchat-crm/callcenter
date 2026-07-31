"""Base de conocimiento: colecciones, documentos e indexación del RAG."""
import sys

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import get_template

from core.custom_models import FormError
from core.funciones import addData, log, paginador, secure_module

from .forms import ColeccionForm, DocumentoForm
from .models import ColeccionConocimiento, DocumentoConocimiento


@secure_module
def conocimiento_view(request):
    data = {'titulo': 'Base de conocimiento', 'modulo': 'Configuración de voz'}

    if request.method == 'POST':
        respuesta = []
        accion = request.POST.get('action', '')
        try:
            with transaction.atomic():
                if accion in ('add', 'change'):
                    if accion == 'add':
                        formulario = ColeccionForm(request.POST)
                    else:
                        instancia = ColeccionConocimiento.objects.get(pk=int(request.POST['pk']))
                        formulario = ColeccionForm(request.POST, instance=instancia)
                    if not formulario.is_valid():
                        raise FormError(formulario)
                    coleccion = formulario.save(commit=False)
                    coleccion.save(request)
                    log(f'Guardó la colección {coleccion}', request, accion, obj=coleccion.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'delete':
                    coleccion = ColeccionConocimiento.objects.get(pk=int(request.POST['id']))
                    coleccion.status = False
                    coleccion.save(request)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'add_documento':
                    formulario = DocumentoForm(request.POST, request.FILES)
                    if not formulario.is_valid():
                        raise FormError(formulario)
                    documento = formulario.save(commit=False)
                    documento.save(request)
                    log(f'Cargó el documento {documento}', request, 'add', obj=documento.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'delete_documento':
                    documento = DocumentoConocimiento.objects.get(pk=int(request.POST['id']))
                    documento.status = False
                    documento.save(request)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'reindexar':
                    coleccion = ColeccionConocimiento.objects.get(pk=int(request.POST['id']))
                    total = coleccion.reindexar()
                    log(f'Reindexó la colección {coleccion}', request, 'change', obj=coleccion.id)
                    return JsonResponse({
                        'error': False,
                        'message': f'Colección indexada con {total} fragmentos.',
                        'fragmentos': total,
                    })

                elif accion == 'buscar':
                    from .rag import buscar_en_coleccion

                    coleccion = ColeccionConocimiento.objects.get(pk=int(request.POST['id']))
                    resultados = buscar_en_coleccion(coleccion, request.POST.get('consulta') or '', 5)
                    return JsonResponse({'error': False, 'resultados': resultados})

                else:
                    respuesta.append({'error': True, 'message': f'Acción no soportada: {accion}'})

        except FormError as ex:
            respuesta = [ex.dict_error]
        except Exception as ex:
            linea = sys.exc_info()[-1].tb_lineno
            respuesta = [{'error': True, 'message': f'{ex} - Línea {linea}'}]
        return JsonResponse(respuesta, safe=False)

    addData(request, data)
    if 'action' in request.GET:
        accion = request.GET['action']
        data['action'] = accion
        try:
            if accion == 'add':
                data['form'] = ColeccionForm()
                return JsonResponse({'result': True,
                                     'data': get_template('agentes_ia/coleccion_form.html').render(data, request)})
            if accion == 'change':
                coleccion = ColeccionConocimiento.objects.get(pk=int(request.GET['id']))
                data['filtro'] = coleccion
                data['form'] = ColeccionForm(instance=coleccion)
                return JsonResponse({'result': True,
                                     'data': get_template('agentes_ia/coleccion_form.html').render(data, request)})
            if accion == 'add_documento':
                coleccion = ColeccionConocimiento.objects.get(pk=int(request.GET['id']))
                data['form'] = DocumentoForm(initial={'coleccion': coleccion})
                data['coleccion'] = coleccion
                return JsonResponse({'result': True,
                                     'data': get_template('agentes_ia/documento_form.html').render(data, request)})
            if accion == 'ver':
                coleccion = ColeccionConocimiento.objects.get(pk=int(request.GET['id']))
                data['filtro'] = coleccion
                data['documentos'] = coleccion.documentos.filter(status=True).order_by('titulo')
                return render(request, 'agentes_ia/coleccion_detalle.html', data)
        except Exception as ex:
            return JsonResponse({'result': False, 'message': str(ex)})

    listado = ColeccionConocimiento.objects.filter(status=True).order_by('nombre')
    criterio = (request.GET.get('criterio') or '').strip()
    if criterio:
        listado = listado.filter(nombre__icontains=criterio)
        data['criterio'] = criterio
    paginador(request, listado, data, 25, f'&criterio={criterio}' if criterio else '')
    return render(request, 'agentes_ia/coleccion_listado.html', data)
