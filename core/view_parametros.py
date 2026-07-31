"""Parámetros del sistema: ajustar el motor sin tocar código ni reiniciar."""
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render

from clientes.contexto import solo_operador
from core.funciones import addData, log, secure_module

from . import parametros


@secure_module
@solo_operador
def parametros_view(request):
    data = {'titulo': 'Parámetros del sistema', 'modulo': 'Centro de seguridad'}
    addData(request, data)

    if request.method == 'POST':
        cambiados = []
        for parametro in parametros.CATALOGO:
            enviado = request.POST.get(f'p_{parametro.clave}')
            if enviado is None:
                continue
            if parametros.obtener(parametro.clave) != parametros._convertir(parametro, enviado):
                cambiados.append(parametro.clave)
            parametros.guardar(parametro.clave, enviado, request)
        if cambiados:
            log(f'Cambió parámetros: {", ".join(cambiados)}', request, 'change')
            messages.success(request, f'{len(cambiados)} parámetro(s) actualizado(s).')
        else:
            messages.success(request, 'Sin cambios que guardar.')
        return HttpResponseRedirect('/parametros/')

    data['grupos'] = [
        (nombre, [
            {'meta': parametro,
             'valor': parametros.obtener(parametro.clave),
             'modificado': parametros.obtener(parametro.clave) != parametro.defecto}
            for parametro in lista
        ])
        for nombre, lista in parametros.grupos()
    ]
    return render(request, 'core/parametros.html', data)
