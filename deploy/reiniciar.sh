#!/usr/bin/env bash
# Reinicia el servidor del callcenter y muestra el estado.
#   ./deploy/reiniciar.sh          → service callcenter restart (producción)
#   ./deploy/reiniciar.sh manual   → Daphne en primer plano, para depurar
set -euo pipefail

RAIZ="/home/callcenter"
SERVICIO="callcenter"
PUERTO="${PUERTO:-8501}"
MODO="${1:-servicio}"

cd "$RAIZ"

if [ "$MODO" = "manual" ]; then
    echo "→ Daphne en primer plano, puerto ${PUERTO}"
    echo "  (si el puerto está ocupado es porque el servicio ya corre: service ${SERVICIO} stop)"
    exec "$RAIZ/venv/bin/daphne" -b 127.0.0.1 -p "$PUERTO" --proxy-headers callcenterdj.asgi:application
fi

echo "→ Aplicando migraciones pendientes"
"$RAIZ/venv/bin/python" manage.py migrate --noinput

echo "→ Recolectando archivos estáticos"
"$RAIZ/venv/bin/python" manage.py collectstatic --noinput >/dev/null 2>&1 || true

echo "→ Reiniciando servicio"
service "$SERVICIO" restart
sleep 3
systemctl --no-pager --lines=8 status "$SERVICIO" || true

echo "→ Comprobando health"
curl -fsS "http://127.0.0.1:${PUERTO}/health/" && echo
