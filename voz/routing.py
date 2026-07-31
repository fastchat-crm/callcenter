from django.urls import re_path

from .consumers import MediaStreamConsumer, VozWebConsumer

websocket_urlpatterns = [
    # El carrier (Twilio/Telnyx/Plivo/Asterisk) se conecta aquí.
    re_path(r'^ws/voz/stream/?$', MediaStreamConsumer.as_asgi()),
    # Compatibilidad con integraciones que apuntan a la ruta clásica de Twilio.
    re_path(r'^ws/voz/twilio/?$', MediaStreamConsumer.as_asgi()),
    # Demo desde el navegador.
    re_path(r'^ws/voz/web/?$', VozWebConsumer.as_asgi()),
]
