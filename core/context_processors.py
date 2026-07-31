from django.conf import settings

from core import guias


def datos_sistema(request):
    return {
        'nombre_sistema': settings.NOMBRE_SISTEMA,
        'url_general': settings.URL_GENERAL,
        'ip_publica': settings.IP_PUBLICA,
        'debug_activo': settings.DEBUG,
    }


def guia_pantalla(request):
    """Guía de la ventana actual, resuelta por la ruta para no tocar cada vista."""
    return {'guia': guias.obtener(request.path)}
