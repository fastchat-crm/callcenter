from django.urls import path

from .view_auditoria import auditoria_view
from .view_modulo import modulo_view, seccion_menu_view
from .view_rol import permisos_rol_view, rol_view
from .view_usuario import usuario_view

seguridad_urls = (
    {'nombre': 'Usuarios', 'url': 'usuarios/', 'vista': usuario_view},
    {'nombre': 'Roles de usuario', 'url': 'roles/', 'vista': rol_view},
    {'nombre': 'Módulos del sistema', 'url': 'modulos/', 'vista': modulo_view},
    {'nombre': 'Secciones del menú', 'url': 'secciones/', 'vista': seccion_menu_view},
    {'nombre': 'Auditoría', 'url': 'auditoria/', 'vista': auditoria_view},
)

urlpatterns = [path(item['url'], item['vista']) for item in seguridad_urls] + [
    path('roles/<int:pk>/permisos/', permisos_rol_view, name='permisos_rol'),
]
