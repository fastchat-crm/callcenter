# Convenciones de código — callcenter

Mismo esqueleto que `fastchatdj`. Lo que cambia está marcado: aquí el frontend es propio
(sin jQuery, DataTables ni SweetAlert) y todo modelo cuelga de un cliente.

## Idioma

Todo el código en **español**: modelos, campos, funciones, variables, comentarios y todo
texto visible. **Excepciones:** built-ins de Django, APIs de terceros y archivos de
configuración. Términos técnicos universales no se traducen: webhook, endpoint, API,
WebSocket, DTMF, SIP, RAG, STT, TTS.

Detalle en `docs/GUIA_DE_USO.md` y en el bloque *Idioma* de `CLAUDE.md`.

---

## Naming

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Modelos | PascalCase, singular | `NumeroTelefonico`, `TurnoLlamada` |
| Campos | snake_case descriptivo | `fecha_inicio`, `duracion_segundos` |
| Foreign keys | sustantivo singular | `cliente`, `flujo`, `agente_ia` |
| ManyToMany | sustantivo plural | `modulos`, `colecciones` |
| Booleanos | `activo`, prefijo `es_` / `tiene_` | `activo`, `es_operador` |
| Funciones/métodos | snake_case verbo primero | `registrar_contacto`, `procesar_cierre` |
| Vistas | `<entidad>_view` en `view_<entidad>.py` | `numero_view` en `view_numero.py` |
| Variables de listado | `criterio`, `filtro`, `listado` | herencia de fastchatdj, se respeta |
| Constantes | UPPER_SNAKE_CASE | `PERFIL_MODULO_CHOICES`, `RUTAS_SIEMPRE_PERMITIDAS` |
| URLs | minúsculas con guiones | `/agentes-ia/conocimiento/` |
| Templates | snake_case + sufijo | `numero_listado.html` |

Sufijos de plantilla: `*_listado.html`, `*_form.html`, `*_detalle.html`.

---

## Estructura de vista

1. Decorador `@secure_module` (el login lo resuelve el middleware).
2. `data = {'titulo': ..., 'modulo': ...}`
3. `addData(request, data)`
4. Ramas por `request.method` / `action`
5. Consultas con `select_related` / `prefetch_related`, **siempre pasadas por `acotar()`**
6. `return render(...)`

CRUD simple: declarar un `ConfigCrud` y delegar en `core.crud.vista_crud`, que ya acota al
cliente, filtra `status=True` y bloquea el acceso a ids de otros clientes. Lógica propia:
escribir el despacho a mano siguiendo el mismo patrón (ver `ivr/view_paso.py`).

---

## Estructura de modelo

1. Choices a nivel de módulo
2. Campos simples
3. Relaciones (FK, M2M)
4. `class Meta` con `verbose_name`, `verbose_name_plural`, `ordering`
5. `__str__`
6. Métodos
7. `@property`

**Heredar siempre `ModeloBase`** (`core/custom_models.py`) y filtrar `status=True`.
Todo modelo con datos de negocio lleva `cliente = models.ForeignKey('clientes.Cliente', ...)`.
La excepción se declara explícita con `CLIENTE_COMPARTIBLE = True` y hoy solo la usa
`ApiKeyIA`, porque una llave del operador puede servir a varios clientes.

---

## Estructura de formulario

Heredan de `FormularioBase` (`core/custom_forms.py`), que aplica las clases del diseño,
filtra `status=True` en los querysets de las FK y los acota al cliente activo.
Orden: `Meta` → `__init__` → `clean_<campo>` → `clean()`.

---

## Orden de imports

1. Standard library
2. Django
3. Terceros
4. Apps locales (`core.*`, `clientes.*`, …)
5. Relativos (`.models`, `.forms`)

Los imports que arrastran modelos pesados (voz, IA) van **dentro de la función**, no en el
encabezado: el proceso de Daphne carga una sola vez y el arranque no debe pagar por una
pantalla que quizá nadie abra.

---

## Estructura de archivos por app

```
<app>/
├── models.py
├── view_<entidad>.py      # un archivo por vista
├── forms.py
├── urls.py                # tupla <app>_urls con nombre/url/vista
├── consumers.py           # WebSocket, si aplica
├── services.py            # integraciones externas
└── consultas.py           # agregados para panel y reportes
```

---

## Comentarios

- Docstring en toda función no trivial: qué hace y, si aplica, por qué existe.
- Los comentarios explican **por qué**, nunca qué. Un comentario que repite la línea sobra.
- Nada de `print()`: `logger = logging.getLogger('<app>')`.
- **Sin comentarios en HTML, CSS ni JS.**

---

## CSS y JavaScript

- Todo el CSS va a `static/css/`. **Nunca** `<style>` en una plantilla ni estilos inline.
- Rutas absolutas `/static/…` y `/media/…`; no se usa `{% static %}`.
- Al tocar un `.css` o `.js`, subir el `?v` del `<link>`/`<script>` en `templates/base.html`.
- Reutilizar las clases de `static/css/base.css` —`tarjeta`, `boton`, `campo`, `etiqueta`,
  `tabla`, `rejilla-*`, `indicador`— antes de inventar una nueva.
- JS vanilla, sin CDN ni frameworks. Los helpers viven en `App` (`static/js/app.js`).

---

## Configuración

Secretos en `credenciales.json`, fuera del control de versiones.
`credenciales_template.json` muestra las claves. Nunca hardcodear ni commitear.
Los ajustes que se cambian en caliente van en `core/parametros.py`, no en settings.
