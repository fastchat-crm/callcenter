"""Servidor AudioSocket para Asterisk auto-hospedado.

Asterisk no habla el protocolo de Media Streams de Twilio —ese es JSON sobre
WebSocket con mu-law en base64—, así que no puede conectarse a
`/ws/voz/stream/`. Lo que sí trae de fábrica es la aplicación `AudioSocket()`
del dialplan, que abre un **TCP plano** y manda audio crudo con un encabezado
mínimo. Este módulo habla ese protocolo y entrega la conversación al mismo
`OrquestadorLlamada` que usan los carriers, para que exista una sola lógica de
conversación sin importar por dónde entró la llamada.

Protocolo (app_audiosocket de Asterisk 18+), en ambos sentidos:

    1 byte   tipo
    2 bytes  longitud del payload, big-endian
    N bytes  payload

    0x00  fin de la llamada
    0x01  UUID de la llamada (16 bytes), llega primero
    0x10  audio: PCM lineal con signo, 16 bits, 8 kHz, mono, little-endian
    0xff  error

Asterisk solo manda el UUID, nunca el número que marcó. Por eso el dialplan
avisa antes por HTTP a `/telefonia/webhook/asterisk/`, que deja la llamada
registrada con ese UUID; aquí se la busca para saber a quién se atiende.
"""
from __future__ import annotations

import asyncio
import logging
import struct
import uuid as uuid_lib

from asgiref.sync import sync_to_async

from voz import services

logger = logging.getLogger('voz')

TIPO_FIN = 0x00
TIPO_UUID = 0x01
TIPO_AUDIO = 0x10
TIPO_ERROR = 0xff

SAMPLE_RATE = 8000
MUESTRAS_POR_TRAMA = 160          # 20 ms a 8 kHz
BYTES_POR_TRAMA = MUESTRAS_POR_TRAMA * 2
INTERVALO_TRAMA = 0.02
ESPERA_METADATOS = 5.0


def _trama(tipo: int, carga: bytes = b'') -> bytes:
    return struct.pack('>BH', tipo, len(carga)) + carga


class SesionAudioSocket:
    """Una llamada de Asterisk, de su UUID hasta que cuelga."""

    def __init__(self, lector, escritor):
        self.lector = lector
        self.escritor = escritor
        self.uuid = ''
        self.llamada = None
        self.orquestador = None
        self.detector = None
        self.procesando = False
        self.cerrada = False

    # --- ORM (siempre detrás de sync_to_async) ---
    def _buscar_llamada(self):
        from llamadas.models import Llamada

        return (
            Llamada.objects.select_related('flujo', 'numero', 'cliente')
            .filter(call_id=self.uuid).order_by('-id').first()
        )

    def _construir_orquestador(self):
        from voz.orquestador import OrquestadorLlamada

        return OrquestadorLlamada(self.llamada, self.llamada.flujo)

    def _marcar_en_curso(self):
        self.llamada.estado = 'en_curso'
        self.llamada.save(update_fields=['estado'])

    # --- Ciclo de vida ---
    async def atender(self):
        try:
            if not await self._esperar_uuid():
                return
            if not await self._preparar():
                return
            await self._saludar()
            await self._bucle()
        except (ConnectionResetError, BrokenPipeError):
            logger.info('[audiosocket] Asterisk cortó la conexión (uuid=%s)', self.uuid)
        except Exception:
            logger.exception('[audiosocket] falló la sesión %s', self.uuid)
        finally:
            await self._cerrar()

    async def _esperar_uuid(self):
        try:
            resultado = await asyncio.wait_for(self._leer(), timeout=ESPERA_METADATOS)
        except asyncio.TimeoutError:
            logger.warning('[audiosocket] Asterisk no envió el UUID; se corta')
            return False
        if resultado is None:
            return False
        tipo, carga = resultado
        if tipo != TIPO_UUID or len(carga) != 16:
            logger.warning('[audiosocket] primer paquete inesperado: tipo=%s', tipo)
            return False
        self.uuid = str(uuid_lib.UUID(bytes=carga))
        return True

    async def _preparar(self):
        self.llamada = await sync_to_async(self._buscar_llamada)()
        if self.llamada is None:
            # El dialplan no avisó, o avisó con otro UUID: sin llamada no se
            # sabe de qué cliente es, y contestar con un flujo cualquiera sería
            # atender con la configuración de otro.
            logger.warning('[audiosocket] no hay llamada registrada con uuid=%s', self.uuid)
            return False
        if self.llamada.flujo_id is None:
            logger.warning('[audiosocket] la llamada %s no tiene flujo; se corta', self.llamada.id)
            return False

        self.orquestador = await sync_to_async(self._construir_orquestador)()
        await sync_to_async(self._marcar_en_curso)()
        self.detector = _DetectorTurno()
        logger.info('[audiosocket] llamada %s en curso desde %s',
                    self.llamada.id, self.llamada.numero_origen)
        return True

    async def _saludar(self):
        salida = await sync_to_async(self.orquestador.saludo_inicial)()
        await self._hablar(salida)

    async def _bucle(self):
        while not self.cerrada:
            resultado = await self._leer()
            if resultado is None:
                return
            tipo, carga = resultado
            if tipo == TIPO_FIN:
                return
            if tipo == TIPO_ERROR:
                logger.warning('[audiosocket] Asterisk reportó un error en %s', self.uuid)
                return
            if tipo != TIPO_AUDIO or self.procesando:
                continue
            if self.detector.acumular(carga):
                await self._procesar_turno()

    async def _procesar_turno(self):
        self.procesando = True
        try:
            pcm = self.detector.vaciar()
            if len(pcm) < BYTES_POR_TRAMA:
                return
            texto = await asyncio.to_thread(services.transcribir_pcm, bytes(pcm), SAMPLE_RATE)
            if not (texto or '').strip():
                return
            salida = await sync_to_async(self.orquestador.procesar_turno)(texto, '')
            await self._hablar(salida)
            if salida.finalizar:
                self.cerrada = True
        finally:
            self.procesando = False

    async def _hablar(self, salida):
        if salida is None:
            return
        texto = (getattr(salida, 'texto', '') or '').strip()
        if not texto:
            return
        pcm = await asyncio.to_thread(services.sintetizar_pcm, texto, SAMPLE_RATE)
        # Se manda al ritmo real de la llamada: de golpe, Asterisk descarta lo
        # que no entra en su buffer y el cliente escucha la frase cortada.
        for inicio in range(0, len(pcm), BYTES_POR_TRAMA):
            if self.cerrada:
                return
            trama = pcm[inicio:inicio + BYTES_POR_TRAMA]
            if len(trama) < BYTES_POR_TRAMA:
                trama = trama + b'\x00' * (BYTES_POR_TRAMA - len(trama))
            self.escritor.write(_trama(TIPO_AUDIO, trama))
            await self.escritor.drain()
            await asyncio.sleep(INTERVALO_TRAMA)

    async def _leer(self):
        """Siguiente paquete, o None si Asterisk cerró el socket."""
        try:
            cabecera = await self.lector.readexactly(3)
            tipo, longitud = struct.unpack('>BH', cabecera)
            carga = await self.lector.readexactly(longitud) if longitud else b''
        except (asyncio.IncompleteReadError, ConnectionResetError):
            return None
        return tipo, carga

    async def _cerrar(self):
        if self.orquestador is not None:
            await sync_to_async(self.orquestador.cerrar)('resuelta_ia')
        try:
            self.escritor.write(_trama(TIPO_FIN))
            await self.escritor.drain()
        except Exception:
            pass
        try:
            self.escritor.close()
            await self.escritor.wait_closed()
        except Exception:
            pass


class _DetectorTurno:
    """Fin de turno por energía, igual que en los consumers WebSocket."""

    def __init__(self):
        from core.parametros import obtener
        from voz import audio as audio_utils

        self.audio = audio_utils
        self.buffer = bytearray()
        self.ms_silencio = 0
        self.hablando = False
        self.umbral = obtener('VOZ_UMBRAL_SILENCIO')
        self.ms_limite = obtener('VOZ_MS_SILENCIO_FIN_TURNO')

    def acumular(self, pcm: bytes) -> bool:
        self.buffer.extend(pcm)
        if self.audio.rms(pcm) > self.umbral:
            self.ms_silencio = 0
            self.hablando = True
            return False
        if not self.hablando:
            # Silencio antes de que hable: no se guarda, o el turno arranca con
            # segundos de nada y Whisper alucina sobre el ruido de fondo.
            self.buffer.clear()
            return False
        self.ms_silencio += self.audio.duracion_ms(pcm, SAMPLE_RATE)
        return self.ms_silencio >= self.ms_limite

    def vaciar(self) -> bytes:
        pcm = bytes(self.buffer)
        self.buffer.clear()
        self.ms_silencio = 0
        self.hablando = False
        return pcm


async def _al_conectar(lector, escritor):
    await SesionAudioSocket(lector, escritor).atender()


async def servir(host: str, puerto: int):
    servidor = await asyncio.start_server(_al_conectar, host, puerto)
    logger.info('[audiosocket] escuchando en %s:%s', host, puerto)
    async with servidor:
        await servidor.serve_forever()
