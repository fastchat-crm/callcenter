"""Orquestador de un turno de llamada: motor IVR + agente IA + persistencia.

Vive fuera de los consumers a proposito: la logica de conversacion no depende
del transporte (Media Streams del carrier, WebRTC del navegador o pruebas por
consola). Todos los metodos son sincronos y se invocan desde el consumer con
`asyncio.to_thread`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger('voz')


@dataclass
class SalidaTurno:
    texto: str = ''
    finalizar: bool = False
    transferir: object = None
    paso_codigo: str = ''
    latencia_ms: int = 0
    latencia_llm_ms: int = 0


class OrquestadorLlamada:
    def __init__(self, llamada, flujo=None):
        self.llamada = llamada
        self.flujo = flujo
        self.motor = None
        self.consultor = None
        self.historial: list[tuple[str, str]] = []
        self.modo_agente = flujo is None

        if flujo is not None:
            from ivr.motor import MotorIVR
            self.motor = MotorIVR(flujo, llamada)
        self._preparar_agente()

    # --- Ciclo de la llamada ---
    def saludo_inicial(self) -> SalidaTurno:
        if self.motor is None:
            texto = 'Hola, soy el asistente virtual. ¿En qué te puedo ayudar?'
            self._registrar_turno('ia', texto)
            return SalidaTurno(texto=texto, paso_codigo='saludo')

        resultado = self.motor.iniciar()
        salida = self._desde_resultado(resultado)
        if salida.texto:
            self._registrar_turno('ia', salida.texto, paso=salida.paso_codigo)
        self._actualizar_paso(salida.paso_codigo)
        return salida

    def procesar_turno(self, texto_cliente: str, dtmf: str = '') -> SalidaTurno:
        inicio = time.time()
        if texto_cliente or dtmf:
            self.historial.append(('cliente', texto_cliente or f'[tecla {dtmf}]'))
            self._registrar_turno('cliente', texto_cliente, dtmf=dtmf)

        if self.motor is None:
            salida = self._responder_con_agente(texto_cliente)
        else:
            resultado = self.motor.procesar_entrada(texto_cliente, dtmf)
            salida = self._desde_resultado(resultado)
            if resultado.modo_agente_ia and not salida.texto:
                salida = self._responder_con_agente(texto_cliente, salida)

        salida.latencia_ms = int((time.time() - inicio) * 1000)
        if salida.texto:
            self.historial.append(('ia', salida.texto))
            self._registrar_turno('ia', salida.texto, paso=salida.paso_codigo,
                                  latencia_llm=salida.latencia_llm_ms, latencia_total=salida.latencia_ms)
        self._actualizar_paso(salida.paso_codigo)
        if salida.transferir is not None:
            self._registrar_transferencia(salida.transferir)
        return salida

    def cerrar(self, resultado='resuelta_ia'):
        try:
            self.llamada.transcripcion = self.transcripcion()
            self.llamada.save(update_fields=['transcripcion'])
            # Si la llamada ya se marcó (por ejemplo, transferida a un asesor),
            # el cierre no debe pisar ese resultado con el genérico.
            actual = self.llamada.resultado
            if actual and actual != 'pendiente':
                resultado = actual
            self.llamada.cerrar(resultado)
        except Exception:
            logger.exception('[voz] no se pudo cerrar la llamada %s', getattr(self.llamada, 'id', '?'))

    def transcripcion(self) -> str:
        lineas = []
        for rol, texto in self.historial:
            etiqueta = 'Cliente' if rol == 'cliente' else 'Asistente'
            lineas.append(f'{etiqueta}: {texto}')
        return '\n'.join(lineas)

    # --- Internos ---
    def _preparar_agente(self):
        from agentes_ia.consultor import AgenteConsultor
        from agentes_ia.models import AgenteIA

        agente = None
        if self.flujo is not None and self.flujo.agente_ia_id:
            agente = self.flujo.agente_ia
        if agente is None:
            # El respaldo se busca dentro del cliente de la llamada: contestar con
            # el agente de otro cliente le entregaría su base de conocimiento.
            cliente_id = getattr(self.llamada, 'cliente_id', None) if self.llamada else None
            if cliente_id is None and self.flujo is not None:
                cliente_id = self.flujo.cliente_id
            if cliente_id is not None:
                agente = (
                    AgenteIA.objects.filter(status=True, activo=True, cliente_id=cliente_id)
                    .select_related('apikey', 'coleccion').first()
                )
        if agente is None:
            logger.warning('[voz] no hay agente IA para este cliente; el flujo responderá solo con textos fijos')
            return
        try:
            self.consultor = AgenteConsultor(agente, self.llamada)
            if self.llamada and not self.llamada.agente_ia_id:
                self.llamada.agente_ia = agente
                self.llamada.save(update_fields=['agente_ia'])
        except Exception:
            logger.exception('[voz] no se pudo construir el agente IA')

    def _responder_con_agente(self, pregunta, salida=None) -> SalidaTurno:
        salida = salida or SalidaTurno()
        if not (pregunta or '').strip():
            salida.texto = salida.texto or '¿Sigues ahí? Cuéntame en qué te ayudo.'
            return salida
        if self.consultor is None:
            from agentes_ia.consultor import FRASE_FALLBACK
            salida.texto = FRASE_FALLBACK
            return salida

        datos = (self.llamada.datos_capturados or {}) if self.llamada else {}
        respuesta = self.consultor.responder(pregunta, self.historial, datos)
        salida.texto = respuesta.texto
        salida.latencia_llm_ms = respuesta.latencia_ms
        return salida

    def _desde_resultado(self, resultado) -> SalidaTurno:
        return SalidaTurno(
            texto=resultado.texto,
            finalizar=resultado.finalizar,
            transferir=resultado.transferir,
            paso_codigo=resultado.paso_codigo,
        )

    def _registrar_turno(self, rol, texto, dtmf='', paso='', latencia_llm=0, latencia_total=0):
        if self.llamada is None:
            return
        from llamadas.models import TurnoLlamada

        try:
            TurnoLlamada.objects.create(
                llamada=self.llamada,
                rol=rol,
                texto=texto or '',
                dtmf=dtmf or '',
                paso_codigo=paso or '',
                latencia_llm_ms=latencia_llm,
                latencia_ms=latencia_total,
            )
        except Exception:
            logger.exception('[voz] no se pudo guardar el turno')

    def _actualizar_paso(self, paso_codigo):
        if self.llamada is None or not paso_codigo:
            return
        try:
            self.llamada.paso_actual = paso_codigo
            self.llamada.save(update_fields=['paso_actual'])
        except Exception:
            logger.exception('[voz] no se pudo actualizar el paso actual')

    def _registrar_transferencia(self, asesor):
        if self.llamada is None:
            return
        from llamadas.models import TransferenciaLlamada

        try:
            TransferenciaLlamada.objects.create(
                llamada=self.llamada,
                asesor=asesor,
                motivo='solicitud_cliente',
                estado='solicitada',
                destino=getattr(asesor, 'numero_destino', '') or getattr(asesor, 'extension_sip', ''),
            )
            self.llamada.estado = 'transfiriendo'
            self.llamada.resultado = 'transferida'
            self.llamada.save(update_fields=['estado', 'resultado'])
        except Exception:
            logger.exception('[voz] no se pudo registrar la transferencia')
