# CLAUDE.md — callcenter

## Qué es este proyecto

Recepción telefónica con IA. El cliente llama, un agente de IA contesta en español, captura
datos, responde con la base de conocimiento y transfiere a un asesor humano cuando toca.
Django 4.2 + Channels/Daphne + PostgreSQL + Redis. Mismas convenciones que `fastchatdj`, con
el pipeline de voz e IA corriendo sobre servicios gratuitos o auto-hospedados.

## Stack

- Python 3.11/3.12, Django 4.2, Channels 4, Daphne, PostgreSQL 14+, Redis
- Frontend propio: CSS con variables y JS vanilla, sin CDN ni frameworks
- `AUTH_USER_MODEL = "autenticacion.Usuario"`
- Configuración sensible en `credenciales.json` (nunca se versiona)

## Apps

- `core/` — `ModeloBase` (auditoría + borrado lógico), `crud.py` (CRUD genérico), `ajax.py`
  (despachador), `funciones.py` (`addData`, `paginador`, `secure_module`, `log`), validadores,
  menú lateral, bitácora
- `autenticacion/` — usuario del panel, ingreso, perfil, cambio de clave
- `seguridad/` — `Modulo` (una URL = un permiso), `ModuloGrupo` (secciones del menú),
  `GroupModulo` (permisos por rol), CRUD de usuarios y roles, auditoría y
  `sincronizacion.py` (descubre las URLs del proyecto)
- `panel/` — tablero con indicadores y `view_doc.py`, que sirve `docs/*.md` en `/doc/`
- `telefonia/` — proveedores, troncales SIP, números E.164, asesores, webhooks del carrier
- `ivr/` — modelos de flujo y `motor.py` (ejecutor paso a paso)
- `agentes_ia/` — agentes, llaves, RAG local, `consultor.py`, `providers/`
- `voz/` — `services.py` (STT/TTS), `consumers.py` (WebSocket), `orquestador.py`, `audio.py`
- `llamadas/` — llamadas, turnos, transferencias, grabaciones, `consultas.py` (métricas)

## Documentación

Vive en `docs/` y se sirve dentro del panel en `/doc/` (`panel/view_doc.py`). Un `.md` nuevo
en esa carpeta aparece solo en el índice; para ubicarlo en un grupo concreto, agrégalo a
`INDICE` en `panel/view_doc.py`. **Léela antes de tocar el módulo correspondiente:**

- `docs/GUIA_DE_USO.md` — qué hace el sistema y cómo se opera (documento de entrada)
- `docs/SEGURIDAD.md` — módulos, roles, permisos y auditoría
- `docs/ARQUITECTURA.md` — recorrido del audio y decisiones de diseño
- `docs/MOTOR_IVR.md` — tipos de paso, validaciones, reglas globales
- `docs/AGENTES_IA.md` — proveedores, prompts, RAG
- `docs/TELEFONIA_SIP.md` — Asterisk, troncales, carriers, transferencia
- `docs/BASE_DATOS_POSTGRESQL.md` — modelo de datos, consultas, respaldos
- `docs/DESPLIEGUE_IP_PUBLICA.md` — Nginx, systemd, firewall, HTTPS
- `docs/SERVICIOS_GRATUITOS.md` — qué es gratis y hasta dónde alcanza

**Regla de sincronía:** si cambias algo en `voz/`, `ivr/`, `agentes_ia/` o `telefonia/`,
actualiza el `.md` correspondiente en el mismo cambio. Un `.md` por módulo, nunca uno por
archivo.

## Vistas basadas en funciones

Contrato del panel:

```
GET  sin action      → listado paginado
GET  ?action=add     → JsonResponse con el HTML del formulario (modal)
GET  ?action=change  → igual, con instancia cargada
GET  ?action=ver     → plantilla de detalle
POST action=add      → crea
POST action=change   → edita
POST action=delete   → status = False
```

CRUD simple: declarar un `ConfigCrud` y delegar en `core.crud.vista_crud`. Lógica propia:
escribir el despacho a mano siguiendo el mismo patrón (ver `ivr/view_paso.py`).

Un archivo por vista: `view_<entidad>.py`. Las URL de cada app se declaran en una tupla
`<app>_urls` con `nombre`/`url`/`vista`.

## Borrado lógico

Todos los modelos heredan de `ModeloBase`. Eliminar es `filtro.status = False;
filtro.save(request)` — **nunca** `.delete()`. Los listados siempre filtran `Q(status=True)`.
`status` no se muestra como columna ni como campo de formulario.

## Idioma

Todo lo visible para el usuario va en español: títulos, botones, mensajes, encabezados de
columna, textos de error, `JsonResponse({'message': ...})`. Las variables de backend también
son en español (`criterio`, `filtro`, `listado`, `respuesta`). Los términos técnicos
universales no se traducen: webhook, endpoint, API, WebSocket, DTMF, SIP, RAG.

## Plantillas y estáticos

```
templates/
├── base.html                 layout del panel
├── componentes/              formulario, paginación, buscador reutilizables
└── <app>/
    ├── <entidad>_listado.html
    ├── <entidad>_form.html      (normalmente solo incluye componentes/formulario.html)
    └── <entidad>_detalle.html
```

- Rutas absolutas: `/static/…` y `/media/…`. No se usa `{% static %}`.
- Sin `<style>` en las plantillas: el CSS va a `static/css/`.
- Al modificar un `.css` o `.js`, subir el `?v` del `<link>`/`<script>` que lo carga.
- Sin comentarios en HTML, CSS ni JS.
- Las clases del diseño están en `static/css/base.css`: `tarjeta`, `boton`, `campo`,
  `etiqueta`, `tabla`, `rejilla-*`, `indicador`. Reutilizarlas antes de inventar nuevas.

## Archivos subidos

Todo `FileField`/`ImageField` declara `FileExtensionValidator` y un validador de tamaño de
`core/validadores.py` (`validate_file_size_2mb`, `_5mb`, `_20mb`, `_50mb`).

## Motor de voz

- `voz/services.py` carga Whisper y Piper de forma perezosa y los deja en memoria. No
  instanciar modelos en cada llamada.
- `voz/audio.py` centraliza las conversiones (mu-law, RMS, remuestreo) y funciona con o sin
  `audioop`. Usar siempre estos helpers, nunca `audioop` directo.
- Los consumers solo manejan transporte. La lógica de conversación va en
  `voz/orquestador.py`.
- Todo lo que bloquea (STT, LLM, TTS, ORM) se llama con `asyncio.to_thread` o
  `sync_to_async` desde los consumers.

## Reglas duras

- **No modificar migraciones ya aplicadas** — crear nuevas
- **No ejecutar** `runserver`; para probar, `bash deploy/reiniciar.sh manual`
- **No leer ni modificar** `credenciales.json`; `credenciales_template.json` muestra las claves
- **No hacer** `git commit`/`push` salvo pedido explícito
- **No formatear ni lintear** archivos que no se estén tocando
- Un solo proceso Daphne: los modelos de voz se comparten entre llamadas
