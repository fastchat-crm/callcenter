# Motor IVR

Un flujo es un grafo de pasos. Cada paso hace **una sola cosa** y declara a dónde continuar.
Se diseña desde el panel: *Centro de voz e IA → Flujos IVR → Diseñar*.

## Tipos de paso

| Tipo | Qué hace | Campos que usa |
|---|---|---|
| `mensaje` | Dice un texto y sigue de largo | `texto`, `paso_siguiente` |
| `menu` | Ofrece opciones por tecla o por voz | `texto`, opciones, `paso_error` |
| `captura` | Pide un dato y lo valida | `variable`, `validacion`, `modo_captura`, longitudes |
| `agente_ia` | Cede el turno al agente IA | `agente_ia`, `max_turnos_ia`, `paso_siguiente` |
| `transferencia` | Escala a un asesor humano | `asesor` |
| `condicion` | Bifurca según una variable | `expresion`, `paso_siguiente`, `paso_error` |
| `webhook` | Llama a una API externa | `url_webhook`, `metodo_webhook` |
| `colgar` | Cierra la llamada | `texto` |

## Captura de datos

`modo_captura` decide qué se acepta:

- `hibrido` (recomendado): teclado **o** voz. La cédula se puede marcar o decir.
- `dtmf`: solo teclado. Para montos y documentos en líneas ruidosas.
- `voz`: solo voz. Para nombres y direcciones.

Validaciones disponibles: `libre`, `numero`, `cedula_ec` (con dígito verificador),
`documento`, `telefono`, `correo`, `monto`, `fecha`, `si_no`.

El motor convierte números dichos en palabras: *"cero nueve ocho…"* → `098…`. Si el dato no
pasa la validación, repite el paso con el mensaje de error; agotados los reintentos va a
`paso_error` o transfiere.

> **Dictar diez dígitos por voz falla seguido.** En las pruebas reales sobre audio
> telefónico, el reconocimiento perdió un dígito de la cédula en una de cada dos tomas: la
> validación lo detectó y volvió a preguntar, que es lo correcto, pero el cliente lo vive
> como fricción. Para cédulas, montos y números de factura deja `modo_captura` en `hibrido`
> y **redacta el texto invitando a marcar en el teclado** —"puedes marcarlo en el teclado"—:
> el DTMF llega exacto siempre. La voz déjala para nombres, direcciones e intenciones.

Lo capturado queda en `Llamada.datos_capturados` (JSONB) y se puede interpolar en cualquier
texto posterior: `Gracias {nombre}, tu cédula {cedula} está registrada.`

## Menús

Cada opción declara una `tecla` DTMF y/o una lista de `frases`. Se comparan sin distinguir
mayúsculas ni tildes:

| Tecla | Frases | Destino |
|---|---|---|
| `1` | `planes, precios, tarifas, costo` | Captura de cédula |
| `2` | `soporte, ayuda, no funciona, falla` | Transferencia |
| `0` | `asesor, humano, persona` | Transferencia |

El texto que se escucha se arma solo: *"Marca 1 para información de planes. Marca 2 para
soporte técnico…"*.

**Cómo compara el motor.** Antes de buscar coincidencias normaliza: minúsculas, sin tildes y
**sin signos de puntuación**. Esto último no es cosmético: el reconocimiento devuelve `"uno."`
y `"¿planes?"`, y sin limpiar los signos ninguna opción coincidiría nunca. Después compara
la frase literal y, si no aparece, compara raíces palabra por palabra, de modo que la frase
configurada `planes` reconoce *"cuánto cuesta el plan empresarial"*.

**Cuando nada coincide.** Si el flujo tiene un agente IA y `menu_cae_en_agente` está activo
—viene activado—, el motor le pasa la frase al agente en vez de repetir el menú. Es la
diferencia entre un sistema que conversa y uno que insiste. Se desactiva por flujo cuando el
menú debe ser estricto, por ejemplo en un cobro.

## Condiciones

`expresion` acepta `variable operador valor` con `==`, `!=`, `>`, `<`, `>=`, `<=` y
`contiene`:

```
monto > 100
tipo_cliente == empresarial
ciudad contiene quito
```

Verdadero va a `paso_siguiente`, falso a `paso_error`.

## Webhooks

El paso `webhook` envía todas las variables capturadas como JSON. Si la respuesta es un
objeto JSON, sus claves se incorporan a las variables y quedan disponibles para los pasos
siguientes. Útil para consultar el CRM del cliente: envías la cédula y recibes nombre, saldo
y estado, que la IA usa en la misma llamada.

## Reglas globales

Independientes del paso en que esté la llamada:

- Si el cliente dice **asesor, humano, persona, operador, ejecutivo** → transfiere.
- Si dice **adiós, chao, hasta luego, nada más, colgar** → despide y cierra.
- Ante entrada no reconocida → repite hasta `max_reintentos` (2 por defecto) y luego escala.

## Flujo de ejemplo

El seed (`scripts/seed_demo.py`) crea *Recepción principal*:

```
saludo del flujo
   └─ menu_principal
        ├─ 1 / "planes"  → captura_cedula (cédula EC, híbrido)
        │                      ├─ válida  → consulta_ia (hasta 8 turnos) → despedida
        │                      └─ falla   → transferir
        ├─ 2 / "soporte" → transferir
        └─ 0 / "asesor"  → transferir
```

## Simulador

En la pantalla de pasos hay un simulador: escribes las respuestas del cliente separadas por
`|` y ves la conversación completa sin gastar un minuto de teléfono.

```
1|1710034065|cuánto cuesta el plan empresarial
```

Muestra cada respuesta de la IA y las variables capturadas al final. Es la forma rápida de
validar un cambio antes de probarlo por voz.

## Buenas prácticas

1. **Textos cortos.** Dos oraciones como máximo: el cliente no retiene más por teléfono.
2. **Menú de tres opciones.** Con más, la gente marca cualquier cosa.
3. **Siempre un asesor de respaldo.** Sin él, el flujo cuelga en lugar de escalar.
4. **Confirma lo capturado.** Repite la cédula antes de seguir; ahorra reprocesos.
5. **Números en palabras.** El TTS lee mejor "veinticinco dólares" que "$25".
6. **Revisa los motivos de transferencia** cada semana: son el mapa de qué mejorar.
