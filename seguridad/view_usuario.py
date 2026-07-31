"""Administración de usuarios del panel."""
import sys

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import get_template

from autenticacion.models import Usuario
from core.custom_models import FormError
from core.funciones import addData, log, paginador, secure_module

from .forms import UsuarioForm

CLAVE_TEMPORAL = 'Temporal2026*'


@secure_module
def usuario_view(request):
    data = {'titulo': 'Usuarios', 'modulo': 'Seguridad'}

    if request.method == 'POST':
        respuesta = []
        accion = request.POST.get('action', '')
        try:
            with transaction.atomic():
                if accion in ('add', 'change'):
                    if accion == 'add':
                        formulario = UsuarioForm(request.POST)
                    else:
                        instancia = Usuario.objects.get(pk=int(request.POST['pk']))
                        formulario = UsuarioForm(request.POST, instance=instancia)
                    if not formulario.is_valid():
                        raise FormError(formulario)
                    usuario = formulario.save()
                    log(f'Guardó el usuario {usuario.username}', request, accion, obj=usuario.id)
                    respuesta.append({'error': False, 'reload': True})

                elif accion == 'delete':
                    usuario = Usuario.objects.get(pk=int(request.POST['id']))
                    if usuario.pk == request.user.pk:
                        raise ValueError('No puedes desactivar tu propio usuario.')
                    usuario.is_active = False
                    usuario.status = False
                    usuario.save()
                    log(f'Desactivó al usuario {usuario.username}', request, 'del', obj=usuario.id)
                    return JsonResponse({'error': False})

                elif accion == 'activar':
                    usuario = Usuario.objects.get(pk=int(request.POST['id']))
                    usuario.is_active = not usuario.is_active
                    usuario.status = usuario.is_active
                    usuario.save()
                    log(f'Cambió el estado del usuario {usuario.username}', request, 'change', obj=usuario.id)
                    return JsonResponse({
                        'error': False,
                        'activo': usuario.is_active,
                        'message': 'Usuario activado.' if usuario.is_active else 'Usuario desactivado.',
                    })

                elif accion == 'resetear_clave':
                    usuario = Usuario.objects.get(pk=int(request.POST['id']))
                    usuario.set_password(CLAVE_TEMPORAL)
                    usuario.cambiar_clave = True
                    usuario.save()
                    log(f'Reseteó la contraseña de {usuario.username}', request, 'change', obj=usuario.id)
                    return JsonResponse({
                        'error': False,
                        'message': f'Contraseña temporal: {CLAVE_TEMPORAL} — debe cambiarla al ingresar.',
                    })

                else:
                    respuesta.append({'error': True, 'message': f'Acción no soportada: {accion}'})

        except FormError as ex:
            respuesta = [ex.dict_error]
        except Usuario.DoesNotExist:
            respuesta = [{'error': True, 'message': 'El usuario no existe.'}]
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
                data['form'] = UsuarioForm()
                return JsonResponse({'result': True,
                                     'data': get_template('seguridad/usuario_form.html').render(data, request)})
            if accion == 'change':
                usuario = Usuario.objects.get(pk=int(request.GET['id']))
                data['filtro'] = usuario
                data['form'] = UsuarioForm(instance=usuario)
                return JsonResponse({'result': True,
                                     'data': get_template('seguridad/usuario_form.html').render(data, request)})
        except Exception as ex:
            return JsonResponse({'result': False, 'message': str(ex)})

    filtros = Q()
    url_vars = ''
    criterio = (request.GET.get('criterio') or '').strip()
    rol = (request.GET.get('rol') or '').strip()
    estado = (request.GET.get('estado') or '').strip()

    if criterio:
        filtros &= (Q(username__icontains=criterio) | Q(first_name__icontains=criterio)
                    | Q(last_name__icontains=criterio) | Q(email__icontains=criterio)
                    | Q(cedula__icontains=criterio))
        data['criterio'] = criterio
        url_vars += f'&criterio={criterio}'
    if rol.isdigit():
        filtros &= Q(groups__id=int(rol))
        data['rol'] = int(rol)
        url_vars += f'&rol={rol}'
    if estado in ('activos', 'inactivos'):
        filtros &= Q(is_active=(estado == 'activos'))
        data['estado'] = estado
        url_vars += f'&estado={estado}'

    listado = Usuario.objects.filter(filtros).prefetch_related('groups').order_by('first_name', 'username')
    paginador(request, listado, data, 25, url_vars)
    data['roles'] = Group.objects.all().order_by('name')
    return render(request, 'seguridad/usuario_listado.html', data)
