"""Grabación de la llamada: junta las dos voces en un solo archivo.

El sistema es **half-duplex** a propósito —mientras la IA habla se ignora el
audio entrante, para que no se escuche a sí misma—, así que las dos voces nunca
suenan a la vez. Eso permite grabar concatenando en el orden en que ocurrieron
las cosas, sin mezclar ni sincronizar pistas: el resultado es fiel a lo que se
oyó en la línea.

El audio se acumula en memoria durante la llamada y se escribe una sola vez al
cerrar. A 8 kHz mono 16 bits son 16 KB por segundo, así que hay un tope: una
llamada que se va de las manos no debe llenar el disco ni la RAM del proceso.
"""
import io
import logging
import os
import subprocess
import tempfile

from django.conf import settings
from django.core.files.base import ContentFile

from voz import audio as audio_utils

logger = logging.getLogger('voz')

SAMPLE_RATE_GRABACION = 8000
MINUTOS_MAXIMOS = 30
BYTES_MAXIMOS = SAMPLE_RATE_GRABACION * 2 * 60 * MINUTOS_MAXIMOS


def grabacion_activa():
    """Si está apagada, ni siquiera se acumula audio en memoria."""
    try:
        from core.parametros import obtener

        return bool(obtener('VOZ_GRABAR_LLAMADAS'))
    except Exception:
        return bool(getattr(settings, 'VOZ_GRABAR_LLAMADAS', True))


class GrabadorLlamada:
    """Acumula el audio de una llamada y lo guarda al cerrarla."""

    def __init__(self, sample_rate=SAMPLE_RATE_GRABACION):
        self.sample_rate = sample_rate
        self.buffer = bytearray()
        self.activo = grabacion_activa()
        self.truncada = False

    def anotar(self, pcm: bytes, sample_rate: int):
        """Agrega un tramo de audio, venga del cliente o de la IA."""
        if not self.activo or not pcm:
            return
        if len(self.buffer) >= BYTES_MAXIMOS:
            if not self.truncada:
                logger.warning('[grabacion] se alcanzaron los %s minutos; se deja de grabar',
                               MINUTOS_MAXIMOS)
                self.truncada = True
            return
        if sample_rate != self.sample_rate:
            pcm = audio_utils.remuestrear(pcm, sample_rate, self.sample_rate)
        self.buffer.extend(pcm)

    @property
    def segundos(self):
        return len(self.buffer) / 2 / self.sample_rate

    def guardar(self, llamada):
        """Escribe la grabación. De mejor esfuerzo: nunca rompe el cierre."""
        if not self.activo or llamada is None or len(self.buffer) < self.sample_rate:
            return None
        try:
            from llamadas.models import GrabacionLlamada

            wav = audio_utils.pcm_a_wav(bytes(self.buffer), self.sample_rate)
            datos, formato = _comprimir(wav)

            grabacion, _ = GrabacionLlamada.objects.get_or_create(llamada=llamada)
            nombre = f'llamada-{llamada.id}.{formato}'
            grabacion.archivo.save(nombre, ContentFile(datos), save=False)
            grabacion.formato = formato
            grabacion.tamano_bytes = len(datos)
            grabacion.save()
            logger.info('[grabacion] llamada %s guardada: %.1f s · %s KB · %s',
                        llamada.id, self.segundos, len(datos) // 1024, formato)
            return grabacion
        except Exception:
            logger.exception('[grabacion] no se pudo guardar la llamada %s',
                             getattr(llamada, 'id', '?'))
            return None
        finally:
            self.buffer.clear()


def _comprimir(wav: bytes):
    """WAV → MP3 con ffmpeg. Un minuto pasa de ~960 KB a ~60 KB.

    Si ffmpeg no está, se guarda el WAV tal cual: mejor ocupar disco que
    quedarse sin grabación.
    """
    try:
        with tempfile.TemporaryDirectory() as carpeta:
            entrada = os.path.join(carpeta, 'entrada.wav')
            salida = os.path.join(carpeta, 'salida.mp3')
            with open(entrada, 'wb') as archivo:
                archivo.write(wav)
            proceso = subprocess.run(
                ['ffmpeg', '-y', '-loglevel', 'error', '-i', entrada,
                 '-codec:a', 'libmp3lame', '-b:a', '32k', '-ac', '1', salida],
                capture_output=True, timeout=60, check=False,
            )
            if proceso.returncode == 0 and os.path.exists(salida):
                with open(salida, 'rb') as archivo:
                    return archivo.read(), 'mp3'
            logger.warning('[grabacion] ffmpeg falló (%s); se guarda el WAV',
                           (proceso.stderr or b'').decode('utf-8', 'ignore')[:120])
    except Exception as ex:
        logger.warning('[grabacion] no se pudo comprimir (%s); se guarda el WAV', ex)
    return wav, 'wav'
