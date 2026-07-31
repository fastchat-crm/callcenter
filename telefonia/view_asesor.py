"""Asesores humanos que reciben las transferencias."""
from core.crud import ConfigCrud, vista_crud
from core.funciones import secure_module

from .forms import AsesorForm
from .models import AsesorHumano


@secure_module
def asesor_view(request):
    return vista_crud(request, ConfigCrud(
        modelo=AsesorHumano,
        formulario=AsesorForm,
        titulo='Asesores humanos',
        modulo='Telefonía',
        plantilla_listado='telefonia/asesor_listado.html',
        plantilla_formulario='telefonia/asesor_form.html',
        campos_busqueda=('nombre', 'departamento', 'numero_destino'),
        orden=('prioridad', 'nombre'),
        singular='un asesor',
    ))
