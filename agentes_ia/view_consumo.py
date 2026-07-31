"""Tablero de consumo de IA: tokens, latencia y costo estimado por agente y modelo."""
from datetime import datetime, timedelta

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from clientes.contexto import acotar, cliente_actual
from core.funciones import addData, paginador, secure_module

from .consumo import resumen_por_agente, resumen_por_modelo, totales
from .models import ConsumoIA

RANGOS = ((7, 'Últimos 7 días'), (30, 'Últimos 30 días'), (90, 'Últimos 90 días'))


@secure_module
def consumo_view(request):
    data = {'titulo': 'Consumo de IA', 'modulo': 'Centro de voz e IA'}
    addData(request, data)

    try:
        dias = int(request.GET.get('dias') or 30)
    except ValueError:
        dias = 30
    agente_id = (request.GET.get('agente') or '').strip()
    solo_errores = request.GET.get('errores') == '1'

    filtros = Q(status=True, fecha__gte=timezone.now() - timedelta(days=dias))
    url_vars = f'&dias={dias}'
    if agente_id.isdigit():
        filtros &= Q(agente_id=int(agente_id))
        url_vars += f'&agente={agente_id}'
        data['agente_id'] = int(agente_id)
    if solo_errores:
        filtros &= ~(Q(error__isnull=True) | Q(error=''))
        url_vars += '&errores=1'
        data['solo_errores'] = True

    consulta = ConsumoIA.objects.filter(filtros, agente__cliente=cliente_actual(request))

    if request.GET.get('action') == 'datos':
        return JsonResponse({
            'error': False,
            'totales': totales(consulta),
            'por_modelo': resumen_por_modelo(consulta),
            'por_agente': resumen_por_agente(consulta),
        })

    data['dias'] = dias
    data['rangos'] = RANGOS
    data['totales'] = totales(consulta)
    data['por_modelo'] = resumen_por_modelo(consulta)
    data['por_agente'] = resumen_por_agente(consulta)
    data['serie'] = _serie_diaria(consulta)
    data['maximo_serie'] = max([punto['turnos'] for punto in data['serie']] or [1]) or 1
    data['agentes'] = _agentes_disponibles(request)

    listado = consulta.select_related('agente', 'llamada', 'apikey').order_by('-fecha')
    paginador(request, listado, data, 25, url_vars)
    return render(request, 'agentes_ia/consumo.html', data)


def _serie_diaria(consulta):
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    filas = (
        consulta.annotate(dia=TruncDate('fecha')).values('dia')
        .annotate(turnos=Count('id'), costo=Sum('costo_usd'))
        .order_by('dia')
    )
    return [
        {'dia': fila['dia'].isoformat() if fila['dia'] else '',
         'turnos': fila['turnos'],
         'costo': round(float(fila['costo'] or 0), 4)}
        for fila in filas
    ]


def _agentes_disponibles(request):
    from .models import AgenteIA

    return list(acotar(AgenteIA.objects.filter(status=True), request)
                .values('id', 'nombre').order_by('nombre'))


@secure_module
def estado_ia_view(request):
    """Diagnóstico: proveedores configurados, Weaviate y colecciones indexadas."""
    from agentes_ia.rag import weaviate_rag
    from agentes_ia.rag import fragmentos_indexados

    from .models import ApiKeyIA, ColeccionConocimiento

    disponible, detalle = weaviate_rag.disponible()
    colecciones = []
    for coleccion in acotar(ColeccionConocimiento.objects.filter(status=True), request):
        colecciones.append({
            'nombre': coleccion.nombre,
            'backend': coleccion.backend,
            'motor_embeddings': coleccion.motor_embeddings,
            'fragmentos': fragmentos_indexados(coleccion),
            'indice': coleccion.descripcion_indice,
        })

    llaves = [
        {'alias': llave.alias, 'proveedor': llave.get_proveedor_display(),
         'modelo': llave.modelo or 'por defecto', 'activo': llave.activo,
         'tokens': llave.consumo_tokens_entrada + llave.consumo_tokens_salida}
        for llave in ApiKeyIA.objects.filter(status=True).order_by('-activo', 'alias')
    ]
    return JsonResponse({
        'error': False,
        'weaviate': {'disponible': disponible, 'detalle': detalle},
        'colecciones': colecciones,
        'llaves': llaves,
    })
