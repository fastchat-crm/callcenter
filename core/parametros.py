"""Parámetros ajustables en caliente, sin tocar código ni reiniciar.

El catálogo vive aquí —clave, qué hace, tipo y valor por defecto— y en la base
solo se guardan las claves que alguien cambió. Así el valor por defecto siempre
es el del código y restaurar es borrar la fila, no adivinar cuál era.

Para agregar uno: declararlo en CATALOGO y leerlo con `obtener('CLAVE')` allí
donde se use. Si no se lee en ningún lado, no se declara: una pantalla llena de
perillas que no hacen nada es peor que no tenerla.
"""
from django.core.cache import cache

CLAVE_CACHE = 'parametros:valores'
SEGUNDOS_CACHE = 30


class Parametro:
    def __init__(self, clave, etiqueta, descripcion, tipo, defecto, unidad='', grupo=''):
        self.clave = clave
        self.etiqueta = etiqueta
        self.descripcion = descripcion
        self.tipo = tipo                # 'entero' | 'decimal' | 'texto' | 'booleano'
        self.defecto = defecto
        self.unidad = unidad
        self.grupo = grupo


CATALOGO = (
    Parametro(
        'REGISTRO_ABIERTO', 'Permitir que se registren solos', tipo='booleano', defecto=False,
        unidad='1 = sí / 0 = no', grupo='Acceso',
        descripcion='Abre /registro/ para que un interesado cree su propia cuenta y pruebe el '
                    'sistema: se le crea su cliente, su usuario con el rol Cliente y un flujo de '
                    'ejemplo que ya funciona. Con esto encendido, cualquiera que tenga la '
                    'dirección puede crear una cuenta en tu servidor, así que conviene apagarlo '
                    'cuando termines de mostrar el producto.'),
    Parametro(
        'VOZ_STT_MOTOR', 'Motor de reconocimiento de voz', tipo='texto', defecto='faster_whisper',
        grupo='Reconocimiento de voz',
        descripcion='«faster_whisper» transcribe en este servidor: nada sale de aquí, pero '
                    'cuesta cerca de dos segundos por turno en CPU. «groq» usa Whisper '
                    'large-v3 en la nube: baja a 200-400 ms y acierta más, con 8 horas de '
                    'audio gratis al día, pero el audio del cliente viaja a Groq y hace falta '
                    'una llave suya activa. «vosk» es el más liviano y el menos preciso. Si '
                    'Groq falla, la llamada se transcribe local en vez de perder el turno.'),
    Parametro(
        'VOZ_UMBRAL_SILENCIO', 'Umbral de silencio', tipo='entero', defecto=500, unidad='RMS',
        grupo='Detección de fin de turno',
        descripcion='Por debajo de este nivel de energía el audio se considera silencio. '
                    'Subirlo hace al sistema menos sensible al ruido de fondo, pero si se pasa '
                    'deja de oír a quien habla bajito. Bajarlo hace que el ruido de la calle '
                    'parezca voz y el turno no cierre nunca.'),
    Parametro(
        'VOZ_MS_SILENCIO_FIN_TURNO', 'Silencio que cierra el turno', tipo='entero', defecto=800,
        unidad='milisegundos', grupo='Detección de fin de turno',
        descripcion='Cuánto silencio tiene que haber para dar por terminado lo que dijo la '
                    'persona y empezar a procesar. Bajo, la IA interrumpe a quien todavía está '
                    'pensando la frase. Alto, la conversación se siente lenta.'),
    Parametro(
        'VOZ_GRABAR_LLAMADAS', 'Grabar las llamadas', tipo='booleano', defecto=True,
        unidad='1 = sí / 0 = no', grupo='Grabación',
        descripcion='Guarda el audio completo de cada llamada para poder escucharla después. '
                    'Un minuto ocupa unos 60 KB comprimido. Apagarlo no afecta a la '
                    'transcripción ni al resumen, que se siguen guardando.'),
    Parametro(
        'IA_INTERNA_TOKENS_RESUMEN', 'Tokens del resumen de llamada', tipo='entero', defecto=220,
        unidad='tokens', grupo='IA interna',
        descripcion='Cuánto puede extenderse el resumen que se genera al cerrar la llamada. '
                    'Con modelos que razonan, un tope corto se consume pensando y no alcanza a '
                    'escribir el resumen.'),
    Parametro(
        'IA_INTERNA_TOKENS_DATOS', 'Tokens de la detección de datos', tipo='entero', defecto=300,
        unidad='tokens', grupo='IA interna',
        descripcion='Tope para el JSON con los datos de quien llamó (nombre, ciudad, motivo). '
                    'Si se queda corto el JSON llega truncado y no se puede leer.'),
    Parametro(
        'IA_INTERNA_MAX_TRANSCRIPCION', 'Transcripción que se le manda a la IA', tipo='entero',
        defecto=6000, unidad='caracteres', grupo='IA interna',
        descripcion='Cuánto de la transcripción se envía para resumir y detectar datos. Es el '
                    'principal control de costo de estas dos funciones: una llamada larga '
                    'entera puede salir cara y aporta poco al final.'),
)

POR_CLAVE = {parametro.clave: parametro for parametro in CATALOGO}


def grupos():
    """Catálogo agrupado, en el orden en que se declaró."""
    resultado = []
    for parametro in CATALOGO:
        if not resultado or resultado[-1][0] != parametro.grupo:
            resultado.append((parametro.grupo, []))
        resultado[-1][1].append(parametro)
    return resultado


def _valores():
    """Overrides guardados, cacheados: esto se lee en cada turno de voz."""
    valores = cache.get(CLAVE_CACHE)
    if valores is None:
        from core.models import ParametroSistema

        valores = dict(ParametroSistema.objects.filter(status=True).values_list('clave', 'valor'))
        cache.set(CLAVE_CACHE, valores, SEGUNDOS_CACHE)
    return valores


def limpiar_cache():
    cache.delete(CLAVE_CACHE)


def _convertir(parametro, crudo):
    try:
        if parametro.tipo == 'entero':
            return int(crudo)
        if parametro.tipo == 'decimal':
            return float(crudo)
        if parametro.tipo == 'booleano':
            return str(crudo).strip().lower() in ('1', 'true', 'si', 'sí')
        return str(crudo)
    except (TypeError, ValueError):
        return parametro.defecto


def obtener(clave):
    """Valor vigente: el guardado si existe, y si no el del catálogo."""
    parametro = POR_CLAVE.get(clave)
    if parametro is None:
        raise KeyError(f'Parámetro no declarado en el catálogo: {clave}')
    try:
        crudo = _valores().get(clave)
    except Exception:
        # Base sin migrar o cache caída: el sistema sigue con el valor del código.
        return parametro.defecto
    if crudo is None or str(crudo).strip() == '':
        return parametro.defecto
    return _convertir(parametro, crudo)


def guardar(clave, crudo, request=None):
    """Guarda un override, o lo borra si el valor coincide con el defecto."""
    from core.models import ParametroSistema

    parametro = POR_CLAVE.get(clave)
    if parametro is None:
        return
    fila = ParametroSistema.objects.filter(clave=clave).first()
    if str(crudo).strip() == '' or _convertir(parametro, crudo) == parametro.defecto:
        if fila is not None:
            fila.status = False
            fila.save(request) if request is not None else fila.save()
        limpiar_cache()
        return
    if fila is None:
        fila = ParametroSistema(clave=clave)
    fila.valor = str(crudo).strip()
    fila.status = True
    fila.save(request) if request is not None else fila.save()
    limpiar_cache()
