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

    # Tika primero cuando está configurado: entiende más formatos y saca mejor
    # el texto de PDF escaneados o con maquetación rara que pypdf. Si no
    # responde, se sigue con los extractores locales en vez de fallar.
    texto = _leer_con_tika(ruta)
    if texto:
        return texto

    if extension == '.pdf':
        return _leer_pdf(ruta)
    if extension in ('.docx',):
        return _leer_docx(ruta)
    if extension in ('.html', '.htm'):
        return _leer_html(ruta)
    logger.warning('[rag] formato no soportado: %s', extension)
    return ''


def _leer_con_tika(ruta):
    """Texto según Apache Tika, o cadena vacía si no está configurado o falla."""
    try:
        import requests

        from core.models import Configuracion

        configuracion = Configuracion.get_instancia()
        if not configuracion.tika_activo:
            return ''
        url = (configuracion.tika_url or '').strip().rstrip('/')
        if not url:
            logger.warning('[rag] Tika está activo pero sin URL configurada')
            return ''

        with open(ruta, 'rb') as archivo:
            respuesta = requests.put(f'{url}/tika', data=archivo,
                                     headers={'Accept': 'text/plain'}, timeout=60)
        if respuesta.status_code >= 400:
            logger.warning('[rag] Tika respondió HTTP %s; se usan los extractores locales',
                           respuesta.status_code)
            return ''
        return (respuesta.text or '').strip()
    except Exception as ex:
        logger.warning('[rag] Tika no respondió (%s); se usan los extractores locales', ex)
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
