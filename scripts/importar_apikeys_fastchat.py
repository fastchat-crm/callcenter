"""Importa las llaves de IA configuradas en fastchatdj hacia este proyecto.

Se ejecuta en dos pasos para no leer las credenciales del otro proyecto:

  1) Volcado, con el entorno de fastchat:
     /home/fastchat/fastchatdj/venv/bin/python /home/fastchat/fastchatdj/manage.py shell \
        < scripts/exportar_apikeys_fastchat.py

  2) Importación, con este entorno:
     ./venv/bin/python manage.py shell < scripts/importar_apikeys_fastchat.py

Es idempotente: si la llave ya existe (mismo alias), la actualiza en vez de duplicarla.
"""
import json
import os

RUTA_VOLCADO = os.environ.get('RUTA_VOLCADO', '/tmp/apikeys_fastchat.json')

# proveedor en fastchat (crm.ApiKeyIA) → (proveedor aquí, base_url por defecto)
MAPA_PROVEEDOR = {
    2: (1, ''),                                   # GEMINI
    3: (5, 'https://api.openai.com/v1'),          # OPEN IA
    5: (6, 'https://ollama.com/v1'),              # OLLAMA CLOUD
    6: (5, 'https://api.deepseek.com/v1'),        # DEEPSEEK
    7: (5, ''),                                   # HUAWEI MAAS (requiere base_url propia)
    8: (4, 'http://127.0.0.1:11434'),             # OLLAMA LOCAL
}

NOMBRE_PROVEEDOR = {2: 'GEMINI', 3: 'OPENAI', 4: 'CLAUDE', 5: 'OLLAMA CLOUD',
                    6: 'DEEPSEEK', 7: 'HUAWEI', 8: 'OLLAMA LOCAL'}

if not os.path.exists(RUTA_VOLCADO):
    print(f'No existe {RUTA_VOLCADO}. Ejecuta primero el paso 1 (exportación).')
else:
    from agentes_ia.models import ApiKeyIA

    with open(RUTA_VOLCADO, encoding='utf-8') as archivo:
        llaves = json.load(archivo)

    creadas = actualizadas = omitidas = 0
    for llave in llaves:
        origen = llave.get('proveedor')
        if origen not in MAPA_PROVEEDOR:
            print(f"  omitida {llave.get('alias')!r}: proveedor "
                  f"{NOMBRE_PROVEEDOR.get(origen, origen)} todavía no está soportado aquí")
            omitidas += 1
            continue

        proveedor, base_url = MAPA_PROVEEDOR[origen]
        alias = (llave.get('alias') or f'importada-{origen}').strip()
        valores = {
            'proveedor': proveedor,
            'clave': llave.get('clave') or '',
            'modelo': llave.get('modelo') or '',
            'base_url': llave.get('base_url') or base_url,
            'activo': bool(llave.get('activo')),
        }
        if proveedor == 1:
            valores['modelo_embeddings'] = 'gemini-embedding-001'

        objeto = ApiKeyIA.objects.filter(alias=alias).first()
        if objeto is None:
            objeto = ApiKeyIA(alias=alias, **valores)
            objeto.save()
            creadas += 1
            estado = 'creada'
        else:
            for campo, valor in valores.items():
                setattr(objeto, campo, valor)
            objeto.save()
            actualizadas += 1
            estado = 'actualizada'
        print(f"  {estado}: {alias} · {objeto.get_proveedor_display()} · "
              f"modelo {objeto.modelo or 'por defecto'} · {'activa' if objeto.activo else 'inactiva'}")

    print(f'\n{creadas} creadas, {actualizadas} actualizadas, {omitidas} omitidas.')
    print('Borra el volcado cuando termines: rm -f ' + RUTA_VOLCADO)
