"""Perfil del usuario autenticado."""
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.funciones import addData, log, secure_module

from .forms import PerfilForm


@secure_module
def perfil_view(request):
    data = {'titulo': 'Mi perfil', 'modulo': 'Administración'}
    addData(request, data)

    if request.method == 'POST':
        formulario = PerfilForm(request.POST, request.FILES, instance=request.user)
        if formulario.is_valid():
            formulario.save()
            log('Actualizó su perfil', request, 'change')
            messages.success(request, 'Perfil actualizado.')
            return HttpResponseRedirect('/perfilpanel/')
        messages.error(request, 'Revisa los datos del formulario.')
        data['form'] = formulario
    else:
        data['form'] = PerfilForm(instance=request.user)
    return render(request, 'autenticacion/perfil.html', data)
