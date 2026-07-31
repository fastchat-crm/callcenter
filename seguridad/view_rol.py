"""Roles de usuario y los módulos que puede abrir cada uno."""
import sys

from django.contrib import messages
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import get_template

from core.custom_models import FormError
from core.funciones import addData, log, paginador, secure_module

from .forms import PermisosRolForm, RolForm
from .models import GroupModulo, Modulo


@secure_module
def rol_view(request):
    data = {'titulo': 'Roles de usuario', 'modulo': 'Seguridad'}

    if request.method == 'POST':
        respuesta = []
        accion = request.POST.get('action', '')
        try:
            with transaction.atomic():
                if accion in ('add', 'change'):
                    if accion == 'add':
                        formulario = RolForm(request.POST)
                    else:
                        instancia = Group.objects.get(pk=int(request.POST['pk']))
                        formulario = RolForm(request.POST, instance=instancia)
                    if not formulario.is_valid():
                        raise FormError(formulario)
                    rol = formulario.save()
                    permisos, _ = GroupModulo.objects.get_or_create(group=rol)
                    permisos.descripcion = formulario.cleaned_data.get('descripcion') or ''
                    permisos.save(request)
                    log(f'Guardó el rol {rol.name}', request, accion, obj=rol.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'delete':
                    rol = Group.objects.get(pk=int(request.POST['id']))
                    if rol.user_set.exists():
                        raise ValueError('El rol tiene usuarios asignados: reasígnalos antes de eliminarlo.')
                    log(f'Eliminó el rol {rol.name}', request, 'del', obj=rol.id)
                    rol.delete()
                    return JsonResponse({'error': False})

                else:
                    respuesta.append({'error': True, 'message': f'Acción no soportada: {accion}'})

        except FormError as ex:
            respuesta = [ex.dict_error]
        except Group.DoesNotExist:
            respuesta = [{'error': True, 'message': 'El rol no existe.'}]
        except ValueError as ex:
            respuesta = [{'error': True, 'message': str(ex)}]
        except Exception as ex:
            linea = sys.exc_info()[-1].tb_lineno
            respuesta = [{'error': True, 'message': f'{ex} - Línea {linea}'}]
        return JsonResponse(respuesta, safe=False)

    addData(request, data)
    if 'action' in request.GET:
        accion = request.GET['action']
        data['action'] = accion
        try:
            if accion == 'add':
                data['form'] = RolForm()
                return JsonResponse({'result': True,
                                     'data': get_template('seguridad/rol_form.html').render(data, request)})
            if accion == 'change':
                rol = Group.objects.get(pk=int(request.GET['id']))
                data['filtro'] = rol
                data['form'] = RolForm(instance=rol)
                return JsonResponse({'result': True,
                                     'data': get_template('seguridad/rol_form.html').render(data, request)})
        except Exception as ex:
            return JsonResponse({'result': False, 'message': str(ex)})

    criterio = (request.GET.get('criterio') or '').strip()
    listado = Group.objects.all().order_by('name')
    if criterio:
        listado = listado.filter(name__icontains=criterio)
        data['criterio'] = criterio

    # Cada rol necesita su fila de permisos para poder asignarle módulos.
    for rol in listado:
        GroupModulo.objects.get_or_create(group=rol)

    paginador(request, listado, data, 25, f'&criterio={criterio}' if criterio else '')
    data['permisos'] = {
        permiso.group_id: permiso
        for permiso in GroupModulo.objects.filter(status=True).prefetch_related('modulos')
    }
    data['total_modulos'] = Modulo.objects.filter(status=True).count()
    return render(request, 'seguridad/rol_listado.html', data)


@secure_module
def permisos_rol_view(request, pk):
    """Marca qué módulos puede abrir un rol."""
    permisos = GroupModulo.objects.filter(group_id=pk).select_related('group').first()
    if permisos is None:
        rol = Group.objects.filter(pk=pk).first()
        if rol is None:
            raise Http404('El rol no existe.')
        permisos = GroupModulo.objects.create(group=rol)

    data = {'titulo': f'Permisos del rol: {permisos.group.name}', 'modulo': 'Seguridad',
            'filtro': permisos}
    addData(request, data)

    if request.method == 'POST':
        formulario = PermisosRolForm(request.POST, instance=permisos)
        if formulario.is_valid():
            formulario.save()
            log(f'Actualizó los permisos del rol {permisos.group.name}', request, 'change',
                obj=permisos.group_id)
            messages.success(request, 'Permisos actualizados.')
            return redirect('/seguridad/roles/')
        messages.error(request, 'No se pudieron guardar los permisos.')

    data['form'] = PermisosRolForm(instance=permisos)
    data['secciones'] = _modulos_por_seccion(permisos)
    return render(request, 'seguridad/rol_permisos.html', data)


def _modulos_por_seccion(permisos):
    """Agrupa los módulos por sección del menú para que la pantalla se lea."""
    from .models import ModuloGrupo

    asignados = set(permisos.modulos.values_list('id', flat=True))
    secciones, vistos = [], set()
    for seccion in ModuloGrupo.objects.filter(status=True).prefetch_related('modulos'):
        modulos = list(seccion.modulos.filter(status=True).order_by('orden', 'nombre'))
        if not modulos:
            continue
        vistos.update(modulo.id for modulo in modulos)
        secciones.append({
            'nombre': seccion.nombre,
            'modulos': [{'obj': modulo, 'marcado': modulo.id in asignados} for modulo in modulos],
        })

    sueltos = Modulo.objects.filter(status=True).exclude(id__in=vistos).order_by('orden', 'nombre')
    if sueltos.exists():
        secciones.append({
            'nombre': 'Sin sección asignada',
            'modulos': [{'obj': modulo, 'marcado': modulo.id in asignados} for modulo in sueltos],
        })
    return secciones
