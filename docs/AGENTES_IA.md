# Agentes IA

El agente es el cerebro de la conversación: entiende la intención, responde con la base de
conocimiento del cliente y decide cuándo ya no puede ayudar.

## Configurar uno

1. **Llaves de IA** → nueva llave. Con Ollama local deja la clave vacía.
2. **Base de conocimiento** → nueva colección → sube el tarifario o las FAQ → *Indexar*.
3. **Agentes IA** → nuevo agente: llave + colección + instrucciones.
4. Botón **Probar**: pregunta algo y verifica la respuesta y la latencia.
5. Asigna el agente al flujo IVR (o a un paso `agente_ia` específico).

## Proveedores

| Proveedor | Gratuito | Modelo sugerido | Notas |
|---|---|---|---|
| Google Gemini | Sí, cuota diaria | `gemini-2.5-flash` | Rápido, buen español. También genera los embeddings del RAG |
| Groq | Sí, cuota generosa | `llama-3.3-70b-versatile` | El más rápido del mercado |
| OpenRouter | Modelos `:free` | `…:free` | Catálogo amplio, cuota variable |
| Ollama local | Sin límite | `qwen2.5:7b-instruct` | Cero costo, los datos no salen del servidor |
| Ollama Cloud | No | `gemma4:31b` | Modelos abiertos servidos en la nube, API compatible con OpenAI |
| Compatible OpenAI | No | `gpt-4o-mini` | Cualquier endpoint compatible |

Agregar uno nuevo: crear la clase en `agentes_ia/providers/`, registrarla en `_PROVIDERS` y
sumar su id a `PROVEEDOR_CHOICES` del modelo. Nada más del sistema cambia.

### Traer las llaves de fastchatdj

Las llaves ya configuradas en el otro proyecto se importan en dos pasos, sin leer su archivo
de credenciales:

```bash
# 1) volcado, con el entorno de fastchat
/home/fastchat/fastchatdj/venv/bin/python /home/fastchat/fastchatdj/manage.py shell \
    < /home/callcenter/scripts/exportar_apikeys_fastchat.py

# 2) importación, con este entorno
cd /home/callcenter
./venv/bin/python manage.py shell < scripts/importar_apikeys_fastchat.py

rm -f /tmp/apikeys_fastchat.json      # el volcado lleva las claves en texto plano
```

El importador mapea proveedores (Gemini → Gemini, OLLAMA → Ollama Cloud, DeepSeek y OpenAI →
compatible con OpenAI) y es idempotente: si el alias ya existe, actualiza en vez de duplicar.
Los proveedores todavía no soportados aquí se informan y se omiten.

Después de importar, **prueba cada llave** con el botón *Probar* del listado: el catálogo de
modelos cambia con el tiempo y una llave puede traer un modelo que ya no existe.

## Parámetros del agente

| Campo | Qué controla | Valor recomendado (teléfono) |
|---|---|---|
| `prompt_sistema` | Personalidad e instrucciones | Ver plantilla abajo |
| `tono` | Cordial, formal, comercial o técnico | Según el cliente |
| `temperatura` | Creatividad | 0,2-0,4 |
| `max_tokens_respuesta` | Tope duro de la respuesta | 200-250 |
| `maximo_oraciones` | Recorte para voz | 2 |
| `usar_rag` | Consultar la base de conocimiento | Sí |
| `fragmentos_contexto` | Cuántos fragmentos se inyectan | 3-5 |

`maximo_oraciones` es el parámetro que más se nota: una respuesta de cinco oraciones por
teléfono se siente eterna.

## Plantilla de prompt

```
Eres el asistente telefónico de <EMPRESA>. Atiendes en español neutro.

Reglas:
- Máximo dos oraciones por respuesta. Nada de listas ni enlaces.
- Si el dato no está en la información entregada, di que no lo tienes y ofrece
  transferir con un asesor. Nunca inventes precios, plazos ni condiciones.
- Los números dilos en palabras: "veinticinco dólares", no "$25".
- Si el cliente se muestra molesto o pide una persona, ofrece transferir de inmediato.
- No pidas datos que ya te dieron en esta llamada.
```

El sistema agrega automáticamente el tono, el idioma, los datos ya capturados y el contexto
recuperado del RAG.

## Base de conocimiento (RAG)

Formatos soportados: PDF, DOCX, TXT, MD, CSV, HTML. También se puede **pegar texto directo**
en el campo *Texto* del documento, que es la vía más rápida para cargar un tarifario o unas
preguntas frecuentes sin armar un archivo.

Al indexar, cada documento se corta en fragmentos de ~900 caracteres con 150 de solape, se
convierte a vectores y se guarda. En cada turno se buscan los fragmentos más parecidos a la
pregunta y se inyectan en el prompt.

### Dónde vive el índice

Cada colección elige su backend:

| Backend | Dónde guarda | Cuándo conviene |
|---|---|---|
| `local` | `.npz` de numpy en `media/vectorstore/<slug>/` | Un solo servidor, pocos miles de fragmentos, sin servicios extra |
| `weaviate` | Colección multi-tenant `ConocimientoCallcenter`, un tenant por colección | Varios clientes, volumen alto, o si ya corre Weaviate en el servidor |

El backend de Weaviate se habla por REST (`agentes_ia/rag/weaviate_rag.py`), sin el SDK, y
reutiliza la instancia que ya existe en el servidor. La configuración se lee de variables de
entorno o de `/home/weaviate/.env`:

```
WEAVIATE_HOST=127.0.0.1
WEAVIATE_HTTP_PORT=8080
WEAVIATE_API_KEY=...
```

El aislamiento entre clientes es por tenant: la colección 1 vive en `coleccion_1` y no puede
leer los datos de `coleccion_2`, aunque compartan la misma colección de Weaviate.

### Cómo se generan los vectores

| Motor | Costo | Dimensiones | Requisitos |
|---|---|---|---|
| `gemini` | Capa gratuita de AI Studio | 768 (recortadas de 3072 y normalizadas) | Una llave de Gemini activa |
| `local` | Cero | 384 | `pip install -r requirements.txt` (descarga PyTorch) |

Con motor `gemini` hay que elegir en la colección **qué llave** genera los embeddings; el
modelo es `gemini-embedding-001`. Los dos motores producen vectores de distinto tamaño, así
que **cambiar de motor obliga a reindexar** la colección completa.

La primera indexación con motor local descarga el modelo (~120 MB); con Gemini es inmediata.

**Hay que reindexar cada vez que se agrega o elimina un documento.** El botón *Indexar* está
en el listado de colecciones.

En la pantalla de detalle hay un probador de búsqueda semántica: escribes una pregunta y ves
qué fragmentos recuperaría el agente. Es la forma de diagnosticar respuestas malas — si el
fragmento correcto no aparece ahí, el problema es el documento, no el modelo.

### Qué cargar

Sí: tarifario con precios y condiciones, FAQ reales de los clientes, horarios, cobertura,
requisitos de contratación, políticas de garantía.

No: documentos de cientos de páginas sin estructura, contratos completos, material interno
que el agente no debe mencionar por teléfono.

## Afinar cuando responde mal

| Síntoma | Causa habitual | Qué hacer |
|---|---|---|
| Inventa precios | Sin RAG o fragmento no recuperado | Cargar el tarifario y reindexar; probar la búsqueda semántica |
| Respuestas largas | `maximo_oraciones` alto | Bajarlo a 2 y recortar `max_tokens_respuesta` |
| Suena robótico | Prompt sin tono | Definir `tono` y dar ejemplos en `prompt_sistema` |
| Tarda mucho | Modelo grande o proveedor lento | Groq, o un modelo más chico en Ollama |
| No transfiere nunca | Falta la instrucción | Agregar la regla de escalamiento al prompt |
| Lee mal los números | El LLM devuelve cifras | Pedir explícitamente números en palabras |

## Consumo y costos

*Centro de voz e IA → Consumo de IA* es el tablero: tokens, latencia y costo estimado por
rango de fechas, con desglose por modelo y por agente, la serie diaria y el detalle turno por
turno.

Cada turno deja un registro en `ConsumoIA` con:

| Campo | Para qué sirve |
|---|---|
| `tokens_entrada` / `tokens_salida` | Lo que reporta el proveedor |
| `costo_usd` | Estimado con el tarifario de `agentes_ia/consumo.py` |
| `latencia_ms` | Cuánto tardó ese turno |
| `uso_rag` | Si la respuesta se apoyó en la base de conocimiento |
| `error` | Mensaje del proveedor cuando falló; el turno se registra igual |
| `apikey` / `proveedor` / `llamada` | Para atribuir el gasto |

Los turnos fallidos **también se registran**: sin eso, un proveedor caído se ve como "sin
consumo" en vez de como un problema. El filtro *Solo con error* del tablero los aísla.

### Tarifario

`PRECIO_USD_POR_1K_TOKENS` en `agentes_ia/consumo.py` tiene los precios públicos por cada
1.000 tokens. Reglas:

- Proveedores auto-hospedados o en capa gratuita (`ollama_local`, `groq`, `openrouter`) → 0.
- Modelos abiertos servidos en la nube (Gemma, Qwen, Llama, Kimi…) → estimado de mercado,
  porque no publican tarifa por token. Sirve para comparar agentes, no para pagar.
- Modelo desconocido → precio conservador, para no subestimar el gasto.

Es un **estimado para el tablero**: el cobro real lo hace el proveedor. Cuando cambie un
precio, se actualiza esa tabla y los registros nuevos ya salen con el valor correcto (los
históricos conservan el costo con el que se calcularon).

Una llamada de 10 minutos con 12 turnos consume alrededor de 6.000 tokens de entrada y 1.200
de salida. Para verlo por llamada: `agentes_ia.consumo.costo_por_llamada(llamada)`.

Consulta directa, si hace falta salir del panel:

```sql
SELECT a.nombre,
       count(*) AS turnos,
       sum(c.tokens_entrada) AS entrada,
       sum(c.tokens_salida) AS salida,
       round(sum(c.costo_usd), 4) AS costo_usd,
       round(avg(c.latencia_ms)) AS ms_promedio
FROM agentes_ia_consumoia c
JOIN agentes_ia_agenteia a ON a.id = c.agente_id
WHERE c.fecha > now() - interval '30 days'
GROUP BY 1 ORDER BY 5 DESC;
```

### Diagnóstico rápido

`GET /agentes-ia/estado/` devuelve en JSON si Weaviate responde, qué colecciones están
indexadas y con qué backend, y el estado de cada llave. Es el primer lugar para mirar cuando
un agente deja de contestar bien.

## Llaves por cliente

Una llave de IA puede ser de dos maneras, según el campo **Cliente** de su formulario:

| Campo Cliente | Qué significa |
|---|---|
| Vacío | Llave por defecto del operador: la pueden usar los agentes de cualquier cliente. |
| Con un cliente | Exclusiva de ese cliente; los agentes de los demás no la ven ni la pueden elegir. |

Es la única excepción a la regla de que todo pertenece a un cliente
(`CLIENTE_COMPARTIBLE = True` en el modelo). Sirve para arrancar con una sola llave del
operador y, cuando un cliente trae la suya, asignársela sin tocar al resto.

No confundirla con el **token global de IA** de *Configuración general*: ese no atiende
llamadas, lo usan las funciones internas del sistema.

## IA interna: resumen y detección de datos

Además del agente que atiende la llamada, el sistema usa la IA para su propio trabajo. Eso
corre con el **token global** de *Configuración general*, nunca con la llave del cliente: así
el consumo del cliente no se gasta en tareas que pidió el operador, y el resumen sale aunque
el cliente todavía no tenga llave propia.

Vive en `agentes_ia/interna.py` y se dispara desde `OrquestadorLlamada.cerrar()`, **después**
de que la llamada ya quedó guardada:

| Función | Qué escribe |
|---|---|
| `resumir_llamada()` | `Llamada.resumen`, tres oraciones sobre qué necesitaba y cómo terminó |
| `extraer_datos_llamada()` | Claves `ia_nombre`, `ia_ciudad`, `ia_correo`, `ia_identificacion`, `ia_motivo` dentro de `datos_capturados` |
| `pais_por_numero()` | `Llamada.pais_iso`, deducido del prefijo marcado |

Tres decisiones que conviene no deshacer:

- **Todo es de mejor esfuerzo.** Si no hay token, si el proveedor falla o si devuelve algo
  ilegible, se registra el aviso y la llamada queda igual de completa. `procesar_cierre()`
  nunca propaga una excepción al cierre.
- **El prompt prohíbe deducir.** Un dato que no se dijo en voz alta se guarda como vacío, no
  como suposición. Es la misma regla que se le pide al agente: no alucinar.
- **Lo que capturó el flujo manda.** Los datos deducidos entran con `setdefault` y con el
  prefijo `ia_`, así que nunca pisan lo que un paso de captura preguntó explícitamente, y en
  el detalle de la llamada se distinguen con la etiqueta *IA*.

El país se deduce siempre, con o sin token: sale del prefijo telefónico y no cuesta nada.

### Cuidado con los modelos que razonan

Los modelos de razonamiento (Gemini 2.5, Gemma con *thinking*) devuelven su borrador en
partes marcadas `thought: true` **antes** de la respuesta. Dos consecuencias que ya se
tropezaron una vez:

- Si se concatenan todas las partes, lo que se le habla al cliente es el razonamiento del
  modelo, no su respuesta. `GeminiProvider` descarta las partes `thought`.
- El razonamiento consume `maxOutputTokens`. Con un presupuesto corto —y en telefonía siempre
  lo es— el modelo se queda sin tokens antes de contestar y devuelve nada. Por eso el
  proveedor manda `thinkingConfig.thinkingBudget = 0`: esto es voz, cada segundo y cada token
  cuentan. Si un modelo no acepta el campo, se reintenta sin él.

Cuando el modelo agota el presupuesto pensando, el proveedor devuelve un error explícito
(«agotó los N tokens antes de responder») en vez de un texto vacío, para que se vea en el log
qué pasó.

Medido contra la API real con el mismo prompt y 220 tokens:

| Modelo | Tokens de razonamiento | Resultado |
|---|---|---|
| `gemini-2.5-flash` | 0 | Responde bien |
| `gemini-2.5-flash-lite` | 0 | Responde bien |
| `gemma-4-31b-it` | 217 | Ignora `thinkingBudget` y se queda sin tokens |

Para el token global conviene `gemini-2.5-flash`, que es el que sale por defecto si se deja
el modelo vacío.
