"""Estado de la puesta en marcha de un cliente.

Recorre la misma cadena que describe `core/guias.py` y para cada eslabón dice si
ya está resuelto, con el detalle concreto de lo que hay o de lo que falta. No
guarda nada: se calcula al vuelo desde los datos reales, así que nunca queda
desactualizado respecto de lo que el usuario ve en cada pantalla.
"""


def _paso(orden, titulo, url, listo, detalle, ayuda):
    return {'orden': orden, 'titulo': titulo, 'url': url, 'listo': listo,
            'detalle': detalle, 'ayuda': ayuda}


def _proveedores(cliente):
    """Por dónde entra el audio. Hay dos caminos y solo hace falta uno.

    Con un carrier de Media Streams (Twilio, Telnyx) la llamada llega por
    WebSocket y **no existe ninguna troncal SIP**: exigirla marcaba en rojo un
    paso que ese camino nunca va a cumplir.
    """
    from telefonia.models import DRIVERS_MEDIA_STREAMS, ProveedorTelefonia, TroncalSIP

    # Proveedores y troncales son infraestructura del operador: se comparten
    # entre clientes, por eso no se filtran por cliente.
    proveedores = ProveedorTelefonia.objects.filter(status=True, activo=True)
    carriers = [p for p in proveedores
                if p.driver in DRIVERS_MEDIA_STREAMS and p.driver != 'asterisk']
    con_troncal = TroncalSIP.objects.filter(status=True, activo=True).count()

    if carriers:
        listo, detalle = True, f'{len(carriers)} carrier(s) por WebSocket: no necesitan troncal SIP'
    elif con_troncal:
        listo, detalle = True, f'{con_troncal} troncal(es) SIP activas'
    elif proveedores.exists():
        listo, detalle = False, 'Hay proveedor, pero ni troncal SIP ni carrier configurado'
    else:
        listo, detalle = False, 'Sin proveedor de telefonía'
    return _paso(1, 'Proveedor de telefonía', '/telefonia/proveedores/', listo, detalle,
                 'Es por donde entra el audio: un carrier como Telnyx, o una troncal SIP propia '
                 'si prefieres administrar Asterisk.')


def _numeros(cliente):
    from telefonia.models import NumeroTelefonico

    numeros = NumeroTelefonico.objects.filter(status=True, activo=True, cliente=cliente)
    total = numeros.count()
    con_flujo = numeros.filter(flujo__isnull=False).count()
    listo = con_flujo > 0
    if not total:
        detalle = 'Este cliente todavía no tiene números'
    elif listo:
        detalle = f'{total} número(s), {con_flujo} con flujo asignado'
    else:
        detalle = f'{total} número(s), pero ninguno apunta a un flujo'
    return _paso(2, 'Números telefónicos', '/telefonia/numeros/', listo, detalle,
                 'Un cliente puede tener N números; cada uno decide qué flujo lo atiende.')


def _flujos(cliente):
    from ivr.models import FlujoVoz

    flujos = FlujoVoz.objects.filter(status=True, activo=True, cliente=cliente)
    total = flujos.count()
    return _paso(3, 'Flujos IVR', '/ivr/flujos/', total > 0,
                 f'{total} flujo(s) activo(s)' if total else 'Sin flujos activos',
                 'El flujo es el guion de la llamada: qué dice la IA y cuándo transfiere.')


def _pasos(cliente):
    from ivr.models import FlujoVoz, PasoVoz

    flujos = FlujoVoz.objects.filter(status=True, activo=True, cliente=cliente)
    primero = flujos.order_by('id').first()
    con_pasos = [f for f in flujos if PasoVoz.objects.filter(status=True, flujo=f).exists()]
    sin_pasos = [f.nombre for f in flujos if f not in con_pasos]
    listo = bool(con_pasos)
    if not primero:
        detalle = 'Primero hace falta un flujo'
    elif sin_pasos:
        detalle = f'Sin pasos: {", ".join(sin_pasos[:3])}'
    else:
        total = PasoVoz.objects.filter(status=True, flujo__in=flujos).count()
        detalle = f'{total} paso(s) en {len(con_pasos)} flujo(s)'
    url = f'/ivr/flujos/{primero.id}/pasos/' if primero else '/ivr/flujos/'
    return _paso(4, 'Pasos del flujo', url, listo, detalle,
                 'Mensajes, menús, capturas, consulta a la IA y transferencia, en orden.')


def _agentes(cliente):
    from agentes_ia.models import AgenteIA

    agentes = AgenteIA.objects.filter(status=True, activo=True, cliente=cliente).select_related('apikey')
    total = agentes.count()
    sin_llave = [a.nombre for a in agentes if not a.apikey_id or not a.apikey.activo]
    listo = total > 0 and not sin_llave
    if not total:
        detalle = 'Sin agentes de IA'
    elif sin_llave:
        detalle = f'Sin llave activa: {", ".join(sin_llave[:3])}'
    else:
        detalle = f'{total} agente(s) con llave activa'
    return _paso(5, 'Agente IA', '/agentes-ia/agentes/', listo, detalle,
                 'Es quien responde las preguntas abiertas. Sin llave válida, el flujo cae a su '
                 'respaldo. La opción gratuita recomendada es Groq con llama-3.1-8b-instant.')


def _conocimiento(cliente):
    from agentes_ia.models import ColeccionConocimiento

    colecciones = ColeccionConocimiento.objects.filter(status=True, cliente=cliente)
    total = colecciones.count()
    indexadas = [c for c in colecciones if (c.fragmentos_indexados or 0) > 0]
    listo = bool(indexadas)
    if not total:
        detalle = 'Sin colecciones de conocimiento'
    elif not indexadas:
        detalle = f'{total} colección(es), ninguna indexada'
    else:
        fragmentos = sum(c.fragmentos_indexados for c in indexadas)
        detalle = f'{len(indexadas)} colección(es) indexada(s) · {fragmentos} fragmentos'
    return _paso(6, 'Base de conocimiento', '/agentes-ia/conocimiento/', listo, detalle,
                 'Sin indexar, el agente no ve los documentos y responde de memoria.')


def _asesores(cliente):
    from telefonia.models import AsesorHumano

    total = AsesorHumano.objects.filter(status=True, cliente=cliente).count()
    return _paso(7, 'Asesores humanos', '/telefonia/asesores/', total > 0,
                 f'{total} asesor(es)' if total else 'Sin asesores para transferir',
                 'Sin asesor de respaldo, la IA cierra la llamada en lugar de escalarla.')


def _llamadas(cliente):
    from llamadas.models import Llamada

    total = Llamada.objects.filter(status=True, cliente=cliente).count()
    return _paso(8, 'Primera llamada', '/llamadas/listado/', total > 0,
                 f'{total} llamada(s) registrada(s)' if total else 'Todavía no entró ninguna llamada',
                 'Cierra el recorrido: aquí ves la transcripción, la duración y el resumen.')


COMPROBACIONES = (_proveedores, _numeros, _flujos, _pasos, _agentes, _conocimiento,
                  _asesores, _llamadas)


def estado(cliente):
    """Los ocho eslabones del recorrido, resueltos para este cliente."""
    if cliente is None:
        return {'pasos': [], 'listos': 0, 'total': 0, 'porcentaje': 0, 'siguiente': None}

    pasos = [comprobar(cliente) for comprobar in COMPROBACIONES]
    listos = sum(1 for paso in pasos if paso['listo'])
    pendientes = [paso for paso in pasos if not paso['listo']]
    return {
        'pasos': pasos,
        'listos': listos,
        'total': len(pasos),
        'porcentaje': round(100 * listos / len(pasos)) if pasos else 0,
        'siguiente': pendientes[0] if pendientes else None,
    }
