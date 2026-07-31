"""Consumers WebSocket de audio en tiempo real.

  MediaStreamConsumer — protocolo Media Streams (mu-law 8 kHz en JSON base64).
                        Lo hablan Twilio, Telnyx, Plivo, SignalWire y el módulo
                        audiosocket/ari de Asterisk auto-hospedado.
  VozWebConsumer      — demo desde el navegador: PCM 16-bit 16 kHz binario.

Ambos delegan la conversación en `voz.orquestador.OrquestadorLlamada`; aquí solo
vive el transporte, la detección de fin de turno y el envío del audio.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncWebsocketConsumer
from django.conf import settings

from voz import audio as audio_utils
from voz import services

logger = logging.getLogger('voz')

TAMANO_TRAMA_ULAW = 160          # 20 ms a 8 kHz
INTERVALO_TRAMA = 0.02
SAMPLE_RATE_NAVEGADOR = 16000
MINIMO_MS_TURNO = 400


class BaseVozConsumer:
    """Estado y helpers comunes a los dos transportes."""

    def inicializar_estado(self):
        self.buffer = bytearray()
        self.ms_silencio = 0
        self.hablando = False
        self.procesando = False
        self.dtmf_pendiente = ''
        self.llamada = None
        self.orquestador = None
        # Desde los parámetros del panel: se ajustan sin reiniciar el servicio.
        from core.parametros import obtener
        from voz.grabador import GrabadorLlamada
        self.umbral = obtener('VOZ_UMBRAL_SILENCIO')
        self.ms_para_cerrar_turno = obtener('VOZ_MS_SILENCIO_FIN_TURNO')
        self.grabador = GrabadorLlamada()

    def detectar_fin_turno(self, pcm: bytes, sample_rate: int) -> bool:
        """VAD por energía: devuelve True cuando el cliente terminó de hablar."""
        amplitud = audio_utils.rms(pcm)
        milisegundos = audio_utils.duracion_ms(pcm, sample_rate)
        if amplitud > self.umbral:
            self.ms_silencio = 0
            self.hablando = True
            return False
        if self.hablando:
            self.ms_silencio += milisegundos
            return self.ms_silencio >= self.ms_para_cerrar_turno
        return False

    def reiniciar_turno(self) -> bytes:
        audio = bytes(self.buffer)
        self.buffer.clear()
        self.ms_silencio = 0
        self.hablando = False
        return audio

    # --- Helpers ORM (se ejecutan con sync_to_async) ---
    def _crear_llamada(self, **campos):
        from llamadas.models import Llamada

        # El dueño de la llamada se hereda del número marcado; si es el demo por
        # navegador, del flujo elegido. Sin esto la llamada queda sin cliente y
        # no aparece en el listado de nadie.
        if campos.get('cliente') is None:
            origen = campos.get('numero') or campos.get('flujo')
            campos['cliente'] = getattr(origen, 'cliente', None)
        return Llamada.objects.create(**campos)

    def _resolver_flujo(self, numero_destino):
        from ivr.models import FlujoVoz
        from telefonia.models import NumeroTelefonico

        numero = NumeroTelefonico.objects.select_related('flujo', 'cliente').filter(
            numero=numero_destino, status=True, activo=True,
        ).first()
        if numero is not None and numero.flujo_id and numero.flujo.activo:
            return numero, numero.flujo

        # El respaldo se busca dentro del mismo cliente: nunca se atiende una
        # llamada con el flujo de otro.
        respaldo = FlujoVoz.objects.filter(status=True, activo=True)
        respaldo = respaldo.filter(cliente=numero.cliente) if numero is not None else respaldo.none()
        return numero, respaldo.order_by('id').first()

    def _construir_orquestador(self, llamada, flujo):
        from voz.orquestador import OrquestadorLlamada
        return OrquestadorLlamada(llamada, flujo)

    def _marcar_en_curso(self, llamada):
        llamada.estado = 'en_curso'
        llamada.save(update_fields=['estado'])


class MediaStreamConsumer(BaseVozConsumer, AsyncJsonWebsocketConsumer):
    """Audio bidireccional con el carrier. Protocolo Twilio Media Streams."""

    async def connect(self):
        await self.accept()
        self.inicializar_estado()
        self.stream_sid = None
        self.call_sid = None
        logger.info('[voz] media stream conectado')

    async def disconnect(self, code):
        logger.info('[voz] media stream cerrado code=%s', code)
        if self.orquestador is not None:
            await sync_to_async(self.orquestador.cerrar)('abandonada' if self.hablando else 'resuelta_ia')
        await sync_to_async(self.grabador.guardar)(self.llamada)

    async def receive_json(self, content, **kwargs):
        evento = content.get('event')
        if evento == 'connected':
            return
        if evento == 'start':
            await self._al_iniciar(content)
        elif evento == 'media':
            await self._al_recibir_audio(content)
        elif evento == 'dtmf':
            self.dtmf_pendiente += (content.get('dtmf') or {}).get('digit', '')
            if self.dtmf_pendiente.endswith('#') or len(self.dtmf_pendiente) >= 12:
                await self._procesar_turno(forzar=True)
        elif evento == 'stop':
            await self.close()

    async def _al_iniciar(self, mensaje):
        inicio = mensaje.get('start', {}) or {}
        self.stream_sid = inicio.get('streamSid')
        self.call_sid = inicio.get('callSid')
        parametros = inicio.get('customParameters') or {}
        numero_origen = parametros.get('from') or inicio.get('from') or ''
        numero_destino = parametros.get('to') or inicio.get('to') or ''

        numero, flujo = await sync_to_async(self._resolver_flujo)(numero_destino)
        self.llamada = await sync_to_async(self._crear_llamada)(
            sentido='entrante',
            driver=parametros.get('driver') or 'twilio',
            call_id=self.call_sid,
            stream_sid=self.stream_sid,
            numero_origen=numero_origen,
            numero_destino=numero_destino,
            numero=numero,
            pais_iso=(numero.pais_iso if numero else ''),
            idioma=(numero.idioma if numero else 'es'),
            flujo=flujo,
            estado='en_curso',
        )
        self.orquestador = await sync_to_async(self._construir_orquestador)(self.llamada, flujo)
        logger.info('[voz] llamada %s iniciada desde %s hacia %s', self.llamada.id, numero_origen, numero_destino)

        salida = await sync_to_async(self.orquestador.saludo_inicial)()
        await self._hablar(salida)

    async def _al_recibir_audio(self, mensaje):
        if self.procesando:
            return
        carga = (mensaje.get('media') or {}).get('payload')
        if not carga:
            return
        pcm = audio_utils.ulaw_a_pcm(base64.b64decode(carga))
        self.buffer.extend(pcm)
        self.grabador.anotar(pcm, services.SAMPLE_RATE_TELEFONICO)
        if self.detectar_fin_turno(pcm, services.SAMPLE_RATE_TELEFONICO):
            await self._procesar_turno()

    async def _procesar_turno(self, forzar=False):
        if self.procesando or self.orquestador is None:
            return
        self.procesando = True
        audio_turno = self.reiniciar_turno()
        dtmf = self.dtmf_pendiente
        self.dtmf_pendiente = ''
        try:
            texto = ''
            if audio_turno and audio_utils.duracion_ms(audio_turno, services.SAMPLE_RATE_TELEFONICO) >= MINIMO_MS_TURNO:
                texto = await asyncio.to_thread(
                    services.transcribir_pcm, audio_turno, services.SAMPLE_RATE_TELEFONICO,
                    self.llamada.idioma if self.llamada else 'es',
                )
            if not texto and not dtmf and not forzar:
                return
            logger.info('[voz] cliente(%s): %s %s', self.llamada.id, texto, f'[dtmf {dtmf}]' if dtmf else '')
            salida = await sync_to_async(self.orquestador.procesar_turno)(texto, dtmf)
            await self._hablar(salida)
        finally:
            self.procesando = False

    async def _hablar(self, salida):
        if salida.texto:
            logger.info('[voz] ia(%s): %s', self.llamada.id, salida.texto)
            ulaw = await asyncio.to_thread(services.sintetizar_ulaw, salida.texto)
            if ulaw:
                self.grabador.anotar(audio_utils.ulaw_a_pcm(ulaw), services.SAMPLE_RATE_TELEFONICO)
                await self._enviar_ulaw(ulaw)
            else:
                logger.warning('[voz] sin audio TTS; el cliente no escuchará la respuesta')
        if salida.transferir is not None:
            await self._solicitar_transferencia(salida.transferir)
            return
        if salida.finalizar:
            await self.close()

    async def _enviar_ulaw(self, ulaw):
        for inicio in range(0, len(ulaw), TAMANO_TRAMA_ULAW):
            trama = ulaw[inicio:inicio + TAMANO_TRAMA_ULAW]
            if len(trama) < TAMANO_TRAMA_ULAW:
                trama = trama + b'\xff' * (TAMANO_TRAMA_ULAW - len(trama))
            await self.send_json({
                'event': 'media',
                'streamSid': self.stream_sid,
                'media': {'payload': base64.b64encode(trama).decode('ascii')},
            })
            await asyncio.sleep(INTERVALO_TRAMA)
        await self.send_json({
            'event': 'mark',
            'streamSid': self.stream_sid,
            'mark': {'name': 'fin_respuesta'},
        })

    async def _solicitar_transferencia(self, asesor):
        """Pide al carrier que redirija la llamada al asesor humano."""
        destino = getattr(asesor, 'numero_destino', '') or getattr(asesor, 'extension_sip', '')
        await self.send_json({
            'event': 'transfer',
            'streamSid': self.stream_sid,
            'transfer': {'to': destino, 'asesor': getattr(asesor, 'nombre', '')},
        })
        logger.info('[voz] transferencia solicitada al carrier hacia %s', destino)
        await self.close()


class VozWebConsumer(BaseVozConsumer, AsyncWebsocketConsumer):
    """Demo desde el navegador: mismo cerebro, sin carrier ni costos.

    Protocolo: binario = PCM 16-bit LE mono 16 kHz. Texto = JSON de control
    (`iniciar_conversacion`, `fin_turno`, `dtmf`, `stop`). El servidor responde
    con JSON (`transcript`, `reply`, `audio_end`, `vad`) y audio binario PCM.
    """

    async def connect(self):
        await self.accept()
        self.inicializar_estado()

        from urllib.parse import parse_qs
        parametros = parse_qs((self.scope.get('query_string') or b'').decode('utf-8'))
        flujo_id = (parametros.get('flujo_id') or [''])[0]

        flujo = await sync_to_async(self._flujo_por_id)(flujo_id)
        self.llamada = await sync_to_async(self._crear_llamada)(
            sentido='entrante', driver='webrtc', numero_origen='navegador',
            numero_destino='demo', flujo=flujo, estado='en_curso',
        )
        self.orquestador = await sync_to_async(self._construir_orquestador)(self.llamada, flujo)
        await self.send(text_data=json.dumps({
            'event': 'ready',
            'sample_rate': SAMPLE_RATE_NAVEGADOR,
            'llamada_id': self.llamada.id,
            'flujo': getattr(flujo, 'nombre', ''),
        }))

    async def disconnect(self, code):
        if self.orquestador is not None:
            await sync_to_async(self.orquestador.cerrar)('resuelta_ia')
        await sync_to_async(self.grabador.guardar)(self.llamada)

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is not None:
            await self._al_recibir_pcm(bytes_data)
            return
        if not text_data:
            return
        try:
            mensaje = json.loads(text_data)
        except json.JSONDecodeError:
            return
        evento = mensaje.get('event')
        if evento == 'iniciar_conversacion':
            salida = await sync_to_async(self.orquestador.saludo_inicial)()
            await self._responder(salida)
        elif evento == 'fin_turno':
            await self._procesar_turno(forzar=True)
        elif evento == 'dtmf':
            self.dtmf_pendiente += str(mensaje.get('digito') or '')
            await self._procesar_turno(forzar=True)
        elif evento == 'stop':
            await self.close()

    async def _al_recibir_pcm(self, pcm):
        if self.procesando:
            return
        self.buffer.extend(pcm)
        self.grabador.anotar(pcm, SAMPLE_RATE_NAVEGADOR)
        estaba_hablando = self.hablando
        fin = self.detectar_fin_turno(pcm, SAMPLE_RATE_NAVEGADOR)
        if self.hablando != estaba_hablando:
            await self.send(text_data=json.dumps({'event': 'vad', 'hablando': self.hablando}))
        if fin:
            await self._procesar_turno()

    async def _procesar_turno(self, forzar=False):
        if self.procesando or self.orquestador is None:
            return
        self.procesando = True
        audio_turno = self.reiniciar_turno()
        dtmf = self.dtmf_pendiente
        self.dtmf_pendiente = ''
        try:
            texto = ''
            if audio_turno and audio_utils.duracion_ms(audio_turno, SAMPLE_RATE_NAVEGADOR) >= MINIMO_MS_TURNO:
                texto = await asyncio.to_thread(
                    services.transcribir_pcm, audio_turno, SAMPLE_RATE_NAVEGADOR, 'es',
                )
            if not texto and not dtmf and not forzar:
                return
            if texto:
                await self.send(text_data=json.dumps({'event': 'transcript', 'texto': texto}))
            salida = await sync_to_async(self.orquestador.procesar_turno)(texto, dtmf)
            await self._responder(salida)
        finally:
            self.procesando = False

    async def _responder(self, salida):
        if salida.texto:
            await self.send(text_data=json.dumps({
                'event': 'reply', 'texto': salida.texto, 'latencia_ms': salida.latencia_ms,
            }))
            pcm = await asyncio.to_thread(services.sintetizar_pcm, salida.texto, SAMPLE_RATE_NAVEGADOR)
            if pcm:
                self.grabador.anotar(pcm, SAMPLE_RATE_NAVEGADOR)
                tamano_bloque = int(SAMPLE_RATE_NAVEGADOR * 2 * 0.04)
                for inicio in range(0, len(pcm), tamano_bloque):
                    await self.send(bytes_data=pcm[inicio:inicio + tamano_bloque])
        await self.send(text_data=json.dumps({'event': 'audio_end'}))
        if salida.transferir is not None:
            await self.send(text_data=json.dumps({
                'event': 'transferencia',
                'asesor': getattr(salida.transferir, 'nombre', ''),
                'destino': getattr(salida.transferir, 'numero_destino', ''),
            }))
        if salida.finalizar:
            await self.send(text_data=json.dumps({'event': 'fin_llamada'}))

    def _cliente_de_la_sesion(self):
        """Cliente del usuario que abrió el demo, o el que eligió en el panel."""
        from clientes.contexto import CLAVE_SESION
        from clientes.models import Cliente

        usuario = self.scope.get('user')
        if usuario is None or not getattr(usuario, 'is_authenticated', False):
            return None
        if usuario.cliente_id is not None:
            return usuario.cliente
        elegido = (self.scope.get('session') or {}).get(CLAVE_SESION)
        return Cliente.objects.filter(pk=elegido, status=True, activo=True).first() if elegido else None

    def _flujo_por_id(self, flujo_id):
        from ivr.models import FlujoVoz

        cliente = self._cliente_de_la_sesion()
        if cliente is None:
            return None
        consulta = FlujoVoz.objects.filter(status=True, activo=True, cliente=cliente)
        if str(flujo_id).isdigit():
            return consulta.filter(pk=int(flujo_id)).first() or consulta.first()
        return consulta.first()
