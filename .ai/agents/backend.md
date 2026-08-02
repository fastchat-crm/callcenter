# Backend — callcenter

Recepción telefónica con IA. Alguien llama, un agente contesta en español, captura sus datos,
responde con la base de conocimiento de **ese cliente** y transfiere a un asesor humano
cuando toca.

Django 4.2 + Channels sobre gunicorn con `UvicornWorker`, PostgreSQL, Redis, Asterisk.

---

## Apps

```
core/          ModeloBase, crud.py (CRUD genérico), funciones.py (addData, paginador,
               secure_module, log), validadores, parametros.py, guias.py, servicios.py
autenticacion/ Usuario del panel, ingreso, registro público, perfil, cambio de clave
clientes/      Cliente, contexto.py (aislamiento), alta.py, puesta en marcha
seguridad/     Modulo (una URL = un permiso, con perfil), ModuloGrupo (secciones del menú),
               GroupModulo (permisos por rol), árbol, auditoría, sincronizacion.py
panel/         Tablero (operador y cliente) y view_doc.py, que sirve docs/*.md en /doc/
telefonia/     Proveedores, troncales SIP, números E.164, asesores, webhooks del carrier
ivr/           Modelos de flujo y motor.py (ejecutor paso a paso)
agentes_ia/    Agentes, llaves, RAG, consultor.py, interna.py, providers/
voz/           services.py (STT/TTS), consumers.py, audiosocket.py, orquestador.py,
               audio.py, grabador.py
llamadas/      Llamadas, turnos, transferencias, contactos, consultas.py (métricas)
```

---

## Antes de tocar nada

1. **Leer el `.md` del módulo** en `docs/`. La regla de sincronía es dura: si cambias algo en
   `voz/`, `ivr/`, `agentes_ia/` o `telefonia/`, actualizas su `.md` **en el mismo cambio**.
   Un `.md` por módulo, nunca uno por archivo.
2. Revisar si ya existe el patrón. `ConfigCrud` + `vista_crud` resuelve el 80 % de las
   pantallas y ya trae el aislamiento por cliente.
3. Si la pantalla es nueva, planificar sus cuatro registros: módulo sincronizado, perfil
   declarado, entrada en `core/guias.py` y sección del menú.

---

## Las reglas que no se negocian

- **Aislamiento por cliente** en las tres capas: consulta (`acotar`), vista (`@solo_operador`)
  y URL (`Modulo.perfil`). Ver `skills/multi-cliente.md`. Es lo que más caro sale romper,
  porque no da error: devuelve datos de otro cliente con toda normalidad.
- **Borrado lógico**: `status = False` y `save(request)`. Nunca `.delete()`.
- **Nada que bloquee en el hilo de eventos**: `asyncio.to_thread` / `sync_to_async`.
- **No modificar migraciones aplicadas** — crear nuevas.
- **No ejecutar** `runserver`; para probar, `bash deploy/reiniciar.sh manual`.
- **No leer ni modificar** `credenciales.json`.
- **No hacer** `git commit` / `push` salvo pedido explícito.
- **No formatear ni lintear** archivos que no se estén tocando.
- Un solo proceso gunicorn: los modelos de voz se comparten entre llamadas.

---

## Comprobar de verdad

Leer el código no demuestra nada. Lo que cuenta:

- Una llamada real y lo que dejó en *Llamadas*: duración, driver, resultado, latencia,
  transcripción, grabación y resumen.
- Una cuenta de cliente creada de verdad, para probar el aislamiento con `puede_entrar()` y
  un `Client()` autenticado.
- `journalctl -u callcenter -f` tras el reinicio: los errores de arranque no salen en pantalla.
- Si tocaste una plantilla, mirar la página renderizada. Editar un `.html` sin reiniciar el
  servicio no cambia nada de lo que ve el usuario, y ya costó una vuelta entera creer que sí.

---

## Documentación

Vive en `docs/` y se sirve en `/doc/`. Cada documento declara para quién es (`TODOS` /
`SOLO_OPERADOR` en `panel/view_doc.py`): la guía de despliegue lleva la IP del servidor y la
comercial los precios de venta, y nada de eso es asunto de un cliente. Filtrar el índice no
basta — el slug directo también se bloquea.
