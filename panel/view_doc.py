"""Documentación del sistema servida desde el propio panel (/doc/).

Lee los archivos Markdown de `docs/` y los renderiza con el diseño del panel.
Así la documentación técnica y la guía de uso viajan con el código: no hay una
copia en un Drive que se desactualice.
"""
import os
import re

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils.safestring import mark_safe

from core.funciones import addData, secure_module

# Orden y agrupación del índice. Los archivos que no estén aquí se agregan al
# final, en el grupo "Otros documentos".
INDICE = (
    ('Empezar', (
        ('guia-de-uso', 'GUIA_DE_USO.md', 'Cómo operar el sistema día a día'),
        ('instalacion', 'INSTALACION.md', 'Instalación paso a paso y verificación'),
    )),
    ('Configurar', (
        ('motor-ivr', 'MOTOR_IVR.md', 'Diseñar flujos: pasos, menús y capturas'),
        ('agentes-ia', 'AGENTES_IA.md', 'Proveedores, prompts y base de conocimiento'),
        ('telefonia-sip', 'TELEFONIA_SIP.md', 'De softphone gratuito a número internacional'),
    )),
    ('Administrar', (
        ('seguridad', 'SEGURIDAD.md', 'Usuarios, roles, módulos y auditoría'),
    )),
    ('Infraestructura', (
        ('arquitectura', 'ARQUITECTURA.md', 'Cómo viaja el audio y qué hace cada capa'),
        ('multi-cliente', 'MULTI_CLIENTE.md', 'Quién es dueño de qué y cómo se aísla'),
        ('base-datos', 'BASE_DATOS_POSTGRESQL.md', 'Modelo de datos, consultas y respaldos'),
        ('despliegue', 'DESPLIEGUE_IP_PUBLICA.md', 'Nginx, systemd, firewall y HTTPS'),
        ('servicios-gratuitos', 'SERVICIOS_GRATUITOS.md', 'Qué es gratis y hasta dónde alcanza'),
    )),
    ('Comercial', (
        ('propuesta', 'PROPUESTA_COMERCIAL.md', 'Propuesta lista para presentar al cliente'),
    )),
)


def _ruta_docs():
    return os.path.join(settings.BASE_DIR, 'docs')


def _mapa_documentos():
    """slug → (nombre de archivo, descripción)."""
    mapa = {}
    for _, documentos in INDICE:
        for slug, archivo, descripcion in documentos:
            mapa[slug] = (archivo, descripcion)
    return mapa


def _indice_visible():
    """Índice con solo los documentos que existen en disco."""
    directorio = _ruta_docs()
    grupos = []
    declarados = set()
    for grupo, documentos in INDICE:
        items = []
        for slug, archivo, descripcion in documentos:
            declarados.add(archivo)
            if os.path.exists(os.path.join(directorio, archivo)):
                items.append({'slug': slug, 'archivo': archivo, 'descripcion': descripcion,
                              'titulo': _titulo(os.path.join(directorio, archivo))})
        if items:
            grupos.append({'grupo': grupo, 'items': items})

    sueltos = []
    for archivo in sorted(os.listdir(directorio)) if os.path.isdir(directorio) else []:
        if archivo.endswith('.md') and archivo not in declarados:
            ruta = os.path.join(directorio, archivo)
            sueltos.append({'slug': _slug(archivo), 'archivo': archivo, 'descripcion': '',
                            'titulo': _titulo(ruta)})
    if sueltos:
        grupos.append({'grupo': 'Otros documentos', 'items': sueltos})
    return grupos


def _slug(archivo):
    return re.sub(r'[^a-z0-9]+', '-', archivo.replace('.md', '').lower()).strip('-')


def _titulo(ruta):
    try:
        with open(ruta, encoding='utf-8') as archivo:
            for linea in archivo:
                if linea.startswith('# '):
                    return linea[2:].strip()
    except OSError:
        pass
    return os.path.basename(ruta).replace('.md', '').replace('_', ' ').title()


def _renderizar(ruta):
    with open(ruta, encoding='utf-8') as archivo:
        contenido = archivo.read()
    try:
        import markdown

        html = markdown.markdown(
            contenido,
            extensions=['tables', 'fenced_code', 'toc', 'sane_lists', 'attr_list'],
        )
        # Las tablas anchas deben desplazarse dentro de su caja, no estirar la página.
        html = html.replace('<table>', '<div class="doc-tabla"><table>')
        html = html.replace('</table>', '</table></div>')
        return mark_safe(html)
    except ImportError:
        from django.utils.html import escape
        return mark_safe(f'<pre class="doc-plano">{escape(contenido)}</pre>')


@secure_module
def doc_view(request, slug='guia-de-uso'):
    data = {'titulo': 'Documentación', 'modulo': 'Ayuda'}
    addData(request, data)

    directorio = _ruta_docs()
    mapa = _mapa_documentos()

    if slug in mapa:
        archivo = mapa[slug][0]
    else:
        # Documento suelto: se busca por slug entre los .md del directorio.
        archivo = next(
            (nombre for nombre in os.listdir(directorio)
             if nombre.endswith('.md') and _slug(nombre) == slug),
            '',
        )
    ruta = os.path.join(directorio, archivo) if archivo else ''
    if not ruta or not os.path.exists(ruta):
        raise Http404('El documento solicitado no existe.')

    data['indice'] = _indice_visible()
    data['slug_actual'] = slug
    data['titulo_documento'] = _titulo(ruta)
    data['contenido'] = _renderizar(ruta)
    data['archivo'] = archivo
    return render(request, 'panel/doc.html', data)
