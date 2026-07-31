"""Registro operativo de llamadas: sesión, turnos, grabación y transferencias."""
from django.core.validators import FileExtensionValidator
from django.db import models

from core.custom_models import ModeloBase
from core.validadores import validate_file_size_50mb

ESTADO_LLAMADA_CHOICES = (
    ('iniciando', 'Iniciando'),
    ('en_curso', 'En curso'),
    ('transfiriendo', 'Transfiriendo'),
    ('finalizada', 'Finalizada'),
    ('fallida', 'Fallida'),
)

RESULTADO_CHOICES = (
    ('pendiente', 'Pendiente'),
    ('resuelta_ia', 'Resuelta por la IA'),
    ('transferida', 'Transferida a asesor'),
    ('abandonada', 'Abandonada por el cliente'),
    ('error', 'Error técnico'),
)

SENTIDO_CHOICES = (
    ('entrante', 'Entrante'),
    ('saliente', 'Saliente'),
)

ROL_TURNO_CHOICES = (
    ('cliente', 'Cliente'),
    ('ia', 'IA'),
    ('sistema', 'Sistema'),
    ('asesor', 'Asesor'),
)


class Llamada(ModeloBase):
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.PROTECT, null=True,
                                related_name='llamadas', db_index=True,
                                help_text='Se copia del número al iniciar la llamada.')
    sentido = models.CharField(max_length=10, choices=SENTIDO_CHOICES, default='entrante')
    numero = models.ForeignKey('telefonia.NumeroTelefonico', on_delete=models.SET_NULL, blank=True,
                               null=True, related_name='llamadas')
    driver = models.CharField(max_length=20, default='asterisk',
                              help_text='Driver del proveedor que originó la llamada.')
    call_id = models.CharField(max_length=120, blank=True, null=True, db_index=True,
                               help_text='Identificador de la llamada en el carrier (CallSid, Call-ID SIP).')
    stream_sid = models.CharField(max_length=120, blank=True, null=True, db_index=True,
                                  help_text='Identificador del stream de audio en tiempo real.')
    numero_origen = models.CharField(max_length=25, blank=True, null=True, db_index=True)
    numero_destino = models.CharField(max_length=25, blank=True, null=True, db_index=True)
    pais_iso = models.CharField(max_length=2, blank=True, null=True)
    idioma = models.CharField(max_length=10, default='es')

    flujo = models.ForeignKey('ivr.FlujoVoz', on_delete=models.SET_NULL, blank=True, null=True,
                              related_name='llamadas')
    agente_ia = models.ForeignKey('agentes_ia.AgenteIA', on_delete=models.SET_NULL, blank=True, null=True,
                                  related_name='llamadas')
    paso_actual = models.CharField(max_length=40, blank=True, null=True)

    estado = models.CharField(max_length=15, choices=ESTADO_LLAMADA_CHOICES, default='iniciando', db_index=True)
    resultado = models.CharField(max_length=15, choices=RESULTADO_CHOICES, default='pendiente')
    fecha_inicio = models.DateTimeField(auto_now_add=True, db_index=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    duracion_segundos = models.IntegerField(default=0)

    datos_capturados = models.JSONField(default=dict, blank=True,
                                        help_text='Variables recogidas durante el flujo: cédula, nombre, etc.')
    resumen = models.TextField(blank=True, null=True, help_text='Resumen generado por la IA al cerrar.')
    transcripcion = models.TextField(blank=True, null=True)
    latencia_promedio_ms = models.IntegerField(default=0)
    costo_estimado = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    notas = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Llamada'
        verbose_name_plural = 'Llamadas'
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['estado', '-fecha_inicio']),
            models.Index(fields=['numero_origen']),
        ]

    def __str__(self):
        return f'Llamada {self.id} · {self.numero_origen or "desconocido"} [{self.estado}]'

    @property
    def duracion_texto(self):
        from core.funciones import formato_duracion
        return formato_duracion(self.duracion_segundos)

    @property
    def minutos(self):
        return round((self.duracion_segundos or 0) / 60, 2)

    def cerrar(self, resultado='resuelta_ia'):
        from django.utils import timezone

        self.fecha_fin = timezone.now()
        if self.fecha_inicio:
            self.duracion_segundos = int((self.fecha_fin - self.fecha_inicio).total_seconds())
        self.estado = 'finalizada'
        self.resultado = resultado
        self.save(update_fields=['fecha_fin', 'duracion_segundos', 'estado', 'resultado'])


class TurnoLlamada(ModeloBase):
    llamada = models.ForeignKey(Llamada, on_delete=models.CASCADE, related_name='turnos')
    rol = models.CharField(max_length=10, choices=ROL_TURNO_CHOICES)
    texto = models.TextField(blank=True, null=True)
    paso_codigo = models.CharField(max_length=40, blank=True, null=True)
    dtmf = models.CharField(max_length=20, blank=True, null=True)
    audio = models.FileField(upload_to='turnos/%Y/%m/', blank=True, null=True,
                             validators=[FileExtensionValidator(['wav', 'mp3', 'ogg'])])
    latencia_stt_ms = models.IntegerField(default=0)
    latencia_llm_ms = models.IntegerField(default=0)
    latencia_tts_ms = models.IntegerField(default=0)
    latencia_ms = models.IntegerField(default=0)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Turno de la llamada'
        verbose_name_plural = 'Turnos de la llamada'
        ordering = ['fecha', 'id']

    def __str__(self):
        return f'[{self.rol}] {(self.texto or "")[:50]}'


class GrabacionLlamada(ModeloBase):
    llamada = models.OneToOneField(Llamada, on_delete=models.CASCADE, related_name='grabacion')
    archivo = models.FileField(upload_to='grabaciones/%Y/%m/',
                               validators=[FileExtensionValidator(['wav', 'mp3', 'ogg']),
                                           validate_file_size_50mb])
    formato = models.CharField(max_length=10, default='wav')
    tamano_bytes = models.BigIntegerField(default=0)
    almacenamiento = models.CharField(max_length=20, default='local',
                                      help_text='local, minio o s3 según la configuración del despliegue.')

    class Meta:
        verbose_name = 'Grabación'
        verbose_name_plural = 'Grabaciones'

    def __str__(self):
        return f'Grabación llamada {self.llamada_id}'


MOTIVO_TRANSFERENCIA_CHOICES = (
    ('solicitud_cliente', 'El cliente pidió un asesor'),
    ('paso_flujo', 'El flujo lo indica'),
    ('reintentos_agotados', 'No se entendió al cliente'),
    ('fuera_alcance', 'Consulta fuera del alcance de la IA'),
    ('error_tecnico', 'Error técnico'),
)

ESTADO_TRANSFERENCIA_CHOICES = (
    ('solicitada', 'Solicitada'),
    ('en_curso', 'En curso'),
    ('atendida', 'Atendida'),
    ('no_contestada', 'No contestada'),
    ('fallida', 'Fallida'),
)


class TransferenciaLlamada(ModeloBase):
    llamada = models.ForeignKey(Llamada, on_delete=models.CASCADE, related_name='transferencias')
    asesor = models.ForeignKey('telefonia.AsesorHumano', on_delete=models.SET_NULL, blank=True, null=True,
                               related_name='transferencias')
    motivo = models.CharField(max_length=25, choices=MOTIVO_TRANSFERENCIA_CHOICES, default='solicitud_cliente')
    estado = models.CharField(max_length=15, choices=ESTADO_TRANSFERENCIA_CHOICES, default='solicitada')
    destino = models.CharField(max_length=40, blank=True, null=True,
                               help_text='Número o extensión efectivamente marcada.')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_atencion = models.DateTimeField(blank=True, null=True)
    detalle = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Transferencia'
        verbose_name_plural = 'Transferencias'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f'Transferencia llamada {self.llamada_id} → {self.asesor or self.destino}'
