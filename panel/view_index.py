"""Tablero principal del sistema."""
from django.http import HttpResponseRedirect
from django.shortcuts import render

from core.funciones import addData


def index_view(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect('/login/')

    from agentes_ia.models import AgenteIA
    from ivr.models import FlujoVoz
    from llamadas.consultas import (costo_estimado_mes, llamadas_por_dia, metricas_generales,
                                    motivos_transferencia, top_paises)
    from llamadas.models import Llamada
    from telefonia.models import NumeroTelefonico
    from voz.services import estado_motores

    data = {'titulo': 'Panel', 'modulo': 'Operación'}
    addData(request, data)

    data['metricas'] = metricas_generales()
    serie = llamadas_por_dia()
    data['serie_dias'] = serie
    data['maximo_serie'] = max([punto['total'] for punto in serie] or [1]) or 1
    data['serie_inicio'] = serie[0]['dia'] if serie else ''
    data['serie_fin'] = serie[-1]['dia'] if serie else ''
    data['paises'] = top_paises()
    data['motivos'] = motivos_transferencia()
    data['costo_mes'] = costo_estimado_mes()
    data['estado_motores'] = estado_motores()
    data['estado_rag'] = _estado_rag()
    data['numeros'] = NumeroTelefonico.objects.filter(status=True, activo=True).select_related('flujo')[:8]
    data['flujos_activos'] = FlujoVoz.objects.filter(status=True, activo=True).count()
    data['agentes_activos'] = AgenteIA.objects.filter(status=True, activo=True).count()
    data['ultimas_llamadas'] = (
        Llamada.objects.filter(status=True).select_related('flujo').order_by('-fecha_inicio')[:8]
    )
    return render(request, 'panel/index.html', data)


def _estado_rag():
    """Resumen de la base de conocimiento para la tarjeta de estado del panel."""
    from agentes_ia.models import ColeccionConocimiento
    from agentes_ia.rag import weaviate_rag

    colecciones = ColeccionConocimiento.objects.filter(status=True)
    usa_weaviate = colecciones.filter(backend='weaviate').exists()
    disponible, detalle = weaviate_rag.disponible() if usa_weaviate else (None, 'No se usa Weaviate')
    return {
        'colecciones': colecciones.count(),
        'fragmentos': sum(coleccion.fragmentos_indexados for coleccion in colecciones),
        'usa_weaviate': usa_weaviate,
        'weaviate_ok': disponible,
        'weaviate_detalle': detalle,
    }
