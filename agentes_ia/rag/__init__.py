"""Fachada del RAG: la colección decide dónde vive su índice.

  local     → `.npz` de numpy en media/vectorstore/<slug>/. Cero servicios extra.
  weaviate  → colección multi-tenant en el Weaviate del servidor.

El resto del sistema llama solo a `indexar_coleccion`, `buscar_en_coleccion` y
`contexto_para_prompt`; nunca importa un backend directamente.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger('agentes_ia')

TAMANO_FRAGMENTO = 900
SOLAPE_FRAGMENTO = 150


def _apikey_embeddings(coleccion) -> str:
    llave = coleccion.apikey_embeddings
    return (llave.clave or '') if llave else ''


def _modelo_embeddings(coleccion) -> str:
    llave = coleccion.apikey_embeddings
    return (llave.modelo_embeddings or '') if llave else ''


def documentos_de(coleccion) -> list[dict]:
    """Texto de cada documento de la colección, extrayendo el archivo si hace falta."""
    from agentes_ia.rag.extraccion import extraer_texto

    documentos = []
    for documento in coleccion.documentos.filter(status=True):
        texto = documento.contenido or ''
        if not texto and documento.archivo:
            texto = extraer_texto(documento.archivo.path)
            documento.contenido = texto
            documento.save(update_fields=['contenido'])
        if texto and texto.strip():
            documentos.append({
                'titulo': documento.titulo,
                'texto': texto,
                'tipo': 'archivo' if documento.archivo else 'texto',
            })
    return documentos


def fragmentar(texto: str, tamano: int = TAMANO_FRAGMENTO, solape: int = SOLAPE_FRAGMENTO) -> list[str]:
    texto = re.sub(r'\s+', ' ', texto or '').strip()
    if not texto:
        return []
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        corte = texto.rfind('. ', inicio, fin)
        corte = fin if (corte == -1 or fin == len(texto)) else corte + 1
        fragmentos.append(texto[inicio:corte].strip())
        if corte >= len(texto):
            break
        inicio = max(corte - solape, inicio + 1)
    return [fragmento for fragmento in fragmentos if fragmento]


def indexar_coleccion(coleccion) -> int:
    """Reconstruye el índice de la colección. Devuelve la cantidad de fragmentos."""
    documentos = documentos_de(coleccion)

    if coleccion.backend == 'weaviate':
        from agentes_ia import embeddings as motor_embeddings
        from agentes_ia.rag import weaviate_rag

        fragmentos, metadatos = [], []
        for documento in documentos:
            for fragmento in fragmentar(documento['texto']):
                fragmentos.append(fragmento)
                metadatos.append(documento)

        vectores = motor_embeddings.vectorizar(
            fragmentos,
            motor=coleccion.motor_embeddings,
            apikey=_apikey_embeddings(coleccion),
            modelo=_modelo_embeddings(coleccion),
        )
        objetos = [
            {'content': texto, 'source': meta['titulo'], 'tipo': meta['tipo'],
             'categoria': coleccion.nombre}
            for texto, meta in zip(fragmentos, metadatos)
        ]
        return weaviate_rag.indexar(coleccion.id, objetos, vectores, reemplazar=True)

    from agentes_ia.rag.vectorstore import indexar as indexar_local

    return indexar_local(
        coleccion.slug,
        [{'titulo': documento['titulo'], 'texto': documento['texto'], 'origen': documento['tipo']}
         for documento in documentos],
    )


def buscar_en_coleccion(coleccion, consulta: str, top_k: int = 4) -> list[dict]:
    """Fragmentos más parecidos a la consulta. Nunca lanza: si falla, devuelve []."""
    if not (consulta or '').strip():
        return []
    try:
        if coleccion.backend == 'weaviate':
            from agentes_ia import embeddings as motor_embeddings
            from agentes_ia.rag import weaviate_rag

            vector = motor_embeddings.vectorizar(
                [consulta],
                motor=coleccion.motor_embeddings,
                apikey=_apikey_embeddings(coleccion),
                modelo=_modelo_embeddings(coleccion),
                consulta=True,
            )
            return weaviate_rag.buscar(coleccion.id, vector[0], top_k) if vector else []

        from agentes_ia.rag.vectorstore import buscar as buscar_local

        return buscar_local(coleccion.slug, consulta, top_k)
    except Exception:
        logger.exception('[rag] búsqueda fallida en la colección %s', coleccion.slug)
        return []


def contexto_para_prompt(coleccion, consulta: str, top_k: int = 4,
                         maximo_caracteres: int = 2500) -> str:
    resultados = buscar_en_coleccion(coleccion, consulta, top_k)
    if not resultados:
        return ''
    partes, total = [], 0
    for resultado in resultados:
        texto = resultado.get('texto', '')
        if not texto or total + len(texto) > maximo_caracteres:
            continue
        partes.append(f"[{resultado.get('titulo') or 'Documento'}] {texto}")
        total += len(texto)
    return '\n\n'.join(partes)


def fragmentos_indexados(coleccion) -> int:
    if coleccion.backend == 'weaviate':
        from agentes_ia.rag import weaviate_rag
        return weaviate_rag.contar(coleccion.id)
    return coleccion.fragmentos_indexados
