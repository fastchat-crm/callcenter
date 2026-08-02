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

**Un solo worker.** El servicio es gunicorn con `uvicorn_worker.UvicornWorker` y
`--workers 1`; Daphne queda para depurar en primer plano. Whisper y Piper tardan segundos en
cargar y ocupan ~1,5 GB.
Compartirlos entre llamadas es la diferencia entre 300 ms y 3 s en el primer turno. Escalar
significa más puertos y balanceo en Nginx, no más workers en el mismo puerto.

**Medio dúplex con interrupción.** El sistema habla o escucha, nunca a la vez, pero la persona
sí puede cortarlo hablándole encima. Sin cancelación de eco no hay forma segura de distinguir
su voz del eco del propio asistente, así que se exige voz sostenida y bastante más fuerte que
el umbral normal. Está detallado en «Interrumpir al asistente», más abajo.

**VAD por energía.** `audio_utils.rms()` sobre tramas de 20 ms con umbral configurable.
Suficiente para telefonía, que ya llega filtrada. Si el entorno es ruidoso, la mejora es
Silero VAD.

**`audioop` con respaldo propio.** El módulo salió de la biblioteca estándar en Python 3.13.
`voz/audio.py` lo usa cuando existe e implementa mu-law, RMS y remuestreo en Python puro
cuando no. El proyecto corre en 3.11, 3.12 y 3.13 sin cambios.

**Multipaís por datos, no por código.** El número guarda su E.164, su ISO de país, su idioma
y su zona horaria. Agregar Colombia o España es crear un registro.

## Qué falta para producción seria

- Cancelación de eco: hoy la interrupción se distingue por energía sostenida, que es una
  heurística, no una certeza
- Reintento automático de transferencia cuando el asesor no contesta
- Métricas exportables a Prometheus
- Firma/validación de los webhooks del carrier

## Grabación de la llamada

El sistema es **medio dúplex** a propósito: habla o escucha, nunca a la vez. Eso tiene una
consecuencia útil para grabar —las dos voces casi nunca suenan a la vez—, así que
`voz/grabador.py` **concatena en el orden en que ocurrieron las cosas** en vez de mezclar y
sincronizar dos pistas. Al interrumpir hay un solapamiento de menos de un segundo, que es lo
que tarda en detectarse; la grabación lo refleja tal cual. El resultado es fiel a lo que se oyó
en la línea, con una fracción de la complejidad.

El audio se acumula en memoria durante la llamada y se escribe una sola vez al cerrar, ya
comprimido a MP3 con ffmpeg: un minuto pasa de ~960 KB a ~60 KB. Si ffmpeg no está, se guarda
el WAV — mejor ocupar disco que quedarse sin grabación.

Hay un tope de 30 minutos por llamada: a 8 kHz mono son 16 KB por segundo, y una llamada que
se va de las manos no debe llenar la RAM del proceso. Al alcanzarlo se deja de grabar y se
avisa en el log; la llamada sigue normal.

Los tres transportes graban igual, porque cada uno anota lo que entra y lo que sale:

| Transporte | Lo que anota |
|---|---|
| `MediaStreamConsumer` | mu-law del carrier, convertido a PCM |
| `VozWebConsumer` | PCM del navegador a 16 kHz, remuestreado a 8 kHz |
| `SesionAudioSocket` | PCM de Asterisk, ya a 8 kHz |

Se apaga desde *Parámetros del sistema* con `VOZ_GRABAR_LLAMADAS`. Apagarlo no afecta a la
transcripción ni al resumen, que se siguen guardando.

## El teclado (DTMF)

Los tres transportes reciben las teclas, cada uno por su vía: el carrier manda un evento
`dtmf` por WebSocket y Asterisk manda el tipo `0x03` de AudioSocket, un dígito por paquete.
Los dos terminan en el mismo `procesar_turno(texto, dtmf)`.

Cuándo se da por terminado lo marcado es la única decisión interesante, porque hay dos casos
opuestos: un menú se resuelve con **una** tecla y una cédula son **diez seguidas**. Esperar
siempre a la almohadilla dejaría el menú sin reaccionar. Lo que los distingue es el tiempo sin
recibir otro dígito, ajustable con `VOZ_MS_ESPERA_DTMF`; también se cierra con `#` o al llegar
a doce dígitos.

Al despachar las teclas se descarta el audio acumulado del turno: si alguien marcó en vez de
hablar, transcribir ese audio inventaría una respuesta que nadie dio.

## Interrumpir al asistente

Recibir y conversar corren en tareas separadas, y esa separación **es** la función. Con una
sola tarea, mientras el asistente hablaba nadie leía el socket: lo que decía la persona se
quedaba en el buffer del sistema y se procesaba segundos después, cuando ya no venía a cuento.
Medido antes del cambio: el asistente siguió hablando **13,3 s** después de que le hablaran
encima.

Ahora la tarea lectora no se detiene nunca, así que puede avisar de que están interrumpiendo
mientras el audio sale. Al detectarlo se deja de emitir y **no se procesa nada todavía**:
interrumpir es el principio de la frase, no el final. Cerrar el turno ahí transcribía solo el
medio segundo que costó detectar la interrupción. Lo acumulado se conserva y el turno lo cierra
el silencio, como siempre.

El problema real no es detectar energía sino distinguir la voz de la persona **del eco del
propio asistente** en la línea. Sin cancelación de eco no hay certeza, así que se exige lo que
el eco rara vez cumple: sonar bastante más fuerte que el umbral normal y sostenerse. Tres
perillas lo gobiernan:

| Parámetro | Por defecto | Para qué |
|---|---|---|
| `VOZ_BARGE_IN` | sí | Apagarlo es la salida si el asistente se corta solo |
| `VOZ_MS_VOZ_PARA_INTERRUMPIR` | 500 ms | Cuánto hay que hablar encima para cortarlo |
| `VOZ_FACTOR_INTERRUPCION` | 200 % | Cuánto más fuerte que el umbral normal |

Marcar una tecla también interrumpe, y ahí sí se procesa de inmediato: quien pulsa ya decidió.

Lo acumulado mientras habla el asistente se descarta si **nadie** interrumpió, porque es ruido
de línea y arrastrarlo al turno siguiente hace que el reconocedor invente sobre el fondo.

## Por qué la respuesta se trocea

El TTS tarda en proporción a lo que sintetiza, así que generar la frase entera antes de emitir
el primer sonido deja a la persona en silencio todo ese tiempo. `services.trocear_para_habla`
parte la respuesta por puntuación fuerte —o por comas si no hay— y el motor sintetiza el trozo
siguiente **mientras suena el actual**: emitir va al ritmo del reloj, 20 ms por trama, y ese
tiempo estaba desaprovechado.

Medido sobre el saludo del flujo de recepción con Piper: 561 ms hasta el primer sonido con la
frase entera, 107 ms con el primer trozo. Los trozos de menos de cuatro palabras se pegan al
vecino, porque un «Claro.» suelto suena entrecortado y cada llamada al TTS tiene su costo fijo.

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
