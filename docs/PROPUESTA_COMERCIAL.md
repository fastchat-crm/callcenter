# Propuesta comercial — Sistema de voz con IA para callcenter inbound

**Inversión de desarrollo: USD 5.000 + mensualidad operativa**
Escalable a números internacionales y agentes de IA conectados al CRM.

---

## 1. Resumen ejecutivo

Sistema de recepción telefónica con inteligencia artificial. El cliente final llama a un
número, un agente de IA contesta en español, recolecta datos (cédula, nombre, intención),
responde consultas sobre planes y servicios desde la base de conocimiento del cliente, y
deriva a un asesor humano cuando corresponde.

Arranca con un número de Ecuador (+593) y está construido para crecer a **números
internacionales sin reescribir nada**: cada número se describe por su E.164 y su país, y el
mismo motor atiende Ecuador, Estados Unidos, España, México o Colombia cambiando un registro
en el panel.

Capacidad incluida: 10 llamadas/día × 10-15 min ≈ **3.000 min/mes**.

---

## 2. Alcance del desarrollo (USD 5.000)

| Entregable | Descripción |
|---|---|
| Setup de carrier + número EC | Compra del DID, configuración de troncal SIP/TeXML, webhook |
| Motor IVR conversacional | Modelos de flujo y paso, administración desde el panel, ejecutor paso a paso |
| Integración Media Streams | Audio en tiempo real por WebSocket, listo para producción |
| Captura DTMF + voz | Híbrido teclado y reconocimiento natural (cédula, monto, opciones) |
| Conexión con agentes de IA | Respuestas sobre planes y FAQ desde la base de conocimiento vectorial |
| Transferencia a asesor humano | Reenvío a celular o cola con softphone |
| Grabación + transcripción | Almacenamiento y tablero de llamadas con búsqueda por texto |
| 1 flujo IVR completo | Saludo → menú → captura → agente IA → transferencia |
| Panel de operación | Indicadores, monitor en vivo, historial y motivos de escalamiento |
| Arquitectura multipaís | Alta de números internacionales por configuración, sin desarrollo |
| Pruebas con llamadas reales | QA de ida y vuelta: latencia, audio, casos borde |
| Capacitación | 2 sesiones de administración + manual operativo |
| Soporte post-lanzamiento | 30 días incluidos |

**Cronograma:** 6-8 semanas
**Pagos:** 40 % anticipo · 30 % demo funcional · 30 % entrega

---

## 3. Tecnologías

**Capa telefónica.** Proveedor SIP con números (DID) y soporte de Media Streams —
transmisión de audio en tiempo real por WebSocket. Telnyx, Twilio, Plivo o SignalWire son
intercambiables; también se soporta **Asterisk auto-hospedado**, que elimina el costo por
minuto a cambio de administrar el servidor.

**STT — reconocimiento de voz.** Convierte el audio del cliente a texto en tiempo real.
Whisper local (gratuito, corre en el servidor) o Deepgram en la nube (menor latencia).

**LLM — el cerebro.** Entiende la intención y genera la respuesta. Gemini Flash, Groq o
GPT-4o-mini, conectados a una base de conocimiento vectorial construida con los documentos
del cliente (tarifarios, FAQ, políticas).

**TTS — la voz.** Convierte la respuesta a audio. Piper local (gratuito, voz clara),
edge-tts (gratuito, voz neuronal) o ElevenLabs (indistinguible de humano).

**Servidor.** Django + Channels + Daphne sobre PostgreSQL y Redis, tras Nginx con TLS.

**Almacenamiento.** PostgreSQL para llamadas, transcripciones y métricas; disco local o
almacenamiento compatible con S3 para las grabaciones.

---

## 4. Comparativa de niveles

| Característica | GRATUITA | ESTÁNDAR (recomendada) | PREMIUM |
|---|---|---|---|
| Telefonía | Asterisk propio | Carrier con Media Streams | Carrier con Media Streams |
| STT | Whisper local | Deepgram Nova-2 | Deepgram Nova-2 |
| LLM | Gemini Flash / Ollama local | Gemini Flash / GPT-4o-mini | GPT-4o |
| TTS | Piper local | ElevenLabs Flash | ElevenLabs Pro |
| Latencia por turno | 2,5 - 4 s | 0,6 - 1,2 s | 0,4 - 0,9 s |
| Calidad de voz | Clara, sintética | Natural | Indistinguible de humano |
| Precisión en español | 85 - 90 % | 94 - 97 % | 94 - 97 % |
| Interrupción de la IA | No | Sí | Sí |
| Llamadas simultáneas | 2 - 4 | 20 - 40 | 20 - 40 |
| Datos salen del país | No | Sí | Sí |
| Costo de proveedor/mes (3.000 min) | USD 0 - 12 | USD 110 | USD 185 |
| Precio sugerido al cliente | USD 250 - 300 | USD 400 - 500 | USD 650 - 850 |
| Margen neto mensual | USD 240 - 290 | USD 290 - 390 | USD 465 - 665 |

### Qué habilita cada nivel

**GRATUITA — recepcionista básica.** Citas simples, recordatorios, mensajes informativos.
Ventaja real: los datos no salen del servidor, lo que resuelve el requisito de normativa
local en salud, legal y sector público. Limitación: el cliente percibe pausas y la voz es
claramente sintética. Sin DID público solo atiende extensiones internas.

**ESTÁNDAR — asistente conversacional profesional.** Conversación fluida con interrupción,
califica leads, responde preguntas complejas sobre planes. Escala a 10-30 clientes finales
sin tocar la arquitectura. Riesgo único: dependencia de servicios en la nube, mitigable con
respaldo local automático.

**PREMIUM — indistinguible de humano.** Voz clonada y razonamiento avanzado. Nicho: banca,
clínicas premium, cuentas en Estados Unidos o Europa. Rentable solo si el cliente final paga
más de USD 800/mes.

---

## 5. Costo operativo mensual

Escenario: 1 cliente, 10 llamadas/día × 12,5 min ≈ 3.000 min/mes.

### Nivel estándar (recomendado)

| Servicio | Tarifa | Mes |
|---|---|---|
| DID Ecuador | fijo | USD 5 |
| Minutos entrantes EC | USD 0,020/min | USD 60 |
| STT en la nube | USD 0,0043/min | USD 13 |
| TTS neuronal | ~USD 0,015/min de IA | USD 27 |
| LLM | ~USD 0,001/turno | USD 3 |
| Almacenamiento de grabaciones (~9 GB) | USD 0,023/GB | USD 1 |
| Servidor | ya existente | USD 0 |
| **Total proveedor** | | **USD ~109** |

**Cobro al cliente: USD 450/mes** → margen neto ~USD 340/mes recurrente por cliente.

### Nivel gratuito

| Servicio | Mes |
|---|---|
| STT, LLM, TTS y RAG locales | USD 0 |
| Almacenamiento local | USD 0 |
| VPS (4 GB, 2 vCPU) | USD 6 - 12 |
| DID (opcional, solo si se necesita número público) | USD 5 + minutos |
| **Total proveedor** | **USD 6 - 12** (sin DID) |

Sirve para demostrar el sistema completo al cliente antes de comprometer costos.

---

## 6. Mensualidad al cliente

| Plan | Mensualidad | Incluye |
|---|---|---|
| Recepcionista (nivel estándar) | USD 450/mes | 1 número, 3.500 min, 1 flujo, soporte 48 h |
| Flujo adicional | +USD 80/mes | Flujo IVR extra |
| Voz premium | +USD 120/mes | Voz neuronal de gama alta |
| Integración con CRM externo | +USD 150/mes | API contra el sistema del cliente |
| **Número internacional adicional** | **+USD 90/mes** | DID en otro país, idioma y flujo propios |
| Exceso de minutos | USD 0,18/min | Sobre el límite incluido |

- Contrato mínimo: 6 meses, para amortizar el setup.
- Incremento anual: 8 % indexado a inflación y mejoras del servicio.

---

## 7. Expansión internacional (fase 2)

La arquitectura ya contempla operación multipaís. Agregar un mercado nuevo es:

1. Comprar el DID en el país (Telnyx y Twilio cubren más de 100).
2. Registrarlo en el panel con su país, idioma y zona horaria.
3. Asignarle un flujo IVR propio.

Sin desarrollo adicional. El idioma del número define automáticamente el modelo de
reconocimiento y la voz.

Precios referenciales de DID mensual: Estados Unidos ~USD 1,15 · España ~USD 3 ·
Ecuador ~USD 5 · México ~USD 6 · Colombia ~USD 8.

Cotización de puesta en marcha por país adicional: **USD 400** (alta, pruebas y flujo
localizado), más la mensualidad del cuadro anterior.

---

## 8. Garantías y soporte

- Disponibilidad objetivo: 99 % mensual (excluye caídas del carrier o de la nube).
- Respuesta de soporte: 24 h hábiles por correo; 4 h en incidentes críticos.
- Respaldo automático diario de transcripciones y configuración.
- Soporte post-lanzamiento: 30 días incluidos en el setup.
- Capacitación: 2 sesiones en línea y manual escrito.

---

## 9. Fuera de alcance (cotización aparte)

- Llamadas salientes automáticas (marcador predictivo)
- Integración con sistemas heredados del cliente (ERP, otros CRM)
- Flujos IVR adicionales más allá del primero incluido
- Voces clonadas a medida
- Reportes de inteligencia de negocio avanzados
- Cumplimiento HIPAA / PCI (requiere infraestructura separada)
