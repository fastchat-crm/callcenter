"""Alta de un cliente nuevo con todo listo para probar.

Un panel vacío no enseña nada: quien se registra ve ocho pasos pendientes y no
puede ni oír al agente. Por eso el alta deja un flujo mínimo que ya funciona
—saludo, pregunta abierta al agente, despedida— apoyado en la llave por defecto
del operador. Es lo que convierte el registro en una demo en lugar de un
formulario.

Todo lo que se crea aquí es del cliente nuevo, así que no toca a nadie más.
"""
import logging

logger = logging.getLogger('clientes')

PROMPT_INICIAL = (
    'Eres el asistente telefónico de {empresa}. Respondes en español neutro, en máximo dos '
    'oraciones, con tono cordial y directo. Si no sabes algo, lo dices y ofreces pasar con '
    'una persona: nunca inventas datos, precios ni plazos.'
)


def preparar_cliente(cliente, request=None):
    """Crea el agente y el flujo de arranque. De mejor esfuerzo: nunca rompe el alta."""
    try:
        agente = _crear_agente(cliente)
        flujo = _crear_flujo(cliente, agente)
        logger.info('[alta] cliente %s preparado con flujo «%s»', cliente.nombre,
                    getattr(flujo, 'nombre', '—'))
        return flujo
    except Exception:
        logger.exception('[alta] no se pudo preparar el cliente %s', cliente.nombre)
        return None


def _crear_agente(cliente):
    from agentes_ia.models import AgenteIA, ApiKeyIA

    llave = ApiKeyIA.por_defecto_de(cliente)
    if llave is None:
        # Sin llave del operador el agente no podría responder; se deja el flujo
        # igual, que al menos habla con sus textos fijos.
        logger.warning('[alta] no hay llave de IA por defecto; el agente queda sin crear')
        return None
    return AgenteIA.objects.create(
        cliente=cliente,
        nombre=f'Asistente de {cliente.nombre}',
        descripcion=f'Agente inicial creado al registrar a {cliente.nombre}.',
        apikey=llave,
        prompt_sistema=PROMPT_INICIAL.format(empresa=cliente.nombre),
        maximo_oraciones=2,
        activo=True,
    )


def _crear_flujo(cliente, agente):
    from ivr.models import FlujoVoz, PasoVoz

    flujo = FlujoVoz.objects.create(
        cliente=cliente,
        nombre='Recepción',
        descripcion='Flujo de arranque: saluda, escucha y responde con la IA.',
        agente_ia=agente,
        saludo=f'Hola, gracias por llamar a {cliente.nombre}. ¿En qué te puedo ayudar?',
        despedida='Gracias por comunicarte. Que tengas un excelente día.',
        activo=True,
    )
    despedida = PasoVoz.objects.create(
        flujo=flujo, codigo='despedida', nombre='Despedida', tipo='colgar', orden=99,
        texto='Gracias por llamar. Hasta luego.',
    )
    consulta = PasoVoz.objects.create(
        flujo=flujo, codigo='consulta', nombre='Consulta con el agente', tipo='agente_ia',
        orden=10, texto='', agente_ia=agente, paso_siguiente=despedida,
    )
    saludo = PasoVoz.objects.create(
        flujo=flujo, codigo='saludo', nombre='Saludo', tipo='mensaje', orden=1,
        texto=flujo.saludo, paso_siguiente=consulta,
    )
    flujo.paso_inicial = saludo
    flujo.save()
    return flujo
