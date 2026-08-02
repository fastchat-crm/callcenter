"""Seguridad: qué existe en el sistema y quién puede entrar a cada cosa.

Mismo esquema que `seguridad` en fastchatdj:

  Modulo       — una URL del sistema. Es la unidad de permiso.
  ModuloGrupo  — agrupación visual: arma el menú lateral.
  GroupModulo  — qué módulos puede usar cada rol (grupo de Django).

Un usuario entra a una URL si es superusuario, o si alguno de sus roles tiene el
módulo cuya `url` es prefijo de la ruta pedida.
"""
from django.contrib.auth.models import Group
from django.db import models

from core.custom_models import ModeloBase


PERFIL_MODULO_CHOICES = (
    ('ambos', 'Administrador y cliente'),
    ('administrador', 'Solo el administrador'),
    ('cliente', 'Solo el cliente'),
)


class Modulo(ModeloBase):
    nombre = models.CharField(max_length=120)
    perfil = models.CharField(max_length=15, choices=PERFIL_MODULO_CHOICES, default='ambos',
                              help_text='Para quién es esta pantalla. «Solo el administrador» la '
                                        'esconde de los clientes aunque su rol la tenga asignada: '
                                        'sirve para lo que lleva datos del servidor o de otros '
                                        'clientes.')
    url = models.CharField(max_length=140, unique=True,
                           help_text='Ruta del sistema, con barra inicial y final: /llamadas/listado/')
    descripcion = models.CharField(max_length=250, blank=True, null=True)
    icono = models.CharField(max_length=60, blank=True, null=True)
    orden = models.IntegerField(default=0)
    visible_menu = models.BooleanField(default=True,
                                       help_text='Desmarcado, el módulo sigue protegido pero no '
                                                 'aparece en el menú lateral.')

    class Meta:
        verbose_name = 'Módulo (URL)'
        verbose_name_plural = 'Módulos (URLs)'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return f'{self.nombre} ({self.url})'

    @property
    def roles(self):
        return GroupModulo.objects.filter(status=True, modulos=self).count()


class ModuloGrupo(ModeloBase):
    """Sección del menú lateral."""

    nombre = models.CharField(max_length=120)
    icono = models.CharField(max_length=60, blank=True, null=True)
    prioridad = models.IntegerField(default=10, help_text='Menor número, más arriba en el menú.')
    modulos = models.ManyToManyField(Modulo, blank=True, related_name='grupos_menu')

    class Meta:
        verbose_name = 'Sección del menú'
        verbose_name_plural = 'Secciones del menú'
        ordering = ['prioridad', 'nombre']

    def __str__(self):
        return self.nombre

    def modulos_visibles(self):
        return self.modulos.filter(status=True, visible_menu=True).order_by('orden', 'nombre')


class GroupModulo(ModeloBase):
    """Permisos de un rol: los módulos que puede abrir."""

    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='permisos')
    modulos = models.ManyToManyField(Modulo, blank=True, related_name='roles_asignados')
    descripcion = models.CharField(max_length=250, blank=True, null=True)

    class Meta:
        verbose_name = 'Permisos del rol'
        verbose_name_plural = 'Permisos de los roles'
        ordering = ['group__name']

    def __str__(self):
        return self.group.name

    @property
    def total_modulos(self):
        return self.modulos.filter(status=True).count()

    @property
    def total_usuarios(self):
        return self.group.user_set.count()


def modulos_de_usuario(usuario, request=None):
    """URLs que el usuario puede abrir. Los superusuarios ven todo.

    Salvo que el operador haya pedido «ver como cliente»: ahí se le aplican los
    módulos del rol Cliente, para que compruebe de verdad qué ve quien va a usar
    el sistema en lugar de imaginárselo.
    """
    if not getattr(usuario, 'is_authenticated', False):
        return Modulo.objects.none()
    if request is not None and _en_modo_cliente(request):
        return modulos_del_rol_cliente()
    if usuario.is_superuser:
        return Modulo.objects.filter(status=True)
    concedidos = Modulo.objects.filter(
        status=True, roles_asignados__group__in=usuario.groups.all(),
    ).distinct()
    return acotar_por_perfil(concedidos, es_cliente=not es_operador(usuario))


def es_operador(usuario):
    """Quien administra el servicio: su usuario no cuelga de ningún cliente."""
    return getattr(usuario, 'cliente_id', None) is None


def acotar_por_perfil(queryset, es_cliente):
    """Quita del queryset las URLs que no son de este perfil.

    Va sobre los permisos del rol, no en su lugar: el rol dice qué se concedió y
    el perfil dice a quién tiene sentido mostrárselo. Se aplica en
    `modulos_de_usuario`, que es lo que consultan tanto el menú como el guardia
    de acceso, así que marcar una pantalla «solo el administrador» no solo la
    esconde: también cierra la puerta a quien la escriba a mano.
    """
    return queryset.exclude(perfil='cliente' if not es_cliente else 'administrador')


def _en_modo_cliente(request):
    try:
        from clientes.contexto import en_modo_cliente

        return en_modo_cliente(request)
    except Exception:
        return False


def modulos_del_rol_cliente():
    """Lo que ve un usuario con el rol «Cliente».

    Cruza dos cosas: lo que su rol tiene asignado y el perfil declarado en el
    módulo. El perfil manda: una pantalla marcada «solo el administrador» no se
    muestra aunque alguien se la asigne al rol por error.
    """
    from django.contrib.auth.models import Group

    from clientes.contexto import ROL_CLIENTE

    rol = Group.objects.filter(name=ROL_CLIENTE).first()
    if rol is None:
        return Modulo.objects.none()
    return (Modulo.objects.filter(status=True, roles_asignados__group=rol)
            .exclude(perfil='administrador').distinct())


# Rutas que nunca se bloquean por permisos. La del modo cliente está aquí por
# una razón concreta: sin ella, entrar en «ver como cliente» dejaba encerrado al
# operador —la salida no figura entre los módulos del rol, así que el guardia
# rechazaba justo la puerta de vuelta—.
RUTAS_SIEMPRE_PERMITIDAS = ('/clientes/modo-cliente/', '/perfilpanel/', '/changepass/')


def puede_entrar(usuario, ruta, request=None):
    """¿El usuario tiene permiso para esta ruta?

    Si todavía no se cargó ningún módulo, no se bloquea a nadie: un sistema recién
    instalado sin módulos dejaría al administrador fuera de su propio panel.
    """
    if not getattr(usuario, 'is_authenticated', False):
        return False
    if (ruta or '').startswith(RUTAS_SIEMPRE_PERMITIDAS):
        return True
    if usuario.is_superuser and not (request is not None and _en_modo_cliente(request)):
        return True
    if not Modulo.objects.filter(status=True).exists():
        return True

    ruta = ruta or '/'
    for url in modulos_de_usuario(usuario, request).values_list('url', flat=True):
        if url and ruta.startswith(url):
            return True
    return False
