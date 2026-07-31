"""Menú lateral del panel.

El menú vive en la base: `seguridad.ModuloGrupo` arma las secciones y
`seguridad.Modulo` las entradas, filtradas por los permisos del rol del usuario.
Mientras esas tablas estén vacías —instalación recién hecha— se usa el menú
estático de abajo, para que el sistema sea navegable desde el primer minuto.
"""

# Icono de cada entrada, por URL. Los símbolos viven en
# `templates/componentes/iconos.html`; si un módulo trae su `icono` en la base,
# ese manda sobre este mapa.
ICONOS_URL = {
    '/panel/': 'tablero',
    '/clientes/puesta-en-marcha/': 'lista-check',
    '/clientes/listado/': 'edificio',
    '/llamadas/listado/': 'telefono',
    '/llamadas/monitor/': 'actividad',
    '/llamadas/transferencias/': 'desvio',
    '/ivr/flujos/': 'flujo',
    '/agentes-ia/agentes/': 'chispa',
    '/agentes-ia/conocimiento/': 'libro',
    '/agentes-ia/apikeys/': 'llave',
    '/agentes-ia/consumo/': 'grafico',
    '/voz/demo/': 'microfono',
    '/telefonia/proveedores/': 'nube',
    '/telefonia/numeros/': 'hash',
    '/telefonia/asesores/': 'persona',
    '/configuracion/': 'engranaje',
    '/seguridad/usuarios/': 'personas',
    '/seguridad/roles/': 'escudo',
    '/seguridad/modulos/': 'cuadricula',
    '/seguridad/secciones/': 'lista',
    '/seguridad/auditoria/': 'historial',
    '/doc/': 'documento',
    '/perfilpanel/': 'persona',
}

ICONOS_GRUPO = {
    'Centro de operación': 'actividad',
    'Centro de voz e IA': 'chispa',
    'Centro de telefonía': 'telefono',
    'Centro de seguridad': 'escudo',
    'Ayuda': 'ayuda',
}

ICONO_POR_DEFECTO = 'cuadricula'


def icono_de(url, declarado=''):
    return (declarado or '').strip() or ICONOS_URL.get(url, ICONO_POR_DEFECTO)


def icono_grupo(nombre):
    return ICONOS_GRUPO.get(nombre, ICONO_POR_DEFECTO)


MENU_BASE = (
    {
        'grupo': 'Operación',
        'items': (
            {'nombre': 'Panel', 'url': '/panel/'},
            {'nombre': 'Llamadas', 'url': '/llamadas/listado/'},
            {'nombre': 'Monitor en vivo', 'url': '/llamadas/monitor/'},
            {'nombre': 'Transferencias', 'url': '/llamadas/transferencias/'},
        ),
    },
    {
        'grupo': 'Configuración de voz',
        'items': (
            {'nombre': 'Flujos IVR', 'url': '/ivr/flujos/'},
            {'nombre': 'Agentes IA', 'url': '/agentes-ia/agentes/'},
            {'nombre': 'Base de conocimiento', 'url': '/agentes-ia/conocimiento/'},
            {'nombre': 'Llaves de IA', 'url': '/agentes-ia/apikeys/'},
            {'nombre': 'Consumo de IA', 'url': '/agentes-ia/consumo/'},
            {'nombre': 'Demo de voz', 'url': '/voz/demo/'},
        ),
    },
    {
        'grupo': 'Telefonía',
        'items': (
            {'nombre': 'Proveedores', 'url': '/telefonia/proveedores/'},
            {'nombre': 'Números', 'url': '/telefonia/numeros/'},
            {'nombre': 'Asesores', 'url': '/telefonia/asesores/'},
        ),
    },
    {
        'grupo': 'Seguridad',
        'items': (
            {'nombre': 'Usuarios', 'url': '/seguridad/usuarios/'},
            {'nombre': 'Roles de usuario', 'url': '/seguridad/roles/'},
            {'nombre': 'Módulos del sistema', 'url': '/seguridad/modulos/', 'solo_superusuario': True},
            {'nombre': 'Secciones del menú', 'url': '/seguridad/secciones/', 'solo_superusuario': True},
            {'nombre': 'Auditoría', 'url': '/seguridad/auditoria/'},
        ),
    },
    {
        'grupo': 'Ayuda',
        'items': (
            {'nombre': 'Documentación', 'url': '/doc/'},
            {'nombre': 'Guía de uso', 'url': '/doc/guia-de-uso/'},
        ),
    },
)


def menu_para_usuario(usuario):
    """Secciones y entradas que este usuario puede ver."""
    desde_base_datos = _menu_desde_base_datos(usuario)
    if desde_base_datos:
        return desde_base_datos
    return _menu_estatico(usuario)


def _menu_desde_base_datos(usuario):
    try:
        from seguridad.models import ModuloGrupo, modulos_de_usuario
    except Exception:
        return []

    try:
        secciones = list(ModuloGrupo.objects.filter(status=True).prefetch_related('modulos'))
        if not secciones:
            return []
        permitidos = set(modulos_de_usuario(usuario).values_list('id', flat=True))
    except Exception:
        # Base sin migrar todavía: el menú estático cubre el arranque.
        return []

    resultado = []
    for seccion in secciones:
        items = [
            {'nombre': modulo.nombre, 'url': modulo.url,
             'icono': icono_de(modulo.url, modulo.icono)}
            for modulo in seccion.modulos_visibles()
            if modulo.id in permitidos
        ]
        if items:
            resultado.append({
                'grupo': seccion.nombre,
                'icono': (seccion.icono or '').strip() or icono_grupo(seccion.nombre),
                'items': items,
            })
    return resultado


def _menu_estatico(usuario):
    es_superusuario = bool(getattr(usuario, 'is_superuser', False))
    resultado = []
    for grupo in MENU_BASE:
        items = [
            {**item, 'icono': icono_de(item['url'])}
            for item in grupo['items']
            if es_superusuario or not item.get('solo_superusuario')
        ]
        if items:
            resultado.append({
                'grupo': grupo['grupo'],
                'icono': icono_grupo(grupo['grupo']),
                'items': items,
            })
    return resultado
