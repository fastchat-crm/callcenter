#!/usr/bin/env bash
# Instala Asterisk y lo conecta al motor de voz del callcenter.
#   sudo bash deploy/instalar_asterisk.sh
#
# Qué deja funcionando:
#   - Asterisk con PJSIP, escuchando SIP en el 5060
#   - El dialplan generado desde las troncales cargadas en el panel
#   - El servicio callcenter-audiosocket, que es quien recibe el audio
#
# Lo que NO hace: contratar la troncal. Eso se carga antes en el panel
# (Centro de telefonía → Proveedores), porque de ahí sale la configuración.
set -euo pipefail

RAIZ="/home/callcenter"
cd "$RAIZ"

if [ "$(id -u)" -ne 0 ]; then
    echo "Hay que ejecutarlo como root: sudo bash deploy/instalar_asterisk.sh" >&2
    exit 1
fi

echo "=== 1/6 Asterisk y utilidades ==="
apt-get update -qq
# uuid-runtime trae uuidgen, que el dialplan usa para identificar cada llamada.
apt-get install -y asterisk asterisk-modules uuid-runtime curl

echo "=== 2/6 Módulos necesarios ==="
# app_audiosocket transporta el audio; func_curl deja avisar al panel quién marcó.
for modulo in app_audiosocket func_curl res_curl; do
    if asterisk -rx "module show like ${modulo}" 2>/dev/null | grep -q "${modulo}"; then
        echo "  ${modulo}: presente"
    else
        echo "  ${modulo}: NO disponible — revisa que el paquete asterisk-modules esté instalado" >&2
    fi
done

echo "=== 3/6 Configuración desde el panel ==="
"$RAIZ/venv/bin/python" manage.py generar_config_asterisk --escribir

echo "=== 4/6 Servicio del puente AudioSocket ==="
mkdir -p /var/log/callcenter
cp deploy/callcenter-audiosocket.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now callcenter-audiosocket
sleep 2
systemctl --no-pager --lines=5 status callcenter-audiosocket || true

echo "=== 5/6 Asterisk arriba ==="
systemctl enable asterisk
systemctl restart asterisk
sleep 3
asterisk -rx "core show version" || true
asterisk -rx "pjsip show registrations" || true

echo "=== 6/6 Firewall ==="
if command -v ufw >/dev/null 2>&1; then
    ufw allow 5060/udp        # señalización SIP
    ufw allow 10000:20000/udp # audio RTP
    echo "  puertos SIP y RTP abiertos en ufw"
    echo "  RECUERDA abrirlos también en el firewall de tu proveedor de nube"
fi

echo
echo "Listo. Comprueba el estado con:"
echo "  ${RAIZ}/venv/bin/python manage.py estado_telefonia"
echo
echo "Para probar sin gastar un minuto: registra un softphone contra este"
echo "servidor y marca 1000; te atiende la IA."
