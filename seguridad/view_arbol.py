"""Árbol del menú: qué secciones existen, qué URL cuelga de cada una y para quién.

Las pantallas de módulos y de secciones se editan por separado, y con cincuenta
URLs sueltas es fácil dejar una sin sección o abierta a los clientes sin querer.
Esta vista pone las tres cosas juntas —sección, URL y perfil— para poder
revisarlas de un vistazo y corregirlas sin salir de aquí.
"""
import sys

from django.http import JsonResponse
from django.shortcuts import render

from core.funciones import addData, log, secure_module

from .models import PERFIL_MODULO_CHOICES, GroupModulo, Modulo, ModuloGrupo


def _ramas(request):
    """Secciones con sus módulos, y al final los que no cuelgan de ninguna."""
    asignados = set()
    ramas = []
    for seccion in ModuloGrupo.objects.filter(status=True).prefetch_related('modulos'):
        modulos = list(seccion.modulos.filter(status=True).order_by('orden', 'nombre'))
        asignados.update(modulo.id for modulo in modulos)
        ramas.append({'seccion': seccion, 'modulos': modulos})

    huerfanos = list(
        Modulo.objects.filter(status=True).exclude(id__in=asignados).order_by('orden', 'nombre')
    )
    if huerfanos:
        # Sin sección no aparecen en el menú, pero siguen siendo URLs protegidas:
        # esconderlas de esta pantalla sería justo esconder lo que hay que revisar.
        ramas.append({'seccion': None, 'modulos': huerfanos})
    return ramas


def _roles_por_modulo():
    """modulo_id → nombres de los roles que lo tienen concedido."""
    mapa = {}
    for permiso in GroupModulo.objects.filter(status=True).select_related('group').prefetch_related('modulos'):
        for modulo in permiso.modulos.all():
            mapa.setdefault(modulo.id, []).append(permiso.group.name)
    return mapa


@secure_module
def arbol_view(request):
    if request.method == 'POST':
        return _guardar(request)

    data = {'titulo': 'Árbol del menú', 'modulo': 'Seguridad'}
    addData(request, data)

    roles = _roles_por_modulo()
    ramas = _ramas(request)
    for rama in ramas:
        rama['items'] = [{'modulo': modulo, 'roles': roles.get(modulo.id, [])}
                         for modulo in rama['modulos']]

    activos = Modulo.objects.filter(status=True)
    data['ramas'] = ramas
    data['perfiles'] = PERFIL_MODULO_CHOICES
    data['secciones'] = ModuloGrupo.objects.filter(status=True)
    data['total_modulos'] = activos.count()
    data['por_perfil'] = {
        clave: activos.filter(perfil=clave).count() for clave, _etiqueta in PERFIL_MODULO_CHOICES
    }
    return render(request, 'seguridad/arbol.html', data)


def _guardar(request):
    """Cambios puntuales desde el árbol, uno por petición."""
    action = request.POST.get('action')
    try:
        modulo = Modulo.objects.get(pk=request.POST.get('id'), status=True)

        if action == 'perfil':
            perfil = request.POST.get('perfil')
            if perfil not in dict(PERFIL_MODULO_CHOICES):
                return JsonResponse({'error': True, 'message': 'Perfil no válido.'}, status=400)
            modulo.perfil = perfil
            modulo.save(request)
            log(f'Cambió el perfil de {modulo.url} a {modulo.get_perfil_display()}', request, 'change')
            return JsonResponse({'error': False, 'message': f'{modulo.nombre}: {modulo.get_perfil_display()}.'})

        if action == 'seccion':
            destino = request.POST.get('seccion') or ''
            modulo.grupos_menu.clear()
            if destino:
                seccion = ModuloGrupo.objects.get(pk=destino, status=True)
                seccion.modulos.add(modulo)
                mensaje = f'{modulo.nombre} pasó a «{seccion.nombre}».'
            else:
                mensaje = f'{modulo.nombre} quedó sin sección: ya no aparece en el menú.'
            log(mensaje, request, 'change')
            return JsonResponse({'error': False, 'message': mensaje})

        return JsonResponse({'error': True, 'message': 'Acción no reconocida.'}, status=400)
    except Exception as ex:
        linea = sys.exc_info()[-1].tb_lineno
        return JsonResponse({'error': True, 'message': f'{ex} - Línea {linea}'}, status=400)
