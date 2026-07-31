# Guía de uso

## Qué hace este proyecto

**Callcenter IA contesta el teléfono por vos.**

Una persona llama al número de la empresa. En lugar de sonar hasta que alguien atienda, un
agente de inteligencia artificial responde al primer timbre, en español, y sostiene una
conversación real:

1. **Saluda y ofrece el menú.** El cliente puede marcar una tecla o simplemente decir lo que
   necesita: *"quiero saber los precios"*.
2. **Captura datos.** Pide la cédula, el nombre o un monto. Acepta el teclado o la voz, y
   valida lo que recibe: una cédula ecuatoriana con dígito verificador mal calculado se
   rechaza y se vuelve a pedir.
3. **Responde consultas.** Con los documentos que la empresa cargó —tarifario, preguntas
   frecuentes, horarios, políticas— el agente contesta sobre planes, precios y requisitos.
   No inventa: si el dato no está, lo dice y ofrece transferir.
4. **Transfiere a una persona.** Cuando la consulta lo supera, o cuando el cliente lo pide,
   la llamada pasa a un asesor humano con el contexto ya recogido.
5. **Deja registro.** Cada llamada queda con su transcripción completa, los datos capturados,
   el tiempo que duró, la latencia de cada respuesta y el motivo por el que escaló.

Todo el procesamiento —reconocer la voz, pensar la respuesta, hablarla— puede correr en el
propio servidor con herramientas gratuitas, o apoyarse en servicios de pago cuando se
necesita más velocidad y una voz más natural. Se cambia de uno a otro sin rehacer nada.

### Para qué sirve en la práctica

- Recepción que nunca pone en espera ni deja llamadas sin contestar.
- Filtrado de llamadas: la IA resuelve lo repetitivo y solo escala lo que vale el tiempo de
  un asesor.
- Captura de leads fuera del horario de oficina.
- Registro auditable de todo lo que se dijo en cada llamada.

### Para qué **no** sirve todavía

- No hace llamadas salientes (marcador predictivo).
- No se le puede interrumpir a mitad de una frase en el nivel gratuito.
- No reemplaza a un asesor en negociaciones ni en reclamos complejos.

---

## La guía que trae cada pantalla

Todas las ventanas de configuración y de operación abren con un recuadro azul que explica qué
hace esa pantalla y en qué punto de la llamada entra. Trae tres cosas:

- **El centro al que pertenece** — *Centro de telefonía*, *Centro de voz e IA*, *Centro de
  operación* o *Centro de seguridad*. Es la agrupación temática del sistema.
- **Su lugar en el recorrido** — las ocho pantallas que forman la cadena de una llamada están
  numeradas, con enlaces a la anterior y a la siguiente. El recorrido es:

  1. Proveedores y troncales SIP → 2. Números telefónicos → 3. Flujos IVR → 4. Pasos del flujo
  → 5. Agentes IA → 6. Base de conocimiento → 7. Asesores humanos → 8. Llamadas

  Las demás pantallas (llaves de IA, consumo, demo de voz, monitor, transferencias y todo
  *Seguridad*) son de apoyo y no llevan número.
- **Un enlace al documento** de `/doc/` que profundiza en esa parte.

El recuadro se pliega con un clic en su cabecera y el sistema recuerda la elección por
pantalla, así que una vez que conoces el módulo deja de estorbar.

Los mismos cuatro centros son las secciones del menú lateral, para que el sitio donde entras
y el recuadro que lo explica hablen del mismo lugar. En el menú cada centro se abre y se
cierra con un clic —el del módulo en el que estás se abre solo— y el botón de la barra
superior reduce toda la barra a una columna de iconos, útil cuando la pantalla es angosta o
cuando el listado es ancho. Las dos elecciones se recuerdan.

Los textos viven en `core/guias.py`; para cambiar uno, o para dar de alta la guía de una
pantalla nueva, basta con editar ese diccionario: se resuelven por la ruta y ninguna vista
necesita tocarse.

## Primeros pasos

### 1. Ingresar

Abre `http://<IP-DEL-SERVIDOR>:<PUERTO>/login/` con el usuario y la contraseña que te
entregaron. Cambia la contraseña de inmediato desde *Mi perfil → Cambiar contraseña*.

### 2. Poner la identidad del operador

*Centro de seguridad → Configuración general*

El nombre de tu empresa, el logo y los datos de contacto: la marca del sistema, la que se ve
en la pantalla de ingreso. El logo acepta PNG, JPG, WEBP o SVG de hasta 2 MB.

Aquí también va el **token global de IA**, el del operador, con su proveedor y su modelo. No
es la llave de ningún cliente: lo usan las funciones internas del sistema. Hoy hace dos cosas,
las dos al cerrar cada llamada:

- **Resume la llamada** en tres oraciones, usando solo lo que se dijo.
- **Detecta los datos de quien llamó** —nombre, ciudad, correo, identificación, motivo— y los
  guarda junto a los datos capturados, marcados con la etiqueta *IA*. Si algo no se dijo en
  voz alta, queda vacío: el prompt prohíbe deducir o completar.

Sin token, esas dos funciones quedan apagadas y todo lo demás sigue igual. El **país** sí se
deduce siempre, del prefijo del número que marcó, porque no cuesta nada.

### 3. Dar de alta el cliente

*Centro de seguridad → Clientes*

**El sistema trabaja por cliente.** Cada cliente es dueño de sus números, sus flujos, sus
agentes, su base de conocimiento y sus asesores: lo que se configura dentro de uno no existe
para los demás, ni aparece en sus listados ni se puede abrir escribiendo su dirección a mano.

Un cliente puede tener **N números**, todos apuntando al flujo que le corresponda.

Cómo se decide qué ves al entrar al panel:

| Usuario | Qué ve |
|---|---|
| Con un cliente asignado | Solo ese cliente. No puede cambiarlo ni sabe que hay otros. |
| Sin cliente (del operador) | Todos. Elige con cuál trabajar en el selector de la barra superior. |

El cliente asignado se pone en *Centro de seguridad → Usuarios*, en el campo **Cliente**.
Dejarlo vacío convierte al usuario en operador.

Con el cliente elegido, su nombre y su logo pasan a encabezar el menú lateral, así siempre
sabes dentro de cuál estás parado.

Los **minutos incluidos al mes** son la referencia del plan contratado de ese cliente: sirven
para comparar contra su consumo real.

### 4. Seguir la puesta en marcha

*Centro de operación → Puesta en marcha*

Es la lista de control del cliente activo: los ocho eslabones del recorrido, cuáles ya están
resueltos y qué falta exactamente en los que no, con el enlace a la pantalla donde se
arregla. No guarda nada —se calcula al vuelo sobre los datos reales—, así que nunca queda
desfasada respecto de lo que ves en cada módulo.

Sirve de mapa para el resto de esta guía: los pasos que siguen son esos mismos eslabones.

### 5. Revisar el estado del motor

El **Panel** muestra arriba a la derecha qué componentes están listos: reconocimiento de voz,
síntesis de voz y agentes de IA. Si alguno aparece en rojo, la llamada no va a funcionar
completa. Debajo dice exactamente qué falta.

### 6. Cargar el conocimiento de la empresa

*Centro de voz e IA → Base de conocimiento*

1. **Nueva colección** — por ejemplo "Planes y servicios".
2. **Documento** — sube el tarifario en PDF, las preguntas frecuentes en Word, o pega el
   texto directamente.
3. **Indexar** — este paso es obligatorio. Sin él, el agente no ve el documento.

> Hay que volver a indexar cada vez que agregues o elimines un documento.

Para comprobar que quedó bien, entra a la colección y usa el buscador: escribe una pregunta
como haría un cliente y mira qué fragmentos aparecen. Si el fragmento correcto no aparece
ahí, el agente tampoco lo va a encontrar — el problema está en el documento, no en la IA.

### 7. Crear el agente

*Centro de voz e IA → Agentes IA → Nuevo agente*

- **Llave de IA**: la que corresponda (ver *Llaves de IA*).
- **Base de conocimiento**: la colección del paso anterior.
- **Instrucciones del sistema**: quién es, para qué empresa trabaja y qué no debe hacer.
- **Máximo de oraciones**: déjalo en **2**. Por teléfono, más que eso cansa.

Botón **Probar**: hazle una pregunta real y mira la respuesta, la latencia y el modelo que
respondió. Es la forma rápida de saber si el agente está listo.

### 8. Diseñar el flujo

*Centro de voz e IA → Flujos IVR → Diseñar*

Un flujo es la ruta que sigue la llamada. El sistema trae uno de ejemplo:

```
saludo
  └─ menú principal
       ├─ 1 o "planes"  → captura de cédula → agente IA → despedida
       ├─ 2 o "soporte" → transferir a asesor
       └─ 0 o "asesor"  → transferir a asesor
```

Cada paso hace una sola cosa: hablar, ofrecer opciones, capturar un dato, conversar con la
IA, transferir o colgar. Detalle completo en la documentación del **Motor IVR**.

### 9. Probar sin gastar un minuto de teléfono

Dos formas:

- **Simulador** (dentro de la pantalla de pasos): escribes las respuestas del cliente
  separadas por `|` y ves la conversación completa en texto. Ideal para validar un cambio en
  segundos.
- **Demo de voz** (*Centro de voz e IA → Demo de voz*): hablas por el micrófono del
  navegador contra el mismo motor que atiende las llamadas reales. Es la prueba de verdad:
  micrófono → reconocimiento → agente → voz.

### 10. Conectar el número

*Centro de telefonía → Números → Nuevo número*

Se registra en formato internacional (`+593987654321`), con su país, idioma y el flujo que lo
atiende. En la parte superior de esa pantalla está la **URL de webhook** que hay que pegar en
el panel del proveedor telefónico.

---

## Operación día a día

### Monitor en vivo

*Centro de operación → Monitor en vivo* muestra las llamadas en curso y se refresca cada 4 segundos:
de dónde llaman, en qué paso del flujo van y cuál fue el último turno de la conversación.
Sirve para ver el sistema trabajando y detectar si alguna llamada se quedó trabada.

### Historial

*Centro de operación → Llamadas* es el archivo completo. Se puede filtrar por fecha, estado, resultado
o buscar una palabra dentro de las transcripciones —útil cuando el cliente reclama algo que
"le dijeron por teléfono".

Al abrir una llamada se ve la conversación turno por turno con la hora, el paso en que
estaba, las teclas que marcó y cuántos milisegundos tardó cada respuesta. Al costado, los
datos capturados y las transferencias.

### Transferencias

*Centro de operación → Transferencias* lista cada escalamiento con su motivo. **Es el reporte más útil
del sistema**, porque dice qué mejorar:

| Motivo predominante | Qué significa | Qué hacer |
|---|---|---|
| El cliente pidió un asesor | Normal, hasta cierto punto | Si supera el 40 %, la IA no está resolviendo |
| No se entendió al cliente | Falla el reconocimiento o el texto del paso | Reescribir el paso, o subir el nivel de STT |
| Consulta fuera de alcance | Falta información en la base de conocimiento | Cargar el documento que falta y reindexar |
| Error técnico | Algo se cayó | Revisar los logs del servidor |

### Indicadores del panel

- **Llamadas** y **minutos consumidos** de los últimos 30 días — sirve para facturar.
- **Resueltas por la IA**: el porcentaje que no necesitó a nadie. Es la métrica del negocio.
- **Latencia media por turno**: cuánto tarda la IA en responder. Sobre 3 segundos, el cliente
  lo nota.

---

## Cuando algo sale mal

| Lo que pasa | Causa más común | Solución |
|---|---|---|
| La llamada entra pero nadie habla | Falta el modelo de voz | Panel → tarjeta de estado del motor; instalar lo que falte |
| El agente inventa precios | El documento no está indexado | Base de conocimiento → Indexar |
| Responde muy largo | Máximo de oraciones alto | Bajarlo a 2 en el agente |
| No entiende la cédula | Línea ruidosa | Cambiar el paso a modo "solo teclado" |
| Nunca transfiere | Falta asesor de respaldo en el flujo | Asignar uno en la configuración del flujo |
| Tarda mucho en responder | Modelo pesado o proveedor lento | Cambiar de proveedor de IA en la llave |

Si nada de esto aplica, el detalle técnico está en la documentación de **Arquitectura**,
**Motor IVR** y **Agentes IA**, en este mismo menú.

---

## Reglas que el sistema aplica siempre

Sin importar en qué paso esté la llamada:

- Si el cliente dice **asesor, humano, persona, operador** → transfiere.
- Si dice **adiós, chao, hasta luego, nada más** → se despide y cuelga.
- Si no se entiende lo que dijo → repite el paso hasta dos veces y luego escala.

Nada de esto hay que configurarlo: viene de fábrica para que ninguna llamada quede atrapada
en un menú.
