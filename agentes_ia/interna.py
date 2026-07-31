"""Funciones internas de IA: resumen de la llamada y detección de datos.

Corren con el **token global** de Configuración general, no con la llave del
cliente: son trabajo del sistema, no del agente que atendió. Así el consumo de
un cliente no se gasta en tareas que pidió el operador, y el resumen sigue
saliendo aunque el cliente todavía no tenga llave propia.

Todo aquí es de mejor esfuerzo: si no hay token, si el proveedor falla o si
devuelve algo que no se puede leer, la llamada ya quedó cerrada y guardada
igual. Nunca se propaga una excepción al cierre.
"""
import json
import logging
import re

logger = logging.getLogger('agentes_ia')


# Prefijo telefónico → ISO del país. Cubre los países donde opera el sistema;
# lo que no esté aquí simplemente no se deduce.
PREFIJOS_PAIS = (
    ('593', 'EC'), ('57', 'CO'), ('51', 'PE'), ('56', 'CL'), ('54', 'AR'),
    ('55', 'BR'), ('52', 'MX'), ('34', 'ES'), ('1', 'US'), ('507', 'PA'),
    ('502', 'GT'), ('503', 'SV'), ('504', 'HN'), ('505', 'NI'), ('506', 'CR'),
    ('591', 'BO'), ('595', 'PY'), ('598', 'UY'), ('58', 'VE'),
)

PROMPT_RESUMEN = (
    'Resume esta llamada telefónica en español, en máximo tres oraciones. '
    'Di qué necesitaba quien llamó y cómo terminó la llamada. '
    'Usa solo lo que aparece en la transcripción: no supongas ni agregues nada. '
    'Responde únicamente con el resumen, sin encabezados ni viñetas.'
)

PROMPT_DATOS = (
    'De la siguiente transcripción telefónica, extrae los datos de la persona que llamó.\n'
    'Responde SOLO con un objeto JSON, sin texto alrededor y sin bloque de código, con estas claves:\n'
    '  "nombre": nombre de quien llamó, o null\n'
    '  "ciudad": ciudad o sector que mencionó, o null\n'
    '  "correo": correo que dictó, o null\n'
    '  "identificacion": cédula o RUC que dictó, o null\n'
    '  "motivo": en pocas palabras, para qué llamaba, o null\n'
    'Regla estricta: si un dato no fue dicho explícitamente, pon null. '
    'No inventes, no deduzcas y no completes datos parciales.'
)


def _configuracion():
    from core.models import Configuracion

    configuracion = Configuracion.get_instancia()
    token = (configuracion.token_ia_interna or '').strip()
    return configuracion, token


def disponible() -> bool:
    """Hay token global configurado (o el proveedor no necesita uno)."""
    try:
        from agentes_ia.providers import get_provider

        configuracion, token = _configuracion()
        proveedor = get_provider(int(configuracion.proveedor_ia_interna or 1))
        return bool(token) or not proveedor.requiere_apikey
    except Exception:
        return False


def _preguntar(instruccion: str, contenido: str, max_tokens: int = 400) -> str:
    from agentes_ia.providers import get_provider

    configuracion, token = _configuracion()
    proveedor = get_provider(int(configuracion.proveedor_ia_interna or 1))
    if not token and proveedor.requiere_apikey:
        return ''

    respuesta = proveedor.responder(
        [{'role': 'system', 'content': instruccion},
         {'role': 'user', 'content': contenido}],
        apikey=token,
        modelo=(configuracion.modelo_ia_interna or ''),
        temperatura=0.1,
        max_tokens=max_tokens,
    )
    if not respuesta.ok:
        logger.warning('[ia-interna] el proveedor no respondió: %s', respuesta.error or 'sin texto')
        return ''
    return (respuesta.texto or '').strip()


def _tope_transcripcion():
    from core.parametros import obtener

    return obtener('IA_INTERNA_MAX_TRANSCRIPCION')


def _transcripcion(llamada) -> str:
    texto = (llamada.transcripcion or '').strip()
    if texto:
        return texto[:_tope_transcripcion()]
    lineas = [
        f"{'Cliente' if turno.rol == 'cliente' else 'Asistente'}: {turno.texto}"
        for turno in llamada.turnos.filter(status=True).order_by('fecha', 'id')
        if (turno.texto or '').strip()
    ]
    return '\n'.join(lineas)[:_tope_transcripcion()]


def pais_por_numero(numero: str) -> str:
    """ISO del país deducido del prefijo. Determinista y sin costo."""
    digitos = re.sub(r'\D', '', numero or '')
    if not digitos:
        return ''
    # De más largo a más corto: 593 antes que 59, 1 al final.
    for prefijo, iso in sorted(PREFIJOS_PAIS, key=lambda par: -len(par[0])):
        if digitos.startswith(prefijo):
            return iso
    return ''


def _json_de(texto: str) -> dict:
    """Lee el JSON de la respuesta aunque venga envuelto en explicaciones."""
    if not texto:
        return {}
    limpio = re.sub(r'^```(?:json)?|```$', '', texto.strip(), flags=re.MULTILINE).strip()
    try:
        datos = json.loads(limpio)
    except ValueError:
        llaves = re.search(r'\{.*\}', limpio, flags=re.DOTALL)
        if not llaves:
            return {}
        try:
            datos = json.loads(llaves.group(0))
        except ValueError:
            return {}
    return datos if isinstance(datos, dict) else {}


def resumir_llamada(llamada) -> str:
    transcripcion = _transcripcion(llamada)
    if not transcripcion:
        return ''
    from core.parametros import obtener

    return _preguntar(PROMPT_RESUMEN, transcripcion,
                      max_tokens=obtener('IA_INTERNA_TOKENS_RESUMEN'))


def extraer_datos_llamada(llamada) -> dict:
    """Datos que la persona dijo en voz alta. Los vacíos no se devuelven."""
    transcripcion = _transcripcion(llamada)
    if not transcripcion:
        return {}
    from core.parametros import obtener

    datos = _json_de(_preguntar(PROMPT_DATOS, transcripcion,
                                max_tokens=obtener('IA_INTERNA_TOKENS_DATOS')))

    limpios = {}
    for clave in ('nombre', 'ciudad', 'correo', 'identificacion', 'motivo'):
        valor = datos.get(clave)
        if valor is None:
            continue
        valor = str(valor).strip()
        if valor and valor.lower() not in ('null', 'none', 'n/a', 'no dice', 'no menciona', ''):
            limpios[clave] = valor[:200]
    return limpios


def procesar_cierre(llamada):
    """Llena resumen, país y datos detectados. De mejor esfuerzo: nunca lanza."""
    campos = []
    try:
        # El país sale del prefijo marcado y no cuesta nada, así que se intenta
        # aunque no haya token de IA.
        if not (llamada.pais_iso or '').strip():
            iso = pais_por_numero(llamada.numero_origen)
            if iso:
                llamada.pais_iso = iso
                campos.append('pais_iso')

        if disponible():
            if not (llamada.resumen or '').strip():
                resumen = resumir_llamada(llamada)
                if resumen:
                    llamada.resumen = resumen
                    campos.append('resumen')

            detectados = extraer_datos_llamada(llamada)
            if detectados:
                # Lo que el flujo capturó explícitamente manda sobre lo deducido.
                capturados = dict(llamada.datos_capturados or {})
                for clave, valor in detectados.items():
                    capturados.setdefault(f'ia_{clave}', valor)
                llamada.datos_capturados = capturados
                campos.append('datos_capturados')

        if campos:
            llamada.save(update_fields=campos)
    except Exception:
        logger.exception('[ia-interna] no se pudo procesar el cierre de la llamada %s',
                         getattr(llamada, 'id', '?'))
    return campos
