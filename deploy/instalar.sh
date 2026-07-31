#!/usr/bin/env bash
# Instalación completa de Callcenter IA en un servidor Ubuntu/Debian limpio.
# Ejecutar como root desde /home/callcenter:  bash deploy/instalar.sh
set -euo pipefail

RAIZ="/home/callcenter"
DB_NOMBRE="${DB_NOMBRE:-callcenter}"
DB_USUARIO="${DB_USUARIO:-callcenter}"
DB_CLAVE="${DB_CLAVE:-callcenter}"

echo "=== 1/7 Paquetes del sistema ==="
apt-get update -qq
apt-get install -y python3-venv python3-dev build-essential \
    postgresql postgresql-contrib libpq-dev \
    redis-server nginx ffmpeg espeak-ng curl git

echo "=== 2/7 PostgreSQL ==="
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USUARIO}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USUARIO} WITH PASSWORD '${DB_CLAVE}';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NOMBRE}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NOMBRE} OWNER ${DB_USUARIO} ENCODING 'UTF8';"
sudo -u postgres psql -c "ALTER ROLE ${DB_USUARIO} SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE ${DB_USUARIO} SET timezone TO 'America/Guayaquil';"

echo "=== 3/7 Entorno virtual ==="
cd "$RAIZ"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install --upgrade pip wheel
./venv/bin/pip install -r requirements.txt

echo "=== 4/7 Credenciales ==="
if [ ! -f credenciales.json ]; then
    ./venv/bin/python - <<'PY'
import json, pathlib, secrets, subprocess
datos = json.loads(pathlib.Path('credenciales_template.json').read_text())
datos['SECRET_KEY'] = secrets.token_urlsafe(50)
try:
    ip = subprocess.check_output(['curl', '-s', '--max-time', '5', 'ifconfig.me']).decode().strip()
    if ip:
        datos['IP_PUBLICA'] = ip
except Exception:
    pass
pathlib.Path('credenciales.json').write_text(json.dumps(datos, indent=2, ensure_ascii=False))
print('credenciales.json creado con IP', datos['IP_PUBLICA'])
PY
fi

echo "=== 5/7 Base de datos y datos iniciales ==="
./venv/bin/python manage.py migrate --noinput
./venv/bin/python manage.py shell < scripts/seed_demo.py

echo "=== 6/7 Modelos de voz gratuitos ==="
bash scripts/descargar_modelos_voz.sh || echo "  (puedes ejecutarlo luego manualmente)"

echo "=== 7/7 Servicios ==="
mkdir -p /var/log/callcenter
cp deploy/callcenter.service /etc/systemd/system/
cp deploy/callcenter.nginx.conf /etc/nginx/sites-available/callcenter
ln -sf /etc/nginx/sites-available/callcenter /etc/nginx/sites-enabled/callcenter
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
systemctl enable --now redis-server postgresql
systemctl enable --now callcenter
nginx -t && systemctl reload nginx

IP=$(curl -s --max-time 5 ifconfig.me || echo "IP-DEL-SERVIDOR")
echo
echo "Listo. Panel disponible en:  http://${IP}:9000/login/"
echo "Usuario: admin   Contraseña: admin1234   (cámbiala antes de producción)"
