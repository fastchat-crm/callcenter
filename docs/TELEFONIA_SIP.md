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

El puente entre Asterisk y el WebSocket se hace con **ARI + externalMedia** o con el módulo
**audiosocket**; ambos entregan audio crudo que el `MediaStreamConsumer` ya sabe leer. En el
panel se registra como proveedor con driver `asterisk`.

Firewall: `5060/udp` para SIP y `10000-20000/udp` para RTP.

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
