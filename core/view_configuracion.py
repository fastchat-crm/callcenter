"""Configuración general: identidad de la empresa y datos de contacto.

Una sola fila, así que no hay listado ni modal: la pantalla es el formulario.
"""
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.funciones import addData, log, secure_module

from .forms import ConfiguracionForm
from .models import Configuracion


@secure_module
def configuracion_view(request):
    data = {'titulo': 'Configuración general', 'modulo': 'Centro de seguridad'}
    addData(request, data)
    configuracion = Configuracion.get_instancia()

    if request.method == 'POST':
        formulario = ConfiguracionForm(request.POST, request.FILES, instance=configuracion)
        if formulario.is_valid():
            formulario.save()
            log('Actualizó la configuración general', request, 'change')
            messages.success(request, 'Configuración actualizada.')
            return HttpResponseRedirect('/configuracion/')
        messages.error(request, 'Revisa los datos del formulario.')
        data['form'] = formulario
    else:
        data['form'] = ConfiguracionForm(instance=configuracion)

    data['configuracion'] = configuracion
    return render(request, 'core/configuracion.html', data)
