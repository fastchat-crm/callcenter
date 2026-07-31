"""Proveedor generico para cualquier API compatible con OpenAI.

Cubre gratis: Groq, OpenRouter (modelos :free), Together, Cerebras, LM Studio,
vLLM y Ollama en modo OpenAI. Solo cambia `base_url` y el modelo.
"""
import requests

from .base import TIMEOUT_LLM, BaseProvider, RespuestaLLM


class OpenAICompatProvider(BaseProvider):
    name = 'openai_compat'
    gratuito = False
    base_url_defecto = 'https://api.openai.com/v1'
    modelo_defecto = 'gpt-4o-mini'

    def default_model(self) -> str:
        return self.modelo_defecto

    def _url(self, base_url):
        return (base_url or self.base_url_defecto).rstrip('/')

    def responder(self, mensajes, apikey='', modelo='', temperatura=0.3, max_tokens=400, base_url=''):
        url = f'{self._url(base_url)}/chat/completions'
        cabeceras = {'Content-Type': 'application/json'}
        if apikey:
            cabeceras['Authorization'] = f'Bearer {apikey}'
        cuerpo = {
            'model': modelo or self.default_model(),
            'messages': mensajes,
            'temperature': temperatura,
            'max_tokens': max_tokens,
        }
        try:
            respuesta = requests.post(url, json=cuerpo, headers=cabeceras, timeout=TIMEOUT_LLM)
            if respuesta.status_code >= 400:
                return RespuestaLLM(error=f'HTTP {respuesta.status_code}: {respuesta.text[:300]}')
            datos = respuesta.json()
            uso = datos.get('usage') or {}
            texto = ''
            opciones = datos.get('choices') or []
            if opciones:
                texto = (opciones[0].get('message') or {}).get('content') or ''
            return RespuestaLLM(
                texto=texto.strip(),
                tokens_entrada=uso.get('prompt_tokens', 0) or 0,
                tokens_salida=uso.get('completion_tokens', 0) or 0,
                modelo=datos.get('model') or modelo,
                crudo=datos,
            )
        except Exception as ex:
            return RespuestaLLM(error=str(ex))

    def listar_modelos(self, apikey='', base_url=''):
        url = f'{self._url(base_url)}/models'
        cabeceras = {'Authorization': f'Bearer {apikey}'} if apikey else {}
        try:
            respuesta = requests.get(url, headers=cabeceras, timeout=10)
            respuesta.raise_for_status()
            datos = respuesta.json().get('data') or []
            return [(item.get('id'), item.get('id')) for item in datos if item.get('id')]
        except Exception:
            return [(self.default_model(), self.default_model())]


class GroqProvider(OpenAICompatProvider):
    """Groq: capa gratuita generosa y la inferencia mas rapida del mercado."""

    name = 'groq'
    gratuito = True
    base_url_defecto = 'https://api.groq.com/openai/v1'
    modelo_defecto = 'llama-3.3-70b-versatile'


class OpenRouterProvider(OpenAICompatProvider):
    """OpenRouter: catalogo con modelos marcados `:free`."""

    name = 'openrouter'
    gratuito = True
    base_url_defecto = 'https://openrouter.ai/api/v1'
    modelo_defecto = 'meta-llama/llama-3.3-70b-instruct:free'
