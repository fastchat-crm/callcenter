"""Alta y mantenimiento de clientes, y cambio del cliente activo."""
from django.shortcuts import redirect

from core.crud import ConfigCrud, vista_crud
from core.funciones import log, secure_module

from .contexto import elegir_cliente, solo_operador
from .forms import ClienteForm
from .models import Cliente


@secure_module
@solo_operador
def cliente_view(request):
    return vista_crud(request, ConfigCrud(
        modelo=Cliente,
        formulario=ClienteForm,
        titulo='Clientes',
        modulo='Centro de seguridad',
        plantilla_listado='clientes/cliente_listado.html',
        plantilla_formulario='clientes/cliente_form.html',
        campos_busqueda=('nombre', 'razon_social', 'identificacion'),
        orden=('nombre',),
        singular='un cliente',
    ))


@secure_module
def cambiar_cliente_view(request):
    """Cambia el cliente sobre el que trabaja el panel."""
    destino = request.POST.get('siguiente') or request.GET.get('siguiente') or '/panel/'
    cliente = elegir_cliente(request, request.POST.get('cliente') or request.GET.get('cliente'))
    if cliente is not None:
        log(f'Cambió al cliente {cliente}', request, 'info', obj=cliente.id)
    if not destino.startswith('/'):
        destino = '/panel/'
    return redirect(destino)
