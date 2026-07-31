"""Motor conversacional del agente IA para canal telefonico.

Diferencias frente a un chat de texto:
  - la respuesta se va a escuchar, no a leer: sin markdown, sin listas, sin URL
  - se limita a pocas oraciones para no cansar al cliente
  - todo fallo cae en una frase segura en vez de romper la llamada
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger('agentes_ia')

FRASE_FALLBACK = 'Disculpa, no tengo esa información a la mano. ¿Deseas que te comunique con un asesor?'
MAXIMO_HISTORIAL = 8

_LIMPIEZA = (
    (re.compile(r'https?://\S+'), ' '),
    (re.compile(r'[*_`#>|]+'), ' '),
    (re.compile(r'^\s*[-•]\s*', re.M), ' '),
    (re.compile(r'\s{2,}'), ' '),
)


def humanizar_para_voz(texto: str, maximo_oraciones: int = 2) -> str:
    """Deja el texto listo para TTS: sin markdown ni enlaces y acotado."""
    resultado = texto or ''
    for patron, reemplazo in _LIMPIEZA:
        resultado = patron.sub(reemplazo, resultado)
    resultado = resultado.strip()
    if not resultado:
        return ''
    oraciones = re.split(r'(?<=[.!?])\s+', resultado)
    if maximo_oraciones and len(oraciones) > maximo_oraciones:
        resultado = ' '.join(oraciones[:maximo_oraciones])
    return resultado.strip()


@dataclass
class RespuestaAgente:
    texto: str = ''
    latencia_ms: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    modelo: str = ''
    uso_contexto: bool = False
    error: str = ''
    contexto: str = field(default='', repr=False)


class AgenteConsultor:
    """Envuelve un `AgenteIA` y responde preguntas usando su proveedor y su RAG."""

    def __init__(self, agente, llamada=None):
        self.agente = agente
        self.llamada = llamada
        self.apikey = agente.apikey
        from agentes_ia.providers import get_provider

        self.provider = get_provider(self.apikey.nombre_proveedor)

    def responder(self, pregunta: str, historial: list[tuple[str, str]] | None = None,
                  datos_llamada: dict | None = None) -> RespuestaAgente:
        inicio = time.time()
        historial = historial or []

        contexto = ''
        if self.agente.usar_rag and self.agente.coleccion_id:
            from agentes_ia.rag import contexto_para_prompt
            try:
                contexto = contexto_para_prompt(
                    self.agente.coleccion, pregunta, self.agente.fragmentos_contexto,
                )
            except Exception:
                logger.exception('[agente] no se pudo recuperar contexto RAG')

        mensajes = self._construir_mensajes(pregunta, historial, contexto, datos_llamada or {})
        respuesta = self.provider.responder(
            mensajes,
            apikey=self.apikey.clave or '',
            modelo=self.apikey.modelo or '',
            temperatura=self.agente.temperatura,
            max_tokens=self.agente.max_tokens_respuesta,
            base_url=self.apikey.base_url or '',
        )
        latencia_ms = int((time.time() - inicio) * 1000)

        if not respuesta.ok:
            logger.warning('[agente] proveedor %s falló: %s', self.provider.name, respuesta.error)
            self._registrar_consumo(respuesta, latencia_ms, bool(contexto))
            return RespuestaAgente(texto=FRASE_FALLBACK, latencia_ms=latencia_ms,
                                   error=respuesta.error or 'respuesta vacía')

        texto = humanizar_para_voz(respuesta.texto, self.agente.maximo_oraciones)
        self._registrar_consumo(respuesta, latencia_ms, bool(contexto))
        return RespuestaAgente(
            texto=texto or FRASE_FALLBACK,
            latencia_ms=latencia_ms,
            tokens_entrada=respuesta.tokens_entrada,
            tokens_salida=respuesta.tokens_salida,
            modelo=respuesta.modelo,
            uso_contexto=bool(contexto),
            contexto=contexto,
        )

    # --- Internos ---
    def _construir_mensajes(self, pregunta, historial, contexto, datos_llamada):
        instrucciones = [
            self.agente.prompt_sistema,
            f'Tono de la conversación: {self.agente.get_tono_display()}.',
            f'Responde siempre en el idioma con código "{self.agente.idioma}".',
            f'Máximo {self.agente.maximo_oraciones} oraciones. Nada de listas, viñetas, enlaces ni emojis.',
            'Los números dilos en palabras naturales para que se escuchen bien.',
        ]
        if self.agente.descripcion:
            instrucciones.append(f'Contexto de negocio: {self.agente.descripcion}')
        if datos_llamada:
            resumen_datos = ', '.join(f'{clave}: {valor}' for clave, valor in datos_llamada.items() if valor)
            if resumen_datos:
                instrucciones.append(f'Datos ya capturados del cliente: {resumen_datos}.')
        if contexto:
            instrucciones.append(
                'Usa exclusivamente la siguiente información para responder consultas sobre '
                f'la empresa, sus planes y servicios:\n{contexto}'
            )
        else:
            instrucciones.append(
                'No tienes documentos de respaldo cargados: si te preguntan un dato específico '
                'que no conoces, ofrece transferir con un asesor.'
            )

        mensajes = [{'role': 'system', 'content': '\n'.join(instrucciones)}]
        for rol, texto in historial[-MAXIMO_HISTORIAL:]:
            mensajes.append({
                'role': 'assistant' if rol in ('ia', 'assistant') else 'user',
                'content': texto,
            })
        mensajes.append({'role': 'user', 'content': pregunta})
        return mensajes

    def _registrar_consumo(self, respuesta, latencia_ms, uso_rag=False):
        """Deja el rastro del turno: tokens, latencia, costo estimado y error si lo hubo."""
        from django.db.models import F

        from agentes_ia.consumo import costo_usd
        from agentes_ia.models import ApiKeyIA, ConsumoIA

        modelo = respuesta.modelo or self.apikey.modelo or ''
        proveedor = self.provider.name
        try:
            ConsumoIA.objects.create(
                agente=self.agente,
                llamada=self.llamada,
                apikey=self.apikey,
                modelo=modelo,
                proveedor=proveedor,
                tokens_entrada=respuesta.tokens_entrada,
                tokens_salida=respuesta.tokens_salida,
                latencia_ms=latencia_ms,
                costo_usd=costo_usd(modelo, respuesta.tokens_entrada,
                                    respuesta.tokens_salida, proveedor),
                uso_rag=uso_rag,
                error=(respuesta.error or '')[:200],
            )
            ApiKeyIA.objects.filter(pk=self.apikey.pk).update(
                consumo_tokens_entrada=F('consumo_tokens_entrada') + int(respuesta.tokens_entrada or 0),
                consumo_tokens_salida=F('consumo_tokens_salida') + int(respuesta.tokens_salida or 0),
            )
        except Exception:
            logger.exception('[agente] no se pudo registrar el consumo')


def responder_generico(pregunta: str, historial=None, idioma='es', cliente=None) -> str:
    """Respuesta cuando el flujo no tiene agente configurado.

    Usa el primer agente activo *de ese cliente*; sin cliente, o si no tiene
    ninguno, devuelve la frase segura para no tumbar la llamada. Nunca contesta
    con el agente de otro cliente: le entregaría su base de conocimiento.
    """
    from agentes_ia.models import AgenteIA

    agente = (
        AgenteIA.objects.filter(status=True, activo=True, cliente=cliente)
        .select_related('apikey').first()
    ) if cliente is not None else None
    if agente is None:
        return FRASE_FALLBACK
    return AgenteConsultor(agente).responder(pregunta, historial or []).texto
