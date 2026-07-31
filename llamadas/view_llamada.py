"""Listado, detalle y monitor de llamadas."""
from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

from clientes.contexto import acotar, cliente_actual
from core.funciones import addData, paginador, secure_module

from .models import Llamada, TransferenciaLlamada


@secure_module
def llamada_view(request):
    data = {'titulo': 'Llamadas', 'modulo': 'Centro de operación'}
    addData(request, data)

    if 'action' in request.GET and request.GET['action'] == 'ver':
        llamada = (
            acotar(Llamada.objects.all(), request)
            .select_related('flujo', 'agente_ia', 'numero')
            .prefetch_related('turnos', 'transferencias')
            .filter(pk=int(request.GET['id'])).first()
        )
        if llamada is None:
            return JsonResponse({'result': False, 'message': 'La llamada no existe.'})
        data['filtro'] = llamada
        data['turnos'] = llamada.turnos.filter(status=True).order_by('fecha', 'id')
        return render(request, 'llamadas/llamada_detalle.html', data)

    filtros = Q(status=True) & Q(cliente=cliente_actual(request))
    url_vars = ''
    criterio = (request.GET.get('criterio') or '').strip()
    estado = (request.GET.get('estado') or '').strip()
    resultado = (request.GET.get('resultado') or '').strip()
    desde = (request.GET.get('desde') or '').strip()
    hasta = (request.GET.get('hasta') or '').strip()

    if criterio:
        filtros &= (Q(numero_origen__icontains=criterio) | Q(numero_destino__icontains=criterio)
                    | Q(transcripcion__icontains=criterio))
        data['criterio'] = criterio
        url_vars += f'&criterio={criterio}'
    if estado:
        filtros &= Q(estado=estado)
        data['estado'] = estado
        url_vars += f'&estado={estado}'
    if resultado:
        filtros &= Q(resultado=resultado)
        data['resultado'] = resultado
        url_vars += f'&resultado={resultado}'
    for nombre, valor, comparador in (('desde', desde, 'gte'), ('hasta', hasta, 'lte')):
        if valor:
            try:
                fecha = datetime.strptime(valor, '%Y-%m-%d').date()
                filtros &= Q(**{f'fecha_inicio__date__{comparador}': fecha})
                data[nombre] = valor
                url_vars += f'&{nombre}={valor}'
            except ValueError:
                pass

    listado = (
        Llamada.objects.filter(filtros)
        .select_related('flujo', 'agente_ia', 'numero')
        .order_by('-fecha_inicio')
    )
    paginador(request, listado, data, 25, url_vars)
    data['estados'] = Llamada._meta.get_field('estado').choices
    data['resultados'] = Llamada._meta.get_field('resultado').choices
    return render(request, 'llamadas/llamada_listado.html', data)


@secure_module
def monitor_view(request):
    """Llamadas en curso, con refresco por AJAX."""
    if request.GET.get('action') == 'datos':
        en_curso = (
            acotar(Llamada.objects.filter(status=True), request)
            .filter(estado__in=('iniciando', 'en_curso', 'transfiriendo'))
            .select_related('flujo', 'agente_ia')
            .order_by('-fecha_inicio')
        )
        return JsonResponse({
            'error': False,
            'llamadas': [
                {
                    'id': llamada.id,
                    'origen': llamada.numero_origen,
                    'destino': llamada.numero_destino,
                    'estado': llamada.get_estado_display(),
                    'paso': llamada.paso_actual or '',
                    'flujo': llamada.flujo.nombre if llamada.flujo else '',
                    'inicio': llamada.fecha_inicio.strftime('%H:%M:%S'),
                    'ultimo_turno': (
                        llamada.turnos.order_by('-id').values_list('texto', flat=True).first() or ''
                    )[:120],
                }
                for llamada in en_curso
            ],
        })

    data = {'titulo': 'Monitor en vivo', 'modulo': 'Centro de operación'}
    addData(request, data)
    return render(request, 'llamadas/monitor.html', data)


@secure_module
def transferencia_view(request):
    data = {'titulo': 'Transferencias', 'modulo': 'Centro de operación'}
    addData(request, data)

    filtros = Q(status=True) & Q(llamada__cliente=cliente_actual(request))
    url_vars = ''
    estado = (request.GET.get('estado') or '').strip()
    if estado:
        filtros &= Q(estado=estado)
        data['estado'] = estado
        url_vars += f'&estado={estado}'

    listado = (
        TransferenciaLlamada.objects.filter(filtros)
        .select_related('llamada', 'asesor')
        .order_by('-fecha_solicitud')
    )
    paginador(request, listado, data, 25, url_vars)
    data['estados'] = TransferenciaLlamada._meta.get_field('estado').choices
    return render(request, 'llamadas/transferencia_listado.html', data)
