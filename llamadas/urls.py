from django.urls import path

from .view_contacto import contacto_view
from .view_llamada import llamada_view, monitor_view, transferencia_view

llamadas_urls = (
    {'nombre': 'Llamadas', 'url': 'listado/', 'vista': llamada_view},
    {'nombre': 'Monitor en vivo', 'url': 'monitor/', 'vista': monitor_view},
    {'nombre': 'Transferencias', 'url': 'transferencias/', 'vista': transferencia_view},
    {'nombre': 'Contactos', 'url': 'contactos/', 'vista': contacto_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in llamadas_urls]
