"""Administración de flujos IVR."""
from core.crud import ConfigCrud, vista_crud
from core.funciones import secure_module

from .forms import FlujoForm
from .models import FlujoVoz


def _contexto(request, data):
    filtro = data.get('filtro')
    if filtro is not None:
        data['pasos'] = filtro.pasos.filter(status=True).prefetch_related('opciones').order_by('orden', 'id')


@secure_module
def flujo_view(request):
    return vista_crud(request, ConfigCrud(
        modelo=FlujoVoz,
        formulario=FlujoForm,
        titulo='Flujos IVR',
        modulo='Configuración de voz',
        plantilla_listado='ivr/flujo_listado.html',
        plantilla_formulario='ivr/flujo_form.html',
        plantilla_detalle='ivr/flujo_detalle.html',
        campos_busqueda=('nombre', 'descripcion'),
        orden=('nombre',),
        singular='un flujo IVR',
        select_related=('agente_ia', 'asesor_respaldo'),
        prefetch_related=('pasos',),
        contexto_extra=_contexto,
    ))
