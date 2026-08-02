"""Guías de pantalla: qué hace cada ventana y en qué punto del recorrido entra.

Las pantallas se agrupan en centros de información y las que forman la cadena de
una llamada llevan un `orden`; a partir de ese número se calculan solos el «paso
N de M» y los enlaces a la pantalla anterior y siguiente.
"""
from fnmatch import fnmatch

CENTRO_TELEFONIA = 'Centro de telefonía'
CENTRO_VOZ = 'Centro de voz e IA'
CENTRO_OPERACION = 'Centro de operación'
CENTRO_SEGURIDAD = 'Centro de seguridad'

GUIAS = {
    '/telefonia/proveedores/': {
        'centro': CENTRO_TELEFONIA,
        'orden': 1,
        'titulo': 'Proveedores y troncales SIP',
        'resumen': 'Aquí registras al carrier y la troncal SIP por donde entran las llamadas. '
                   'Sin una troncal activa, Asterisk no tiene por dónde recibir audio y el resto '
                   'del recorrido nunca llega a ejecutarse.',
        'doc': ('telefonia-sip', 'Telefonía y SIP'),
    },
    '/telefonia/numeros/': {
        'centro': CENTRO_TELEFONIA,
        'orden': 2,
        'titulo': 'Números telefónicos',
        'resumen': 'Cada número E.164 que publicas al cliente se asocia aquí a una troncal y a un '
                   'flujo IVR. Es el enlace entre «alguien marcó» y «qué conversación se ejecuta».',
        'doc': ('telefonia-sip', 'Telefonía y SIP'),
    },
    '/ivr/flujos/': {
        'centro': CENTRO_VOZ,
        'orden': 3,
        'titulo': 'Flujos IVR',
        'resumen': 'El flujo es el guion de la llamada: qué dice la IA, qué datos captura y cuándo '
                   'transfiere. Cada número apunta a un flujo y el motor lo recorre paso a paso.',
        'doc': ('motor-ivr', 'Motor IVR'),
    },
    '/ivr/flujos/*/pasos/': {
        'centro': CENTRO_VOZ,
        'orden': 4,
        'titulo': 'Pasos del flujo',
        'resumen': 'Los pasos son las piezas del guion: mensajes, menús DTMF, capturas de datos, '
                   'consultas al agente IA y la transferencia final. El motor los ejecuta en orden '
                   'hasta colgar o pasar a un asesor.',
        'doc': ('motor-ivr', 'Motor IVR'),
    },
    '/agentes-ia/agentes/': {
        'centro': CENTRO_VOZ,
        'orden': 5,
        'titulo': 'Agentes IA',
        'resumen': 'Cuando un paso es de tipo «agente IA», la pregunta del cliente llega al agente '
                   'configurado aquí: su proveedor, su modelo y su prompt. Es lo que convierte un '
                   'guion rígido en una conversación.',
        'doc': ('agentes-ia', 'Agentes de IA'),
    },
    '/agentes-ia/conocimiento/': {
        'centro': CENTRO_VOZ,
        'orden': 6,
        'titulo': 'Base de conocimiento',
        'resumen': 'Los documentos que subes aquí se indexan y el agente los consulta antes de '
                   'responder (RAG). Es la diferencia entre que la IA improvise y que conteste con '
                   'los datos reales del negocio.',
        'doc': ('agentes-ia', 'Agentes de IA'),
    },
    '/telefonia/asesores/': {
        'centro': CENTRO_TELEFONIA,
        'orden': 7,
        'titulo': 'Asesores humanos',
        'resumen': 'Cuando el flujo llega a un paso de transferencia, la llamada se enruta a uno de '
                   'estos asesores según su disponibilidad. Si ninguno está libre, el flujo aplica '
                   'su respaldo.',
        'doc': ('telefonia-sip', 'Telefonía y SIP'),
    },
    '/llamadas/listado/': {
        'centro': CENTRO_OPERACION,
        'orden': 8,
        'titulo': 'Llamadas',
        'resumen': 'Cierra el recorrido: cada llamada queda registrada con sus turnos, su grabación '
                   'y su resultado. Es donde compruebas si el guion que diseñaste funcionó.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },

    '/clientes/puesta-en-marcha/': {
        'centro': CENTRO_OPERACION,
        'titulo': 'Puesta en marcha',
        'resumen': 'El estado real de los ocho eslabones del recorrido para el cliente activo: qué '
                   'ya está resuelto, qué falta y por qué importa. No se guarda nada, se calcula '
                   'al vuelo, así que siempre coincide con lo que ves en cada pantalla.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/panel/': {
        'centro': CENTRO_OPERACION,
        'titulo': 'Tablero',
        'resumen': 'Resumen del día: llamadas atendidas, transferencias y estado de los motores de '
                   'voz e IA. Si un indicador aparece en rojo, empieza por ahí.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/llamadas/monitor/': {
        'centro': CENTRO_OPERACION,
        'titulo': 'Monitor en vivo',
        'resumen': 'Llamadas en curso en tiempo real, con el turno que el motor está ejecutando en '
                   'ese momento. Sirve para ver el flujo funcionando mientras suena.',
        'doc': ('arquitectura', 'Arquitectura'),
    },
    '/llamadas/contactos/': {
        'centro': CENTRO_OPERACION,
        'titulo': 'Contactos',
        'resumen': 'Quiénes han llamado, con lo que dijeron de sí mismos. No se captura a mano: '
                   'se arma solo al cerrar cada llamada, juntando el número que marcó con lo que '
                   'el flujo capturó y lo que la IA detectó. Un dato que ya existe no se pisa.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/llamadas/transferencias/': {
        'centro': CENTRO_OPERACION,
        'titulo': 'Transferencias',
        'resumen': 'Historial de los pases a asesor humano: quién la tomó, cuánto esperó el cliente '
                   'y si la transferencia llegó a completarse.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/agentes-ia/apikeys/': {
        'centro': CENTRO_VOZ,
        'titulo': 'Llaves de IA',
        'resumen': 'Las credenciales de cada proveedor de IA. Un agente sin llave válida no responde '
                   'y el flujo cae a su respaldo, así que conviene probar la conexión al guardarla.',
        'doc': ('agentes-ia', 'Agentes de IA'),
    },
    '/agentes-ia/consumo/': {
        'centro': CENTRO_VOZ,
        'titulo': 'Consumo de IA',
        'resumen': 'Cuántos tokens gastó cada agente y cuánto margen queda en los planes gratuitos '
                   'de cada proveedor.',
        'doc': ('servicios-gratuitos', 'Servicios gratuitos'),
    },
    '/voz/demo/': {
        'centro': CENTRO_VOZ,
        'titulo': 'Demo de voz',
        'resumen': 'Prueba el pipeline completo —transcripción, agente y síntesis— desde el '
                   'navegador, sin gastar una llamada real ni depender del carrier.',
        'doc': ('arquitectura', 'Arquitectura'),
    },
    '/clientes/listado/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Clientes',
        'resumen': 'Cada cliente es dueño de sus números, flujos, agentes, base de conocimiento y '
                   'asesores: lo que se configura dentro de uno no existe para los demás. Con '
                   '«Trabajar aquí» el panel entero pasa a ese cliente.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/parametros/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Parámetros del sistema',
        'resumen': 'Las perillas del motor que antes vivían en credenciales.json y exigían '
                   'reiniciar: cuánto silencio cierra un turno, cuánta transcripción se le manda '
                   'a la IA interna. Cada una dice qué pasa si la subes o la bajas, y se puede '
                   'volver al valor por defecto de un clic.',
        'doc': ('arquitectura', 'Arquitectura'),
    },
    '/configuracion/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Configuración general',
        'resumen': 'La identidad del sistema: nombre de la empresa, logo y datos de contacto. El '
                   'nombre y el logo se muestran en el menú lateral y en la pantalla de ingreso; '
                   'los minutos incluidos sirven de referencia contra el consumo real.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/doc/': {
        'centro': 'Ayuda',
        'titulo': 'Documentación',
        'resumen': 'Los mismos documentos que viven en la carpeta docs/ del proyecto, servidos '
                   'dentro del panel. Empieza por la Guía de uso si no sabes por dónde arrancar.',
        'doc': ('guia-de-uso', 'Guía de uso'),
    },
    '/perfilpanel/': {
        'centro': 'Ayuda',
        'titulo': 'Mi perfil',
        'resumen': 'Tus datos y tu foto. Desde aquí también se cambia la contraseña, que conviene '
                   'hacer en el primer ingreso si te la entregaron por escrito.',
        'doc': ('seguridad', 'Seguridad'),
    },
    '/seguridad/usuarios/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Usuarios',
        'resumen': 'Quién puede entrar al panel. Cada usuario pertenece a uno o más roles y de ahí '
                   'salen todos sus permisos.',
        'doc': ('seguridad', 'Seguridad'),
    },
    '/seguridad/roles/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Roles',
        'resumen': 'Un rol agrupa los módulos que puede abrir un usuario. La regla del sistema es '
                   'simple: una URL es un permiso.',
        'doc': ('seguridad', 'Seguridad'),
    },
    '/seguridad/modulos/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Módulos del sistema',
        'resumen': 'El catálogo de URLs protegidas. «Sincronizar con las URLs» recorre el proyecto y '
                   'da de alta las que falten, para que ninguna pantalla quede sin permiso.',
        'doc': ('seguridad', 'Seguridad'),
    },
    '/seguridad/secciones/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Secciones del menú',
        'resumen': 'Agrupa los módulos en los bloques del menú lateral. Un módulo sin sección sigue '
                   'protegido, pero no aparece en la barra.',
        'doc': ('seguridad', 'Seguridad'),
    },
    '/seguridad/arbol/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Árbol del menú',
        'resumen': 'Sección, URL y perfil en una sola pantalla. Aquí se marca si cada URL es del '
                   'administrador, del cliente o de ambos, y se mueve de sección sin salir.',
        'doc': ('seguridad', 'Seguridad'),
    },
    '/seguridad/auditoria/': {
        'centro': CENTRO_SEGURIDAD,
        'titulo': 'Auditoría',
        'resumen': 'La bitácora del sistema: quién creó, editó o dio de baja cada registro y cuándo. '
                   'Nada se borra de verdad, solo cambia de estado.',
        'doc': ('seguridad', 'Seguridad'),
    },
}


def _recorrido():
    """Pantallas de la cadena de una llamada, ordenadas por su `orden`."""
    conCadena = [(patron, guia) for patron, guia in GUIAS.items() if guia.get('orden')]
    return sorted(conCadena, key=lambda par: par[1]['orden'])


def _url_visitable(patron):
    """Los patrones con comodín no sirven como enlace; se ofrece la pantalla padre."""
    return patron.split('*')[0] if '*' in patron else patron


def obtener(ruta):
    """Guía de la pantalla, con su posición en el recorrido resuelta."""
    if ruta == '/':
        ruta = '/panel/'
    encontrado = None
    for patron, guia in GUIAS.items():
        if patron == ruta or fnmatch(ruta, patron):
            encontrado = (patron, guia)
            break
    if not encontrado:
        return None

    patron, guia = encontrado
    resuelta = {
        'clave': patron.strip('/').replace('/', '-').replace('*', 'x'),
        'centro': guia['centro'],
        'titulo': guia['titulo'],
        'resumen': guia['resumen'],
        'doc_slug': guia['doc'][0],
        'doc_nombre': guia['doc'][1],
        'paso': None,
        'total': None,
        'antes': None,
        'despues': None,
    }
    if not guia.get('orden'):
        return resuelta

    cadena = _recorrido()
    posicion = [p for p, _ in cadena].index(patron)
    resuelta['paso'] = posicion + 1
    resuelta['total'] = len(cadena)
    if posicion > 0:
        resuelta['antes'] = _vecino(cadena[posicion - 1], ruta)
    if posicion < len(cadena) - 1:
        resuelta['despues'] = _vecino(cadena[posicion + 1], ruta)
    return resuelta


def _vecino(par, ruta):
    """Vecino del recorrido; sin enlace si apunta a la pantalla en la que ya estamos."""
    patron, guia = par
    destino = _url_visitable(patron)
    return {'nombre': guia['titulo'], 'url': None if destino == ruta else destino}
