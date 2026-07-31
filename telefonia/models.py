"""Capa de telefonia: proveedores, troncales SIP, numeros y asesores humanos.

Diseñado multipais desde el dia uno: un numero se describe por su E.164 y su
ISO de pais, y el `driver` del proveedor decide como se contesta la llamada.
Agregar un pais nuevo = crear un registro de NumeroTelefonico, sin tocar codigo.
"""
from django.core.validators import FileExtensionValidator
from django.db import models

from core.custom_models import ModeloBase
from core.validadores import validar_e164, validate_file_size_2mb

DRIVER_CHOICES = (
    ('asterisk', 'Asterisk / FreeSWITCH auto-hospedado (gratuito)'),
    ('sip_generico', 'Troncal SIP genérica'),
    ('twilio', 'Twilio'),
    ('telnyx', 'Telnyx'),
    ('plivo', 'Plivo'),
    ('signalwire', 'SignalWire'),
    ('webrtc', 'WebRTC / navegador (pruebas)'),
)

# Drivers que hablan el protocolo Media Streams (audio en tiempo real por WebSocket).
DRIVERS_MEDIA_STREAMS = ('twilio', 'telnyx', 'plivo', 'signalwire', 'asterisk', 'webrtc')

TIPO_NUMERO_CHOICES = (
    ('local', 'Local / fijo'),
    ('movil', 'Móvil'),
    ('tollfree', 'Toll free (0800)'),
    ('nacional', 'Nacional'),
)

TRANSPORTE_CHOICES = (
    ('udp', 'UDP'),
    ('tcp', 'TCP'),
    ('tls', 'TLS'),
    ('wss', 'WSS (WebRTC)'),
)


class ProveedorTelefonia(ModeloBase):
    nombre = models.CharField(max_length=80)
    driver = models.CharField(max_length=20, choices=DRIVER_CHOICES, default='asterisk',
                              help_text='Determina cómo se contesta la llamada y cómo se envía el audio.')
    base_url = models.CharField(max_length=200, blank=True, null=True,
                                help_text='Endpoint de la API del proveedor. Vacío para Asterisk local.')
    cuenta_sid = models.CharField(max_length=120, blank=True, null=True,
                                  help_text='Account SID / API user del proveedor.')
    token = models.CharField(max_length=200, blank=True, null=True,
                             help_text='Auth token / API key del proveedor.')
    activo = models.BooleanField(default=True)
    costo_minuto_entrante = models.DecimalField(max_digits=8, decimal_places=4, default=0,
                                                help_text='Costo por minuto entrante en USD (0 si es auto-hospedado).')
    costo_mensual_did = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notas = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Proveedor de telefonía'
        verbose_name_plural = 'Proveedores de telefonía'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.get_driver_display()})'

    @property
    def soporta_media_streams(self):
        return self.driver in DRIVERS_MEDIA_STREAMS

    @property
    def es_gratuito(self):
        return self.driver in ('asterisk', 'webrtc')


class TroncalSIP(ModeloBase):
    """Registro de troncal para el driver auto-hospedado (Asterisk/FreeSWITCH)."""

    proveedor = models.ForeignKey(ProveedorTelefonia, on_delete=models.CASCADE, related_name='troncales')
    nombre = models.CharField(max_length=80)
    host = models.CharField(max_length=120)
    puerto = models.IntegerField(default=5060)
    transporte = models.CharField(max_length=5, choices=TRANSPORTE_CHOICES, default='udp')
    usuario = models.CharField(max_length=120, blank=True, null=True)
    clave = models.CharField(max_length=200, blank=True, null=True)
    contexto = models.CharField(max_length=80, default='desde-troncal',
                                help_text='Contexto del dialplan de Asterisk que recibe las llamadas.')
    codec_preferido = models.CharField(max_length=20, default='alaw',
                                       help_text='alaw/ulaw para telefonía tradicional, opus para WebRTC.')
    registrar = models.BooleanField(default=True, help_text='Enviar REGISTER al proveedor.')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Troncal SIP'
        verbose_name_plural = 'Troncales SIP'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} → {self.host}:{self.puerto}/{self.transporte}'


class NumeroTelefonico(ModeloBase):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, null=True,
                                related_name='numeros', help_text='Dueño de este número.')
    numero = models.CharField(max_length=20, unique=True, validators=[validar_e164],
                              help_text='Formato internacional E.164, ejemplo +593987654321.')
    pais_iso = models.CharField(max_length=2, default='EC', help_text='ISO 3166-1 alfa-2: EC, US, ES, MX, CO.')
    prefijo_pais = models.CharField(max_length=5, default='593')
    ciudad = models.CharField(max_length=80, blank=True, null=True)
    tipo = models.CharField(max_length=10, choices=TIPO_NUMERO_CHOICES, default='local')
    proveedor = models.ForeignKey(ProveedorTelefonia, on_delete=models.PROTECT, related_name='numeros')
    troncal = models.ForeignKey(TroncalSIP, on_delete=models.SET_NULL, blank=True, null=True,
                                related_name='numeros')
    flujo = models.ForeignKey('ivr.FlujoVoz', on_delete=models.SET_NULL, blank=True, null=True,
                              related_name='numeros', help_text='Flujo IVR que atiende este número.')
    idioma = models.CharField(max_length=10, default='es',
                              help_text='Idioma de atención: es, en, pt. Define STT y voz TTS.')
    zona_horaria = models.CharField(max_length=60, default='America/Guayaquil')
    concurrencia_maxima = models.IntegerField(default=4,
                                              help_text='Llamadas simultáneas permitidas en este número.')
    minutos_incluidos = models.IntegerField(default=3500)
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Número telefónico'
        verbose_name_plural = 'Números telefónicos'
        ordering = ['pais_iso', 'numero']

    def __str__(self):
        return f'{self.numero} [{self.pais_iso}]'

    @property
    def llamadas_en_curso(self):
        from llamadas.models import Llamada
        return Llamada.objects.filter(numero_destino=self.numero, estado='en_curso').count()

    @property
    def tiene_cupo(self):
        return self.llamadas_en_curso < self.concurrencia_maxima


HORARIO_CHOICES = (
    ('siempre', '24/7'),
    ('laboral', 'Lunes a viernes 08:00 - 18:00'),
    ('extendido', 'Lunes a sábado 08:00 - 20:00'),
)


class AsesorHumano(ModeloBase):
    """Destino de la transferencia cuando la IA decide escalar."""

    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, null=True,
                                related_name='asesores')
    nombre = models.CharField(max_length=120)
    numero_destino = models.CharField(max_length=20, blank=True, null=True, validators=[validar_e164],
                                      help_text='Celular o fijo en E.164 al que se reenvía la llamada.')
    extension_sip = models.CharField(max_length=40, blank=True, null=True,
                                     help_text='Extensión interna del softphone, ejemplo 1001.')
    correo = models.EmailField(blank=True, null=True)
    departamento = models.CharField(max_length=80, blank=True, null=True)
    horario = models.CharField(max_length=15, choices=HORARIO_CHOICES, default='laboral')
    prioridad = models.IntegerField(default=1, help_text='Menor número = se intenta primero.')
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Asesor humano'
        verbose_name_plural = 'Asesores humanos'
        ordering = ['prioridad', 'nombre']

    def __str__(self):
        return f'{self.nombre} ({self.numero_destino or self.extension_sip or "sin destino"})'


class AudioSistema(ModeloBase):
    """Audios pregrabados opcionales (saludo institucional, música de espera)."""

    nombre = models.CharField(max_length=120)
    archivo = models.FileField(upload_to='audios/%Y/%m/',
                               validators=[FileExtensionValidator(['wav', 'mp3', 'ogg']),
                                           validate_file_size_2mb])
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        verbose_name = 'Audio del sistema'
        verbose_name_plural = 'Audios del sistema'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
