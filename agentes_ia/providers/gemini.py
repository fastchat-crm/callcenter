"""Google Gemini via API REST (AI Studio tiene capa gratuita)."""
import requests

from .base import TIMEOUT_LISTADO, TIMEOUT_LLM, BaseProvider, RespuestaLLM

BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'


class GeminiProvider(BaseProvider):
    name = 'gemini'
    gratuito = True

    def default_model(self) -> str:
        return 'gemini-2.5-flash'

    def responder(self, mensajes, apikey='', modelo='', temperatura=0.3, max_tokens=400, base_url=''):
        modelo = modelo or self.default_model()
        url = f'{(base_url or BASE_URL).rstrip("/")}/models/{modelo}:generateContent'

        instruccion_sistema = '\n'.join(
            m['content'] for m in mensajes if m.get('role') == 'system'
        ).strip()
        contenidos = [
            {
                'role': 'model' if m.get('role') == 'assistant' else 'user',
                'parts': [{'text': m.get('content') or ''}],
            }
            for m in mensajes if m.get('role') in ('user', 'assistant')
        ]

        cuerpo = {
            'contents': contenidos,
            'generationConfig': {'temperature': temperatura, 'maxOutputTokens': max_tokens},
        }
        if instruccion_sistema:
            cuerpo['systemInstruction'] = {'parts': [{'text': instruccion_sistema}]}

        try:
            respuesta = requests.post(url, json=cuerpo, params={'key': apikey}, timeout=TIMEOUT_LLM)
            if respuesta.status_code >= 400:
                return RespuestaLLM(error=f'HTTP {respuesta.status_code}: {respuesta.text[:300]}')
            datos = respuesta.json()
            candidatos = datos.get('candidates') or []
            texto = ''
            if candidatos:
                partes = (candidatos[0].get('content') or {}).get('parts') or []
                texto = ''.join(parte.get('text', '') for parte in partes)
            uso = datos.get('usageMetadata') or {}
            return RespuestaLLM(
                texto=texto.strip(),
                tokens_entrada=uso.get('promptTokenCount', 0) or 0,
                tokens_salida=uso.get('candidatesTokenCount', 0) or 0,
                modelo=modelo,
                crudo=datos,
            )
        except Exception as ex:
            return RespuestaLLM(error=str(ex))

    def listar_modelos(self, apikey='', base_url=''):
        url = f'{(base_url or BASE_URL).rstrip("/")}/models'
        try:
            respuesta = requests.get(url, params={'key': apikey, 'pageSize': 200}, timeout=TIMEOUT_LISTADO)
            respuesta.raise_for_status()
            modelos = []
            for item in respuesta.json().get('models', []):
                if 'generateContent' not in (item.get('supportedGenerationMethods') or []):
                    continue
                identificador = (item.get('name') or '').replace('models/', '')
                if identificador:
                    modelos.append((identificador, item.get('displayName') or identificador))
            return modelos or [(self.default_model(), self.default_model())]
        except Exception:
            return [(self.default_model(), self.default_model())]
