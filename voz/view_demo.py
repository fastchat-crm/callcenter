"""Demo de voz por navegador y diagnóstico del pipeline."""
from django.http import JsonResponse
from django.shortcuts import render

from core.funciones import addData, secure_module


@secure_module
def demo_view(request):
    from ivr.models import FlujoVoz

    data = {'titulo': 'Demo de voz', 'modulo': 'Configuración de voz'}
    addData(request, data)
    data['flujos'] = list(
        FlujoVoz.objects.filter(status=True, activo=True).values('id', 'nombre').order_by('nombre')
    )
    data['url_websocket'] = _url_websocket(request)
    return render(request, 'voz/demo.html', data)


@secure_module
def estado_view(request):
    """Diagnóstico: qué motores del pipeline están listos en este servidor."""
    from voz.services import estado_motores

    return JsonResponse({'error': False, 'estado': estado_motores()})


def _url_websocket(request):
    esquema = 'wss' if request.is_secure() else 'ws'
    return f'{esquema}://{request.get_host()}/ws/voz/web/'
