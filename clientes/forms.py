"""Formularios de clientes."""
from django import forms

from core.custom_forms import FormularioBase

from .models import Cliente


class ClienteForm(FormularioBase):
    class Meta:
        model = Cliente
        fields = ('nombre', 'razon_social', 'identificacion', 'logo', 'correo', 'telefono',
                  'direccion', 'zona_horaria', 'minutos_incluidos_mes', 'activo')
        labels = {
            'nombre': 'Nombre comercial',
            'razon_social': 'Razón social',
            'identificacion': 'RUC o identificación',
            'logo': 'Logo',
            'correo': 'Correo',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
            'zona_horaria': 'Zona horaria',
            'minutos_incluidos_mes': 'Minutos incluidos al mes',
            'activo': 'Activo',
        }

    def clean_nombre(self):
        nombre = (self.cleaned_data['nombre'] or '').strip()
        existentes = Cliente.objects.filter(nombre__iexact=nombre, status=True)
        if self.instance and self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Ya existe un cliente con ese nombre.')
        return nombre
