"""Quién es el cliente activo y cómo se acota todo a él.

Un usuario con `cliente` asignado solo existe dentro de ese cliente: no puede
verlo ni cambiarlo. Un usuario sin cliente es del operador y elige con cuál
trabajar; la elección vive en la sesión.
"""
from django.db.models import Q

from .models import Cliente

CLAVE_SESION = 'cliente_activo'
CLAVE_MODO = 'ver_como_cliente'
ROL_CLIENTE = 'Cliente'


def en_modo_cliente(request):
    """El operador está mirando el panel con los ojos de su cliente.

    Sirve para comprobar qué ve de verdad quien va a usar el sistema, sin tener
    que crear un usuario aparte y cerrar sesión. Solo cambia lo que se ve: los
    datos ya venían acotados al cliente activo.
    """
    sesion = getattr(request, 'session', None)
    return bool(sesion.get(CLAVE_MODO)) if sesion is not None else False


def activar_modo_cliente(request):
    request.session[CLAVE_MODO] = True


def salir_modo_cliente(request):
    request.session.pop(CLAVE_MODO, None)


def es_operador(usuario):
    """Sin cliente propio: puede recorrer todos los clientes."""
    return bool(usuario) and usuario.is_authenticated and usuario.cliente_id is None


def clientes_visibles(usuario):
    listado = Cliente.objects.filter(status=True, activo=True)
    if es_operador(usuario):
        return listado
    return listado.filter(pk=getattr(usuario, 'cliente_id', None))


def cliente_actual(request):
    """Cliente sobre el que trabaja la pantalla; None si todavía no hay ninguno."""
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return None
    if not es_operador(usuario):
        return usuario.cliente

    elegido = request.session.get(CLAVE_SESION)
    cliente = Cliente.objects.filter(pk=elegido, status=True, activo=True).first() if elegido else None
    if cliente is None:
        cliente = clientes_visibles(usuario).order_by('nombre').first()
        if cliente is not None:
            request.session[CLAVE_SESION] = cliente.pk
    return cliente


def elegir_cliente(request, cliente_id):
    """Cambia el cliente activo. Devuelve el cliente o None si no le corresponde."""
    cliente = clientes_visibles(request.user).filter(pk=cliente_id).first()
    if cliente is not None:
        request.session[CLAVE_SESION] = cliente.pk
    return cliente


def modelo_por_cliente(modelo):
    return any(campo.name == 'cliente' for campo in modelo._meta.fields)


def es_compartible(modelo):
    """El modelo admite registros sin cliente, visibles para todos (llaves de IA)."""
    return bool(getattr(modelo, 'CLIENTE_COMPARTIBLE', False))


def filtro_cliente(request, modelo):
    """Q que acota el modelo al cliente activo; vacío si el modelo no es por cliente."""
    if not modelo_por_cliente(modelo):
        return Q()
    cliente = cliente_actual(request)
    if cliente is None:
        return Q(cliente__isnull=True) if es_compartible(modelo) else Q(pk__isnull=True)
    filtro = Q(cliente=cliente)
    if es_compartible(modelo):
        filtro |= Q(cliente__isnull=True)
    return filtro


def acotar(queryset, request):
    """Aplica el filtro del cliente activo a un queryset cualquiera."""
    return queryset.filter(filtro_cliente(request, queryset.model))


def solo_operador(vista):
    """Pantalla que un usuario de cliente no debe abrir jamás.

    Es para lo que no se filtra por cliente porque es infraestructura
    compartida: proveedores y troncales llevan las credenciales del carrier del
    operador, y el CRUD genérico no puede protegerlas —no hay FK `cliente` por
    la que filtrar—. Sin esto, un usuario con el rol equivocado abre el
    formulario del proveedor y ve el token.
    """
    from functools import wraps

    from django.http import JsonResponse
    from django.shortcuts import render

    @wraps(vista)
    def envoltorio(request, *args, **kwargs):
        usuario = getattr(request, 'user', None)
        # En modo cliente el operador se autoimpone el límite: si no, entraría a
        # pantallas que su cliente no ve y la comprobación no serviría de nada.
        if (usuario is not None and usuario.is_authenticated
                and not en_modo_cliente(request)
                and (usuario.is_superuser or es_operador(usuario))):
            return vista(request, *args, **kwargs)
        mensaje = 'Esta pantalla es del operador del sistema.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'action' in request.GET:
            return JsonResponse({'result': False, 'error': True, 'message': mensaje}, status=403)
        return render(request, '403.html', status=403)

    return envoltorio
