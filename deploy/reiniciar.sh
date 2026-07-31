#!/usr/bin/env bash
# Reinicia el servidor ASGI del callcenter y muestra el estado.
#   ./deploy/reiniciar.sh          → usa systemd (producción)
#   ./deploy/reiniciar.sh manual   → levanta Daphne en primer plano (depuración)
set -euo pipefail

RAIZ="/home/callcenter"
PUERTO="${PUERTO:-8001}"
MODO="${1:-systemd}"

cd "$RAIZ"

if [ "$MODO" = "manual" ]; then
    echo "→ Daphne en primer plano, puerto ${PUERTO}"
    exec "$RAIZ/venv/bin/daphne" -b 0.0.0.0 -p "$PUERTO" --proxy-headers callcenterdj.asgi:application
fi

echo "→ Aplicando migraciones pendientes"
"$RAIZ/venv/bin/python" manage.py migrate --noinput

echo "→ Recolectando archivos estáticos"
"$RAIZ/venv/bin/python" manage.py collectstatic --noinput >/dev/null 2>&1 || true

echo "→ Reiniciando servicio"
systemctl restart callcenter-daphne
sleep 2
systemctl --no-pager --lines=8 status callcenter-daphne || true

echo "→ Comprobando health"
curl -fsS "http://127.0.0.1:${PUERTO}/health/" && echo
