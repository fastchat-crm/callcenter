from django.urls import path

from .view_demo import demo_view, estado_view

voz_urls = (
    {'nombre': 'Demo de voz', 'url': 'demo/', 'vista': demo_view},
    {'nombre': 'Estado del motor de voz', 'url': 'estado/', 'vista': estado_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in voz_urls]
