"""Ollama Cloud — endpoint compatible con OpenAI en https://ollama.com/v1.

Es el mismo servicio que usa fastchatdj: se reutiliza la misma llave. No provee
embeddings, así que el RAG usa embeddings de otro proveedor (Gemini) o locales.
"""
import requests

from .base import TIMEOUT_LISTADO
from .openai_compat import OpenAICompatProvider


class OllamaCloudProvider(OpenAICompatProvider):
    name = 'ollama_cloud'
    gratuito = False
    base_url_defecto = 'https://ollama.com/v1'
    modelo_defecto = 'gpt-oss:20b'

    def listar_modelos(self, apikey='', base_url=''):
        url = f'{self._url(base_url)}/models'
        try:
            respuesta = requests.get(url, headers={'Authorization': f'Bearer {apikey}'},
                                     timeout=TIMEOUT_LISTADO)
            respuesta.raise_for_status()
            datos = respuesta.json().get('data') or []
            modelos = [(item.get('id'), item.get('id')) for item in datos if item.get('id')]
            return modelos or [(self.default_model(), self.default_model())]
        except Exception:
            return [(self.default_model(), self.default_model())]
