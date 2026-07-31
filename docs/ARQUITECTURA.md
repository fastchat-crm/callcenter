# Arquitectura

## Recorrido de una llamada

```
  Cliente marca +593 …
        │
        ▼
  Carrier / Asterisk
        │  HTTP POST  /telefonia/webhook/entrante/
        ▼
  telefonia/view_webhook.py  ──►  XML con <Stream url="ws://IP/ws/voz/stream/">
        │
        ▼  WebSocket (audio mu-law 8 kHz en base64)
  voz/consumers.py  MediaStreamConsumer
        │
        ├── crea llamadas.Llamada, resuelve el número → flujo IVR
        ├── VAD por energía: detecta cuándo el cliente terminó de hablar
        │
        ▼
  voz/orquestador.py  OrquestadorLlamada
        │
        ├── voz/services.transcribir_pcm()      STT   (faster-whisper local)
        ├── ivr/motor.py  MotorIVR              flujo (menú, captura, condición…)
        ├── agentes_ia/consultor.py             LLM   (Gemini / Groq / Ollama)
        │      └── agentes_ia/rag/vectorstore   RAG   (embeddings locales)
        └── voz/services.sintetizar_ulaw()      TTS   (Piper / espeak / edge)
        │
        ▼  audio de vuelta en tramas de 20 ms
  Cliente escucha la respuesta
```

Cada turno se guarda en `llamadas_turnollamada` con sus latencias separadas (STT, LLM, TTS),
que es lo que permite saber qué componente conviene optimizar.

## Capas

### Transporte — `voz/consumers.py` y `voz/audiosocket.py`

**Tres** transportes sobre la misma lógica de conversación:

| Transporte | Protocolo | Quién lo usa |
|---|---|---|
| `MediaStreamConsumer` | WebSocket, JSON con `start/media/dtmf/stop`, mu-law 8 kHz en base64 | Twilio, Telnyx, Plivo, SignalWire |
| `VozWebConsumer` | WebSocket, PCM 16 bits 16 kHz binario | El demo del navegador |
| `SesionAudioSocket` | **TCP plano**, encabezado de 3 bytes, PCM 16 bits 8 kHz | Asterisk auto-hospedado |

Asterisk **no puede** usar el primero: Media Streams es un protocolo propio de Twilio y
Asterisk no lo habla. Por eso existe el tercero, que habla el `AudioSocket()` que Asterisk sí
trae de fábrica. El detalle de cómo se resuelve que AudioSocket no transporte el número que
marcó está en [`TELEFONIA_SIP.md`](TELEFONIA_SIP.md).

Los tres **solo manejan transporte**: buffer de audio, detección de fin de turno y envío de
tramas. Toda la conversación vive fuera, en el orquestador. Por eso agregar un transporte
nuevo no toca la lógica: hay dos protocolos completamente distintos —WebSocket con JSON y TCP
crudo— compartiendo el mismo `OrquestadorLlamada`.

### Conversación — `voz/orquestador.py`

`OrquestadorLlamada` recibe el texto del cliente y decide:

1. Si hay flujo IVR, se lo pasa a `MotorIVR`.
2. Si el paso es de tipo `agente_ia` (o no hay flujo), consulta al `AgenteConsultor`.
3. Persiste el turno, actualiza el paso actual y registra la transferencia si toca.

Es síncrono a propósito: el consumer lo invoca con `asyncio.to_thread`, así el ORM de Django
trabaja en su modo natural y el event loop nunca se bloquea.

### Motor IVR — `ivr/motor.py`

Grafo de pasos con estado por llamada: variables capturadas, reintentos y turnos gastados
con la IA. Devuelve un `ResultadoPaso` con qué decir, si espera respuesta, si transfiere y
si finaliza. Reglas heredadas del motor de chatbot de fastchat: comparación insensible a
mayúsculas y tildes, repetición del paso ante entrada inválida, y escalamiento a humano
cuando se agotan los reintentos.

### Agente IA — `agentes_ia/`

`AgenteConsultor` arma el prompt (instrucciones + tono + datos ya capturados + contexto RAG),
llama al proveedor y **humaniza la respuesta para voz**: sin markdown, sin enlaces, sin
viñetas y acotada a N oraciones. Si el proveedor falla, devuelve una frase segura que ofrece
transferir — la llamada nunca se queda en silencio por un error de API.

Los proveedores implementan `BaseProvider` y se registran en un diccionario. Se usa
`requests` en lugar de SDKs pesados: el proyecto arranca en un VPS modesto sin compilar
dependencias.

### Datos — `llamadas/`, `telefonia/`, `ivr/`, `agentes_ia/`

Todos los modelos heredan `ModeloBase` (auditoría + `status` como borrado lógico). Las
consultas de listado siempre filtran `status=True`.

### Panel — vistas basadas en funciones

Misma convención que fastchatdj:

```
GET  sin action     → listado paginado
GET  ?action=add    → JSON con el HTML del formulario (se abre en modal)
GET  ?action=ver    → plantilla de detalle
POST action=add     → crea
POST action=change  → edita
POST action=delete  → status = False
```

`core/crud.py` implementa ese contrato una sola vez; cada `view_*.py` declara un `ConfigCrud`
y delega. Las vistas con lógica propia (pasos del IVR, conocimiento, llamadas) escriben el
despacho a mano siguiendo el mismo patrón.

## Decisiones de diseño

**Un solo proceso Daphne.** Whisper y Piper tardan segundos en cargar y ocupan ~1,5 GB.
Compartirlos entre llamadas es la diferencia entre 300 ms y 3 s en el primer turno. Escalar
significa más puertos y balanceo en Nginx, no más workers en el mismo puerto.

**Half-duplex simple.** Mientras la IA habla se ignora el audio entrante, para evitar que se
escuche a sí misma. El *barge-in* (interrumpir a la IA) exige cancelación de eco y detección
de voz sobre el audio de salida: es el siguiente paso natural, no está incluido.

**VAD por energía.** `audio_utils.rms()` sobre tramas de 20 ms con umbral configurable.
Suficiente para telefonía, que ya llega filtrada. Si el entorno es ruidoso, la mejora es
Silero VAD.

**`audioop` con respaldo propio.** El módulo salió de la biblioteca estándar en Python 3.13.
`voz/audio.py` lo usa cuando existe e implementa mu-law, RMS y remuestreo en Python puro
cuando no. El proyecto corre en 3.11, 3.12 y 3.13 sin cambios.

**Multipaís por datos, no por código.** El número guarda su E.164, su ISO de país, su idioma
y su zona horaria. Agregar Colombia o España es crear un registro.

## Qué falta para producción seria

- Barge-in con cancelación de eco
- Grabación del audio completo (hoy se guarda la transcripción; el modelo de grabación existe)
- Reintento automático de transferencia cuando el asesor no contesta
- Métricas exportables a Prometheus
- Firma/validación de los webhooks del carrier

## Parámetros ajustables en caliente

Las perillas del motor —cuánto silencio cierra un turno, cuánta transcripción se le manda a la
IA interna— vivían en `credenciales.json` y cambiarlas exigía reiniciar el servicio. Ahora
están en *Centro de seguridad → Parámetros del sistema* y entran en las llamadas nuevas.

El catálogo vive en `core/parametros.py`: clave, qué hace, tipo y valor por defecto. En la
base (`ParametroSistema`) **solo se guardan las claves que alguien cambió**, así que el valor
por defecto siempre es el del código y restaurar es dar de baja la fila, no recordar cuál era
el número original.

```python
from core.parametros import obtener

self.umbral = obtener('VOZ_UMBRAL_SILENCIO')
```

Los valores se cachean 30 segundos, porque esto se lee en cada turno de voz. Si la base no
responde, `obtener()` devuelve el valor del código en vez de fallar.

**Regla al agregar uno:** declararlo en `CATALOGO` y leerlo con `obtener()` donde se use. Si
no se lee en ningún lado, no se declara — una pantalla llena de perillas que no hacen nada es
peor que no tenerla.
