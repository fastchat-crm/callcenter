# Dependencias y servicios — callcenter

Qué corre de verdad en este servidor y qué pasa si falta. `requirements.txt` lleva el detalle
de versiones; esto explica el porqué.

---

## Servicios del sistema

| Servicio | Para qué | Si se cae |
|---|---|---|
| `callcenter` | El panel y los WebSockets de voz (gunicorn + `UvicornWorker`, `--workers 1`) | No hay sistema |
| `callcenter-audiosocket` | Puente TCP entre Asterisk y el orquestador | Asterisk contesta y nadie habla |
| `asterisk` | Central telefónica, troncales SIP y transferencias | No entran llamadas |
| `postgresql@17-main` | Todo el dato | No hay sistema |
| `redis-server` | Capa de canales y caché de parámetros | Se caen los WebSockets |
| `nginx` | HTTPS en `callcenter.integrasoluc.net` y proxy al 9000 | Solo se llega por IP y puerto |

```bash
service callcenter restart        # nunca runserver
service asterisk status
journalctl -u callcenter -f
```

`bash deploy/reiniciar.sh manual` para probar en primer plano.

**Un solo worker, a propósito.** Los modelos de voz viven en memoria y se comparten entre
llamadas; con dos workers se duplican y el estado de las llamadas deja de ser coherente.

---

## Python

**Núcleo** — Django 4.2, Channels 4, gunicorn + `uvicorn-worker` (los WebSockets de voz no
viajan por WSGI; Daphne queda para depurar en primer plano), psycopg2, redis.

`audioop` salió de la biblioteca estándar en 3.13, así que `audioop-lts` se instala solo en
esa versión. Por eso `voz/audio.py` centraliza las conversiones y funciona con o sin él: usar
`audioop` directo rompe según el intérprete.

**Voz** — `faster-whisper` (STT local) y `piper-tts` (TTS local). Ambos gratuitos y sin salir
del servidor. `edge-tts` queda como alternativa de voces neuronales, y `espeak-ng` se instala
por apt. El motor activo se elige con el parámetro `VOZ_STT_MOTOR`.

**RAG** — `sentence-transformers` para embeddings locales, sin costo por API. Los documentos
se leen con `pypdf` y, si está configurado, con **Apache Tika** para el resto de formatos.

---

## Servicios externos

| Servicio | Uso | Gratuito hasta |
|---|---|---|
| Groq | LLM `llama-3.1-8b-instant` y STT `whisper-large-v3-turbo` | El límite que ata es el RPM, no el RPD |
| Weaviate | Base vectorial, solo si la colección lo pide | Auto-hospedado |
| Apache Tika | Extraer texto de documentos para el RAG | Auto-hospedado |

Ninguno es imprescindible para que el panel levante, y **ninguno debe tumbar una pantalla al
no responder**: se consultan siempre dentro de un `try` (ver `skills/django-patterns.md`).

Medido sobre las llamadas reales de esta instalación —36 s, 5,2 turnos, ~1.400 tokens— la
capa gratuita de Groq da del orden de 355 llamadas al día. Lo que limita la concurrencia son
las peticiones por minuto.

---

## Configuración

`credenciales.json`, fuera del control de versiones (`credenciales_template.json` muestra las
claves). **No se lee ni se modifica desde el código de tareas.**

Lo que se ajusta en caliente vive en `core/parametros.py`: motores de voz, umbrales de
silencio, grabación, límites de la IA interna y el registro público. La base guarda solo los
valores cambiados, con 30 s de caché.
