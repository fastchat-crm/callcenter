"""Vistas de sesion: ingreso, salida y cambio de contrasena."""
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.funciones import log

from .forms import CambiarClaveForm, LoginForm


def login_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('/panel/')

    data = {'titulo': 'Ingreso al sistema'}
    if request.method == 'POST':
        formulario = LoginForm(request.POST)
        if formulario.is_valid():
            usuario = authenticate(
                request,
                username=formulario.cleaned_data['username'].strip(),
                password=formulario.cleaned_data['password'],
            )
            if usuario is None:
                messages.error(request, 'Usuario o contraseña incorrectos.')
            elif not usuario.is_active:
                messages.error(request, 'Tu usuario está inactivo. Contacta al administrador.')
            else:
                login(request, usuario)
                log('Inició sesión', request, 'login')
                if usuario.cambiar_clave:
                    return HttpResponseRedirect('/changepass/')
                return HttpResponseRedirect(request.GET.get('next') or '/panel/')
        data['form'] = formulario
    else:
        data['form'] = LoginForm()
    return render(request, 'autenticacion/login.html', data)


def logout_view(request):
    if request.user.is_authenticated:
        log('Cerró sesión', request, 'logout')
    logout(request)
    return HttpResponseRedirect('/login/')


def cambiar_clave_view(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/login/')

    data = {'titulo': 'Cambiar contraseña'}
    if request.method == 'POST':
        formulario = CambiarClaveForm(request.POST)
        if formulario.is_valid():
            if not request.user.check_password(formulario.cleaned_data['clave_actual']):
                messages.error(request, 'La contraseña actual no es correcta.')
            else:
                request.user.set_password(formulario.cleaned_data['clave_nueva'])
                request.user.cambiar_clave = False
                request.user.save()
                update_session_auth_hash(request, request.user)
                log('Cambió su contraseña', request, 'change')
                messages.success(request, 'Contraseña actualizada.')
                return HttpResponseRedirect('/panel/')
        data['form'] = formulario
    else:
        data['form'] = CambiarClaveForm()
    return render(request, 'autenticacion/cambiar_clave.html', data)
