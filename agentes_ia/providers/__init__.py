"""Registro central de proveedores de LLM.

Punto de entrada unico: `get_provider(nombre_o_id)`.
Los marcados con `gratuito = True` funcionan con capa gratuita o auto-hospedados.
"""
from .base import BaseProvider, RespuestaLLM
from .gemini import GeminiProvider
from .ollama_cloud import OllamaCloudProvider
from .ollama_local import OllamaLocalProvider
from .openai_compat import GroqProvider, OpenAICompatProvider, OpenRouterProvider

_PROVIDERS: dict[str, BaseProvider] = {
    GeminiProvider.name: GeminiProvider(),
    GroqProvider.name: GroqProvider(),
    OpenRouterProvider.name: OpenRouterProvider(),
    OllamaLocalProvider.name: OllamaLocalProvider(),
    OpenAICompatProvider.name: OpenAICompatProvider(),
    OllamaCloudProvider.name: OllamaCloudProvider(),
}

# Id numerico (agentes_ia.models.PROVEEDOR_CHOICES) → nombre interno
PROVEEDOR_ID_TO_NAME: dict[int, str] = {
    1: 'gemini',
    2: 'groq',
    3: 'openrouter',
    4: 'ollama_local',
    5: 'openai_compat',
    6: 'ollama_cloud',
}

PROVEEDOR_NAME_TO_ID = {nombre: identificador for identificador, nombre in PROVEEDOR_ID_TO_NAME.items()}


def get_provider(nombre_o_id) -> BaseProvider:
    nombre = nombre_o_id
    if isinstance(nombre_o_id, int) or str(nombre_o_id).isdigit():
        nombre = PROVEEDOR_ID_TO_NAME.get(int(nombre_o_id))
    proveedor = _PROVIDERS.get(nombre)
    if proveedor is None:
        disponibles = ', '.join(sorted(_PROVIDERS))
        raise ValueError(f'Proveedor de IA desconocido: {nombre_o_id}. Disponibles: {disponibles}')
    return proveedor


def proveedores_gratuitos():
    return [nombre for nombre, proveedor in _PROVIDERS.items() if proveedor.gratuito]


__all__ = ['BaseProvider', 'RespuestaLLM', 'get_provider', 'proveedores_gratuitos',
           'PROVEEDOR_ID_TO_NAME', 'PROVEEDOR_NAME_TO_ID']
