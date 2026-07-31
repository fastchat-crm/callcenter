"""Ollama auto-hospedado: 100% gratuito y sin salida de datos del servidor."""
import requests

from .base import TIMEOUT_LISTADO, TIMEOUT_LLM_LOCAL, BaseProvider, RespuestaLLM

BASE_URL = 'http://127.0.0.1:11434'


class OllamaLocalProvider(BaseProvider):
    name = 'ollama_local'
    gratuito = True
    requiere_apikey = False

    def default_model(self) -> str:
        return 'qwen2.5:7b-instruct'

    def responder(self, mensajes, apikey='', modelo='', temperatura=0.3, max_tokens=400, base_url=''):
        url = f'{(base_url or BASE_URL).rstrip("/")}/api/chat'
        cuerpo = {
            'model': modelo or self.default_model(),
            'messages': mensajes,
            'stream': False,
            'options': {'temperature': temperatura, 'num_predict': max_tokens},
        }
        try:
            respuesta = requests.post(url, json=cuerpo, timeout=TIMEOUT_LLM_LOCAL)
            if respuesta.status_code >= 400:
                return RespuestaLLM(error=f'HTTP {respuesta.status_code}: {respuesta.text[:300]}')
            datos = respuesta.json()
            return RespuestaLLM(
                texto=((datos.get('message') or {}).get('content') or '').strip(),
                tokens_entrada=datos.get('prompt_eval_count', 0) or 0,
                tokens_salida=datos.get('eval_count', 0) or 0,
                modelo=datos.get('model') or modelo,
                crudo=datos,
            )
        except Exception as ex:
            return RespuestaLLM(error=str(ex))

    def listar_modelos(self, apikey='', base_url=''):
        url = f'{(base_url or BASE_URL).rstrip("/")}/api/tags'
        try:
            respuesta = requests.get(url, timeout=TIMEOUT_LISTADO)
            respuesta.raise_for_status()
            modelos = [(item['name'], item['name']) for item in respuesta.json().get('models', [])]
            return modelos or [(self.default_model(), self.default_model())]
        except Exception:
            return [(self.default_model(), self.default_model())]
