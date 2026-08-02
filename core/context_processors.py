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
    guia = guias.obtener(request.path)
    if guia:
        guia = dict(guia)
        guia['doc_slug'], guia['doc_nombre'] = _documento_para(request, guia)
    return {'guia': guia}


def _documento_para(request, guia):
    """A qué documento enlaza el recuadro según quién mira.

    Casi todas las guías apuntan a documentación del operador. Para un cliente
    esos enlaces dan 404, así que se le manda a la suya en lugar de dejarle un
    enlace roto en cada pantalla.
    """
    from panel.view_doc import SOLO_OPERADOR, _es_operador, _mapa_documentos

    try:
        if _es_operador(request):
            return guia['doc_slug'], guia['doc_nombre']
        entrada = _mapa_documentos().get(guia['doc_slug'])
        if entrada and entrada[2] == SOLO_OPERADOR:
            return 'guia-cliente', 'Guía para empezar'
    except Exception:
        pass
    return guia['doc_slug'], guia['doc_nombre']
