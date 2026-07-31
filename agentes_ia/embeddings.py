"""Embeddings para el RAG, con dos caminos.

  gemini  → API REST de Google (`text-embedding-004`). Sin SDK: solo `requests`.
            Tiene capa gratuita y no consume CPU del servidor.
  local   → sentence-transformers en el propio servidor. Cero costo y los datos
            no salen, pero exige tener instalado el requirements completo.

El backend se elige por colección. Si el elegido falla, se informa el error en
vez de indexar a medias: un vectorstore incompleto responde peor que uno vacío.
"""
from __future__ import annotations

import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger('agentes_ia')

URL_GEMINI = 'https://generativelanguage.googleapis.com/v1beta'
MODELO_GEMINI = 'gemini-embedding-001'
# gemini-embedding-001 devuelve 3072 dimensiones por defecto. Se recorta a 768:
# ocupa cuatro veces menos y la calidad de recuperación es equivalente. Ojo:
# por debajo de 3072 los vectores vienen sin normalizar y hay que normalizarlos.
DIMENSION_GEMINI = 768
LOTE_GEMINI = 25
PAUSA_LOTE = 0.6
REINTENTOS = 4

_modelo_local = None


class ErrorEmbeddings(Exception):
    pass


# ---------------------------------------------------------------------------
# Gemini por REST
# ---------------------------------------------------------------------------
def _normalizar(vector: list[float]) -> list[float]:
    magnitud = sum(valor * valor for valor in vector) ** 0.5
    return [valor / magnitud for valor in vector] if magnitud else vector


def _peticion_gemini(url: str, cuerpo: dict, apikey: str):
    respuesta = requests.post(url, json=cuerpo, params={'key': apikey}, timeout=60)
    if respuesta.status_code >= 400:
        raise ErrorEmbeddings(f'HTTP {respuesta.status_code}: {respuesta.text[:300]}')
    return respuesta.json()


def _gemini_uno(texto: str, apikey: str, modelo: str, tarea: str) -> list[float]:
    datos = _peticion_gemini(
        f'{URL_GEMINI}/models/{modelo}:embedContent',
        {
            'model': f'models/{modelo}',
            'content': {'parts': [{'text': texto}]},
            'taskType': tarea,
            'outputDimensionality': DIMENSION_GEMINI,
        },
        apikey,
    )
    return _normalizar((datos.get('embedding') or {}).get('values', []))


def _gemini_lote(textos: list[str], apikey: str, modelo: str, tarea: str) -> list[list[float]]:
    """Intenta el endpoint por lotes; si el modelo no lo soporta, va uno por uno."""
    peticiones = [
        {
            'model': f'models/{modelo}',
            'content': {'parts': [{'text': texto}]},
            'taskType': tarea,
            'outputDimensionality': DIMENSION_GEMINI,
        }
        for texto in textos
    ]
    try:
        datos = _peticion_gemini(
            f'{URL_GEMINI}/models/{modelo}:batchEmbedContents',
            {'requests': peticiones},
            apikey,
        )
        vectores = [item.get('values', []) for item in datos.get('embeddings', [])]
        if len(vectores) == len(textos):
            return [_normalizar(vector) for vector in vectores]
        raise ErrorEmbeddings('El lote devolvió menos vectores de los pedidos.')
    except ErrorEmbeddings as ex:
        if 'HTTP 404' not in str(ex) and 'HTTP 400' not in str(ex):
            raise
        logger.info('[rag] %s no soporta lotes; se vectoriza uno por uno', modelo)
        return [_gemini_uno(texto, apikey, modelo, tarea) for texto in textos]


def embeddings_gemini(textos: list[str], apikey: str, modelo: str = '',
                      consulta: bool = False) -> list[list[float]]:
    """Vectoriza con Gemini en lotes, con reintento ante límite de tasa."""
    if not apikey:
        raise ErrorEmbeddings('La colección usa embeddings de Gemini pero no hay llave configurada.')
    modelo = modelo or MODELO_GEMINI
    tarea = 'RETRIEVAL_QUERY' if consulta else 'RETRIEVAL_DOCUMENT'

    vectores: list[list[float]] = []
    for inicio in range(0, len(textos), LOTE_GEMINI):
        parte = textos[inicio:inicio + LOTE_GEMINI]
        for intento in range(REINTENTOS):
            try:
                vectores.extend(_gemini_lote(parte, apikey, modelo, tarea))
                break
            except ErrorEmbeddings as ex:
                mensaje = str(ex).lower()
                limite = '429' in mensaje or 'exhausted' in mensaje or 'rate' in mensaje
                if limite and intento < REINTENTOS - 1:
                    espera = PAUSA_LOTE * (2 ** intento)
                    logger.warning('[rag] límite de tasa en embeddings, reintento en %.1fs', espera)
                    time.sleep(espera)
                else:
                    raise
        if len(textos) > LOTE_GEMINI:
            time.sleep(PAUSA_LOTE)
    return vectores


# ---------------------------------------------------------------------------
# sentence-transformers local
# ---------------------------------------------------------------------------
def _cargar_local():
    global _modelo_local
    if _modelo_local is not None:
        return _modelo_local
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as ex:
        raise ErrorEmbeddings(
            'sentence-transformers no está instalado. Instala requirements.txt '
            'o cambia la colección a embeddings de Gemini.'
        ) from ex
    nombre = settings.RAG_MODELO_EMBEDDINGS
    logger.info('[rag] cargando modelo local de embeddings %s', nombre)
    _modelo_local = SentenceTransformer(nombre)
    return _modelo_local


def embeddings_local(textos: list[str]) -> list[list[float]]:
    modelo = _cargar_local()
    return [list(map(float, vector)) for vector in
            modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False)]


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def vectorizar(textos: list[str], motor: str = 'gemini', apikey: str = '',
               modelo: str = '', consulta: bool = False) -> list[list[float]]:
    if not textos:
        return []
    if motor == 'local':
        return embeddings_local(textos)
    return embeddings_gemini(textos, apikey, modelo, consulta)


def dimension(motor: str = 'gemini') -> int:
    """Tamaño del vector, para validar que no se mezclen motores en una colección."""
    return 384 if motor == 'local' else DIMENSION_GEMINI
