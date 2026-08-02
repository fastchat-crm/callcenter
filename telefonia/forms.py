from django import forms

from core.custom_forms import FormularioBase
from core.funciones import normalizar_e164

from .models import AsesorHumano, AudioSistema, NumeroTelefonico, ProveedorTelefonia, TroncalSIP


class ProveedorForm(FormularioBase):
    class Meta:
        model = ProveedorTelefonia
        fields = ('nombre', 'driver', 'base_url', 'cuenta_sid', 'token', 'costo_minuto_entrante',
                  'costo_mensual_did', 'activo', 'notas')
        labels = {
            'nombre': 'Nombre', 'driver': 'Tecnología', 'base_url': 'URL de la API',
            'cuenta_sid': 'Cuenta / usuario API', 'token': 'Token / clave API',
            'costo_minuto_entrante': 'Costo por minuto entrante (USD)',
            'costo_mensual_did': 'Costo mensual del número (USD)',
            'activo': 'Activo', 'notas': 'Notas',
        }


class TroncalForm(FormularioBase):
    class Meta:
        model = TroncalSIP
        fields = ('proveedor', 'nombre', 'host', 'puerto', 'transporte', 'usuario', 'clave',
                  'contexto', 'codec_preferido', 'registrar', 'activo')
        labels = {
            'proveedor': 'Proveedor', 'nombre': 'Nombre', 'host': 'Host SIP', 'puerto': 'Puerto',
            'transporte': 'Transporte', 'usuario': 'Usuario', 'clave': 'Clave',
            'contexto': 'Contexto del dialplan', 'codec_preferido': 'Códec preferido',
            'registrar': 'Registrar en el proveedor', 'activo': 'Activo',
        }


class NumeroForm(FormularioBase):
    class Meta:
        model = NumeroTelefonico
        fields = ('numero', 'pais_iso', 'prefijo_pais', 'ciudad', 'tipo', 'proveedor', 'troncal',
                  'agente_ia',
                  'flujo', 'idioma', 'zona_horaria', 'concurrencia_maxima', 'minutos_incluidos',
                  'activo', 'notas')
        labels = {
            'numero': 'Número (E.164)', 'pais_iso': 'País (ISO)', 'prefijo_pais': 'Prefijo país',
            'ciudad': 'Ciudad', 'tipo': 'Tipo', 'proveedor': 'Proveedor', 'troncal': 'Troncal SIP',
            'flujo': 'Flujo IVR', 'idioma': 'Idioma', 'zona_horaria': 'Zona horaria',
            'concurrencia_maxima': 'Llamadas simultáneas', 'minutos_incluidos': 'Minutos incluidos',
            'activo': 'Activo', 'notas': 'Notas',
        }

    def clean_numero(self):
        return normalizar_e164(self.cleaned_data['numero'], self.data.get('prefijo_pais') or '593')


class AsesorForm(FormularioBase):
    class Meta:
        model = AsesorHumano
        fields = ('nombre', 'numero_destino', 'extension_sip', 'clave_sip', 'correo',
                  'departamento', 'horario', 'prioridad', 'disponible')
        labels = {
            'nombre': 'Nombre', 'numero_destino': 'Número destino (E.164)',
            'extension_sip': 'Extensión SIP', 'clave_sip': 'Clave SIP',
            'correo': 'Correo', 'departamento': 'Departamento',
            'horario': 'Horario', 'prioridad': 'Prioridad', 'disponible': 'Disponible',
        }
        help_texts = {
            'clave_sip': 'Con esta clave el softphone se registra. Sin ella, la extensión '
                         'no se genera en Asterisk.',
        }
        widgets = {'clave_sip': forms.PasswordInput(render_value=True)}

    def clean_numero_destino(self):
        numero = self.cleaned_data.get('numero_destino')
        return normalizar_e164(numero) if numero else numero


class AudioForm(FormularioBase):
    class Meta:
        model = AudioSistema
        fields = ('nombre', 'archivo', 'descripcion')
        labels = {'nombre': 'Nombre', 'archivo': 'Archivo de audio', 'descripcion': 'Descripción'}
