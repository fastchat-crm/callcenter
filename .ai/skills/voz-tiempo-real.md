# Voz en tiempo real — callcenter

Lo que no existe en fastchatdj y define este proyecto: hay una persona esperando al otro lado
del teléfono. Un segundo de más se nota; un bloqueo se lleva por delante todas las llamadas
en curso.

---

## El recorrido

```
Asterisk  ──AudioSocket TCP──┐
Twilio    ──WebSocket────────┼──▶ OrquestadorLlamada ──▶ STT ──▶ Agente IA ──▶ TTS ──▶ audio
Navegador ──WebSocket────────┘
```

Tres transportes, **un solo orquestador**:

| Transporte | Archivo | Origen |
|---|---|---|
| `SesionAudioSocket` | `voz/audiosocket.py` | Asterisk, TCP, tipos `0x00 0x01 0x10 0xff` |
| `MediaStreamConsumer` | `voz/consumers.py` | Carrier por WebSocket |
| `VozWebConsumer` | `voz/consumers.py` | Demo desde el navegador |

**Los consumers solo manejan transporte.** Toda la lógica de conversación vive en
`voz/orquestador.py`. Si hay que decidir algo sobre el turno, la interrupción o el cierre, se
decide ahí: de lo contrario las tres rutas se van comportando distinto sin que se note.

---

## Reglas duras

- Todo lo que bloquea —STT, LLM, TTS, ORM— se llama con `asyncio.to_thread` o
  `sync_to_async`. Un solo proceso Daphne comparte los modelos entre llamadas.
- `voz/services.py` carga Whisper y Piper de forma perezosa y los deja en memoria. **Nunca**
  instanciar un modelo dentro de una llamada.
- `voz/audio.py` centraliza mu-law, RMS y remuestreo, y funciona con o sin `audioop`. Usar
  esos helpers, jamás `audioop` directo: en Python 3.13 no existe.
- Un solo proceso: `gunicorn --workers 1` con `uvicorn_worker.UvicornWorker`. Subir los
  workers duplica los modelos en memoria y rompe el estado compartido de las llamadas.

---

## Medio dúplex

El sistema habla o escucha, nunca a la vez. De ahí que la grabación por concatenación
(`voz/grabador.py`) sea fiel al orden real de la conversación: se anota cada tramo con
`anotar()` y se cierra con `guardar()`, que produce un MP3 vía ffmpeg con tope de 30 minutos.

---

## Fin de turno

Se corta por silencio, no por tiempo fijo. Los parámetros que lo gobiernan se ajustan en
caliente desde *Parámetros del sistema*:

- `VOZ_UMBRAL_SILENCIO` — bajo qué RMS se considera silencio
- `VOZ_MS_SILENCIO_FIN_TURNO` — cuánto silencio hace falta para dar el turno por terminado
- `VOZ_MS_ESPERA_DTMF` — cuánto se espera otra tecla antes de cerrar lo marcado

Subirlos corta a la gente que habla pausado; bajarlos deja huecos incómodos. Se calibran
escuchando grabaciones reales, no a ojo.

Con el teclado el criterio es el mismo pero por otro motivo: un menú se resuelve con una tecla
y una cédula son diez seguidas, así que esperar siempre a `#` dejaría el menú sin reaccionar.
Lo que los distingue es el tiempo sin recibir otro dígito.

## Hablar por trozos

`services.trocear_para_habla` parte la respuesta por puntuación y el transporte sintetiza el
trozo siguiente mientras suena el actual. Emitir va al ritmo del reloj —20 ms por trama—, así
que ese tiempo estaba libre. Medido con Piper sobre el saludo del flujo de recepción: 561 ms →
107 ms hasta el primer sonido.

**No sintetizar la respuesta completa antes de emitir.** Es la causa más barata de latencia
percibida, y ya está resuelta en los tres transportes: `_hablar` en `audiosocket.py` y en
`consumers.py`. Si añades un transporte nuevo, usa el mismo helper.

Cuidado con dos cosas al trocear: la marca de fin de respuesta (`fin_respuesta`) se manda una
sola vez, tras el último trozo, y la tarea del trozo que venía sintetizándose se cancela si la
llamada se corta a mitad.

---

## Al cerrar la llamada

`agentes_ia/interna.py` genera el resumen y extrae los datos con el **token global**, no con
la llave del cliente: es una función interna del sistema. Todo es de mejor esfuerzo y va
envuelto — si el resumen falla, la llamada igual queda guardada con su transcripción.

Los prompts prohíben inventar de forma explícita. Es lo que sostiene la promesa del producto:
el asistente responde **solo** con el RAG de ese cliente y, si no está ahí, lo dice.

---

## Cómo se comprueba

No basta con que arranque. Una llamada real deja rastro medible:

```bash
service callcenter restart          # nunca runserver
journalctl -u callcenter -f
```

Y después, en *Llamadas*: duración, `driver`, resultado, latencia media, transcripción,
grabación y resumen. Si el resumen viene en inglés o parece el razonamiento del modelo en vez
de la respuesta, el problema está en el proveedor —ya pasó con Gemini y sus partes
`thought: true`—, no en el orquestador.

Para el demo del navegador: `getUserMedia` **solo existe en contexto seguro**. Sobre
`http://IP:9000` no está definido, y hay que avisarlo en pantalla en lugar de fallar callado.
