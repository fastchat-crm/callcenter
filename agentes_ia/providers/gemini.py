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
            'generationConfig': {
                'temperature': temperatura,
                'maxOutputTokens': max_tokens,
                # Esto es un sistema de voz: el razonamiento interno de los
                # modelos 2.5 se come el presupuesto de tokens y agrega segundos
                # a una llamada telefónica. Los modelos que no lo aceptan
                # responden 400 y se reintenta sin el campo.
                'thinkingConfig': {'thinkingBudget': 0},
            },
        }
        if instruccion_sistema:
            cuerpo['systemInstruction'] = {'parts': [{'text': instruccion_sistema}]}

        try:
            respuesta = requests.post(url, json=cuerpo, params={'key': apikey}, timeout=TIMEOUT_LLM)
            if respuesta.status_code == 400 and 'thinking' in respuesta.text.lower():
                cuerpo['generationConfig'].pop('thinkingConfig', None)
                respuesta = requests.post(url, json=cuerpo, params={'key': apikey}, timeout=TIMEOUT_LLM)
            if respuesta.status_code >= 400:
                return RespuestaLLM(error=f'HTTP {respuesta.status_code}: {respuesta.text[:300]}')
            datos = respuesta.json()
            candidatos = datos.get('candidates') or []
            texto = ''
            motivo = ''
            if candidatos:
                motivo = candidatos[0].get('finishReason') or ''
                partes = (candidatos[0].get('content') or {}).get('parts') or []
                # Las partes con `thought` son el razonamiento del modelo, no su
                # respuesta: devolverlas sería filtrar su borrador al cliente.
                texto = ''.join(
                    parte.get('text', '') for parte in partes if not parte.get('thought')
                )
            uso = datos.get('usageMetadata') or {}
            texto = texto.strip()
            if not texto and motivo == 'MAX_TOKENS':
                pensados = uso.get('thoughtsTokenCount', 0) or 0
                return RespuestaLLM(
                    error=f'El modelo agotó los {max_tokens} tokens antes de responder'
                          + (f' ({pensados} se fueron en razonamiento)' if pensados else ''),
                    modelo=modelo, crudo=datos,
                )
            return RespuestaLLM(
                texto=texto,
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
