# Callcenter IA

Sistema de recepción telefónica con inteligencia artificial. El cliente llama a un número,
un agente de IA contesta en español, entiende la intención, captura datos (cédula, nombre,
monto), responde consultas desde la base de conocimiento del cliente y transfiere a un asesor
humano cuando corresponde.

Construido con la misma arquitectura que `fastchatdj`: **Django 4.2 + Channels/Daphne +
PostgreSQL + Redis**, vistas basadas en funciones, borrado lógico y modelos con auditoría.
La diferencia es que todo el pipeline de voz e IA corre con **servicios gratuitos o
auto-hospedados**, así que se puede levantar y probar sin pagar un solo dólar.

---

## Qué incluye

| Módulo | Qué resuelve |
|---|---|
| `telefonia/` | Proveedores, troncales SIP, números E.164 multipaís, asesores humanos, webhooks del carrier |
| `ivr/` | Motor de flujos conversacionales paso a paso: mensaje, menú DTMF+voz, captura validada, agente IA, condición, webhook, transferencia |
| `agentes_ia/` | Agentes, llaves de proveedor, base de conocimiento RAG (índice local o Weaviate), tablero de consumo y costos |
| `voz/` | Pipeline STT → LLM → TTS, consumers de Media Streams y demo por navegador |
| `llamadas/` | Registro de llamadas, turnos, transcripción, grabaciones, transferencias y métricas |
| `panel/` | Tablero con indicadores de operación y estado del motor |
| `core/` | Modelo base, CRUD genérico, bitácora, validadores, despachador AJAX |
| `autenticacion/` | Usuario del panel (`AUTH_USER_MODEL`), ingreso y perfil |
| `seguridad/` | Módulos (una URL = un permiso), roles, secciones del menú, usuarios y auditoría |

## Internacional desde el día uno

Un número se describe por su **E.164** (`+593…`, `+1…`, `+34…`) y su **ISO de país**. El
`driver` del proveedor decide cómo se contesta la llamada. Agregar un país nuevo es crear
un registro en *Telefonía → Números*: no se toca código. Cada número lleva su idioma
(define el modelo STT y la voz TTS) y su zona horaria.

## Arranque rápido

```bash
cd /home/callcenter
bash deploy/instalar.sh          # Ubuntu/Debian limpio: instala todo y deja el panel arriba
```

O paso a paso: [`docs/INSTALACION.md`](docs/INSTALACION.md).

Después ingresa con `admin` / `admin1234` (superusuario) y cambia la contraseña antes de
exponer el sistema a clientes.

**En este servidor está publicado en el puerto 9000**, porque el 80 y el 443 ya los usan
otros sitios: <http://145.223.79.221:9000/login/>

## Documentación dentro del panel

El menú lateral tiene la sección **Ayuda → Documentación**: toda la carpeta `docs/` se
renderiza dentro del propio sistema en `/doc/`. La puerta de entrada es la
[guía de uso](docs/GUIA_DE_USO.md) (`/doc/guia-de-uso/`), que explica qué hace el sistema y
cómo operarlo día a día.

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/GUIA_DE_USO.md`](docs/GUIA_DE_USO.md) | Qué hace el sistema y cómo operarlo día a día |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Cómo viaja el audio, qué hace cada capa, decisiones de diseño |
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Instalación paso a paso y verificación |
| [`docs/BASE_DATOS_POSTGRESQL.md`](docs/BASE_DATOS_POSTGRESQL.md) | PostgreSQL: creación, tuning, respaldos, modelo de datos |
| [`docs/DESPLIEGUE_IP_PUBLICA.md`](docs/DESPLIEGUE_IP_PUBLICA.md) | Salir por la IP pública: Nginx, systemd, firewall, HTTPS |
| [`docs/SERVICIOS_GRATUITOS.md`](docs/SERVICIOS_GRATUITOS.md) | Qué usar sin pagar y sus límites reales |
| [`docs/TELEFONIA_SIP.md`](docs/TELEFONIA_SIP.md) | Asterisk auto-hospedado, troncales y carriers comerciales |
| [`docs/MOTOR_IVR.md`](docs/MOTOR_IVR.md) | Cómo diseñar un flujo y cómo lo ejecuta el motor |
| [`docs/AGENTES_IA.md`](docs/AGENTES_IA.md) | Proveedores, prompts, RAG y afinado del agente |
| [`docs/PROPUESTA_COMERCIAL.md`](docs/PROPUESTA_COMERCIAL.md) | Propuesta comercial lista para presentar al cliente |
| [`CLAUDE.md`](CLAUDE.md) | Convenciones del proyecto para quien programe encima |

## Probar sin teléfono

*Configuración de voz → Demo de voz*: habla por el micrófono del navegador contra el mismo
motor que atiende las llamadas reales. Sirve para validar flujo, agente y latencia antes de
contratar un número.

## Requisitos mínimos del servidor

- Ubuntu 22.04+ / Debian 12+, 4 GB de RAM (8 GB si corres Ollama local), 2 vCPU
- PostgreSQL 14+, Redis 6+, Nginx
- Python 3.11 o 3.12
