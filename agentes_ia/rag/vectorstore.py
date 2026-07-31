"""Vectorstore local minimalista: embeddings gratuitos + busqueda coseno en numpy.

Sin servicios pagos ni servidores extra. Cada coleccion es un `.npz` en
`media/vectorstore/<slug>/`. Para volumenes grandes se puede migrar a FAISS o
pgvector sin cambiar la interfaz publica (`indexar`, `buscar`).
"""
from __future__ import annotations

import json
import logging
import os
import re

from django.conf import settings

logger = logging.getLogger('agentes_ia')

_modelo_embeddings = None
TAMANO_FRAGMENTO = 900
SOLAPE_FRAGMENTO = 150


def _ruta_coleccion(slug: str) -> str:
    directorio = os.path.join(settings.MEDIA_ROOT, settings.RAG_DIRECTORIO_VECTORSTORE, slug)
    os.makedirs(directorio, exist_ok=True)
    return directorio


def cargar_modelo_embeddings():
    """Carga perezosa de sentence-transformers (modelo multilingue, gratuito)."""
    global _modelo_embeddings
    if _modelo_embeddings is not None:
        return _modelo_embeddings
    from sentence_transformers import SentenceTransformer

    nombre = settings.RAG_MODELO_EMBEDDINGS
    logger.info('[rag] cargando modelo de embeddings %s', nombre)
    _modelo_embeddings = SentenceTransformer(nombre)
    return _modelo_embeddings


def fragmentar(texto: str, tamano: int = TAMANO_FRAGMENTO, solape: int = SOLAPE_FRAGMENTO) -> list[str]:
    texto = re.sub(r'\s+', ' ', texto or '').strip()
    if not texto:
        return []
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        corte = texto.rfind('. ', inicio, fin)
        if corte == -1 or fin == len(texto):
            corte = fin
        else:
            corte += 1
        fragmentos.append(texto[inicio:corte].strip())
        if corte >= len(texto):
            break
        inicio = max(corte - solape, inicio + 1)
    return [fragmento for fragmento in fragmentos if fragmento]


def indexar(slug: str, documentos: list[dict]) -> int:
    """Reconstruye la coleccion. `documentos` = [{'titulo':..., 'texto':...}]."""
    import numpy as np

    modelo = cargar_modelo_embeddings()
    fragmentos, metadatos = [], []
    for documento in documentos:
        for fragmento in fragmentar(documento.get('texto', '')):
            fragmentos.append(fragmento)
            metadatos.append({'titulo': documento.get('titulo', ''), 'origen': documento.get('origen', '')})

    directorio = _ruta_coleccion(slug)
    if not fragmentos:
        for archivo in ('vectores.npz', 'fragmentos.json'):
            ruta = os.path.join(directorio, archivo)
            if os.path.exists(ruta):
                os.remove(ruta)
        return 0

    vectores = modelo.encode(fragmentos, normalize_embeddings=True, show_progress_bar=False)
    np.savez_compressed(os.path.join(directorio, 'vectores.npz'), vectores=np.asarray(vectores, dtype='float32'))
    with open(os.path.join(directorio, 'fragmentos.json'), 'w', encoding='utf-8') as archivo:
        json.dump([{'texto': t, **m} for t, m in zip(fragmentos, metadatos)], archivo, ensure_ascii=False)
    logger.info('[rag] colección %s indexada con %s fragmentos', slug, len(fragmentos))
    return len(fragmentos)


def buscar(slug: str, consulta: str, top_k: int = 4) -> list[dict]:
    """Devuelve los fragmentos mas parecidos a la consulta."""
    import numpy as np

    directorio = _ruta_coleccion(slug)
    ruta_vectores = os.path.join(directorio, 'vectores.npz')
    ruta_fragmentos = os.path.join(directorio, 'fragmentos.json')
    if not (os.path.exists(ruta_vectores) and os.path.exists(ruta_fragmentos)):
        return []

    try:
        modelo = cargar_modelo_embeddings()
        vector_consulta = np.asarray(
            modelo.encode([consulta], normalize_embeddings=True)[0], dtype='float32'
        )
        vectores = np.load(ruta_vectores)['vectores']
        with open(ruta_fragmentos, encoding='utf-8') as archivo:
            fragmentos = json.load(archivo)

        similitudes = vectores @ vector_consulta
        indices = np.argsort(-similitudes)[:top_k]
        return [
            {**fragmentos[indice], 'similitud': float(similitudes[indice])}
            for indice in indices if similitudes[indice] > 0.15
        ]
    except Exception:
        logger.exception('[rag] falló la búsqueda en la colección %s', slug)
        return []


def contexto_para_prompt(slug: str, consulta: str, top_k: int = 4, maximo_caracteres: int = 2500) -> str:
    resultados = buscar(slug, consulta, top_k)
    if not resultados:
        return ''
    partes, total = [], 0
    for resultado in resultados:
        texto = resultado['texto']
        if total + len(texto) > maximo_caracteres:
            break
        titulo = resultado.get('titulo') or 'Documento'
        partes.append(f'[{titulo}] {texto}')
        total += len(texto)
    return '\n\n'.join(partes)
