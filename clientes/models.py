"""Cliente: el dueño de sus números, flujos, agentes, conocimiento y asesores.

Todo lo que se configura en el panel pertenece a un cliente. Un usuario sin
cliente asignado es del operador y puede verlos a todos; el resto queda
encerrado en el suyo (ver `clientes/contexto.py`).
"""
from django.core.validators import FileExtensionValidator
from django.db import models

from core.custom_models import ModeloBase
from core.validadores import validate_file_size_2mb


class Cliente(ModeloBase):
    nombre = models.CharField(max_length=120, unique=True,
                              help_text='Nombre comercial con el que se identifica en el panel.')
    razon_social = models.CharField(max_length=180, blank=True, null=True)
    identificacion = models.CharField(max_length=20, blank=True, null=True,
                                      help_text='RUC, NIT o identificación fiscal.')
    logo = models.FileField(upload_to='clientes/', blank=True, null=True,
                            validators=[FileExtensionValidator(['png', 'jpg', 'jpeg', 'webp', 'svg']),
                                        validate_file_size_2mb])
    correo = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    zona_horaria = models.CharField(max_length=60, default='America/Guayaquil')
    minutos_incluidos_mes = models.IntegerField(default=3500,
                                                help_text='Minutos del plan contratado, como referencia.')
    activo = models.BooleanField(default=True,
                                 help_text='Si se desactiva, sus números dejan de atender llamadas.')

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def iniciales(self):
        partes = (self.nombre or '').split()
        if len(partes) >= 2:
            return (partes[0][:1] + partes[1][:1]).upper()
        return (self.nombre or '??')[:2].upper()
