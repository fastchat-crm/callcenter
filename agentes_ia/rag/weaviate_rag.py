"""RAG sobre Weaviate multi-tenant, hablado por REST.

Mismo planteo que `agents_ai/weaviate_rag.py` de fastchatdj —una colección
multi-tenant con vectores externos, un tenant por base de conocimiento— pero
sin el SDK: solo `requests` contra la API v1. Eso evita arrastrar grpc y
pydantic a un proyecto que ya carga modelos de voz en memoria.

Configuración: variables de entorno o `/home/weaviate/.env`, igual que fastchat,
para reutilizar la instancia que ya corre en el servidor.
"""
from __future__ import annotations

import json
import logging
import os

import requests

logger = logging.getLogger('agentes_ia')

COLECCION = 'ConocimientoCallcenter'
TIEMPO_ESPERA = 30
RUTAS_ENV = ('/home/callcenter/.weaviate.env', '/home/weaviate/.env')


class ErrorWeaviate(Exception):
    pass


# ---------------------------------------------------------------------------
# Configuración y conexión
# ---------------------------------------------------------------------------
def _config(clave: str, defecto: str = '') -> str:
    valor = os.environ.get(clave)
    if valor:
        return valor
    for ruta in RUTAS_ENV:
        try:
            with open(ruta, encoding='utf-8') as archivo:
                for linea in archivo:
                    linea = linea.strip()
                    if linea.startswith(f'{clave}=') and not linea.startswith('#'):
                        return linea.split('=', 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return defecto


def _base_url() -> str:
    host = _config('WEAVIATE_HOST', '127.0.0.1')
    puerto = _config('WEAVIATE_HTTP_PORT', '8080')
    esquema = _config('WEAVIATE_ESQUEMA', 'http')
    return f'{esquema}://{host}:{puerto}'


def _cabeceras() -> dict:
    cabeceras = {'Content-Type': 'application/json'}
    apikey = _config('WEAVIATE_API_KEY', '')
    if apikey:
        cabeceras['Authorization'] = f'Bearer {apikey}'
    return cabeceras


def _peticion(metodo: str, ruta: str, cuerpo=None, parametros=None):
    url = f'{_base_url()}{ruta}'
    try:
        respuesta = requests.request(metodo, url, headers=_cabeceras(), json=cuerpo,
                                     params=parametros, timeout=TIEMPO_ESPERA)
    except requests.RequestException as ex:
        raise ErrorWeaviate(f'No se pudo conectar con Weaviate en {url}: {ex}') from ex
    if respuesta.status_code >= 400:
        raise ErrorWeaviate(f'Weaviate respondió {respuesta.status_code}: {respuesta.text[:300]}')
    if not respuesta.content:
        return {}
    try:
        return respuesta.json()
    except json.JSONDecodeError:
        return {}


def disponible() -> tuple[bool, str]:
    """(está listo, detalle) — para mostrarlo en el panel sin romper nada."""
    try:
        meta = _peticion('GET', '/v1/meta')
        return True, f"Weaviate {meta.get('version', '?')} en {_base_url()}"
    except ErrorWeaviate as ex:
        return False, str(ex)


def tenant_de(coleccion_id) -> str:
    return f'coleccion_{coleccion_id}'


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
def asegurar_esquema() -> None:
    esquema = _peticion('GET', '/v1/schema') or {}
    existentes = {clase.get('class') for clase in (esquema.get('classes') or [])}
    if COLECCION in existentes:
        return
    _peticion('POST', '/v1/schema', {
        'class': COLECCION,
        'description': 'Base de conocimiento de los agentes de voz del callcenter.',
        'vectorizer': 'none',
        'multiTenancyConfig': {'enabled': True, 'autoTenantCreation': True},
        'properties': [
            {'name': 'content', 'dataType': ['text']},
            {'name': 'source', 'dataType': ['text']},
            {'name': 'tipo', 'dataType': ['text']},
            {'name': 'categoria', 'dataType': ['text']},
        ],
    })
    logger.info('[rag] colección Weaviate %s creada (multi-tenant)', COLECCION)


def asegurar_tenant(coleccion_id) -> str:
    tenant = tenant_de(coleccion_id)
    try:
        actuales = _peticion('GET', f'/v1/schema/{COLECCION}/tenants') or []
        nombres = {item.get('name') for item in actuales}
        if tenant not in nombres:
            _peticion('POST', f'/v1/schema/{COLECCION}/tenants', [{'name': tenant}])
    except ErrorWeaviate as ex:
        # autoTenantCreation cubre el caso; se registra y se sigue.
        logger.debug('[rag] asegurar_tenant: %s', ex)
    return tenant


def borrar_tenant(coleccion_id) -> None:
    tenant = tenant_de(coleccion_id)
    try:
        _peticion('DELETE', f'/v1/schema/{COLECCION}/tenants', [tenant])
    except ErrorWeaviate as ex:
        logger.debug('[rag] borrar_tenant: %s', ex)


# ---------------------------------------------------------------------------
# Indexado
# ---------------------------------------------------------------------------
def indexar(coleccion_id, documentos: list[dict], vectores: list[list[float]],
            reemplazar: bool = True) -> int:
    """`documentos` = [{'content', 'source', 'tipo', 'categoria'}] con sus vectores."""
    if not documentos:
        if reemplazar:
            borrar_tenant(coleccion_id)
        return 0
    if len(documentos) != len(vectores):
        raise ErrorWeaviate('La cantidad de fragmentos y de vectores no coincide.')

    asegurar_esquema()
    if reemplazar:
        borrar_tenant(coleccion_id)
    tenant = asegurar_tenant(coleccion_id)

    insertados = 0
    TAMANO_LOTE = 100
    for inicio in range(0, len(documentos), TAMANO_LOTE):
        parte = documentos[inicio:inicio + TAMANO_LOTE]
        vectores_parte = vectores[inicio:inicio + TAMANO_LOTE]
        objetos = [
            {
                'class': COLECCION,
                'tenant': tenant,
                'properties': {
                    'content': documento.get('content', ''),
                    'source': documento.get('source', ''),
                    'tipo': documento.get('tipo', ''),
                    'categoria': documento.get('categoria', ''),
                },
                'vector': vector,
            }
            for documento, vector in zip(parte, vectores_parte)
        ]
        resultado = _peticion('POST', '/v1/batch/objects', {'objects': objetos})
        for item in resultado or []:
            estado = ((item.get('result') or {}).get('status') or '').upper()
            if estado in ('SUCCESS', ''):
                insertados += 1
            else:
                errores = (item.get('result') or {}).get('errors') or {}
                logger.warning('[rag] objeto rechazado por Weaviate: %s', errores)
    logger.info('[rag] tenant %s indexado con %s objetos', tenant, insertados)
    return insertados


# ---------------------------------------------------------------------------
# Búsqueda
# ---------------------------------------------------------------------------
def buscar(coleccion_id, vector_consulta: list[float], top_k: int = 4,
           distancia_maxima: float = 0.75) -> list[dict]:
    tenant = tenant_de(coleccion_id)
    consulta = {
        'query': (
            '{ Get { %s(tenant: "%s", limit: %d, nearVector: {vector: %s}) '
            '{ content source tipo categoria _additional { distance } } } }'
        ) % (COLECCION, tenant, top_k, json.dumps(vector_consulta))
    }
    try:
        datos = _peticion('POST', '/v1/graphql', consulta)
    except ErrorWeaviate as ex:
        logger.error('[rag] búsqueda en Weaviate falló: %s', ex)
        return []

    if datos.get('errors'):
        logger.error('[rag] GraphQL devolvió errores: %s', datos['errors'])
        return []

    objetos = ((datos.get('data') or {}).get('Get') or {}).get(COLECCION) or []
    resultados = []
    for objeto in objetos:
        distancia = ((objeto.get('_additional') or {}).get('distance'))
        if distancia is not None and distancia > distancia_maxima:
            continue
        resultados.append({
            'texto': objeto.get('content', ''),
            'titulo': objeto.get('source', '') or 'Documento',
            'tipo': objeto.get('tipo', ''),
            'categoria': objeto.get('categoria', ''),
            'similitud': round(1 - distancia, 4) if distancia is not None else None,
        })
    return resultados


def contar(coleccion_id) -> int:
    tenant = tenant_de(coleccion_id)
    consulta = {
        'query': '{ Aggregate { %s(tenant: "%s") { meta { count } } } }' % (COLECCION, tenant)
    }
    try:
        datos = _peticion('POST', '/v1/graphql', consulta)
        agregados = ((datos.get('data') or {}).get('Aggregate') or {}).get(COLECCION) or []
        if agregados:
            return ((agregados[0].get('meta') or {}).get('count')) or 0
    except ErrorWeaviate as ex:
        logger.debug('[rag] contar: %s', ex)
    return 0
