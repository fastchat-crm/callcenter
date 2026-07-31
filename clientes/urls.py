from django.urls import path

from .view_cliente import cambiar_cliente_view, cliente_view

clientes_urls = (
    {'nombre': 'Clientes', 'url': 'listado/', 'vista': cliente_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in clientes_urls] + [
    path('cambiar/', cambiar_cliente_view, name='cambiar_cliente'),
]
