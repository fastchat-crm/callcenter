"""Descubre las URLs reales del proyecto y las registra como módulos.

Evita el trabajo manual de mantener la tabla al día: se recorre el resolver de
Django y se dan de alta las rutas fijas que aún no existen. Solo agrega; nunca
borra ni pisa lo que el administrador editó a mano.
"""
import logging

from django.conf import settings
from django.urls import URLPattern, URLResolver, get_resolver

logger = logging.getLogger('seguridad')

# Rutas que no son módulos del panel: infraestructura, endpoints y públicas.
PREFIJOS_IGNORADOS = (
    '/admin/', '/static/', '/media/', '/ajaxrequest/', '/health/', '/login/',
    '/logout/', '/changepass/', '/telefonia/webhook/', '/agentes-ia/estado/',
    '/voz/estado/',
)

# Nombre legible para las rutas que el descubridor no puede nombrar solo.
NOMBRES = {
    '/panel/': 'Panel',
    '/perfilpanel/': 'Mi perfil',
    '/doc/': 'Documentación',
    '/llamadas/listado/': 'Llamadas',
    '/llamadas/monitor/': 'Monitor en vivo',
    '/llamadas/transferencias/': 'Transferencias',
    '/ivr/flujos/': 'Flujos IVR',
    '/agentes-ia/agentes/': 'Agentes IA',
    '/agentes-ia/conocimiento/': 'Base de conocimiento',
    '/agentes-ia/apikeys/': 'Llaves de IA',
    '/agentes-ia/consumo/': 'Consumo de IA',
    '/telefonia/proveedores/': 'Proveedores de telefonía',
    '/telefonia/numeros/': 'Números telefónicos',
    '/telefonia/asesores/': 'Asesores humanos',
    '/voz/demo/': 'Demo de voz',
    '/seguridad/usuarios/': 'Usuarios',
    '/seguridad/roles/': 'Roles de usuario',
    '/seguridad/modulos/': 'Módulos del sistema',
    '/seguridad/secciones/': 'Secciones del menú',
    '/seguridad/auditoria/': 'Auditoría',
}


def _recorrer(patrones, prefijo=''):
    """Rutas fijas del proyecto, en orden de declaración."""
    rutas = []
    for patron in patrones:
        if isinstance(patron, URLResolver):
            rutas.extend(_recorrer(patron.url_patterns, prefijo + str(patron.pattern)))
        elif isinstance(patron, URLPattern):
            ruta = prefijo + str(patron.pattern)
            ruta = ruta.replace('^', '').replace('$', '')
            if not ruta.startswith('/'):
                ruta = '/' + ruta
            # Solo rutas fijas: las que llevan parámetros no son un módulo del menú.
            if '<' in ruta or '(' in ruta or '\\' in ruta:
                continue
            if not ruta.endswith('/'):
                ruta += '/'
            rutas.append(ruta)
    return rutas


def rutas_del_proyecto():
    resolver = get_resolver(settings.ROOT_URLCONF)
    vistas = []
    for ruta in _recorrer(resolver.url_patterns):
        if ruta == '/' or any(ruta.startswith(ignorado) for ignorado in PREFIJOS_IGNORADOS):
            continue
        if ruta not in vistas:
            vistas.append(ruta)
    return vistas


def nombre_para(ruta):
    if ruta in NOMBRES:
        return NOMBRES[ruta]
    partes = [parte for parte in ruta.split('/') if parte]
    if not partes:
        return ruta
    return partes[-1].replace('-', ' ').replace('_', ' ').capitalize()


def sincronizar_modulos():
    """Crea los módulos que faltan. Devuelve (creados, ya existentes)."""
    from .models import Modulo

    creados = existentes = 0
    orden = (Modulo.objects.order_by('-orden').values_list('orden', flat=True).first() or 0)
    for ruta in rutas_del_proyecto():
        if Modulo.objects.filter(url=ruta).exists():
            existentes += 1
            continue
        orden += 10
        Modulo.objects.create(
            nombre=nombre_para(ruta),
            url=ruta,
            descripcion='Detectado automáticamente desde las URLs del proyecto.',
            orden=orden,
        )
        creados += 1
    logger.info('[seguridad] sincronización de módulos: %s nuevos, %s existentes', creados, existentes)
    return creados, existentes
