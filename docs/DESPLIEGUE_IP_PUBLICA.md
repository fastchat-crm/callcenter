# Despliegue: salir por la IP pública del servidor

Objetivo: que el panel y —sobre todo— el WebSocket de audio sean alcanzables desde
internet, para que el carrier pueda conectarse y para que el demo funcione desde
cualquier navegador.

Ejemplo de este servidor: **145.223.79.221**.

## 0. Elegir el puerto

Si el servidor ya aloja otros sitios, los puertos 80 y 443 están tomados. Antes de decidir:

```bash
ss -tlnp | grep -E ':(80|443|8000|8001|8080|9000) '
ls -l /etc/nginx/sites-enabled/
ufw status
```

**En este servidor** el 80 y el 443 los usa Nginx con `fastchatdj` y `chatpdf`, el 8001 lo
tiene Gunicorn y el 8080 un contenedor Docker. Por eso el callcenter se publica en el
**puerto 9000**, con Daphne escuchando en `127.0.0.1:8501`:

```
navegador → 145.223.79.221:9000 (Nginx) → 127.0.0.1:8501 (Daphne)
```

Al cambiar de puerto hay que actualizar tres lugares y mantenerlos iguales:

| Dónde | Qué poner |
|---|---|
| `deploy/callcenter.nginx.conf` | `listen 9000;` |
| `credenciales.json` → `VOZ_PUBLIC_HOST` | `145.223.79.221:9000` |
| `credenciales.json` → `CSRF_TRUSTED_ORIGINS` | `http://145.223.79.221:9000` |

Y abrir el puerto: `sudo ufw allow 9000/tcp`.

Si el puerto queda fuera de `CSRF_TRUSTED_ORIGINS`, el panel carga pero el formulario de
ingreso rechaza el envío.

## 1. Confirmar la IP pública

```bash
curl -s ifconfig.me; echo
hostname -I
```

Si `hostname -I` muestra una IP privada (`10.x`, `172.16-31.x`, `192.168.x`) y `ifconfig.me`
otra distinta, estás detrás de NAT: hay que redirigir los puertos 80 y 443 hacia esta
máquina en el router o en el panel del proveedor de nube.

Ponla en `credenciales.json`:

```json
{
  "IP_PUBLICA": "145.223.79.221",
  "DOMINIO_GENERAL": "145.223.79.221:9000",
  "ALLOWED_HOSTS": ["145.223.79.221", "127.0.0.1", "localhost"],
  "CSRF_TRUSTED_ORIGINS": ["http://145.223.79.221:9000"],
  "USE_SSL": false,
  "VOZ_PUBLIC_HOST": "145.223.79.221:9000"
}
```

`ALLOWED_HOSTS` va **sin puerto** (Django lo compara contra el host); `VOZ_PUBLIC_HOST` y
`CSRF_TRUSTED_ORIGINS` van **con puerto**, porque forman URL completas.

`VOZ_PUBLIC_HOST` es la pieza crítica: es el host que se escribe dentro del XML que recibe
el carrier (`<Stream url="ws://145.223.79.221/ws/voz/stream/">`). Si queda vacío o apunta a
`localhost`, el carrier no puede conectarse y la llamada se queda muda.

## 2. Daphne detrás de Nginx

Daphne escucha solo en `127.0.0.1:8001`; Nginx publica los puertos 80/443. Nunca expongas
Daphne directo a internet.

```bash
sudo mkdir -p /var/log/callcenter
sudo cp deploy/callcenter-daphne.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now callcenter-daphne
sudo systemctl status callcenter-daphne
```

**Un solo proceso Daphne**, a propósito: Whisper y Piper quedan cargados en memoria y se
comparten entre llamadas. Con varios workers cada uno cargaría su copia (~1,5 GB) y la
primera respuesta de cada worker volvería a tardar segundos.

## 3. Nginx

```bash
sudo cp deploy/callcenter.nginx.conf /etc/nginx/sites-available/callcenter
sudo ln -s /etc/nginx/sites-available/callcenter /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Edita `server_name` con la IP o el dominio. Lo que no se puede omitir del bloque `/ws/`:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 3600s;
proxy_buffering off;
```

Sin `proxy_buffering off` el audio llega a tirones; sin los timeouts largos la llamada se
corta al minuto.

## 4. Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status numbered
```

Si usas Asterisk en el mismo servidor, además:

```bash
sudo ufw allow 5060/udp                 # SIP
sudo ufw allow 10000:20000/udp          # RTP (audio)
```

En nubes con firewall propio (Oracle, AWS, GCP, Hetzner) hay que abrir los mismos puertos
en el panel del proveedor: el `ufw` local no basta.

## 5. Verificación desde afuera

```bash
curl -s http://145.223.79.221:9000/health/
curl -I http://145.223.79.221:9000/login/
curl -o /dev/null -w "%{http_code}\n" http://145.223.79.221:9000/static/css/base.css
```

Prueba también el ingreso completo, que es lo que valida la configuración de CSRF:

```bash
TOKEN=$(curl -s -c /tmp/ck.txt http://145.223.79.221:9000/login/ \
        | grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' | head -1 | cut -d'"' -f4)
curl -s -b /tmp/ck.txt -o /dev/null -w "%{http_code} → %{redirect_url}\n" \
     -e http://145.223.79.221:9000/login/ \
     -d "csrfmiddlewaretoken=${TOKEN}&username=admin&password=TU-CLAVE" \
     http://145.223.79.221:9000/login/
```

Un `302` hacia `/panel/` significa que todo está bien. Un `403` es CSRF: falta el puerto en
`CSRF_TRUSTED_ORIGINS`.

WebSocket:

```bash
# Con websocat instalado
websocat ws://145.223.79.221/ws/voz/stream/
```

O directamente en el navegador con el **Demo de voz**, que es la prueba de extremo a
extremo: micrófono → STT → agente → TTS → parlante.

## 6. HTTPS (obligatorio con carriers comerciales)

Twilio, Telnyx, Plivo y SignalWire exigen `wss://` con certificado válido, y los
certificados públicos no se emiten para una IP. Necesitas un dominio o subdominio
apuntando a la IP:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d callcenter.tudominio.com
```

Y luego en `credenciales.json`:

```json
{
  "USE_SSL": true,
  "DOMINIO_GENERAL": "callcenter.tudominio.com",
  "VOZ_PUBLIC_HOST": "callcenter.tudominio.com",
  "ALLOWED_HOSTS": ["callcenter.tudominio.com"],
  "CSRF_TRUSTED_ORIGINS": ["https://callcenter.tudominio.com"]
}
```

Reinicia con `sudo systemctl restart callcenter-daphne`. El sistema pasa solo a generar
`wss://` en los webhooks (`VOZ_WS_ESQUEMA` se deriva de `USE_SSL`).

Mientras no haya dominio, funciona igual con **Asterisk local por IP** (`ws://`), que es
justamente el camino gratuito: el carrier "comercial" no interviene.

## 7. Operación diaria

```bash
sudo systemctl status callcenter-daphne
sudo journalctl -u callcenter-daphne -f
tail -f /var/log/callcenter/daphne.log
tail -f /var/log/nginx/callcenter-error.log
bash deploy/reiniciar.sh              # migrar + collectstatic + reiniciar + health
bash deploy/reiniciar.sh manual       # Daphne en primer plano para depurar
```

## 8. Lista de verificación

- [ ] `curl ifconfig.me` coincide con `IP_PUBLICA` en `credenciales.json`
- [ ] `ALLOWED_HOSTS` incluye esa IP o el dominio
- [ ] `VOZ_PUBLIC_HOST` apunta al host alcanzable desde internet
- [ ] `DEBUG` en `false`
- [ ] `SECRET_KEY` cambiada respecto de la plantilla
- [ ] Contraseña de `admin` cambiada
- [ ] El puerto elegido (9000 aquí) abierto en `ufw` **y** en el firewall del proveedor de nube
- [ ] `CSRF_TRUSTED_ORIGINS` incluye el puerto; el ingreso responde 302 y no 403
- [ ] `/health/` responde `ok: true` desde afuera
- [ ] Demo de voz funciona desde un navegador ajeno al servidor
- [ ] Respaldo de PostgreSQL programado en cron
