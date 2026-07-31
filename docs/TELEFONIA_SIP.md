# Telefonía: de gratis a número internacional

## Los tres escenarios

| Escenario | Costo | Sirve para |
|---|---|---|
| Softphone + Asterisk local | USD 0 | Desarrollo, QA, demo al cliente |
| Asterisk + troncal SIP con DID | ~USD 5/mes + minutos | Producción con control total |
| Carrier con Media Streams (Twilio, Telnyx…) | ~USD 5/mes + USD 0,02/min | Producción sin administrar Asterisk |

Los tres terminan en el **mismo WebSocket** (`/ws/voz/stream/`): lo único que cambia es
quién le entrega el audio.

## 1. Gratis: Asterisk local + softphone

```bash
sudo apt install -y asterisk
```

`/etc/asterisk/pjsip.conf` — una extensión para el softphone:

```ini
[transport-udp]
type = transport
protocol = udp
bind = 0.0.0.0:5060

[1001]
type = endpoint
context = desde-interno
disallow = all
allow = alaw,ulaw
auth = 1001-auth
aors = 1001

[1001-auth]
type = auth
auth_type = userpass
username = 1001
password = una-clave-larga

[1001]
type = aor
max_contacts = 2
```

`/etc/asterisk/extensions.conf` — marcar `*100` entrega la llamada al bot:

```ini
[desde-interno]
exten => *100,1,Answer()
 same => n,Stasis(callcenter-ia)
 same => n,Hangup()

[desde-troncal]
exten => _X.,1,Answer()
 same => n,Stasis(callcenter-ia)
 same => n,Hangup()
```

```bash
sudo systemctl restart asterisk
sudo asterisk -rx "pjsip show endpoints"
```

Configura Linphone o Zoiper con usuario `1001`, la clave y la IP del servidor, marca `*100`
y estarás hablando con el mismo motor que atenderá las llamadas reales.

Firewall: `5060/udp` para SIP y `10000-20000/udp` para RTP.

## El puente con Asterisk

Conviene entender esto antes de instalar nada, porque es la parte que más confusión genera.

**Asterisk no puede conectarse a `/ws/voz/stream/`.** Ese endpoint habla el protocolo de
Media Streams de Twilio: JSON sobre WebSocket con el audio en mu-law codificado en base64.
Asterisk no lo habla y no hay forma de que lo hable. Lo que sí trae de fábrica es la
aplicación `AudioSocket()` del dialplan, que abre un **TCP plano** y manda audio crudo con un
encabezado de tres bytes.

Por eso existe `voz/audiosocket.py`: un servidor que habla ese protocolo y entrega la
conversación al mismo `OrquestadorLlamada` que usan los carriers. Hay dos transportes, una
sola lógica de conversación.

```
Twilio / Telnyx  →  WebSocket /ws/voz/stream/   ┐
                                                 ├→  OrquestadorLlamada
Asterisk         →  TCP AudioSocket :8090       ┘
```

Queda un problema: **AudioSocket solo transporta un UUID**, nunca dice desde qué número
llamaron ni a cuál. Sin eso no se sabe de qué cliente es la llamada ni qué flujo la atiende.
La solución es que el dialplan avise antes por HTTP:

```
1. Entra la llamada          →  Asterisk contesta y genera un UUID
2. CURL a /telefonia/webhook/asterisk/  (uuid, from, to)
   → el panel crea la Llamada, ya con su cliente y su flujo
   → responde {"error": false}; si el número no existe o no tiene flujo,
     responde 409 y el dialplan cuelga con un mensaje en vez de dejar la
     llamada muda
3. AudioSocket(${CALLUUID},127.0.0.1:8090)
   → el servidor busca la llamada por ese UUID y empieza a conversar
```

### Instalación

```bash
sudo bash deploy/instalar_asterisk.sh
```

Antes de correrlo, **carga la troncal en el panel** (*Centro de telefonía → Proveedores →
Troncales*): de ahí sale la configuración. El script instala Asterisk, genera `pjsip.conf` y
`extensions.conf` desde la base, levanta el servicio del puente y abre los puertos.

La configuración no se escribe a mano. Se regenera cuando cambies algo en el panel:

```bash
./venv/bin/python manage.py generar_config_asterisk            # muestra qué haría
./venv/bin/python manage.py generar_config_asterisk --escribir # instala
sudo asterisk -rx "pjsip reload"
sudo asterisk -rx "dialplan reload"
```

Los archivos originales se respaldan una vez como `.antes-callcenter`.

### Los dos servicios

| Servicio | Qué hace | Reinicio |
|---|---|---|
| `callcenter` | Panel, webhooks y WebSocket de los carriers | `service callcenter restart` |
| `callcenter-audiosocket` | Recibe el audio de Asterisk | `service callcenter-audiosocket restart` |
| `asterisk` | Habla SIP con el proveedor | `service asterisk restart` |

El puente corre **en su propio proceso**, no dentro de gunicorn: una llamada ocupa su hilo
durante toda la conversación y no debe competir con las peticiones del panel. Escucha solo en
`127.0.0.1:8090`, porque Asterisk está en el mismo servidor; exponerlo dejaría el audio de las
llamadas abierto a internet sin autenticación.

### Saber si está arriba y cuánto se usa

```bash
./venv/bin/python manage.py estado_telefonia
./venv/bin/python manage.py estado_telefonia --cliente "Ferretería Andina"
```

Responde tres cosas: si Asterisk corre, si las troncales siguen **registradas** con el
proveedor —una troncal que se cae deja de recibir llamadas sin avisar— y cuánto se viene
usando (llamadas y minutos de hoy y del período, cuántas hay en curso, y qué porcentaje del
plan contratado va consumido).

Lo mismo, en JSON, para monitoreo externo o un cron:

```bash
curl -s http://127.0.0.1:9000/health/?telefonia=1
```

La telefonía **no** entra en el `ok` del health check: el panel funciona perfectamente sin
Asterisk, y un balanceador no debería sacar el servidor de rotación porque una troncal se
cayó. Por eso va detrás de `?telefonia=1`.

En el panel, la tarjeta *Estado del motor de voz* muestra Asterisk (con sus canales activos)
y el puente. Si el puente aparece **Apagado**, Asterisk no tiene a dónde entregar el audio y
las llamadas entran mudas.

### Cuando algo no suena

| Síntoma | Dónde mirar |
|---|---|
| La llamada entra pero cuelga enseguida | `journalctl -u asterisk -f` — el dialplan fue a `sinpanel`: el número no está cargado o su flujo está inactivo |
| Entra y queda muda | ¿El puente escucha? `manage.py estado_telefonia`. Si no, `service callcenter-audiosocket restart` |
| El proveedor no manda llamadas | `asterisk -rx "pjsip show registrations"` — si no dice `Registered`, revisa usuario y clave de la troncal |
| Se oye entrecortado | Falta `10000-20000/udp` abierto, o el códec no coincide con el del proveedor |

## 2. Producción con troncal SIP propia

Compra un DID a un proveedor mayorista (DIDWW, VoIP.ms, Voxbeam, Zadarma) y regístralo en
Asterisk:

```ini
[troncal-ec]
type = registration
transport = transport-udp
outbound_auth = troncal-ec-auth
server_uri = sip:sip.proveedor.com
client_uri = sip:USUARIO@sip.proveedor.com
```

En el panel: *Centro de telefonía → Proveedores* (driver `asterisk` o `sip_generico`) → *Troncales* →
*Números*. El número entrante se enruta al contexto `desde-troncal`, que lo entrega al bot.

Ventaja: control total, minutos al costo mayorista, el audio nunca sale de tu servidor.
Costo: administrar Asterisk.

## 3. Producción con carrier de Media Streams

El camino más rápido. Todos hablan el mismo protocolo, así que el sistema los soporta sin
cambios de código.

**Configuración en el carrier:**

- Voice webhook (POST): `https://tu-dominio/telefonia/webhook/entrante/`
- Status callback (POST): `https://tu-dominio/telefonia/webhook/estado/`

El sistema responde con el XML que conecta el stream:

```xml
<Response>
    <Connect>
        <Stream url="wss://tu-dominio/ws/voz/stream/">
            <Parameter name="from" value="+593987654321" />
            <Parameter name="to" value="+59323456789" />
        </Stream>
    </Connect>
</Response>
```

**Requiere HTTPS con certificado válido** (`wss://`), es decir: un dominio. Ver
[`DESPLIEGUE_IP_PUBLICA.md`](DESPLIEGUE_IP_PUBLICA.md), sección 6.

Referencias: [Twilio](https://www.twilio.com/voice/pricing) ·
[Telnyx](https://telnyx.com/pricing/call-control) · [Plivo](https://www.plivo.com/pricing/) ·
[SignalWire](https://signalwire.com/pricing)

## Números internacionales

El sistema no distingue países: solo E.164 e ISO. Para operar en varios:

1. Compra el DID en el país (Telnyx y Twilio cubren 100+).
2. *Centro de telefonía → Números* → alta con `pais_iso`, `prefijo_pais`, `idioma` y `zona_horaria`.
3. Asigna el flujo IVR que corresponda a ese mercado.

El idioma del número define el modelo STT y la voz TTS. Con flujos separados por país puedes
tener saludo distinto, horario distinto y asesores distintos sin duplicar nada más.

Precios referenciales de DID mensual: Ecuador ~USD 5 · EE. UU. ~USD 1,15 ·
España ~USD 3 · México ~USD 6 · Colombia ~USD 8. Los minutos entrantes van de USD 0,004
(EE. UU.) a USD 0,03 (móviles de LatAm).

## Transferencia a un asesor humano

Cuando el motor decide escalar, el consumer envía al carrier:

```json
{"event": "transfer", "streamSid": "...", "transfer": {"to": "+593987654321"}}
```

- **Con carrier comercial**: se traduce a un `<Dial>` mediante la API de call control.
- **Con Asterisk**: la aplicación ARI hace `channels/{id}/redirect` a la extensión del asesor.

En ambos casos queda registrado en `llamadas_transferenciallamada` con su motivo, que es lo
que después permite afinar el flujo: si el 40 % de las transferencias son
`reintentos_agotados`, el problema es el STT o el texto del paso, no el agente.

## Diagnóstico

| Síntoma | Dónde mirar |
|---|---|
| La llamada entra pero no hay audio | ¿El carrier llegó al WebSocket? `journalctl -u callcenter -f` debe mostrar `media stream conectado` |
| Se escucha entrecortado | Falta `proxy_buffering off` en Nginx, o el servidor está saturado |
| La llamada se corta al minuto | `proxy_read_timeout` bajo en Nginx |
| El carrier no conecta | `VOZ_PUBLIC_HOST` mal configurado, o `wss://` sin certificado válido |
| Audio en un solo sentido | Puertos RTP cerrados en el firewall (Asterisk) |
