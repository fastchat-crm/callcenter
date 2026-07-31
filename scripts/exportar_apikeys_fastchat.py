"""Volcado de las llaves de IA de fastchatdj a un JSON temporal.

Se ejecuta con el entorno de fastchat, no con el de este proyecto:

    /home/fastchat/fastchatdj/venv/bin/python /home/fastchat/fastchatdj/manage.py shell \
        < /home/callcenter/scripts/exportar_apikeys_fastchat.py

El archivo resultante contiene claves en texto plano: bórralo apenas termine la
importación.
"""
import json
import os

RUTA_VOLCADO = os.environ.get('RUTA_VOLCADO', '/tmp/apikeys_fastchat.json')

from crm.models import ApiKeyIA  # noqa: E402

llaves = []
for llave in ApiKeyIA.objects.filter(status=True).order_by('proveedor', 'id'):
    llaves.append({
        'alias': llave.alias,
        'proveedor': llave.proveedor,
        'clave': llave.descripcion or '',
        'modelo': llave.modelo or '',
        'base_url': getattr(llave, 'base_url', '') or '',
        'activo': bool(llave.estado),
    })

with open(RUTA_VOLCADO, 'w', encoding='utf-8') as archivo:
    json.dump(llaves, archivo, ensure_ascii=False, indent=2)
os.chmod(RUTA_VOLCADO, 0o600)

print(f'{len(llaves)} llaves volcadas en {RUTA_VOLCADO}')
