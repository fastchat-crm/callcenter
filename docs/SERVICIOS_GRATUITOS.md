# Servicios gratuitos: qué usar y hasta dónde alcanza

Todo el pipeline puede correr sin pagar. Este documento dice qué se usa en cada capa, cuál
es el límite real de la opción gratuita y cuándo conviene pagar.

## Resumen

| Capa | Opción gratuita | Límite real | Alternativa de pago |
|---|---|---|---|
| Telefonía | Asterisk auto-hospedado + softphone | Sin DID público; para llamar desde la calle hace falta un número | Twilio / Telnyx / Plivo (~USD 0,02/min entrante) |
| STT | faster-whisper `small` local | ~1,2 s por turno en 2 vCPU; español 88-93 % | Deepgram (~USD 0,0043/min) |
| LLM | Gemini Flash (AI Studio), Groq, Ollama local | Cuota diaria por proyecto; Ollama sin límite pero pide RAM | GPT-4o, Gemini Pro |
| TTS | Piper local · espeak-ng · edge-tts | Piper: voz clara pero no indistinguible | ElevenLabs (~USD 0,015/min) |
| Embeddings / RAG | sentence-transformers local | Primera carga descarga ~120 MB | OpenAI / Gemini embeddings |
| Almacenamiento | Disco local del servidor | Lo que dé el VPS | S3 / R2 / Wasabi |
| Base de datos | PostgreSQL | — | Servicio administrado |
| Cache / colas | Redis | — | Servicio administrado |

## Telefonía

**Asterisk en el mismo servidor** es la vía gratuita: registras softphones (Linphone,
Zoiper, MicroSIP) y llamas a la extensión del bot. Sirve para desarrollar, demostrar al
cliente y hacer QA completo del flujo.

Lo que **no** es gratis es el número público (DID): para que alguien llame desde su celular
hace falta comprarlo. En Ecuador ronda USD 5/mes más USD 0,015-0,025 por minuto entrante.
Detalles en [`TELEFONIA_SIP.md`](TELEFONIA_SIP.md).

Camino recomendado: desarrollar y demostrar con Asterisk + softphone; comprar el DID recién
cuando el cliente firme.

## STT — reconocimiento de voz

**faster-whisper** (CTranslate2) corre en CPU con cuantización `int8`.

Medido en este servidor —4 vCPU, 15 GB de RAM— sobre un turno de 4,5 segundos de audio
telefónico a 8 kHz, con el modelo ya cargado en memoria:

| Tamaño | Carga inicial | Por turno de 4,5 s | Factor tiempo real | Transcripción de prueba |
|---|---|---|---|---|
| `tiny` | 1,8 s | **0,97 s** | 0,21× | correcta |
| `base` | 5,0 s | **1,98 s** | 0,44× | correcta |
| `small` | 3,0 s | **3,17 s** | 0,70× | correcta |

`base` es el valor por defecto (`VOZ_WHISPER_SIZE` en `credenciales.json`): los tres
acertaron la frase de prueba, pero en línea ruidosa `tiny` se equivoca y `small` agrega un
segundo entero de espera que el cliente sí percibe. Con GPU —`VOZ_WHISPER_DEVICE: "cuda"` y
`VOZ_WHISPER_COMPUTE: "float16"`— se baja a 200-400 ms y conviene `small`.

El factor tiempo real es lo que importa para dimensionar: con `base` en 0,44× un solo
proceso aguanta cómodamente dos llamadas simultáneas; más allá de eso hay que sumar puertos
Daphne o subir de servidor.

Alternativa aún más liviana: **Vosk** (`VOZ_STT_MOTOR: "vosk"`), modelo español de ~40 MB,
menos preciso pero casi instantáneo.

## LLM — el cerebro

Los tres proveedores gratuitos ya vienen registrados en `agentes_ia/providers/`:

**Google Gemini (AI Studio)** — capa gratuita con cuota diaria por proyecto. Rápido y
suficiente para atención telefónica. Llave en <https://aistudio.google.com/apikey>.

**Groq** — capa gratuita generosa y la inferencia más rápida disponible hoy (Llama 3.3 70B
en cientos de milisegundos). Llave en <https://console.groq.com/keys>.

**Ollama local** — cero costo, cero salida de datos del servidor, sin cuotas. Requiere RAM:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b-instruct     # ~4,7 GB, buen español
ollama pull llama3.2:3b             # ~2 GB, más rápido y menos preciso
```

Es la única opción que cumple "los datos no salen del país" sin infraestructura extra —
argumento de venta real en salud, legal y sector público.

**OpenRouter** completa la lista: catálogo con modelos marcados `:free`.

## TTS — la voz

**Piper** es el motor por defecto: modelos ONNX que corren en CPU en decenas de
milisegundos, voz clara aunque reconociblemente sintética.

```bash
bash scripts/descargar_modelos_voz.sh es_MX-claude-high
```

Voces disponibles: `es_MX-claude-high`, `es_ES-davefx-medium`, `es_ES-sharvard-medium`,
`es_AR-daniela-high`. Catálogo completo en
<https://huggingface.co/rhasspy/piper-voices>.

**espeak-ng** (`apt install espeak-ng`) es el respaldo: siempre funciona, suena a robot de
los noventa. Sirve para no dejar la llamada muda si falta el modelo Piper.

**edge-tts** usa las voces neuronales de Microsoft Edge, gratuitas y sin API key. Suenan
notablemente mejor que Piper, pero el audio se genera en la nube: agrega 300-600 ms y saca
el texto del servidor. Requiere `ffmpeg`.

`voz/services.py` intenta el motor configurado y, si falla, cae al siguiente
automáticamente. La llamada nunca se queda sin audio por una dependencia faltante.

## RAG — base de conocimiento

`sentence-transformers` con `paraphrase-multilingual-MiniLM-L12-v2` genera los embeddings
en el propio servidor. El índice es un `.npz` de numpy por colección en
`media/vectorstore/<slug>/`, y la búsqueda es un producto punto sobre vectores normalizados.

Sin FAISS, sin base vectorial, sin costo por API. Para decenas de miles de fragmentos rinde
de sobra; por encima de eso conviene migrar a FAISS o `pgvector` — la interfaz pública
(`indexar`, `buscar`, `contexto_para_prompt`) no cambia.

## Almacenamiento

Grabaciones y transcripciones van al disco local (`media/`). Cuando crezca:

- **Cloudflare R2** — 10 GB gratis y sin cargo de salida
- **Wasabi** — ~USD 6/TB al mes
- **MinIO auto-hospedado** — S3 compatible, gratis, en tu propio disco

El modelo `GrabacionLlamada` ya tiene el campo `almacenamiento` (`local`, `minio`, `s3`)
para cuando se migre.

## Cuántas llamadas aguanta cada capa gratuita

Las cuotas de los proveedores vienen en peticiones y tokens por día, que no dice nada hasta
traducirlo a llamadas. Esta es la traducción, medida sobre las llamadas reales de esta
instalación (no sobre supuestos):

| Medida | Valor real |
|---|---|
| Duración media de una llamada | 36 s |
| Turnos por llamada | 5,2 (3,1 de la IA, 2,1 del cliente) |
| Tokens por turno de IA | 430 de entrada + 22 de salida |
| **Tokens por llamada** | **~1.400** |
| Latencia media del turno | 1.015 ms |

Con eso, el techo diario de cada opción gratuita:

| Proveedor y modelo | Cuota gratuita | Llamadas/día | Qué la limita |
|---|---|---|---|
| Groq · `llama-3.1-8b-instant` | 14.4K peticiones, 500K tokens/día | **~355** | los tokens |
| Groq · `llama-3.3-70b-versatile` | 1K peticiones, 100K tokens/día | **~70** | los tokens |
| Cerebras | 1M tokens/día | ~715 por tokens | **5 RPM: 1 llamada a la vez** |
| Groq · `whisper-large-v3` (STT) | 2K peticiones, 8 h de audio/día | **~950** | las peticiones |
| Ollama local | sin cuota | sin techo | la RAM y la CPU del servidor |

**Lo que de verdad limita no es el techo diario sino las peticiones por minuto**, porque las
llamadas son simultáneas. Una llamada consume ~5,2 turnos por minuto, así que:

| Límite del proveedor | Llamadas simultáneas |
|---|---|
| Groq, 30 RPM | 5 a 6 |
| Gemini, 15 RPM | ~3 |
| Cerebras, 5 RPM | **1** |

Cerebras regala un millón de tokens al día pero con 5 peticiones por minuto: sirve para
tareas por lotes, no para atender teléfono. Es el ejemplo de por qué la cuota diaria sola
engaña.

### Lo que cambió en 2025

Google **recortó la capa gratuita de Gemini** hacia finales de 2025. Las cifras que circulan
—15 peticiones por minuto y 1.500 al día en Flash— no están publicadas en la documentación
oficial, que ahora remite al panel de AI Studio de cada cuenta. Antes de apoyar un cliente en
esa cuota, míralas en <https://aistudio.google.com/rate-limit>: son por proyecto y cambian
sin aviso.

### STT en la nube en vez de local

Groq expone Whisper con **8 horas de audio al día gratis**. Comparado con el Whisper local de
este servidor:

| | Whisper local `base` | Groq `whisper-large-v3` |
|---|---|---|
| Latencia por turno de 4,5 s | ~2,0 s | 200-400 ms más red |
| Costo | CPU del servidor | gratis hasta 8 h/día |
| Precisión | buena | mejor (modelo `large`) |
| El audio sale del servidor | no | **sí** |

Para un cliente que exige que la voz no salga del país, el local es la única opción. Para el
resto, Groq baja el turno más de un segundo sin pagar nada.

### TTS: la trampa de la capa gratuita

**ElevenLabs regala 10.000 caracteres al mes.** Una respuesta de la IA ronda los 100
caracteres y hay 3 por llamada, así que la cuota gratuita da para **unas 33 llamadas al mes**.
Sirve para grabar una demo, no para operar.

Las opciones que sí sostienen producción sin pagar son **Piper** (local, sin cuota, voz
sintética reconocible) y **edge-tts** (voces neuronales de Microsoft, notablemente mejores).
Ojo con edge-tts: usa un endpoint interno de Edge sin contrato ni API key, así que puede
dejar de funcionar cuando Microsoft quiera. Está bien como mejora, no como cimiento.

### Conclusión práctica

- **Para desarrollar y demostrar:** todo local. Cero cuentas, cero cuotas, cero sorpresas.
- **Hasta ~350 llamadas/día:** Groq con `llama-3.1-8b-instant` + Whisper de Groq + Piper.
  Cero dólares y latencia por debajo del segundo.
- **Más que eso, o si el cliente exige que los datos no salgan:** Ollama local, y la factura
  es el servidor.

Las cuotas gratuitas se recortan sin aviso —Gemini es la prueba—, así que un cliente en
producción sobre capa gratuita es una promesa que no controlas.

### Cómo dejarlo funcionando

Una sola cuenta —Groq— cubre el cerebro y el reconocimiento de voz, y no pide tarjeta.

1. Crea la llave en <https://console.groq.com/keys>.
2. *Centro de voz e IA → Llaves de IA → Nueva llave*: proveedor **Groq**, pega la clave, deja
   el modelo vacío (sale `llama-3.1-8b-instant`, que es el que rinde ~355 llamadas/día) y
   márcala **por defecto**. Usa **Probar** antes de guardar.
3. *Centro de voz e IA → Agentes IA*: en el agente, elige esa llave.
4. *Centro de seguridad → Parámetros del sistema*: pon `VOZ_STT_MOTOR` en **groq**. El cambio
   entra en las llamadas nuevas, sin reiniciar.

La misma llave sirve para las dos cosas: el agente la usa para responder y el motor de voz la
usa para transcribir. Si Groq no responde, la transcripción **cae sola a Whisper local** en vez
de perder el turno, así que cambiar el parámetro no es un salto sin red.

Para revertir, pon `VOZ_STT_MOTOR` en `faster_whisper` y todo vuelve a correr en el servidor.

## Costo mensual comparado

Escenario: 1 cliente, 10 llamadas/día × 12,5 min ≈ **3.000 min/mes**.

| Componente | Todo gratuito | Mixto (recomendado) | Todo de pago |
|---|---|---|---|
| Número + minutos | USD 0 (sin DID público) | USD 65 | USD 65 |
| STT | USD 0 (Whisper local) | USD 13 (Deepgram) | USD 13 |
| LLM | USD 0 (Gemini free / Ollama) | USD 3 | USD 25 |
| TTS | USD 0 (Piper) | USD 27 (ElevenLabs) | USD 27 |
| Almacenamiento | USD 0 (local) | USD 1 | USD 1 |
| Servidor | USD 6-12 (VPS) | USD 12 | USD 24 |
| **Total** | **USD 6-12** | **USD ~121** | **USD ~155** |

La versión gratuita entrega 2,5-4 s de latencia por turno y voz sintética reconocible.
La mixta baja a 0,6-1,2 s con voz natural. Para vender, la ruta sensata es demostrar con la
gratuita y ofrecer la mixta como plan estándar.

## Enlaces

**Telefonía** · [Asterisk](https://www.asterisk.org/) · [FreeSWITCH](https://freeswitch.com/) ·
[Twilio](https://www.twilio.com/voice/pricing) · [Telnyx](https://telnyx.com/pricing/call-control) ·
[Plivo](https://www.plivo.com/pricing/) · [SignalWire](https://signalwire.com/pricing)

**STT** · [faster-whisper](https://github.com/SYSTRAN/faster-whisper) ·
[Vosk](https://alphacephei.com/vosk/) · [Deepgram](https://deepgram.com/pricing)

**LLM** · [Google AI Studio](https://aistudio.google.com/apikey) ·
[Groq](https://console.groq.com/keys) · [Ollama](https://ollama.com/) ·
[OpenRouter](https://openrouter.ai/models?q=free)

**TTS** · [Piper](https://github.com/rhasspy/piper) ·
[voces Piper](https://huggingface.co/rhasspy/piper-voices) ·
[edge-tts](https://github.com/rany2/edge-tts) · [ElevenLabs](https://elevenlabs.io/pricing)

**RAG** · [sentence-transformers](https://www.sbert.net/) · [pgvector](https://github.com/pgvector/pgvector)

**Almacenamiento** · [Cloudflare R2](https://developers.cloudflare.com/r2/pricing/) ·
[Wasabi](https://wasabi.com/cloud-storage-pricing) · [MinIO](https://min.io/)
