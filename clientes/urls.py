from django.urls import path

from .view_cliente import cambiar_cliente_view, cliente_view, modo_cliente_view
from .view_puesta_en_marcha import puesta_en_marcha_view

clientes_urls = (
    {'nombre': 'Clientes', 'url': 'listado/', 'vista': cliente_view},
    {'nombre': 'Puesta en marcha', 'url': 'puesta-en-marcha/', 'vista': puesta_en_marcha_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in clientes_urls] + [
    path('cambiar/', cambiar_cliente_view, name='cambiar_cliente'),
    path('modo-cliente/', modo_cliente_view, name='modo_cliente'),
]
