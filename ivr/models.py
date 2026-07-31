"""Motor IVR conversacional: flujos, pasos y opciones.

El flujo es un grafo de pasos. Cada paso hace una sola cosa (hablar, capturar,
consultar al agente IA, transferir, colgar) y declara a donde continuar. El
recorrido concreto de una llamada lo ejecuta `ivr/motor.py`.
"""
from django.db import models

from core.custom_models import ModeloBase

TIPO_PASO_CHOICES = (
    ('mensaje', 'Mensaje hablado'),
    ('menu', 'Menú de opciones (DTMF + voz)'),
    ('captura', 'Captura de dato'),
    ('agente_ia', 'Conversación con agente IA'),
    ('transferencia', 'Transferencia a asesor humano'),
    ('condicion', 'Condición sobre una variable'),
    ('webhook', 'Llamada a API externa'),
    ('colgar', 'Finalizar llamada'),
)

VALIDACION_CHOICES = (
    ('libre', 'Texto libre'),
    ('numero', 'Solo números'),
    ('cedula_ec', 'Cédula ecuatoriana'),
    ('documento', 'Documento genérico (5 a 15 dígitos)'),
    ('telefono', 'Teléfono E.164'),
    ('correo', 'Correo electrónico'),
    ('monto', 'Monto / decimal'),
    ('fecha', 'Fecha'),
    ('si_no', 'Sí / No'),
)

MODO_CAPTURA_CHOICES = (
    ('hibrido', 'Híbrido (teclado o voz)'),
    ('dtmf', 'Solo teclado (DTMF)'),
    ('voz', 'Solo voz'),
)


class FlujoVoz(ModeloBase):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, null=True,
                                related_name='flujos')
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    idioma = models.CharField(max_length=10, default='es')
    agente_ia = models.ForeignKey('agentes_ia.AgenteIA', on_delete=models.SET_NULL, blank=True, null=True,
                                  related_name='flujos',
                                  help_text='Agente que responde las preguntas abiertas del flujo.')
    saludo = models.TextField(default='Hola, gracias por llamar. Soy el asistente virtual, ¿en qué puedo ayudarte?')
    despedida = models.TextField(default='Gracias por comunicarte. Que tengas un excelente día.')
    mensaje_error = models.TextField(default='No te entendí. ¿Puedes repetirlo por favor?')
    paso_inicial = models.ForeignKey('ivr.PasoVoz', on_delete=models.SET_NULL, blank=True, null=True,
                                     related_name='flujos_iniciados')
    asesor_respaldo = models.ForeignKey('telefonia.AsesorHumano', on_delete=models.SET_NULL, blank=True,
                                        null=True, related_name='flujos_respaldo',
                                        help_text='A quién se transfiere si el flujo falla o el cliente lo pide.')
    menu_cae_en_agente = models.BooleanField(
        default=True,
        help_text='Si el cliente dice algo que no coincide con ninguna opción del menú, '
                  'responde el agente IA en lugar de repetir el menú.',
    )
    max_reintentos = models.IntegerField(default=2)
    segundos_espera_respuesta = models.IntegerField(default=8)
    grabar_llamada = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Flujo IVR'
        verbose_name_plural = 'Flujos IVR'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def primer_paso(self):
        if self.paso_inicial_id and self.paso_inicial.status:
            return self.paso_inicial
        return self.pasos.filter(status=True).order_by('orden', 'id').first()


class PasoVoz(ModeloBase):
    flujo = models.ForeignKey(FlujoVoz, on_delete=models.CASCADE, related_name='pasos')
    codigo = models.SlugField(max_length=40, help_text='Identificador corto del paso, ejemplo: menu_principal.')
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15, choices=TIPO_PASO_CHOICES, default='mensaje')
    orden = models.IntegerField(default=1)
    texto = models.TextField(blank=True, null=True,
                             help_text='Lo que dice la IA. Admite variables: {nombre}, {cedula}.')
    audio = models.ForeignKey('telefonia.AudioSistema', on_delete=models.SET_NULL, blank=True, null=True,
                              related_name='pasos', help_text='Audio pregrabado en lugar del TTS.')

    # Captura
    variable = models.SlugField(max_length=40, blank=True, null=True,
                                help_text='Nombre de la variable donde se guarda el dato capturado.')
    validacion = models.CharField(max_length=15, choices=VALIDACION_CHOICES, default='libre')
    modo_captura = models.CharField(max_length=10, choices=MODO_CAPTURA_CHOICES, default='hibrido')
    longitud_minima = models.IntegerField(default=0)
    longitud_maxima = models.IntegerField(default=0)

    # Agente IA
    agente_ia = models.ForeignKey('agentes_ia.AgenteIA', on_delete=models.SET_NULL, blank=True, null=True,
                                  related_name='pasos')
    max_turnos_ia = models.IntegerField(default=8, help_text='Tope de turnos antes de continuar el flujo.')

    # Transferencia
    asesor = models.ForeignKey('telefonia.AsesorHumano', on_delete=models.SET_NULL, blank=True, null=True,
                               related_name='pasos')

    # Condicion / webhook
    expresion = models.CharField(max_length=200, blank=True, null=True,
                                 help_text='Condición evaluada sobre variables, ejemplo: monto > 100.')
    url_webhook = models.CharField(max_length=300, blank=True, null=True)
    metodo_webhook = models.CharField(max_length=6, default='POST')

    paso_siguiente = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True,
                                       related_name='pasos_previos')
    paso_error = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True,
                                   related_name='pasos_error')

    class Meta:
        verbose_name = 'Paso del flujo'
        verbose_name_plural = 'Pasos del flujo'
        ordering = ['flujo', 'orden', 'id']
        unique_together = ('flujo', 'codigo')

    def __str__(self):
        return f'{self.flujo.nombre} · {self.orden}. {self.nombre}'


class OpcionPaso(ModeloBase):
    """Salida de un paso tipo menú: una tecla o unas frases llevan a otro paso."""

    paso = models.ForeignKey(PasoVoz, on_delete=models.CASCADE, related_name='opciones')
    tecla = models.CharField(max_length=2, blank=True, null=True, help_text='Dígito DTMF: 1, 2, 3, 0, *, #.')
    frases = models.CharField(max_length=300, blank=True, null=True,
                              help_text='Frases separadas por coma que activan la opción por voz.')
    etiqueta = models.CharField(max_length=120)
    paso_destino = models.ForeignKey(PasoVoz, on_delete=models.SET_NULL, blank=True, null=True,
                                     related_name='opciones_entrantes')
    orden = models.IntegerField(default=1)

    class Meta:
        verbose_name = 'Opción del menú'
        verbose_name_plural = 'Opciones del menú'
        ordering = ['paso', 'orden', 'id']

    def __str__(self):
        return f'{self.tecla or "voz"} · {self.etiqueta}'

    def lista_frases(self):
        return [frase.strip().lower() for frase in (self.frases or '').split(',') if frase.strip()]
