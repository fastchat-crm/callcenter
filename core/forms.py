"""Formularios del núcleo."""
from django import forms

from agentes_ia.models import PROVEEDOR_CHOICES
from core.custom_forms import FormularioBase

from .models import Configuracion


class ConfiguracionForm(FormularioBase):
    # Las opciones se declaran aquí y no en el modelo: `core` no debería importar
    # a `agentes_ia` al definir sus tablas.
    proveedor_ia_interna = forms.ChoiceField(choices=PROVEEDOR_CHOICES, label='Proveedor del token global')

    class Meta:
        model = Configuracion
        fields = ('nombre_empresa', 'logo', 'zona_horaria', 'minutos_incluidos_mes',
                  'correo_notificaciones', 'telefono_soporte',
                  'token_ia_interna', 'proveedor_ia_interna', 'modelo_ia_interna',
                  'tika_activo', 'tika_url')
        labels = {
            'nombre_empresa': 'Nombre de la empresa',
            'logo': 'Logo',
            'zona_horaria': 'Zona horaria',
            'minutos_incluidos_mes': 'Minutos incluidos al mes',
            'correo_notificaciones': 'Correo de notificaciones',
            'telefono_soporte': 'Teléfono de soporte',
            'token_ia_interna': 'Token global de IA',
            'modelo_ia_interna': 'Modelo del token global',
            'tika_activo': 'Usar Apache Tika',
            'tika_url': 'URL de Apache Tika',
        }
        help_texts = {
            'logo': 'PNG, JPG, WEBP o SVG de hasta 2 MB. Se muestra en el menú lateral.',
            'minutos_incluidos_mes': 'Sirve de referencia para el consumo del plan contratado.',
            'token_ia_interna': 'Resume la llamada al cerrarla y detecta los datos de quien llamó. '
                                'Sin él, esas dos funciones quedan apagadas.',
            'modelo_ia_interna': 'Vacío usa el modelo por defecto del proveedor.',
            'tika_activo': 'Extrae el texto de los documentos al indexar el conocimiento. '
                           'Apagado usa solo los extractores locales.',
            'tika_url': 'Ejemplo: https://tika.tu-dominio.com. Se le agrega /tika al llamar.',
        }
        widgets = {
            'token_ia_interna': forms.PasswordInput(render_value=True),
        }

    def clean_nombre_empresa(self):
        nombre = (self.cleaned_data['nombre_empresa'] or '').strip()
        if not nombre:
            raise forms.ValidationError('El nombre de la empresa no puede quedar vacío.')
        return nombre
