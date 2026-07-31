"""Utilidades transversales: contexto de vistas, paginacion, permisos y bitacora."""
import logging
from datetime import date

from django.conf import settings
from django.contrib import messages
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseRedirect

logger = logging.getLogger('core')

REGISTROS_POR_PAGINA = 25


def addData(request, data):
    """Inyecta en `data` el contexto comun del panel."""
    from core.menu import menu_para_usuario

    data.setdefault('titulo', settings.NOMBRE_SISTEMA)
    data.setdefault('modulo', '')
    data['ruta'] = request.path
    data['fecha_actual'] = date.today()
    data['nombre_sistema'] = settings.NOMBRE_SISTEMA
    data['url_general'] = settings.URL_GENERAL
    data['ip_publica'] = settings.IP_PUBLICA
    data['menu'] = menu_para_usuario(request.user, request)
    data['full_url'] = request.path + ('?' + request.GET.urlencode() if request.GET else '')
    return data


def paginador(request, listado, data, cantidad=REGISTROS_POR_PAGINA, url_vars=''):
    """Pagina un queryset y deja en `data` lo que consume `paginacion.html`."""
    paginator = Paginator(listado, cantidad)
    numero = request.GET.get('page', 1)
    try:
        pagina = paginator.page(numero)
    except PageNotAnInteger:
        pagina = paginator.page(1)
    except EmptyPage:
        pagina = paginator.page(paginator.num_pages)

    data['paginator'] = paginator
    data['page_obj'] = pagina
    data['listado'] = pagina.object_list
    data['total_registros'] = paginator.count
    data['url_vars'] = url_vars
    return pagina


def secure_module(vista):
    """Exige sesión iniciada, usuario activo y permiso sobre el módulo.

    El permiso lo resuelve `seguridad.puede_entrar` contra los roles del usuario.
    Si la app de seguridad todavía no está migrada, se cae al criterio básico
    (staff o superusuario) para no dejar el panel inaccesible.
    """

    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(f'{settings.LOGIN_URL}?next={request.path}')
        if not request.user.is_active:
            messages.error(request, 'Tu usuario está inactivo.')
            return HttpResponseRedirect('/login/')
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, 'No tienes acceso al panel.')
            return HttpResponseRedirect('/login/')
        if request.user.cambiar_clave and request.path != '/changepass/':
            return HttpResponseRedirect('/changepass/')

        try:
            from seguridad.models import puede_entrar

            if not puede_entrar(request.user, request.path, request):
                messages.error(request, 'No tienes permiso para entrar a este módulo.')
                return HttpResponseRedirect('/panel/')
        except Exception:
            logger.exception('No se pudo verificar el permiso de %s', request.path)
        return vista(request, *args, **kwargs)

    envoltura.__name__ = getattr(vista, '__name__', 'vista')
    envoltura.__doc__ = vista.__doc__
    return envoltura


def log(descripcion, request=None, accion='', obj=None):
    """Bitacora de acciones del panel."""
    from core.models import Bitacora

    usuario = None
    if request is not None and getattr(request, 'user', None) is not None:
        if request.user.is_authenticated:
            usuario = request.user
    try:
        Bitacora.objects.create(
            usuario=usuario,
            accion=accion or 'info',
            descripcion=descripcion,
            ruta=getattr(request, 'path', '') or '',
            ip=obtener_ip(request),
            objeto_id=obj if isinstance(obj, int) else None,
        )
    except Exception:
        logger.exception('No se pudo escribir en bitácora: %s', descripcion)


def obtener_ip(request):
    if request is None:
        return ''
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or ''


def solo_digitos(texto):
    return ''.join(caracter for caracter in (texto or '') if caracter.isdigit())


def normalizar_e164(numero, prefijo_pais='593'):
    """Normaliza un numero a formato E.164 internacional (+<pais><numero>)."""
    numero = (numero or '').strip()
    if numero.startswith('+'):
        return '+' + solo_digitos(numero)
    digitos = solo_digitos(numero)
    if not digitos:
        return ''
    if digitos.startswith('00'):
        return '+' + digitos[2:]
    if digitos.startswith(prefijo_pais):
        return '+' + digitos
    return '+' + prefijo_pais + digitos.lstrip('0')


def formato_duracion(segundos):
    segundos = int(segundos or 0)
    minutos, resto = divmod(segundos, 60)
    horas, minutos = divmod(minutos, 60)
    if horas:
        return f'{horas}h {minutos:02d}m {resto:02d}s'
    return f'{minutos:02d}:{resto:02d}'
