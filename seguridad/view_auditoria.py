"""Auditoría: quién hizo qué y desde dónde."""
from datetime import datetime

from django.db.models import Q
from django.shortcuts import render

from core.funciones import addData, paginador, secure_module
from core.models import ACCION_CHOICES, Bitacora


@secure_module
def auditoria_view(request):
    data = {'titulo': 'Auditoría', 'modulo': 'Seguridad'}
    addData(request, data)

    filtros = Q()
    url_vars = ''
    criterio = (request.GET.get('criterio') or '').strip()
    accion = (request.GET.get('accion') or '').strip()
    usuario = (request.GET.get('usuario') or '').strip()
    desde = (request.GET.get('desde') or '').strip()
    hasta = (request.GET.get('hasta') or '').strip()

    if criterio:
        filtros &= (Q(descripcion__icontains=criterio) | Q(ruta__icontains=criterio)
                    | Q(ip__icontains=criterio))
        data['criterio'] = criterio
        url_vars += f'&criterio={criterio}'
    if accion:
        filtros &= Q(accion=accion)
        data['accion'] = accion
        url_vars += f'&accion={accion}'
    if usuario.isdigit():
        filtros &= Q(usuario_id=int(usuario))
        data['usuario'] = int(usuario)
        url_vars += f'&usuario={usuario}'
    for nombre, valor, comparador in (('desde', desde, 'gte'), ('hasta', hasta, 'lte')):
        if valor:
            try:
                fecha = datetime.strptime(valor, '%Y-%m-%d').date()
                filtros &= Q(**{f'fecha__date__{comparador}': fecha})
                data[nombre] = valor
                url_vars += f'&{nombre}={valor}'
            except ValueError:
                pass

    listado = Bitacora.objects.filter(filtros).select_related('usuario').order_by('-fecha')
    paginador(request, listado, data, 40, url_vars)

    from autenticacion.models import Usuario

    data['acciones'] = ACCION_CHOICES
    data['usuarios'] = Usuario.objects.filter(is_staff=True).order_by('first_name', 'username')
    return render(request, 'seguridad/auditoria.html', data)
