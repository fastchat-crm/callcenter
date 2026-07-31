"""Health check para monitoreo externo y balanceadores."""
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def health_view(request):
    estado = {'servicio': 'callcenter', 'base_datos': False, 'redis': False}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        estado['base_datos'] = True
    except Exception as ex:
        estado['error_base_datos'] = str(ex)

    if getattr(settings, 'USAR_REDIS', False):
        try:
            from django.core.cache import cache
            cache.set('health', 1, 10)
            estado['redis'] = cache.get('health') == 1
        except Exception as ex:
            estado['error_redis'] = str(ex)
    else:
        estado['redis'] = None

    ok = estado['base_datos'] and (estado['redis'] is not False)
    return JsonResponse({'ok': ok, **estado}, status=200 if ok else 503)
