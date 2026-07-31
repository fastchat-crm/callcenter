from django.urls import path

from .view_asesor import asesor_view
from .view_numero import numero_view
from .view_proveedor import proveedor_view
from .view_webhook import webhook_estado_llamada, webhook_llamada_entrante

telefonia_urls = (
    {'nombre': 'Proveedores', 'url': 'proveedores/', 'vista': proveedor_view},
    {'nombre': 'Números', 'url': 'numeros/', 'vista': numero_view},
    {'nombre': 'Asesores', 'url': 'asesores/', 'vista': asesor_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in telefonia_urls] + [
    path('webhook/entrante/', webhook_llamada_entrante, name='webhook_entrante'),
    path('webhook/estado/', webhook_estado_llamada, name='webhook_estado'),
]
