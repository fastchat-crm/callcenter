"""Formularios base: aplican las clases del diseño a todos los widgets."""
from django import forms


class FormularioBase(forms.ModelForm):
    """ModelForm que estiliza sus widgets sin repetir `attrs` en cada campo.

    También acota los desplegables al cliente activo: ningún formulario puede
    ofrecer el flujo, el agente o el asesor de otro cliente.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._acotar_al_cliente()
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

    def _acotar_al_cliente(self):
        from clientes.contexto import acotar, clientes_visibles, modelo_por_cliente
        from clientes.models import Cliente
        from core.custom_middleware import get_current_request

        request = get_current_request()
        for campo in self.fields.values():
            listado = getattr(campo, 'queryset', None)
            if listado is None:
                continue

            # Con borrado lógico, `objects.all()` sigue trayendo lo dado de baja:
            # sin esto los desplegables ofrecen registros que ya no existen para
            # el usuario, y elegir uno lo revive de hecho.
            if any(f.name == 'status' for f in listado.model._meta.fields):
                listado = listado.filter(status=True)
                campo.queryset = listado

            if request is None or not getattr(request.user, 'is_authenticated', False):
                continue
            if listado.model is Cliente:
                campo.queryset = clientes_visibles(request.user)
            elif modelo_por_cliente(listado.model):
                campo.queryset = acotar(listado, request)
