"""Tablero principal del sistema."""
from django.http import HttpResponseRedirect
from django.shortcuts import render

from clientes.contexto import acotar, cliente_actual
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

    data = {'titulo': 'Panel', 'modulo': 'Centro de operación'}
    addData(request, data)
    cliente = cliente_actual(request)

    data['metricas'] = metricas_generales(cliente=cliente)
    serie = llamadas_por_dia(cliente=cliente)
    data['serie_dias'] = serie
    data['maximo_serie'] = max([punto['total'] for punto in serie] or [1]) or 1
    data['serie_inicio'] = serie[0]['dia'] if serie else ''
    data['serie_fin'] = serie[-1]['dia'] if serie else ''
    data['paises'] = top_paises(cliente=cliente)
    data['motivos'] = motivos_transferencia(cliente=cliente)
    data['costo_mes'] = costo_estimado_mes(cliente=cliente)
    data['estado_motores'] = estado_motores()
    data['estado_rag'] = _estado_rag(request)
    data['numeros'] = acotar(
        NumeroTelefonico.objects.filter(status=True, activo=True), request
    ).select_related('flujo')[:8]
    data['flujos_activos'] = acotar(FlujoVoz.objects.filter(status=True, activo=True), request).count()
    data['agentes_activos'] = acotar(AgenteIA.objects.filter(status=True, activo=True), request).count()
    data['ultimas_llamadas'] = (
        acotar(Llamada.objects.filter(status=True), request)
        .select_related('flujo').order_by('-fecha_inicio')[:8]
    )
    return render(request, 'panel/index.html', data)


def _estado_rag(request):
    """Resumen de la base de conocimiento para la tarjeta de estado del panel."""
    from agentes_ia.models import ColeccionConocimiento
    from agentes_ia.rag import weaviate_rag

    colecciones = acotar(ColeccionConocimiento.objects.filter(status=True), request)
    usa_weaviate = colecciones.filter(backend='weaviate').exists()
    disponible, detalle = weaviate_rag.disponible() if usa_weaviate else (None, 'No se usa Weaviate')
    return {
        'colecciones': colecciones.count(),
        'fragmentos': sum(coleccion.fragmentos_indexados for coleccion in colecciones),
        'usa_weaviate': usa_weaviate,
        'weaviate_ok': disponible,
        'weaviate_detalle': detalle,
    }
