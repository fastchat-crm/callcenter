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
    '/logout/', '/changepass/', '/registro/', '/telefonia/webhook/', '/agentes-ia/estado/',
    '/voz/estado/', '/clientes/cambiar/', '/clientes/modo-cliente/',
)

# Nombre legible para las rutas que el descubridor no puede nombrar solo.
NOMBRES = {
    '/panel/': 'Panel',
    '/perfilpanel/': 'Mi perfil',
    '/doc/': 'Documentación',
    '/configuracion/': 'Configuración general',
    '/parametros/': 'Parámetros del sistema',
    '/clientes/listado/': 'Clientes',
    '/clientes/puesta-en-marcha/': 'Puesta en marcha',
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
        existente = Modulo.objects.filter(url=ruta).first()
        if existente is not None:
            existentes += 1
            _refrescar_descripcion(existente)
            continue
        orden += 10
        Modulo.objects.create(
            nombre=nombre_para(ruta),
            url=ruta,
            descripcion=descripcion_para(ruta),
            orden=orden,
        )
        creados += 1
    logger.info('[seguridad] sincronización de módulos: %s nuevos, %s existentes', creados, existentes)
    return creados, existentes


# Texto que dejaban las versiones anteriores: no dice nada, así que se pisa.
RELLENO = 'Detectado automáticamente desde las URLs del proyecto.'


def descripcion_para(ruta):
    """Qué hace esta pantalla, tomado de la guía que ya se muestra dentro de ella.

    Una sola fuente: `core/guias.py`. Así el módulo, el menú y el recuadro de la
    pantalla dicen lo mismo, y cambiar la explicación es tocar un solo archivo.
    """
    from core.guias import obtener

    guia = obtener(ruta)
    if not guia:
        return RELLENO
    from seguridad.models import Modulo

    return _recortar(guia['resumen'], Modulo._meta.get_field('descripcion').max_length)


def _recortar(texto, maximo):
    """Corta en el último espacio para no partir una palabra a la mitad."""
    texto = (texto or '').strip()
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo - 1]
    espacio = corte.rfind(' ')
    return (corte[:espacio] if espacio > maximo * 0.6 else corte).rstrip(' ,.;') + '…'


def _refrescar_descripcion(modulo):
    """Completa la descripción si está vacía o es el relleno viejo.

    Nunca pisa un texto que alguien haya escrito a mano en el panel.
    """
    actual = (modulo.descripcion or '').strip()
    if actual and actual != RELLENO:
        return
    nueva = descripcion_para(modulo.url)
    if nueva != actual:
        modulo.descripcion = nueva
        modulo.save(update_fields=['descripcion'])
