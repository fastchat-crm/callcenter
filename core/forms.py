"""Formularios del núcleo."""
from django import forms

from core.custom_forms import FormularioBase

from .models import Configuracion


class ConfiguracionForm(FormularioBase):
    class Meta:
        model = Configuracion
        fields = ('nombre_empresa', 'logo', 'zona_horaria', 'minutos_incluidos_mes',
                  'correo_notificaciones', 'telefono_soporte')
        labels = {
            'nombre_empresa': 'Nombre de la empresa',
            'logo': 'Logo',
            'zona_horaria': 'Zona horaria',
            'minutos_incluidos_mes': 'Minutos incluidos al mes',
            'correo_notificaciones': 'Correo de notificaciones',
            'telefono_soporte': 'Teléfono de soporte',
        }
        help_texts = {
            'logo': 'PNG, JPG, WEBP o SVG de hasta 2 MB. Se muestra en el menú lateral.',
            'minutos_incluidos_mes': 'Sirve de referencia para el consumo del plan contratado.',
        }

    def clean_nombre_empresa(self):
        nombre = (self.cleaned_data['nombre_empresa'] or '').strip()
        if not nombre:
            raise forms.ValidationError('El nombre de la empresa no puede quedar vacío.')
        return nombre
