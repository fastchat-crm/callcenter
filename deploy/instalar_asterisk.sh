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

echo "=== 1/7 Asterisk y utilidades ==="
apt-get update -qq
# uuid-runtime trae uuidgen, que el dialplan usa para identificar cada llamada.
apt-get install -y asterisk asterisk-modules uuid-runtime curl

echo "=== 2/7 Módulos necesarios ==="
# app_audiosocket transporta el audio; func_curl deja avisar al panel quién marcó.
MODULOS=$(asterisk -rx "core show settings" 2>/dev/null | awk '/Module directory/{print $3}')
MODULOS=${MODULOS:-/usr/lib/x86_64-linux-gnu/asterisk/modules}
for modulo in app_audiosocket res_audiosocket func_curl res_curl; do
    if [ -f "${MODULOS}/${modulo}.so" ]; then
        echo "  ${modulo}: instalado"
    else
        echo "  ${modulo}: FALTA en ${MODULOS} — sin él la llamada entra muda" >&2
    fi
done

echo "=== 3/7 Configuración desde el panel ==="
"$RAIZ/venv/bin/python" manage.py generar_config_asterisk --escribir

echo "=== 4/7 Servicio del puente AudioSocket ==="
mkdir -p /var/log/callcenter
cp deploy/callcenter-audiosocket.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now callcenter-audiosocket
sleep 2
systemctl --no-pager --lines=5 status callcenter-audiosocket || true

echo "=== 5/7 Asterisk arriba ==="
systemctl enable asterisk
systemctl restart asterisk
sleep 3
asterisk -rx "core show version" || true
asterisk -rx "pjsip show registrations" || true

echo "=== 6/7 Protección contra fuerza bruta SIP ==="
# Abrir el 5060 sin esto es una invitación al fraude telefónico: los escáneres
# lo encuentran en horas y prueban usuarios y claves hasta poder llamar.
apt-get install -y fail2ban
grep -q "^security =>" /etc/asterisk/logger.conf || \
    sed -i '/^messages.log =>/a security => security' /etc/asterisk/logger.conf
cat > /etc/fail2ban/jail.d/asterisk.local <<'CONF'
[asterisk]
backend  = auto
enabled  = true
port     = 5060,5061
protocol = udp
filter   = asterisk
logpath  = /var/log/asterisk/security
maxretry = 5
findtime = 600
bantime  = 86400
CONF
asterisk -rx "logger reload" >/dev/null 2>&1 || true
systemctl restart fail2ban || echo "  revisa fail2ban a mano: systemctl status fail2ban" >&2
fail2ban-client status asterisk 2>/dev/null | head -3 || true

echo "=== 7/7 Firewall ==="
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
