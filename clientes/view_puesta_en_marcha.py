"""Asistente de puesta en marcha del cliente activo."""
from django.shortcuts import render

from core.funciones import addData, secure_module

from .contexto import cliente_actual
from .puesta_en_marcha import estado


@secure_module
def puesta_en_marcha_view(request):
    data = {'titulo': 'Puesta en marcha', 'modulo': 'Centro de operación'}
    addData(request, data)
    cliente = cliente_actual(request)
    data['cliente_activo'] = cliente
    data['estado'] = estado(cliente)
    return render(request, 'clientes/puesta_en_marcha.html', data)
