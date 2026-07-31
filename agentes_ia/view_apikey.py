"""Llaves de proveedores de IA (todas con capa gratuita disponible)."""
from django.http import JsonResponse

from core.crud import ConfigCrud, vista_crud
from core.funciones import secure_module

from .forms import ApiKeyForm
from .models import ApiKeyIA


def _contexto(request, data):
    from .providers import proveedores_gratuitos

    data['proveedores_gratuitos'] = proveedores_gratuitos()


@secure_module
def apikey_view(request):
    if request.method == 'POST' and request.POST.get('action') in ('probar', 'modelos'):
        return _acciones_proveedor(request)

    return vista_crud(request, ConfigCrud(
        modelo=ApiKeyIA,
        formulario=ApiKeyForm,
        titulo='Llaves de IA',
        modulo='Configuración de voz',
        plantilla_listado='agentes_ia/apikey_listado.html',
        plantilla_formulario='agentes_ia/apikey_form.html',
        campos_busqueda=('alias', 'modelo'),
        orden=('alias',),
        singular='una llave de IA',
        contexto_extra=_contexto,
    ))


def _acciones_proveedor(request):
    from .providers import get_provider

    try:
        llave = ApiKeyIA.objects.get(pk=int(request.POST['id']))
        proveedor = get_provider(llave.nombre_proveedor)
        if request.POST['action'] == 'modelos':
            modelos = proveedor.listar_modelos(llave.clave or '', llave.base_url or '')
            return JsonResponse({'error': False, 'modelos': modelos})

        respuesta = proveedor.probar(llave.clave or '', llave.modelo or '', llave.base_url or '')
        return JsonResponse({
            'error': not respuesta.ok,
            'message': respuesta.error or 'Conexión correcta.',
            'respuesta': respuesta.texto,
        })
    except Exception as ex:
        return JsonResponse({'error': True, 'message': str(ex)}, status=400)
