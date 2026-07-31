"""Números telefónicos: alta multipaís y enrutamiento a flujos IVR."""
from django.db.models import Q

from core.crud import ConfigCrud, vista_crud
from core.funciones import secure_module

from .forms import NumeroForm
from .models import NumeroTelefonico


def _filtros(request, filtros, url_vars, data):
    pais = (request.GET.get('pais') or '').strip().upper()
    if pais:
        filtros &= Q(pais_iso=pais)
        data['pais'] = pais
        url_vars += f'&pais={pais}'
    return filtros, url_vars


def _contexto(request, data):
    data['paises'] = list(
        NumeroTelefonico.objects.filter(status=True)
        .values_list('pais_iso', flat=True).distinct().order_by('pais_iso')
    )
    data['url_webhook'] = f"{data['url_general']}/telefonia/webhook/entrante/"


@secure_module
def numero_view(request):
    return vista_crud(request, ConfigCrud(
        modelo=NumeroTelefonico,
        formulario=NumeroForm,
        titulo='Números telefónicos',
        modulo='Telefonía',
        plantilla_listado='telefonia/numero_listado.html',
        plantilla_formulario='telefonia/numero_form.html',
        campos_busqueda=('numero', 'ciudad', 'pais_iso'),
        orden=('pais_iso', 'numero'),
        singular='un número telefónico',
        select_related=('proveedor', 'flujo'),
        filtros_extra=_filtros,
        contexto_extra=_contexto,
    ))
