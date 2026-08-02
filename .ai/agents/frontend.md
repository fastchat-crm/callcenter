# Frontend — callcenter

Frontend propio: CSS con variables y JS vanilla. **Sin CDN, sin frameworks, sin jQuery, sin
Bootstrap, sin DataTables, sin SweetAlert.** Es la diferencia grande con fastchatdj, y la
razón por la que sus skills de frontend no se copian tal cual.

---

## Estructura

```
templates/
├── base.html                 layout del panel: sidebar, barra superior, modal, avisos
├── componentes/              formulario, paginación y buscador reutilizables
└── <app>/
    ├── <entidad>_listado.html
    ├── <entidad>_form.html      normalmente solo incluye componentes/formulario.html
    └── <entidad>_detalle.html

static/css/base.css           todo el diseño
static/js/app.js              el objeto App
```

---

## Reglas

- Rutas absolutas `/static/…` y `/media/…`. No se usa `{% static %}`.
- **Nunca** `<style>` en una plantilla ni estilos inline: el CSS va a `static/css/`.
- Al tocar un `.css` o `.js`, subir el `?v` del `<link>`/`<script>` en `base.html`. Sin eso
  el navegador sirve la versión vieja y parece que el cambio no funcionó.
- **Sin comentarios en HTML, CSS ni JS.**
- Todo texto visible en español, incluidos los estados vacíos y los mensajes de error.

---

## Clases del diseño

Reutilizar antes de inventar: `tarjeta`, `tarjeta-encabezado`, `tarjeta-titulo`,
`tarjeta-nota`, `tarjeta-cuerpo`, `boton` (`boton-primario`, `boton-sm`, `boton-peligro`),
`campo` (`campo-sm`, `campo-select`), `etiqueta` (`etiqueta-exito`), `tabla`,
`tabla-envoltura`, `rejilla-*`, `indicador`, `fila-flex`, `vacio`, `celda-mono`,
`celda-acciones`, `texto-tenue`, `texto-pequeno`.

Los colores salen de variables (`--primario`, `--borde`, `--fondo-elevado`,
`--fondo-hundido`, `--texto-suave`, `--texto-tenue`, `--radio-sm`). No hardcodear un hex.

---

## El objeto `App`

`static/js/app.js` engancha los botones por `data-accion`; las plantillas no llevan `onclick`.

```html
<button class="boton boton-primario" data-accion="add" data-titulo="Nuevo número">Nuevo número</button>
<button class="boton boton-sm" data-accion="change" data-id="{{ filtro.id }}" data-titulo="Editar">Editar</button>
<button class="boton boton-sm boton-peligro" data-accion="delete" data-id="{{ filtro.id }}"
        data-mensaje="¿Eliminar el número {{ filtro.numero }}?">Eliminar</button>
```

Helpers: `App.aviso(texto, tipo)` con tipo ∈ `exito` | `error` | `alerta`, y `App.token()`
para el CSRF. El contrato completo está en `skills/forms-ajax.md`.

---

## Estados vacíos

Una tabla sin filas nunca se deja en blanco: dice qué falta y cuál es el siguiente paso.

```html
<tr><td colspan="7" class="vacio">
    <strong>Sin módulos registrados</strong>
    Usa «Sincronizar con las URLs» para darlos de alta automáticamente.
</td></tr>
```

Es la misma idea del tablero del cliente: sin números no se muestra un panel en ceros, se
muestra qué hacer y en qué orden.

---

## Guías de pantalla

El recuadro explicativo de cada pantalla no se escribe en la plantilla: sale de
`core/guias.py`, que es también la fuente de `Modulo.descripcion`. Una sola fuente para que
el módulo, el menú y la pantalla digan lo mismo.

---

## Comprobar

Editar un `.html` no cambia nada hasta reiniciar el servicio. El ciclo real es:

```bash
service callcenter restart
```

y después mirar la página renderizada —no el código—. Ya pasó una vez: el sidebar viejo
seguía saliendo porque el servicio no se había reiniciado.
