"""Modelos transversales: bitacora de acciones y configuracion del sistema."""
from django.conf import settings
from django.db import models

from core.custom_models import ModeloBase

ACCION_CHOICES = (
    ('add', 'Creación'),
    ('change', 'Edición'),
    ('del', 'Eliminación'),
    ('login', 'Inicio de sesión'),
    ('logout', 'Cierre de sesión'),
    ('info', 'Información'),
    ('error', 'Error'),
)


class Bitacora(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                blank=True, null=True, related_name='bitacoras')
    accion = models.CharField(max_length=15, choices=ACCION_CHOICES, default='info')
    descripcion = models.TextField()
    ruta = models.CharField(max_length=255, blank=True, null=True)
    ip = models.CharField(max_length=60, blank=True, null=True)
    objeto_id = models.IntegerField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de bitácora'
        verbose_name_plural = 'Bitácora'
        ordering = ['-fecha']

    def __str__(self):
        return f'[{self.accion}] {self.descripcion[:60]}'


class Configuracion(ModeloBase):
    """Parametros editables del sistema (una sola fila)."""

    nombre_empresa = models.CharField(max_length=120, default='Callcenter IA')
    logo = models.ImageField(upload_to='configuracion/', blank=True, null=True)
    zona_horaria = models.CharField(max_length=60, default='America/Guayaquil')
    minutos_incluidos_mes = models.IntegerField(default=3500)
    correo_notificaciones = models.EmailField(blank=True, null=True)
    telefono_soporte = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        verbose_name = 'Configuración'
        verbose_name_plural = 'Configuración'

    def __str__(self):
        return self.nombre_empresa

    @classmethod
    def get_instancia(cls):
        instancia = cls.objects.filter(status=True).order_by('id').first()
        if instancia is None:
            instancia = cls()
            instancia.save()
        return instancia
