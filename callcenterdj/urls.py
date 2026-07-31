"""Ruteo raiz del proyecto callcenter.

Convencion heredada de fastchatdj: cada app publica una tupla `<app>_urls` con
`nombre`/`url`/`vista`; el proyecto la incluye bajo un prefijo y el menu lateral
se arma desde la misma tupla (ver `core/menu.py`).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from autenticacion.view_login import cambiar_clave_view, login_view, logout_view
from autenticacion.view_perfil import perfil_view
from callcenterdj.view_health import health_view
from core.ajax import ConsultasAjax
from core.view_configuracion import configuracion_view
from core.view_parametros import parametros_view
from panel.view_doc import doc_view
from panel.view_index import index_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_view, name='health_check'),

    path('', index_view, name='inicio'),
    path('panel/', index_view, name='panel'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('perfilpanel/', perfil_view, name='perfil'),
    path('configuracion/', configuracion_view, name='configuracion'),
    path('parametros/', parametros_view, name='parametros'),
    path('doc/', doc_view, name='documentacion'),
    path('doc/<slug:slug>/', doc_view, name='documentacion_detalle'),
    path('changepass/', cambiar_clave_view, name='cambiar_clave'),

    path('ajaxrequest/', ConsultasAjax.as_view(), name='ajax_consultas'),
    path('ajaxrequest/<slug:accion>', ConsultasAjax.as_view(), name='ajax_consultas_accion'),
    path('ajaxrequest/<slug:accion>/<str:pk>', ConsultasAjax.as_view(), name='ajax_consultas_pk'),

    path('clientes/', include('clientes.urls')),
    path('seguridad/', include('seguridad.urls')),
    path('telefonia/', include('telefonia.urls')),
    path('ivr/', include('ivr.urls')),
    path('llamadas/', include('llamadas.urls')),
    path('agentes-ia/', include('agentes_ia.urls')),
    path('voz/', include('voz.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]

admin.site.site_header = 'Administración Callcenter IA'
admin.site.site_title = 'Administración Callcenter IA'
