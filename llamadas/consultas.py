"""Consultas agregadas para el panel y los reportes de llamadas.

Todas aceptan `cliente`: con uno, los números salen acotados a ese cliente; sin
él (None) no devuelven nada, para que una pantalla que se olvide de pasarlo no
muestre por error los datos de todos.
"""
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


def _base(modelo, cliente, prefijo=''):
    """Queryset vivo del modelo, ya acotado al cliente."""
    consulta = modelo.objects.filter(status=True)
    if cliente is None:
        return consulta.none()
    return consulta.filter(**{f'{prefijo}cliente': cliente})


def metricas_generales(dias=30, cliente=None):
    from llamadas.models import Llamada

    desde = timezone.now() - timedelta(days=dias)
    base = _base(Llamada, cliente).filter(fecha_inicio__gte=desde)
    agregados = base.aggregate(
        total=Count('id'),
        minutos=Sum('duracion_segundos'),
        latencia=Avg('latencia_promedio_ms'),
        transferidas=Count('id', filter=Q(resultado='transferida')),
        resueltas=Count('id', filter=Q(resultado='resuelta_ia')),
        abandonadas=Count('id', filter=Q(resultado='abandonada')),
    )
    total = agregados['total'] or 0
    minutos = round((agregados['minutos'] or 0) / 60, 1)
    return {
        'dias': dias,
        'total_llamadas': total,
        'minutos_consumidos': minutos,
        'duracion_promedio_seg': round((agregados['minutos'] or 0) / total, 1) if total else 0,
        'latencia_promedio_ms': int(agregados['latencia'] or 0),
        'transferidas': agregados['transferidas'] or 0,
        'resueltas_ia': agregados['resueltas'] or 0,
        'abandonadas': agregados['abandonadas'] or 0,
        'tasa_resolucion': round(100 * (agregados['resueltas'] or 0) / total, 1) if total else 0,
        'en_curso': _base(Llamada, cliente).filter(estado='en_curso').count(),
    }


def llamadas_por_dia(dias=14, cliente=None):
    """Una entrada por día de la ventana, incluidos los días sin llamadas.

    La consulta agrupada solo devuelve los días que tuvieron actividad; si se
    dibujaran tal cual, un único día con llamadas ocuparía todo el ancho del
    gráfico y el eje mentiría sobre el período que se está mirando.
    """
    from django.db.models.functions import TruncDate

    from llamadas.models import Llamada

    # `timezone.now()` respeta USE_TZ, que en este proyecto está en False.
    hoy = timezone.now().date()
    primero = hoy - timedelta(days=dias - 1)
    filas = (
        _base(Llamada, cliente).filter(fecha_inicio__date__gte=primero)
        .annotate(dia=TruncDate('fecha_inicio'))
        .values('dia')
        .annotate(total=Count('id'), minutos=Sum('duracion_segundos'))
    )
    porDia = {
        fila['dia']: (fila['total'], fila['minutos'] or 0)
        for fila in filas if fila['dia']
    }
    serie = []
    for desplazamiento in range(dias):
        dia = primero + timedelta(days=desplazamiento)
        total, segundos = porDia.get(dia, (0, 0))
        serie.append({'dia': dia.isoformat(), 'total': total,
                      'minutos': round(segundos / 60, 1)})
    return serie


def top_paises(limite=8, cliente=None):
    from llamadas.models import Llamada

    filas = (
        _base(Llamada, cliente).exclude(pais_iso='')
        .values('pais_iso').annotate(total=Count('id')).order_by('-total')[:limite]
    )
    return list(filas)


def motivos_transferencia(cliente=None):
    from llamadas.models import TransferenciaLlamada

    filas = (
        _base(TransferenciaLlamada, cliente, prefijo='llamada__')
        .values('motivo').annotate(total=Count('id')).order_by('-total')
    )
    return list(filas)


def costo_estimado_mes(costo_minuto=0.02, cliente=None):
    """Costo del carrier del mes en curso. Con Asterisk auto-hospedado es 0."""
    from llamadas.models import Llamada

    ahora = timezone.now()
    segundos = (
        _base(Llamada, cliente)
        .filter(fecha_inicio__year=ahora.year, fecha_inicio__month=ahora.month)
        .aggregate(total=Sum('duracion_segundos'))['total'] or 0
    )
    minutos = segundos / 60
    return {'minutos': round(minutos, 1), 'costo_usd': round(minutos * costo_minuto, 2)}
