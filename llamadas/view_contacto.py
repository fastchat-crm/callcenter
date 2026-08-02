"""Quiénes han llamado: se arma solo desde las llamadas, no se captura a mano."""
from django.db.models import Q
from django.shortcuts import render

from clientes.contexto import cliente_actual
from core.funciones import addData, paginador, secure_module

from .models import Contacto


@secure_module
def contacto_view(request):
    data = {'titulo': 'Contactos', 'modulo': 'Centro de operación'}
    addData(request, data)

    filtros = Q(status=True) & Q(cliente=cliente_actual(request))
    url_vars = ''
    criterio = (request.GET.get('criterio') or '').strip()
    if criterio:
        filtros &= (Q(numero__icontains=criterio) | Q(nombre__icontains=criterio)
                    | Q(ciudad__icontains=criterio) | Q(correo__icontains=criterio))
        data['criterio'] = criterio
        url_vars += f'&criterio={criterio}'

    listado = Contacto.objects.filter(filtros).order_by('-ultima_llamada')
    paginador(request, listado, data, 25, url_vars)
    return render(request, 'llamadas/contacto_listado.html', data)
