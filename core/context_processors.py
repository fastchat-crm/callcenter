from django.conf import settings

from core import guias


def _configuracion():
    """Fila única de configuración; None si la tabla aún no existe (primer migrate)."""
    from core.models import Configuracion

    try:
        return Configuracion.get_instancia()
    except Exception:
        return None


def datos_sistema(request):
    return {
        'configuracion': _configuracion(),
        'nombre_sistema': settings.NOMBRE_SISTEMA,
        'url_general': settings.URL_GENERAL,
        'ip_publica': settings.IP_PUBLICA,
        'debug_activo': settings.DEBUG,
        'registro_abierto': _registro_abierto(),
    }


def _registro_abierto():
    from autenticacion.view_registro import registro_abierto

    try:
        return registro_abierto()
    except Exception:
        return False


def cliente_panel(request):
    """Cliente sobre el que trabaja el panel y los que puede elegir el usuario."""
    from clientes.contexto import cliente_actual, clientes_visibles, es_operador

    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {'cliente': None, 'clientes_elegibles': [], 'puede_cambiar_cliente': False,
                'modo_cliente': False, 'puede_ver_como_cliente': False}
    from clientes.contexto import en_modo_cliente

    modo = en_modo_cliente(request)
    return {
        'cliente': cliente_actual(request),
        'clientes_elegibles': clientes_visibles(usuario).order_by('nombre'),
        # En modo cliente el selector desaparece: un cliente no elige cliente.
        'puede_cambiar_cliente': es_operador(usuario) and not modo,
        'modo_cliente': modo,
        'puede_ver_como_cliente': es_operador(usuario) or usuario.is_superuser,
    }


def guia_pantalla(request):
    """Guía de la ventana actual, resuelta por la ruta para no tocar cada vista."""
    return {'guia': guias.obtener(request.path)}
