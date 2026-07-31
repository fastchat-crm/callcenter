"""Registro público: alguien crea su cuenta y prueba el sistema por su cuenta.

Crea el cliente, su usuario con el rol Cliente y un flujo de arranque que ya
funciona, y lo deja en la puesta en marcha, que es la pantalla que explica qué
falta y por qué.

Se apaga desde *Parámetros del sistema* con `REGISTRO_ABIERTO`: dejarlo abierto
significa que cualquiera con la dirección puede crear una cuenta.
"""
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.funciones import log

from .forms import RegistroForm


def registro_abierto():
    try:
        from core.parametros import obtener

        return bool(obtener('REGISTRO_ABIERTO'))
    except Exception:
        return False


def registro_view(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect('/panel/')
    if not registro_abierto():
        return render(request, 'autenticacion/registro_cerrado.html', status=403)

    data = {'titulo': 'Crear cuenta'}
    if request.method == 'POST':
        formulario = RegistroForm(request.POST)
        if formulario.is_valid():
            usuario = _crear_cuenta(request, formulario)
            login(request, usuario)
            log(f'Se registró y creó el cliente {usuario.cliente}', request, 'add')
            messages.success(
                request,
                'Cuenta creada. Dejamos un flujo de ejemplo listo: pruébalo en Demo de voz.')
            return HttpResponseRedirect('/clientes/puesta-en-marcha/')
        data['form'] = formulario
    else:
        data['form'] = RegistroForm()
    return render(request, 'autenticacion/registro.html', data)


@transaction.atomic
def _crear_cuenta(request, formulario):
    """Cliente + usuario + flujo de arranque, todo o nada."""
    from django.contrib.auth.models import Group

    from clientes.alta import preparar_cliente
    from clientes.contexto import ROL_CLIENTE
    from clientes.models import Cliente

    from .models import Usuario

    datos = formulario.cleaned_data
    cliente = Cliente.objects.create(
        nombre=datos['empresa'],
        correo=datos['email'],
        activo=True,
    )
    usuario = Usuario(
        username=datos['username'],
        email=datos['email'],
        first_name=datos['nombres'],
        cliente=cliente,
        perfil='administrador',
        is_staff=True,          # necesario para entrar al panel
        is_superuser=False,     # jamás: es el usuario de un cliente
    )
    usuario.set_password(datos['clave'])
    usuario.save()

    rol = Group.objects.filter(name=ROL_CLIENTE).first()
    if rol is not None:
        usuario.groups.set([rol])

    preparar_cliente(cliente, request)
    return usuario
