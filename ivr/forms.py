from django import forms

from core.custom_forms import FormularioBase

from .models import FlujoVoz, OpcionPaso, PasoVoz


class FlujoForm(FormularioBase):
    class Meta:
        model = FlujoVoz
        fields = ('nombre', 'descripcion', 'idioma', 'agente_ia', 'saludo', 'despedida',
                  'mensaje_error', 'asesor_respaldo', 'menu_cae_en_agente', 'max_reintentos',
                  'segundos_espera_respuesta', 'grabar_llamada', 'activo')
        labels = {
            'nombre': 'Nombre del flujo', 'descripcion': 'Descripción', 'idioma': 'Idioma',
            'agente_ia': 'Agente IA', 'saludo': 'Saludo inicial', 'despedida': 'Despedida',
            'mensaje_error': 'Mensaje cuando no entiende', 'asesor_respaldo': 'Asesor de respaldo',
            'menu_cae_en_agente': 'Si no coincide el menú, responde el agente IA',
            'max_reintentos': 'Máximo de reintentos',
            'segundos_espera_respuesta': 'Segundos de espera por respuesta',
            'grabar_llamada': 'Grabar llamadas', 'activo': 'Activo',
        }


class PasoForm(FormularioBase):
    class Meta:
        model = PasoVoz
        fields = ('flujo', 'codigo', 'nombre', 'tipo', 'orden', 'texto', 'audio', 'variable',
                  'validacion', 'modo_captura', 'longitud_minima', 'longitud_maxima',
                  'agente_ia', 'max_turnos_ia', 'asesor', 'expresion', 'url_webhook',
                  'metodo_webhook', 'paso_siguiente', 'paso_error')
        labels = {
            'flujo': 'Flujo', 'codigo': 'Código', 'nombre': 'Nombre', 'tipo': 'Tipo de paso',
            'orden': 'Orden', 'texto': 'Texto que dice la IA', 'audio': 'Audio pregrabado',
            'variable': 'Variable donde se guarda', 'validacion': 'Validación',
            'modo_captura': 'Modo de captura', 'longitud_minima': 'Longitud mínima',
            'longitud_maxima': 'Longitud máxima', 'agente_ia': 'Agente IA',
            'max_turnos_ia': 'Máximo de turnos con la IA', 'asesor': 'Asesor destino',
            'expresion': 'Condición', 'url_webhook': 'URL del webhook',
            'metodo_webhook': 'Método HTTP', 'paso_siguiente': 'Paso siguiente',
            'paso_error': 'Paso si falla',
        }

    def __init__(self, *args, **kwargs):
        flujo = kwargs.pop('flujo', None)
        super().__init__(*args, **kwargs)
        instancia = self.instance if self.instance and self.instance.pk else None
        flujo_id = getattr(flujo, 'id', None) or getattr(instancia, 'flujo_id', None)
        if flujo_id:
            pasos = PasoVoz.objects.filter(status=True, flujo_id=flujo_id)
            if instancia:
                pasos = pasos.exclude(pk=instancia.pk)
            self.fields['paso_siguiente'].queryset = pasos
            self.fields['paso_error'].queryset = pasos
            self.fields['flujo'].initial = flujo_id
            self.fields['flujo'].widget = forms.HiddenInput()


class OpcionForm(FormularioBase):
    class Meta:
        model = OpcionPaso
        fields = ('paso', 'tecla', 'frases', 'etiqueta', 'paso_destino', 'orden')
        labels = {
            'paso': 'Paso', 'tecla': 'Tecla (DTMF)', 'frases': 'Frases por voz',
            'etiqueta': 'Etiqueta', 'paso_destino': 'Paso destino', 'orden': 'Orden',
        }
