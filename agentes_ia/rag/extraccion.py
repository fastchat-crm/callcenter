"""Extraccion de texto de los documentos que alimentan la base de conocimiento.

Todo con librerias gratuitas y opcionales: si la libreria no esta instalada, el
formato simplemente se reporta como no soportado en lugar de romper la carga.
"""
import logging
import os

logger = logging.getLogger('agentes_ia')


def extraer_texto(ruta: str) -> str:
    extension = os.path.splitext(ruta)[1].lower()
    if extension in ('.txt', '.md', '.csv'):
        return _leer_plano(ruta)
    if extension == '.pdf':
        return _leer_pdf(ruta)
    if extension in ('.docx',):
        return _leer_docx(ruta)
    if extension in ('.html', '.htm'):
        return _leer_html(ruta)
    logger.warning('[rag] formato no soportado: %s', extension)
    return ''


def _leer_plano(ruta):
    with open(ruta, encoding='utf-8', errors='ignore') as archivo:
        return archivo.read()


def _leer_pdf(ruta):
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning('[rag] instala pypdf para leer PDF: pip install pypdf')
        return ''
    lector = PdfReader(ruta)
    return '\n'.join((pagina.extract_text() or '') for pagina in lector.pages)


def _leer_docx(ruta):
    try:
        import docx
    except ImportError:
        logger.warning('[rag] instala python-docx para leer DOCX: pip install python-docx')
        return ''
    documento = docx.Document(ruta)
    return '\n'.join(parrafo.text for parrafo in documento.paragraphs)


def _leer_html(ruta):
    import re

    contenido = _leer_plano(ruta)
    contenido = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', contenido, flags=re.S | re.I)
    return re.sub(r'<[^>]+>', ' ', contenido)
