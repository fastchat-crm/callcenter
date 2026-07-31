"""Usuario del panel (AUTH_USER_MODEL)."""
from django.contrib.auth.models import AbstractUser
from django.db import models

PERFIL_CHOICES = (
    ('administrador', 'Administrador'),
    ('supervisor', 'Supervisor'),
    ('asesor', 'Asesor'),
    ('auditor', 'Auditor'),
)


class Usuario(AbstractUser):
    cedula = models.CharField(max_length=20, blank=True, null=True, db_index=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES, default='asesor')
    foto = models.ImageField(upload_to='usuarios/', blank=True, null=True)
    cambiar_clave = models.BooleanField(default=False,
                                        help_text='Obliga a cambiar la contraseña en el próximo ingreso.')
    status = models.BooleanField(default=True, editable=False)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return self.nombre_completo or self.username

    @property
    def nombre_completo(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def iniciales(self):
        nombre = self.nombre_completo or self.username
        partes = [parte for parte in nombre.split() if parte]
        if not partes:
            return '?'
        if len(partes) == 1:
            return partes[0][:2].upper()
        return (partes[0][0] + partes[1][0]).upper()
