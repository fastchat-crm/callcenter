import os

import django

os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'callcenterdj.settings')

from django.core.asgi import get_asgi_application  # noqa: E402

django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402

import voz.routing  # noqa: E402

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    # El carrier (Twilio/Telnyx/Asterisk) abre el WebSocket sin cabecera Origin
    # valida, por eso NO se envuelve en AllowedHostsOriginValidator: el
    # consumer valida el token del stream por su cuenta.
    'websocket': AuthMiddlewareStack(
        URLRouter(voz.routing.websocket_urlpatterns)
    ),
})
