"""Estado de los servicios externos de los que depende el sistema.

Responde una sola pregunta por servicio: ¿está respondiendo ahora mismo? Se usa
en el tablero y en `manage.py estado_servicios`. Todo de mejor esfuerzo y con
timeout corto: comprobar el estado nunca debe colgar una pantalla.
"""
import logging
import socket

logger = logging.getLogger('core')

TIEMPO_MAXIMO = 3


def _resultado(nombre, activo, detalle, requerido=True):
    return {'nombre': nombre, 'activo': activo, 'detalle': detalle, 'requerido': requerido}


def estado_tika():
    """Apache Tika: extrae texto de PDF y Office al indexar el conocimiento."""
    import requests

    from core.models import Configuracion

    configuracion = Configuracion.get_instancia()
    url = (configuracion.tika_url or '').strip().rstrip('/')
    if not configuracion.tika_activo:
        return _resultado('Apache Tika', None,
                          'Apagado: se usan los extractores locales (pypdf, python-docx).',
                          requerido=False)
    if not url:
        return _resultado('Apache Tika', False,
                          'Activado pero sin URL configurada.', requerido=False)
    try:
        respuesta = requests.get(f'{url}/version', timeout=TIEMPO_MAXIMO)
        if respuesta.status_code < 400:
            return _resultado('Apache Tika', True,
                              (respuesta.text or '').strip()[:60] or 'Responde', requerido=False)
        return _resultado('Apache Tika', False,
                          f'HTTP {respuesta.status_code}', requerido=False)
    except Exception as ex:
        return _resultado('Apache Tika', False, f'No responde: {ex}'[:90], requerido=False)


def estado_base_datos():
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return _resultado('PostgreSQL', True, 'Conectado')
    except Exception as ex:
        return _resultado('PostgreSQL', False, str(ex)[:90])


def estado_redis():
    from django.conf import settings

    if not getattr(settings, 'USAR_REDIS', False):
        return _resultado('Redis', None, 'No se usa: canal en memoria.', requerido=False)
    try:
        from django.core.cache import cache

        cache.set('estado_servicios', 1, 10)
        listo = cache.get('estado_servicios') == 1
        return _resultado('Redis', listo, 'Conectado' if listo else 'No devuelve lo que guarda')
    except Exception as ex:
        return _resultado('Redis', False, str(ex)[:90])


def estado_weaviate():
    from agentes_ia.models import ColeccionConocimiento

    usa = ColeccionConocimiento.objects.filter(status=True, backend='weaviate').exists()
    if not usa:
        return _resultado('Weaviate', None, 'No se usa: el RAG corre local.', requerido=False)
    try:
        from agentes_ia.rag import weaviate_rag

        disponible, detalle = weaviate_rag.disponible()
        return _resultado('Weaviate', disponible, detalle, requerido=False)
    except Exception as ex:
        return _resultado('Weaviate', False, str(ex)[:90], requerido=False)


def estado_audiosocket():
    from django.conf import settings

    host, puerto = settings.AUDIOSOCKET_HOST, settings.AUDIOSOCKET_PUERTO
    try:
        with socket.create_connection((host, puerto), timeout=2):
            return _resultado('Puente AudioSocket', True, f'Escuchando en {host}:{puerto}',
                              requerido=False)
    except OSError:
        return _resultado('Puente AudioSocket', False,
                          'Apagado: Asterisk no tendría a dónde entregar el audio.',
                          requerido=False)


def estado_asterisk():
    from telefonia.estado import estado_asterisk as detalle_asterisk

    datos = detalle_asterisk()
    if not datos['instalado']:
        return _resultado('Asterisk', None, 'No instalado: se usan carriers por WebSocket.',
                          requerido=False)
    return _resultado('Asterisk', datos['activo'], datos['detalle'], requerido=False)


COMPROBACIONES = (estado_base_datos, estado_redis, estado_tika, estado_weaviate,
                  estado_asterisk, estado_audiosocket)


def estado_servicios():
    """Todos los servicios, en orden. Un fallo se reporta, no se propaga."""
    listado = []
    for comprobar in COMPROBACIONES:
        try:
            listado.append(comprobar())
        except Exception as ex:
            logger.exception('[servicios] falló la comprobación %s', comprobar.__name__)
            listado.append(_resultado(comprobar.__name__, False, str(ex)[:90], requerido=False))
    return listado
