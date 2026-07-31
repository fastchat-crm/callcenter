from django.urls import path

from .view_agente import agente_view
from .view_apikey import apikey_view
from .view_conocimiento import conocimiento_view
from .view_consumo import consumo_view, estado_ia_view

agentes_ia_urls = (
    {'nombre': 'Agentes IA', 'url': 'agentes/', 'vista': agente_view},
    {'nombre': 'Base de conocimiento', 'url': 'conocimiento/', 'vista': conocimiento_view},
    {'nombre': 'Llaves de IA', 'url': 'apikeys/', 'vista': apikey_view},
    {'nombre': 'Consumo de IA', 'url': 'consumo/', 'vista': consumo_view},
    {'nombre': 'Estado de la IA', 'url': 'estado/', 'vista': estado_ia_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in agentes_ia_urls]
