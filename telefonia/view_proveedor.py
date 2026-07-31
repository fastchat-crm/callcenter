"""Proveedores de telefonía y troncales SIP."""
from core.crud import ConfigCrud, vista_crud
from core.funciones import secure_module

from .forms import ProveedorForm
from .models import ProveedorTelefonia


def _contexto(request, data):
    data['total_gratuitos'] = ProveedorTelefonia.objects.filter(
        status=True, driver__in=('asterisk', 'webrtc'),
    ).count()


@secure_module
def proveedor_view(request):
    return vista_crud(request, ConfigCrud(
        modelo=ProveedorTelefonia,
        formulario=ProveedorForm,
        titulo='Proveedores de telefonía',
        modulo='Telefonía',
        plantilla_listado='telefonia/proveedor_listado.html',
        plantilla_formulario='telefonia/proveedor_form.html',
        campos_busqueda=('nombre', 'driver'),
        orden=('nombre',),
        singular='un proveedor de telefonía',
        contexto_extra=_contexto,
        prefetch_related=('numeros',),
    ))
