# Cómo poner a funcionar tu contestador

Esta guía es para ti, que vas a operar tu propio contestador. No hace falta saber de
telefonía ni de programación: cada paso dice qué hacer, dónde hacerlo y cómo comprobar que
quedó bien.

El orden importa. Cada paso se apoya en el anterior, y la pantalla
*Centro de operación → Puesta en marcha* te va marcando cuáles ya están resueltos.

---

## 1. Enséñale de qué habla tu negocio

*Centro de voz e IA → Base de conocimiento*

Tu asistente responde **solo con lo que le des**. Si no le cargas nada, va a decir «no tengo
esa información» a casi todo, que es lo correcto pero no sirve de mucho.

1. **Nueva colección** — ponle un nombre, por ejemplo «Precios y servicios».
2. **Documento** — sube tu tarifario, tus preguntas frecuentes, tus horarios. Acepta PDF,
   Word, texto plano o que pegues el texto directamente.
3. **Indexar** — este paso es obligatorio. Sin él, el asistente no ve el documento.

> Cada vez que agregues o quites un documento, hay que volver a indexar.

**Cómo comprobar que quedó bien:** entra a la colección y usa el buscador. Escribe una
pregunta como la haría un cliente tuyo —«¿cuánto cuesta el envío?»— y mira qué fragmentos
aparecen. Si el fragmento correcto no sale ahí, el asistente tampoco lo va a encontrar: el
problema está en el documento, no en la IA.

**Consejo:** un documento bien redactado vale más que diez mal escritos. Si tus precios están
en una tabla escaneada como imagen, el sistema no puede leerla — pásalos a texto.

---

## 2. Ajusta cómo habla tu asistente

*Centro de voz e IA → Agentes IA*

Ya tienes un asistente creado. Lo que conviene revisar:

- **Instrucciones del sistema** — quién es, para qué empresa trabaja y qué **no** debe hacer.
  Sé concreto: «no des plazos de entrega, ofrece pasar con un asesor» es mejor que «sé
  prudente».
- **Base de conocimiento** — asegúrate de que apunte a la colección del paso anterior.
- **Máximo de oraciones** — déjalo en **2**. Por teléfono, más que eso cansa y la gente
  interrumpe.

**Botón Probar:** hazle una pregunta real y mira la respuesta y cuánto tardó. Es la forma
rápida de saber si está listo, sin gastar una llamada.

---

## 3. Escúchalo antes de que lo escuche un cliente

*Centro de voz e IA → Demo de voz*

Habla con tu asistente desde el navegador, con tu micrófono. Es el mismo motor que va a
atender las llamadas reales, así que lo que oigas aquí es lo que van a oír tus clientes.

A la derecha ves la **transcripción en vivo**: lo que el sistema entendió de lo que dijiste y
lo que respondió. Si entiende mal tu voz, ahí lo notas.

> El navegador solo entrega el micrófono en conexiones seguras. Si el botón no funciona,
> revisa que la dirección empiece por `https://`.

---

## 4. Prepara a quién pasarle las llamadas difíciles

*Centro de telefonía → Asesores humanos*

Cuando el asistente no puede resolver algo, o el cliente pide hablar con una persona, la
llamada se transfiere. Si no hay nadie cargado, **la llamada se cierra en vez de escalar**,
que es la peor experiencia posible.

Carga al menos una persona con su celular en formato internacional (`+593987654321`).

---

## 5. Consigue tu número de teléfono

Este es el **único paso que cuesta dinero** y el que no puedes resolver dentro del panel:
hay que contratarlo con una empresa de telefonía.

### Dónde comprarlo

| Opción | Costo aproximado | Trámite | Cuándo conviene |
|---|---|---|---|
| **Telnyx** (recomendado) | USD 1–2/mes + minutos | Ninguno para número de EE.UU. | Empezar hoy mismo |
| **Twilio** | USD 1–2/mes + minutos | Igual, algo más caro por minuto | Si ya lo usas para otra cosa |
| **Número de Ecuador** | ~USD 5/mes + minutos | Carta de intención y comprobante de domicilio · ~72 h | Que te llamen a un número local |

- Telnyx: <https://telnyx.com>
- Twilio: <https://twilio.com>

**Recomendación:** empieza con un número de **Estados Unidos**. Sale hoy mismo, cuesta un
dólar y te deja probar todo con llamadas reales. En paralelo arranca el trámite del
ecuatoriano, que es lo que tarda.

### Qué configurar en la empresa de telefonía

En su panel vas a encontrar una sección de *Voice* o *Webhooks*. Ahí pega:

```
Llamada entrante:  https://TU-DOMINIO/telefonia/webhook/entrante/
Estado de llamada: https://TU-DOMINIO/telefonia/webhook/estado/
```

Tu dirección exacta es la misma que usas para entrar al panel. Si no estás seguro,
pregúntale a quien te dio el acceso.

---

## 6. Carga el número en el panel

*Centro de telefonía → Números telefónicos → Nuevo número*

- **Número** — en formato internacional, con el `+` y el código de país: `+593987654321`.
- **Proveedor** — el que contrataste.
- **Flujo** — «Recepción», el que ya viene creado.
- **Agente IA** — déjalo vacío. Solo se llena si quieres que ese número suene distinto al
  resto.

Desde este momento, quien marque ese número habla con tu asistente.

---

## 7. Mira lo que pasa

Cuando entren llamadas:

- **Centro de operación → Monitor en vivo** — las llamadas que están sonando ahora mismo,
  con la conversación turno por turno. Sirve para ver el sistema trabajando.
- **Centro de operación → Llamadas** — el archivo completo. Cada una trae su **grabación
  para escuchar**, la transcripción, un **resumen escrito por la IA** y los datos que la
  persona dio.
- **Centro de operación → Contactos** — quiénes te han llamado, cuántas veces y para qué. Se
  arma solo: no tienes que cargar nada.
- **Panel** — cuántas llamadas, cuántos minutos, cuántas resolvió la IA sola y cuántas
  pasaron a un asesor.

**El reporte más útil es Transferencias.** Dice por qué la IA no pudo resolver:

| Si el motivo se repite | Qué significa | Qué hacer |
|---|---|---|
| El cliente pidió un asesor | Normal, hasta cierto punto | Si pasa de la mitad, la IA no está resolviendo |
| No se entendió al cliente | Falla el reconocimiento o el texto del paso | Reescribe el paso con palabras más simples |
| Consulta fuera de alcance | Falta información en tu base de conocimiento | Sube el documento que falta y vuelve a indexar |

---

## Cuando algo no funciona

| Lo que ves | Qué suele ser |
|---|---|
| El asistente dice «no tengo esa información» a todo | La colección no está indexada, o el agente no la tiene asignada |
| Contesta cosas que no son de tu negocio | Las instrucciones del sistema están muy sueltas; sé más específico |
| La llamada entra pero nadie habla | Avisa a quien administra el servicio: es un problema del servidor |
| El demo de voz no toma el micrófono | La dirección no empieza por `https://`, o el navegador bloqueó el permiso |
| Suena muy lento entre pregunta y respuesta | Normal en la primera llamada del día; si sigue, avísalo |

Lo que no puedas resolver desde estas pantallas, es del operador del sistema, no tuyo.
