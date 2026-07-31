# Instalación

Servidor de referencia: Ubuntu 22.04 / Debian 12, 4 GB de RAM, IP pública.

## Opción A — automática

```bash
cd /home/callcenter
bash deploy/instalar.sh
```

El script instala paquetes, crea la base de datos, arma el entorno virtual, genera
`credenciales.json` con la IP pública detectada, migra, carga datos de ejemplo, descarga
los modelos de voz y deja Daphne + Nginx corriendo.

## Opción B — paso a paso

### 1. Paquetes del sistema

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential \
    postgresql postgresql-contrib libpq-dev \
    redis-server nginx ffmpeg espeak-ng curl git
```

`ffmpeg` y `espeak-ng` son el respaldo del motor de voz cuando Piper no está disponible.

### 2. Base de datos

Ver [`BASE_DATOS_POSTGRESQL.md`](BASE_DATOS_POSTGRESQL.md). Resumen:

```bash
sudo -u postgres psql -c "CREATE USER callcenter WITH PASSWORD 'una-clave-larga';"
sudo -u postgres psql -c "CREATE DATABASE callcenter OWNER callcenter ENCODING 'UTF8';"
```

### 3. Entorno virtual

Hay dos niveles de instalación:

```bash
cd /home/callcenter
python3 -m venv venv
./venv/bin/pip install --upgrade pip wheel

# Mínima: panel, motor IVR y agentes de IA por API. Tarda menos de un minuto.
./venv/bin/pip install -r requirements-base.txt

# Completa: agrega el motor de voz local (Whisper, Piper, embeddings).
./venv/bin/pip install -r requirements.txt
```

La completa descarga PyTorch: la primera vez tarda varios minutos y ocupa ~2 GB. Conviene
empezar por la mínima, dejar el panel funcionando y sumar el motor de voz después.

### 4. Credenciales

```bash
cp credenciales_template.json credenciales.json
nano credenciales.json
```

Mínimo a revisar:

| Clave | Para qué sirve |
|---|---|
| `SECRET_KEY` | Firma de sesiones. Genera una larga y aleatoria |
| `DEBUG` | `false` en producción |
| `POSTGRES_*` | Conexión a la base |
| `IP_PUBLICA` | IP por la que sale el servidor; alimenta `ALLOWED_HOSTS` y las URL de webhook |
| `VOZ_PUBLIC_HOST` | Host que se escribe en la URL `ws://…/ws/voz/stream/` que recibe el carrier. Vacío = usa `DOMINIO_GENERAL` |
| `VOZ_PIPER_MODELO` | Ruta al modelo de voz descargado |

Genera la clave con:

```bash
./venv/bin/python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 5. Migraciones y datos iniciales

```bash
./venv/bin/python manage.py migrate
./venv/bin/python manage.py shell < scripts/seed_demo.py
```

El seed crea el usuario `admin` (contraseña `admin1234`), un proveedor Asterisk local,
una llave de Ollama, una colección de conocimiento y un flujo IVR completo de ejemplo.

### 6. Modelos de voz gratuitos

```bash
bash scripts/descargar_modelos_voz.sh es_MX-claude-high
```

Otras voces: `es_ES-davefx-medium`, `es_ES-sharvard-medium`, `es_AR-daniela-high`.

### 7. Servicios

```bash
sudo mkdir -p /var/log/callcenter
sudo cp deploy/callcenter.service /etc/systemd/system/
sudo cp deploy/callcenter.nginx.conf /etc/nginx/sites-available/callcenter
sudo ln -s /etc/nginx/sites-available/callcenter /etc/nginx/sites-enabled/
sudo systemctl daemon-reload
sudo systemctl enable --now callcenter
sudo nginx -t && sudo systemctl reload nginx
```

Detalle completo en [`DESPLIEGUE_IP_PUBLICA.md`](DESPLIEGUE_IP_PUBLICA.md).

## Verificación

```bash
curl -s http://127.0.0.1:8001/health/ | python3 -m json.tool
```

Debe responder `"ok": true` con `base_datos` y `redis` en `true`.

En el navegador:

1. `http://<IP>/login/` → ingresa con `admin`.
2. *Panel* → la tarjeta **Estado del motor de voz** dice qué falta instalar.
3. *Centro de voz e IA → Demo de voz* → habla por el micrófono y verifica la respuesta.

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `DisallowedHost` | Agrega la IP o dominio a `ALLOWED_HOSTS` en `credenciales.json` |
| El demo conecta pero no responde audio | Falta el modelo Piper. Ejecuta `scripts/descargar_modelos_voz.sh` o instala `espeak-ng` |
| `ModuleNotFoundError: faster_whisper` | El entorno virtual no está activo o falta `pip install -r requirements.txt` |
| El WebSocket cierra a los 60 s | Faltan los `proxy_read_timeout` del bloque `/ws/` en Nginx |
| Primera respuesta tarda 20 s | Whisper y Piper se cargan en el primer turno. Precárgalos con el script de modelos |
| `connection refused` a Redis | `sudo systemctl start redis-server` o pon `"USAR_REDIS": false` |
