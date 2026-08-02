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
    0x03  tecla DTMF marcada, un dígito ASCII
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
import time
import uuid as uuid_lib

from asgiref.sync import sync_to_async

from voz import services

logger = logging.getLogger('voz')

TIPO_FIN = 0x00
TIPO_UUID = 0x01
TIPO_DTMF = 0x03
TIPO_AUDIO = 0x10
TIPO_ERROR = 0xff

MAXIMO_DIGITOS = 12
TECLA_FIN = '#'

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
        self.grabador = None
        self.procesando = False
        self.cerrada = False
        self.dtmf_pendiente = ''
        self.dtmf_ultimo = 0.0
        self.ms_espera_dtmf = 1200
        self.hablando = False
        self.interrumpido = False
        self.ms_voz_encima = 0
        self.barge_in = True
        self.ms_para_interrumpir = 500
        self.umbral_interrupcion = 1000
        self.turno_listo = asyncio.Event()

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
        """Recibir y conversar corren por separado, y esa separación es el diseño.

        Con una sola tarea, mientras el asistente hablaba nadie leía el socket:
        lo que decía la persona se quedaba en el buffer y se procesaba segundos
        después, cuando ya no venía a cuento. Ahora la lectora no para nunca, así
        que puede avisar de que la están interrumpiendo mientras el audio sale.
        """
        lectora = None
        try:
            if not await self._esperar_uuid():
                return
            if not await self._preparar():
                return
            lectora = asyncio.create_task(self._recibir())
            await self._saludar()
            await self._conversar()
        except (ConnectionResetError, BrokenPipeError):
            logger.info('[audiosocket] Asterisk cortó la conexión (uuid=%s)', self.uuid)
        except Exception:
            logger.exception('[audiosocket] falló la sesión %s', self.uuid)
        finally:
            self.cerrada = True
            if lectora is not None and not lectora.done():
                lectora.cancel()
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
        from core.parametros import obtener
        self.ms_espera_dtmf = obtener('VOZ_MS_ESPERA_DTMF')
        self.barge_in = obtener('VOZ_BARGE_IN')
        self.ms_para_interrumpir = obtener('VOZ_MS_VOZ_PARA_INTERRUMPIR')
        self.umbral_interrupcion = self.detector.umbral * obtener('VOZ_FACTOR_INTERRUPCION') / 100
        from voz.grabador import GrabadorLlamada
        self.grabador = GrabadorLlamada()
        logger.info('[audiosocket] llamada %s en curso desde %s',
                    self.llamada.id, self.llamada.numero_origen)
        return True

    async def _saludar(self):
        salida = await sync_to_async(self.orquestador.saludo_inicial)()
        await self._hablar(salida)

    async def _recibir(self):
        """Lee el socket de principio a fin. Nunca se bloquea por el asistente."""
        try:
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
                if tipo == TIPO_DTMF:
                    self._anotar_tecla(carga)
                elif tipo == TIPO_AUDIO:
                    self._al_recibir_audio(carga)
                if self._teclas_completas():
                    # Marcar también interrumpe: quien pulsa una tecla mientras
                    # el asistente habla ya decidió, y seguir hablándole sobra.
                    self.interrumpido = True
                    self.turno_listo.set()
        except asyncio.CancelledError:
            raise
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            self.cerrada = True
            # Despierta a `_conversar`, que si no se quedaría esperando un turno
            # que ya nunca va a llegar.
            self.turno_listo.set()

    def _al_recibir_audio(self, carga):
        self.grabador.anotar(carga, SAMPLE_RATE)
        # Se acumula siempre, también mientras el asistente habla: si esto solo
        # empezara al detectar la interrupción, se perdería el arranque de la
        # frase y llegaría cortada al reconocedor.
        fin_de_turno = self.detector.acumular(carga)
        if self.hablando:
            if self._interrumpe(carga):
                self.interrumpido = True
                logger.info('[audiosocket] llamada %s interrumpió al asistente', self.llamada.id)
            return
        if self.procesando:
            return
        if fin_de_turno:
            self.turno_listo.set()

    def _interrumpe(self, carga):
        """¿Esto es la persona hablando, o el eco del propio asistente?

        No hay forma de distinguirlos con certeza sin cancelación de eco, así que
        se exige lo que el eco rara vez cumple: sonar bastante más fuerte que el
        umbral normal y sostenerse. Si aun así el asistente se corta solo, la
        salida es subir el margen o apagar `VOZ_BARGE_IN`.
        """
        if not self.barge_in:
            return False
        if self.detector.audio.rms(carga) < self.umbral_interrupcion:
            self.ms_voz_encima = 0
            return False
        self.ms_voz_encima += self.detector.audio.duracion_ms(carga, SAMPLE_RATE)
        return self.ms_voz_encima >= self.ms_para_interrumpir

    async def _conversar(self):
        while not self.cerrada:
            await self.turno_listo.wait()
            self.turno_listo.clear()
            if self.cerrada:
                return
            dtmf = self._vaciar_teclas() if self.dtmf_pendiente else ''
            await self._procesar_turno(dtmf=dtmf)

    # --- Teclado ---
    def _anotar_tecla(self, carga):
        """Un dígito marcado. Asterisk lo manda como ASCII, uno por paquete."""
        tecla = carga.decode('ascii', 'ignore').strip()
        if not tecla:
            return
        self.dtmf_pendiente = (self.dtmf_pendiente + tecla)[-MAXIMO_DIGITOS:]
        self.dtmf_ultimo = time.monotonic()
        logger.info('[audiosocket] llamada %s marcó %s', self.llamada.id, tecla)

    def _teclas_completas(self):
        """¿Ya se puede dar por terminado lo marcado?

        Un menú se resuelve con una tecla y una cédula son diez seguidas, así que
        no sirve esperar siempre a la almohadilla: lo que distingue los dos casos
        es cuánto lleva sin llegar otro dígito. El bucle se despierta con cada
        trama de audio —cada 20 ms—, así que mirar el reloj aquí alcanza y no
        hace falta un temporizador aparte.
        """
        if not self.dtmf_pendiente:
            return False
        if self.dtmf_pendiente.endswith(TECLA_FIN) or len(self.dtmf_pendiente) >= MAXIMO_DIGITOS:
            return True
        return (time.monotonic() - self.dtmf_ultimo) * 1000 >= self.ms_espera_dtmf

    def _vaciar_teclas(self):
        teclas = self.dtmf_pendiente
        self.dtmf_pendiente = ''
        # Lo que se dijo mientras se marcaba ya no interesa: la persona eligió
        # con el teclado, y transcribir ese audio inventaría una respuesta.
        self.detector.vaciar()
        return teclas

    async def _procesar_turno(self, dtmf=''):
        self.procesando = True
        try:
            texto = ''
            if not dtmf:
                pcm = self.detector.vaciar()
                if len(pcm) < BYTES_POR_TRAMA:
                    return
                texto = await asyncio.to_thread(services.transcribir_pcm, bytes(pcm), SAMPLE_RATE)
                if not (texto or '').strip():
                    return
            salida = await sync_to_async(self.orquestador.procesar_turno)(texto, dtmf)
            await self._hablar(salida)
            if salida.finalizar:
                self.cerrada = True
        finally:
            self.procesando = False

    async def _hablar(self, salida):
        """Reproduce la respuesta troceada por puntuación.

        Sintetizar la frase entera antes de emitir el primer sonido deja a la
        persona esperando en silencio todo lo que tarda el TTS. Cortando por
        puntuación, el primer trozo empieza a sonar enseguida y el siguiente se
        sintetiza mientras ese suena: emitir va al ritmo del reloj —20 ms por
        trama— y ese tiempo estaba desaprovechado.
        """
        if salida is None:
            return
        trozos = services.trocear_para_habla(getattr(salida, 'texto', ''))
        if not trozos:
            return

        self.hablando = True
        self.interrumpido = False
        self.ms_voz_encima = 0
        siguiente = asyncio.create_task(self._sintetizar(trozos[0]))
        try:
            for indice, _trozo in enumerate(trozos):
                pcm = await siguiente
                siguiente = (asyncio.create_task(self._sintetizar(trozos[indice + 1]))
                             if indice + 1 < len(trozos) else None)
                await self._emitir(pcm)
                if self.cerrada or self.interrumpido:
                    return
        finally:
            self.hablando = False
            # Si se cortó a mitad, el trozo que venía sintetizándose no se va a
            # usar: dejarlo colgando ensucia el bucle de eventos al cerrar.
            if siguiente is not None and not siguiente.done():
                siguiente.cancel()
            if not self.interrumpido:
                # Nadie interrumpió: lo que se acumuló mientras hablaba el
                # asistente es ruido de línea, y arrastrarlo al turno siguiente
                # hace que el reconocedor invente sobre el fondo.
                self.detector.vaciar()
            # Si sí interrumpieron, lo acumulado se conserva y **no** se procesa
            # todavía: interrumpir es el principio de la frase, no el final.
            # Cerrarlo aquí transcribía solo el medio segundo que costó detectar
            # la interrupción. El turno lo cierra el silencio, como siempre.

    async def _sintetizar(self, texto):
        return await asyncio.to_thread(services.sintetizar_pcm, texto, SAMPLE_RATE)

    async def _emitir(self, pcm):
        if not pcm:
            return
        if self.grabador is not None:
            self.grabador.anotar(pcm, SAMPLE_RATE)
        # Se manda al ritmo real de la llamada: de golpe, Asterisk descarta lo
        # que no entra en su buffer y el cliente escucha la frase cortada.
        for inicio in range(0, len(pcm), BYTES_POR_TRAMA):
            if self.cerrada or self.interrumpido:
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
        if self.grabador is not None:
            await sync_to_async(self.grabador.guardar)(self.llamada)
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
