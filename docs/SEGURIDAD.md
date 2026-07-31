# Seguridad: usuarios, roles y módulos

El control de acceso sigue el mismo esquema que `seguridad` en fastchatdj. Tres piezas:

| Pieza | Qué es | Dónde se administra |
|---|---|---|
| **Módulo** | Una URL del sistema. Es la unidad de permiso | *Seguridad → Módulos del sistema* |
| **Sección del menú** | Agrupación visual que arma la barra lateral | *Seguridad → Secciones del menú* |
| **Rol** | Un grupo de Django con la lista de módulos que puede abrir | *Seguridad → Roles de usuario* |

Un usuario entra a una ruta si es **superusuario**, o si alguno de sus roles tiene un módulo
cuya `url` es prefijo de esa ruta. Por eso un módulo `/llamadas/` habilita todo lo que
cuelgue de ahí, y `/llamadas/listado/` habilita solo esa pantalla.

## Puesta en marcha

```bash
./venv/bin/python manage.py shell < scripts/seed_seguridad.py
```

Descubre las URLs reales del proyecto, crea los módulos, arma las cinco secciones del menú y
deja cuatro roles listos:

| Rol | Alcance |
|---|---|
| Administrador | Todo el sistema |
| Supervisor | Opera y configura flujos, agentes y telefonía |
| Asesor | Atiende llamadas y consulta el historial |
| Auditor | Solo lectura de llamadas, consumo y auditoría |

## Módulos

*Seguridad → Módulos del sistema* lista cada URL protegida. El botón **Sincronizar con las
URLs** recorre el resolver de Django y da de alta las rutas nuevas.

La sincronización **solo agrega**: nunca borra ni pisa lo que se editó a mano, así que se
puede correr después de cada despliegue sin miedo. Quedan fuera las rutas de infraestructura
—`/admin/`, `/static/`, `/media/`, `/ajaxrequest/`, `/health/`, webhooks— y las que llevan
parámetros, que no son entradas de menú.

Campos que importan:

- **URL** — se normaliza siempre con barra inicial y final.
- **Orden** — posición dentro de su sección del menú.
- **Mostrar en el menú** — desmarcado, el módulo sigue protegido pero no aparece en la barra
  lateral. Útil para pantallas de detalle o acciones que se abren desde otra vista.

## El menú se arma solo

`core/menu.py` construye la barra lateral desde `ModuloGrupo` y `Modulo`, filtrada por los
permisos del usuario. Mientras no exista ninguna sección en la base —instalación recién
hecha— usa el menú estático del código, para que el sistema sea navegable desde el primer
minuto.

Consecuencia práctica: **agregar una pantalla al menú no requiere tocar código**. Se
sincronizan los módulos, se arrastra el nuevo a una sección y aparece para quien tenga
permiso.

## Roles y permisos

*Seguridad → Roles de usuario → Permisos* muestra los módulos agrupados por sección, con
casillas. Marcar todo / desmarcar todo para empezar rápido.

- Un rol sin módulos no puede entrar a nada: el usuario ve el panel vacío.
- Los superusuarios ignoran los roles por completo.
- Un rol con usuarios asignados no se puede eliminar hasta reasignarlos.

## Usuarios

*Seguridad → Usuarios* reemplaza al admin de Django para el trabajo diario:

- **Nuevo usuario** con roles, perfil y contraseña inicial.
- **Activar / desactivar** sin borrar nada — el histórico de llamadas conserva la referencia.
- **Resetear clave** genera una contraseña temporal y marca al usuario para que la cambie en
  su próximo ingreso.

Casillas que se confunden seguido:

| Casilla | Qué hace |
|---|---|
| Activo | Puede iniciar sesión |
| Accede al panel | Requisito para entrar a cualquier módulo; déjala marcada |
| Superusuario | Ignora todos los permisos. Úsala con dos o tres personas, no más |

## Auditoría

*Seguridad → Auditoría* lista cada alta, edición, eliminación e ingreso, con usuario, ruta e
IP. Se llena sola: las vistas llaman a `core.funciones.log`, y `secure_module` valida el
permiso antes de dejar pasar.

Filtros por usuario, acción y rango de fechas. Es lo primero que se mira cuando alguien
pregunta "¿quién cambió esto?".

## Cuando alguien no puede entrar

1. ¿El usuario está **activo** y con **accede al panel** marcado?
2. ¿Tiene algún rol asignado? Sin rol y sin ser superusuario, no entra a nada.
3. ¿El rol tiene marcado ese módulo? Revisa la pantalla de permisos.
4. ¿El módulo existe? Si es una pantalla nueva, corre **Sincronizar con las URLs**.

Si al sistema le faltan todos los módulos, `puede_entrar` deja pasar a cualquiera con acceso
al panel: es a propósito, para que una instalación a medias no deje al administrador fuera
de su propio sistema.
