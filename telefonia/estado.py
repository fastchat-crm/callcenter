"""Estado y uso de la capa telefónica.

Responde tres preguntas que se hacen a diario: ¿está levantado?, ¿la troncal
sigue registrada con el proveedor? y ¿cuánto se está usando? Lo consulta el
panel, el endpoint `/health/` y el comando `manage.py estado_telefonia`.

Todo es de mejor esfuerzo: si Asterisk no está instalado o el comando no
responde, se devuelve el hecho, nunca una excepción.
"""
import socket
import subprocess
from datetime import timedelta

from django.conf import settings

TIEMPO_MAXIMO = 4


def _correr(comando):
    try:
        salida = subprocess.run(comando, capture_output=True, text=True,
                                timeout=TIEMPO_MAXIMO, check=False)
        return (salida.stdout or salida.stderr or '').strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ''


def _asterisk(comando):
    return _correr(['asterisk', '-rx', comando])


def servicio_activo(nombre):
    return _correr(['systemctl', 'is-active', nombre]) == 'active'


def puerto_escuchando(host, puerto):
    try:
        with socket.create_connection((host, puerto), timeout=2):
            return True
    except OSError:
        return False


def estado_asterisk():
    instalado = bool(_correr(['which', 'asterisk']))
    if not instalado:
        return {'instalado': False, 'activo': False, 'version': '',
                'registros': [], 'canales': 0,
                'detalle': 'Asterisk no está instalado en este servidor.'}

    activo = servicio_activo('asterisk')
    if not activo:
        return {'instalado': True, 'activo': False, 'version': '',
                'registros': [], 'canales': 0,
                'detalle': 'Asterisk está instalado pero el servicio no corre.'}

    registros = []
    for linea in _asterisk('pjsip show registrations').splitlines():
        partes = linea.split()
        # Las líneas útiles terminan en el estado: Registered, Rejected, …
        if len(partes) >= 2 and partes[-1] in ('Registered', 'Unregistered', 'Rejected', 'No', 'Auth'):
            registros.append({'troncal': partes[0], 'estado': partes[-1]})

    canales = 0
    for linea in _asterisk('core show channels count').splitlines():
        if 'active channel' in linea:
            try:
                canales = int(linea.split()[0])
            except (ValueError, IndexError):
                pass

    registradas = sum(1 for r in registros if r['estado'] == 'Registered')
    return {
        'instalado': True,
        'activo': True,
        'version': _asterisk('core show version').split('\n')[0][:80],
        'registros': registros,
        'canales': canales,
        'detalle': (f'{registradas} de {len(registros)} troncales registradas'
                    if registros else 'Sin troncales registradas'),
    }


def estado_audiosocket():
    host, puerto = settings.AUDIOSOCKET_HOST, settings.AUDIOSOCKET_PUERTO
    activo = servicio_activo('callcenter-audiosocket')
    escuchando = puerto_escuchando(host, puerto)
    return {
        'servicio_activo': activo,
        'escuchando': escuchando,
        'destino': f'{host}:{puerto}',
        'detalle': ('Listo para recibir llamadas de Asterisk' if escuchando
                    else 'Nadie escucha el puerto: Asterisk no podría entregar el audio'),
    }


def uso(cliente=None, dias=30):
    """Cuánto se viene usando: llamadas y minutos, hoy y en el período."""
    from django.db.models import Count, Sum
    from django.utils import timezone

    from llamadas.models import Llamada

    consulta = Llamada.objects.filter(status=True)
    if cliente is not None:
        consulta = consulta.filter(cliente=cliente)

    hoy = timezone.now().date()
    desde = hoy - timedelta(days=dias - 1)

    periodo = consulta.filter(fecha_inicio__date__gte=desde).aggregate(
        total=Count('id'), segundos=Sum('duracion_segundos'))
    dia = consulta.filter(fecha_inicio__date=hoy).aggregate(
        total=Count('id'), segundos=Sum('duracion_segundos'))

    incluidos = 0
    if cliente is not None:
        incluidos = cliente.minutos_incluidos_mes or 0
    minutos = round((periodo['segundos'] or 0) / 60, 1)
    return {
        'dias': dias,
        'llamadas_periodo': periodo['total'] or 0,
        'minutos_periodo': minutos,
        'llamadas_hoy': dia['total'] or 0,
        'minutos_hoy': round((dia['segundos'] or 0) / 60, 1),
        'en_curso': consulta.filter(estado='en_curso').count(),
        'minutos_incluidos': incluidos,
        'porcentaje_plan': round(100 * minutos / incluidos) if incluidos else 0,
    }


def resumen(cliente=None):
    return {
        'asterisk': estado_asterisk(),
        'audiosocket': estado_audiosocket(),
        'uso': uso(cliente),
    }
