"""Consultas agregadas para el panel y los reportes de llamadas."""
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


def metricas_generales(dias=30):
    from llamadas.models import Llamada

    desde = timezone.now() - timedelta(days=dias)
    base = Llamada.objects.filter(status=True, fecha_inicio__gte=desde)
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
        'en_curso': Llamada.objects.filter(status=True, estado='en_curso').count(),
    }


def llamadas_por_dia(dias=14):
    from django.db.models.functions import TruncDate

    from llamadas.models import Llamada

    desde = timezone.now() - timedelta(days=dias)
    filas = (
        Llamada.objects.filter(status=True, fecha_inicio__gte=desde)
        .annotate(dia=TruncDate('fecha_inicio'))
        .values('dia')
        .annotate(total=Count('id'), minutos=Sum('duracion_segundos'))
        .order_by('dia')
    )
    return [
        {'dia': fila['dia'].isoformat() if fila['dia'] else '',
         'total': fila['total'],
         'minutos': round((fila['minutos'] or 0) / 60, 1)}
        for fila in filas
    ]


def top_paises(limite=8):
    from llamadas.models import Llamada

    filas = (
        Llamada.objects.filter(status=True).exclude(pais_iso='')
        .values('pais_iso').annotate(total=Count('id')).order_by('-total')[:limite]
    )
    return list(filas)


def motivos_transferencia():
    from llamadas.models import TransferenciaLlamada

    filas = (
        TransferenciaLlamada.objects.filter(status=True)
        .values('motivo').annotate(total=Count('id')).order_by('-total')
    )
    return list(filas)


def costo_estimado_mes(costo_minuto=0.02):
    """Costo del carrier del mes en curso. Con Asterisk auto-hospedado es 0."""
    from llamadas.models import Llamada

    ahora = timezone.now()
    segundos = (
        Llamada.objects.filter(status=True, fecha_inicio__year=ahora.year,
                               fecha_inicio__month=ahora.month)
        .aggregate(total=Sum('duracion_segundos'))['total'] or 0
    )
    minutos = segundos / 60
    return {'minutos': round(minutos, 1), 'costo_usd': round(minutos * costo_minuto, 2)}
