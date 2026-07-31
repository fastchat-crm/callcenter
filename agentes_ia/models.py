"""Agentes de IA, llaves de proveedor y base de conocimiento (RAG)."""
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify

from core.custom_models import ModeloBase
from core.validadores import validate_file_size_20mb

PROVEEDOR_CHOICES = (
    (1, 'Google Gemini (capa gratuita)'),
    (2, 'Groq (capa gratuita)'),
    (3, 'OpenRouter (modelos :free)'),
    (4, 'Ollama local (auto-hospedado)'),
    (5, 'Compatible con OpenAI'),
    (6, 'Ollama Cloud'),
)

BACKEND_RAG_CHOICES = (
    ('local', 'Local (numpy en el servidor)'),
    ('weaviate', 'Weaviate (multi-tenant)'),
)

MOTOR_EMBEDDINGS_CHOICES = (
    ('gemini', 'Gemini (API, capa gratuita)'),
    ('local', 'Local (sentence-transformers)'),
)

TONO_CHOICES = (
    ('cordial', 'Cordial y cercano'),
    ('formal', 'Formal y corporativo'),
    ('comercial', 'Comercial y persuasivo'),
    ('tecnico', 'Técnico y preciso'),
)


class ApiKeyIA(ModeloBase):
    alias = models.CharField(max_length=80, help_text='Nombre interno de la llave, ejemplo: gemini-produccion.')
    proveedor = models.IntegerField(choices=PROVEEDOR_CHOICES, default=1)
    clave = models.CharField(max_length=300, blank=True, null=True,
                             help_text='Vacío para Ollama local, que no requiere llave.')
    modelo = models.CharField(max_length=120, blank=True, null=True,
                              help_text='Vacío usa el modelo por defecto del proveedor.')
    modelo_embeddings = models.CharField(max_length=120, blank=True, null=True,
                                         help_text='Modelo de embeddings para el RAG. '
                                                   'Solo aplica a proveedores que los ofrecen.')
    base_url = models.CharField(max_length=200, blank=True, null=True,
                                help_text='Endpoint alterno para proveedores auto-hospedados.')
    limite_mensual_llamadas = models.IntegerField(default=0, help_text='0 = sin límite.')
    consumo_tokens_entrada = models.BigIntegerField(default=0, editable=False)
    consumo_tokens_salida = models.BigIntegerField(default=0, editable=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Llave de IA'
        verbose_name_plural = 'Llaves de IA'
        ordering = ['alias']

    def __str__(self):
        return f'{self.alias} · {self.get_proveedor_display()}'

    @property
    def nombre_proveedor(self):
        from agentes_ia.providers import PROVEEDOR_ID_TO_NAME
        return PROVEEDOR_ID_TO_NAME.get(self.proveedor, 'gemini')

    @property
    def clave_enmascarada(self):
        clave = self.clave or ''
        if len(clave) <= 8:
            return '••••'
        return f'{clave[:4]}••••{clave[-4:]}'


class ColeccionConocimiento(ModeloBase):
    """Agrupa los documentos que alimentan el RAG de uno o varios agentes."""

    nombre = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    descripcion = models.TextField(blank=True, null=True)
    backend = models.CharField(max_length=10, choices=BACKEND_RAG_CHOICES, default='local',
                               help_text='Dónde vive el índice vectorial de esta colección.')
    motor_embeddings = models.CharField(max_length=10, choices=MOTOR_EMBEDDINGS_CHOICES,
                                        default='gemini',
                                        help_text='Cómo se vectoriza el texto.')
    apikey_embeddings = models.ForeignKey('agentes_ia.ApiKeyIA', on_delete=models.SET_NULL,
                                          blank=True, null=True, related_name='colecciones',
                                          help_text='Llave usada para generar embeddings '
                                                    '(solo con motor Gemini).')
    fragmentos_indexados = models.IntegerField(default=0, editable=False)
    fecha_indexacion = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        verbose_name = 'Colección de conocimiento'
        verbose_name_plural = 'Colecciones de conocimiento'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)[:140]
        super().save(*args, **kwargs)

    def reindexar(self):
        from django.utils import timezone

        from agentes_ia.rag import indexar_coleccion

        total = indexar_coleccion(self)
        self.fragmentos_indexados = total
        self.fecha_indexacion = timezone.now()
        self.save(update_fields=['fragmentos_indexados', 'fecha_indexacion'])
        return total

    @property
    def descripcion_indice(self):
        if self.backend == 'weaviate':
            return f'Weaviate · tenant coleccion_{self.id} · embeddings {self.motor_embeddings}'
        return f'Local · media/vectorstore/{self.slug} · embeddings {self.motor_embeddings}'


class DocumentoConocimiento(ModeloBase):
    coleccion = models.ForeignKey(ColeccionConocimiento, on_delete=models.CASCADE, related_name='documentos')
    titulo = models.CharField(max_length=200)
    archivo = models.FileField(upload_to='conocimiento/%Y/%m/', blank=True, null=True,
                               validators=[FileExtensionValidator(['pdf', 'txt', 'md', 'docx', 'csv', 'html']),
                                           validate_file_size_20mb])
    contenido = models.TextField(blank=True, null=True,
                                 help_text='Texto plano. Se completa solo al procesar el archivo.')

    class Meta:
        verbose_name = 'Documento de conocimiento'
        verbose_name_plural = 'Documentos de conocimiento'
        ordering = ['titulo']

    def __str__(self):
        return self.titulo


class AgenteIA(ModeloBase):
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True,
                                   help_text='Qué hace este agente y para qué cliente trabaja.')
    apikey = models.ForeignKey(ApiKeyIA, on_delete=models.PROTECT, related_name='agentes')
    coleccion = models.ForeignKey(ColeccionConocimiento, on_delete=models.SET_NULL, blank=True, null=True,
                                  related_name='agentes')
    prompt_sistema = models.TextField(
        default=(
            'Eres un asistente telefónico. Respondes en español neutro, en máximo dos oraciones '
            'cortas, con lenguaje natural para ser escuchado por teléfono. Nunca inventas datos: '
            'si no está en el contexto, ofreces transferir con un asesor.'
        ),
    )
    tono = models.CharField(max_length=15, choices=TONO_CHOICES, default='cordial')
    idioma = models.CharField(max_length=10, default='es')
    temperatura = models.FloatField(default=0.3)
    max_tokens_respuesta = models.IntegerField(default=220)
    maximo_oraciones = models.IntegerField(default=2, help_text='Tope de oraciones por respuesta hablada.')
    usar_rag = models.BooleanField(default=True)
    fragmentos_contexto = models.IntegerField(default=4)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Agente IA'
        verbose_name_plural = 'Agentes IA'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class ConsumoIA(ModeloBase):
    """Consumo por turno, para calcular costo y detectar agentes caros."""

    agente = models.ForeignKey(AgenteIA, on_delete=models.CASCADE, related_name='consumos')
    llamada = models.ForeignKey('llamadas.Llamada', on_delete=models.SET_NULL, blank=True, null=True,
                                related_name='consumos_ia')
    apikey = models.ForeignKey(ApiKeyIA, on_delete=models.SET_NULL, blank=True, null=True,
                               related_name='consumos')
    modelo = models.CharField(max_length=120, blank=True, null=True)
    proveedor = models.CharField(max_length=20, blank=True, null=True)
    tokens_entrada = models.IntegerField(default=0)
    tokens_salida = models.IntegerField(default=0)
    latencia_ms = models.IntegerField(default=0)
    costo_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0,
                                    help_text='Estimado según el tarifario del proveedor.')
    uso_rag = models.BooleanField(default=False)
    error = models.CharField(max_length=200, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Consumo de IA'
        verbose_name_plural = 'Consumos de IA'
        ordering = ['-fecha']
        indexes = [models.Index(fields=['-fecha', 'agente'])]

    def __str__(self):
        return f'{self.agente} {self.tokens_entrada}/{self.tokens_salida}'

    @property
    def tokens_total(self):
        return (self.tokens_entrada or 0) + (self.tokens_salida or 0)
