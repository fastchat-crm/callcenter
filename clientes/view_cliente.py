"""Alta y mantenimiento de clientes, y cambio del cliente activo."""
from django.http import JsonResponse
from django.shortcuts import redirect

from core.crud import ConfigCrud, vista_crud
from core.funciones import log, secure_module

from .contexto import elegir_cliente, es_operador
from .forms import ClienteForm
from .models import Cliente


@secure_module
def cliente_view(request):
    if not es_operador(request.user) and not request.user.is_superuser:
        return JsonResponse({'error': True, 'message': 'Solo el operador administra los clientes.'},
                            status=403)
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
