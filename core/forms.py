"""Formularios del núcleo."""
from django import forms

from core.custom_forms import FormularioBase

from .models import Configuracion


class ConfiguracionForm(FormularioBase):
    # En vez de volver a pegar una clave a mano, se elige entre las que ya están
    # cargadas y probadas en Llaves de IA. Escribirla otra vez es una fuente de
    # errores y deja la misma clave en dos sitios.
    llave_interna = forms.ChoiceField(
        required=False, label='Token global de IA',
        help_text='Se elige entre las llaves cargadas en Centro de voz e IA → Llaves de IA. '
                  'Resume la llamada al cerrarla y detecta los datos de quien llamó.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['llave_interna'].choices = self._llaves_disponibles()
        actual = (self.instance.token_ia_interna or '').strip() if self.instance else ''
        for valor, _ in self.fields['llave_interna'].choices:
            if valor and valor == str(self._llave_de(actual) or ''):
                self.fields['llave_interna'].initial = valor
                break

    def _llaves_disponibles(self):
        from agentes_ia.models import ApiKeyIA

        opciones = [('', 'Sin token: resumen y detección de datos apagados')]
        for llave in ApiKeyIA.objects.filter(status=True, activo=True).order_by('-por_defecto', 'alias'):
            if not (llave.clave or '').strip():
                continue
            marca = ' · por defecto' if llave.por_defecto else ''
            opciones.append((str(llave.pk), f'{llave.alias} — {llave.get_proveedor_display()}{marca}'))
        return opciones

    def _llave_de(self, clave):
        """Qué llave cargada corresponde al token guardado, si es que alguna."""
        from agentes_ia.models import ApiKeyIA

        if not clave:
            return None
        return ApiKeyIA.objects.filter(status=True, clave=clave).values_list('pk', flat=True).first()

    def save(self, commit=True):
        """El token y su proveedor se copian de la llave elegida."""
        from agentes_ia.models import ApiKeyIA

        configuracion = super().save(commit=False)
        elegida = (self.cleaned_data.get('llave_interna') or '').strip()
        if elegida:
            llave = ApiKeyIA.objects.filter(pk=int(elegida), status=True).first()
            if llave is not None:
                configuracion.token_ia_interna = llave.clave
                configuracion.proveedor_ia_interna = llave.proveedor
                configuracion.modelo_ia_interna = llave.modelo or ''
        else:
            configuracion.token_ia_interna = ''
        if commit:
            configuracion.save()
        return configuracion

    class Meta:
        model = Configuracion
        fields = ('nombre_empresa', 'logo', 'zona_horaria', 'minutos_incluidos_mes',
                  'correo_notificaciones', 'telefono_soporte',
                  'tika_activo', 'tika_url')
        labels = {
            'nombre_empresa': 'Nombre de la empresa',
            'logo': 'Logo',
            'zona_horaria': 'Zona horaria',
            'minutos_incluidos_mes': 'Minutos incluidos al mes',
            'correo_notificaciones': 'Correo de notificaciones',
            'telefono_soporte': 'Teléfono de soporte',
            'tika_activo': 'Usar Apache Tika',
            'tika_url': 'URL de Apache Tika',
        }
        help_texts = {
            'logo': 'PNG, JPG, WEBP o SVG de hasta 2 MB. Se muestra en el menú lateral.',
            'minutos_incluidos_mes': 'Sirve de referencia para el consumo del plan contratado.',
            'tika_activo': 'Extrae el texto de los documentos al indexar el conocimiento. '
                           'Apagado usa solo los extractores locales.',
            'tika_url': 'Ejemplo: https://tika.tu-dominio.com. Se le agrega /tika al llamar.',
        }

    def clean_nombre_empresa(self):
        nombre = (self.cleaned_data['nombre_empresa'] or '').strip()
        if not nombre:
            raise forms.ValidationError('El nombre de la empresa no puede quedar vacío.')
        return nombre
