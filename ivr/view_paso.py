"""Pasos y opciones de un flujo IVR, más el simulador de conversación."""
import sys

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import get_template

from core.custom_models import FormError
from core.funciones import addData, log, secure_module

from .forms import OpcionForm, PasoForm
from .models import FlujoVoz, OpcionPaso, PasoVoz


@secure_module
def paso_view(request, flujo_id):
    flujo = FlujoVoz.objects.filter(pk=flujo_id, status=True).first()
    if flujo is None:
        return JsonResponse({'error': True, 'message': 'El flujo no existe.'}, status=404)

    data = {'titulo': f'Pasos · {flujo.nombre}', 'modulo': 'Configuración de voz', 'flujo': flujo}

    if request.method == 'POST':
        respuesta = []
        accion = request.POST.get('action', '')
        try:
            with transaction.atomic():
                if accion in ('add', 'change'):
                    if accion == 'add':
                        formulario = PasoForm(request.POST, request.FILES, flujo=flujo)
                    else:
                        instancia = PasoVoz.objects.get(pk=int(request.POST['pk']), flujo=flujo)
                        formulario = PasoForm(request.POST, request.FILES, instance=instancia, flujo=flujo)
                    if not formulario.is_valid():
                        raise FormError(formulario)
                    paso = formulario.save(commit=False)
                    paso.flujo = flujo
                    paso.save(request)
                    if flujo.paso_inicial_id is None:
                        flujo.paso_inicial = paso
                        flujo.save(request)
                    log(f'Guardó el paso {paso}', request, accion, obj=paso.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'delete':
                    paso = PasoVoz.objects.get(pk=int(request.POST['id']), flujo=flujo)
                    paso.status = False
                    paso.save(request)
                    log(f'Eliminó el paso {paso}', request, 'del', obj=paso.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'add_opcion':
                    formulario = OpcionForm(request.POST)
                    if not formulario.is_valid():
                        raise FormError(formulario)
                    opcion = formulario.save(commit=False)
                    opcion.save(request)
                    log(f'Agregó la opción {opcion}', request, 'add', obj=opcion.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'delete_opcion':
                    opcion = OpcionPaso.objects.get(pk=int(request.POST['id']))
                    opcion.status = False
                    opcion.save(request)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'simular':
                    return _simular(request, flujo)

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
                data['form'] = PasoForm(flujo=flujo)
                return JsonResponse({'result': True, 'data': get_template('ivr/paso_form.html').render(data, request)})
            if accion == 'change':
                paso = PasoVoz.objects.get(pk=int(request.GET['id']), flujo=flujo)
                data['filtro'] = paso
                data['form'] = PasoForm(instance=paso, flujo=flujo)
                return JsonResponse({'result': True, 'data': get_template('ivr/paso_form.html').render(data, request)})
            if accion == 'add_opcion':
                paso = PasoVoz.objects.get(pk=int(request.GET['id']), flujo=flujo)
                formulario = OpcionForm(initial={'paso': paso})
                formulario.fields['paso_destino'].queryset = flujo.pasos.filter(status=True)
                data['form'] = formulario
                data['paso'] = paso
                return JsonResponse({'result': True, 'data': get_template('ivr/opcion_form.html').render(data, request)})
        except Exception as ex:
            return JsonResponse({'result': False, 'message': str(ex)})

    data['pasos'] = (
        flujo.pasos.filter(status=True)
        .select_related('paso_siguiente', 'asesor', 'agente_ia')
        .prefetch_related('opciones')
        .order_by('orden', 'id')
    )
    return render(request, 'ivr/paso_listado.html', data)


def _simular(request, flujo):
    """Corre el motor sin telefonía: útil para probar el flujo desde el panel."""
    from ivr.motor import MotorIVR

    historial = request.POST.get('historial') or ''
    entradas = [linea for linea in historial.split('|') if linea.strip()]
    motor = MotorIVR(flujo)
    salidas = [motor.iniciar().texto]
    for entrada in entradas:
        resultado = motor.procesar_entrada(entrada)
        salidas.append(resultado.texto)
        if resultado.finalizar or resultado.transferir:
            break
    return JsonResponse({'error': False, 'salidas': salidas, 'variables': motor.variables})
