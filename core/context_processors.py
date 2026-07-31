from django.conf import settings


def datos_sistema(request):
    return {
        'nombre_sistema': settings.NOMBRE_SISTEMA,
        'url_general': settings.URL_GENERAL,
        'ip_publica': settings.IP_PUBLICA,
        'debug_activo': settings.DEBUG,
    }
