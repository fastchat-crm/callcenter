"""Agentes IA: alta, edición y prueba en caliente."""
from django.http import JsonResponse

from core.crud import ConfigCrud, vista_crud
from core.funciones import secure_module

from .forms import AgenteForm
from .models import AgenteIA


@secure_module
def agente_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'probar':
        return _probar_agente(request)

    return vista_crud(request, ConfigCrud(
        modelo=AgenteIA,
        formulario=AgenteForm,
        titulo='Agentes IA',
        modulo='Configuración de voz',
        plantilla_listado='agentes_ia/agente_listado.html',
        plantilla_formulario='agentes_ia/agente_form.html',
        campos_busqueda=('nombre', 'descripcion'),
        orden=('nombre',),
        singular='un agente IA',
        select_related=('apikey', 'coleccion'),
    ))


def _probar_agente(request):
    from .consultor import AgenteConsultor

    try:
        agente = AgenteIA.objects.select_related('apikey', 'coleccion').get(pk=int(request.POST['id']))
        pregunta = (request.POST.get('pregunta') or '¿Qué servicios ofrecen?').strip()
        respuesta = AgenteConsultor(agente).responder(pregunta)
        return JsonResponse({
            'error': bool(respuesta.error),
            'respuesta': respuesta.texto,
            'latencia_ms': respuesta.latencia_ms,
            'modelo': respuesta.modelo,
            'uso_contexto': respuesta.uso_contexto,
            'message': respuesta.error,
        })
    except Exception as ex:
        return JsonResponse({'error': True, 'message': str(ex)}, status=400)
