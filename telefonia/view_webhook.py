"""Webhooks de entrada de llamada.

Un solo endpoint sirve a todos los carriers compatibles con TwiML/TeXML
(Twilio, Telnyx, Plivo, SignalWire): la respuesta XML conecta la llamada al
WebSocket de Media Streams del propio servidor. Asterisk auto-hospedado usa el
mismo WebSocket a través de su módulo audiosocket/ARI.
"""
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger('telefonia')


def url_websocket_stream(request=None):
    host = (settings.VOZ_PUBLIC_HOST or '').strip()
    if not host and request is not None:
        host = request.get_host()
    host = host.replace('https://', '').replace('http://', '').rstrip('/')
    return f'{settings.VOZ_WS_ESQUEMA}://{host}/ws/voz/stream/'


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def webhook_llamada_entrante(request):
    """Devuelve el XML que conecta la llamada al motor de voz."""
    datos = request.POST if request.method == 'POST' else request.GET
    numero_origen = datos.get('From') or datos.get('from') or ''
    numero_destino = datos.get('To') or datos.get('to') or ''
    driver = datos.get('driver') or _detectar_driver(request)
    logger.info('[telefonia] llamada entrante %s → %s (driver=%s)', numero_origen, numero_destino, driver)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{url_websocket_stream(request)}">
            <Parameter name="from" value="{numero_origen}" />
            <Parameter name="to" value="{numero_destino}" />
            <Parameter name="driver" value="{driver}" />
        </Stream>
    </Connect>
</Response>"""
    return HttpResponse(xml, content_type='application/xml')


@csrf_exempt
@require_http_methods(['POST'])
def webhook_estado_llamada(request):
    """Actualiza la llamada cuando el carrier informa que terminó."""
    from llamadas.models import Llamada

    call_id = request.POST.get('CallSid') or request.POST.get('call_id') or ''
    estado_carrier = (request.POST.get('CallStatus') or request.POST.get('status') or '').lower()
    duracion = request.POST.get('CallDuration') or request.POST.get('duration') or 0

    llamada = Llamada.objects.filter(call_id=call_id).order_by('-id').first()
    if llamada is None:
        return JsonResponse({'error': True, 'message': 'Llamada no encontrada.'}, status=404)

    if estado_carrier in ('completed', 'finalizada', 'hangup'):
        try:
            llamada.duracion_segundos = int(duracion or 0) or llamada.duracion_segundos
        except (TypeError, ValueError):
            pass
        llamada.cerrar(llamada.resultado if llamada.resultado != 'pendiente' else 'resuelta_ia')
    elif estado_carrier in ('no-answer', 'busy', 'failed'):
        llamada.estado = 'fallida'
        llamada.resultado = 'error'
        llamada.save(update_fields=['estado', 'resultado'])

    return JsonResponse({'error': False})


def _detectar_driver(request):
    agente = (request.META.get('HTTP_USER_AGENT') or '').lower()
    for driver in ('twilio', 'telnyx', 'plivo', 'signalwire', 'asterisk'):
        if driver in agente:
            return driver
    return 'sip_generico'
