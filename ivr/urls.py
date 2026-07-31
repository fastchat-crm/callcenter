from django.urls import path

from .view_flujo import flujo_view
from .view_paso import paso_view

ivr_urls = (
    {'nombre': 'Flujos IVR', 'url': 'flujos/', 'vista': flujo_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in ivr_urls] + [
    path('flujos/<int:flujo_id>/pasos/', paso_view, name='ivr_pasos'),
]
