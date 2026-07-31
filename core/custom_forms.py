"""Formularios base: aplican las clases del diseño a todos los widgets."""
from django import forms


class FormularioBase(forms.ModelForm):
    """ModelForm que estiliza sus widgets sin repetir `attrs` en cada campo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            clases = widget.attrs.get('class', '')
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = f'{clases} campo-check'.strip()
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs['class'] = f'{clases} campo campo-select'.strip()
            elif isinstance(widget, forms.Textarea):
                widget.attrs['class'] = f'{clases} campo campo-area'.strip()
                widget.attrs.setdefault('rows', 3)
            else:
                widget.attrs['class'] = f'{clases} campo'.strip()
            if campo.required:
                widget.attrs['required'] = 'required'
