"""Middlewares base: request en thread-local y datos comunes de plantilla."""
import threading

_local = threading.local()


def get_current_request():
    return getattr(_local, 'request', None)


def get_current_user():
    request = get_current_request()
    if request is None:
        return None
    usuario = getattr(request, 'user', None)
    if usuario is not None and getattr(usuario, 'is_authenticated', False):
        return usuario
    return None


class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            respuesta = self.get_response(request)
        finally:
            _local.request = None
        return respuesta


class DatosInicialesApp:
    """Deja en el request los datos que todas las vistas del panel necesitan."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        request.nombre_sistema = settings.NOMBRE_SISTEMA
        request.url_general = settings.URL_GENERAL
        return self.get_response(request)
