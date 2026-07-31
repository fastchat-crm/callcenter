"""Modelo base compartido: auditoria + borrado logico.

Misma semantica que `core.custom_models.ModeloBase` de fastchatdj:
  - `status` es el borrado logico (nunca se usa `.delete()`)
  - `save(request)` sella usuario y fecha de creacion/modificacion
"""
from datetime import datetime

from django.db import models

from callcenterdj.settings import AUTH_USER_MODEL


class ModeloBase(models.Model):
    usuario_creacion = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True,
                                         null=True, related_name='+', editable=False)
    fecha_registro = models.DateTimeField(verbose_name='Fecha de registro', auto_now_add=True, editable=False)
    usuario_modificacion = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True,
                                             null=True, related_name='+', editable=False)
    fecha_modificacion = models.DateTimeField(verbose_name='Fecha de modificación', blank=True,
                                              null=True, editable=False)
    status = models.BooleanField(default=True, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from core.custom_middleware import get_current_request

        request = kwargs.pop('request', None)
        if request is None:
            for argumento in args:
                if hasattr(argumento, 'META') and hasattr(argumento, 'method'):
                    request = argumento
                    break
        request = request or get_current_request()

        usuario_id = kwargs.pop('usuario_id', None)
        if usuario_id is None and request is not None:
            usuario = getattr(request, 'user', None)
            if usuario is not None and getattr(usuario, 'is_authenticated', False):
                usuario_id = usuario.id

        update_fields = kwargs.get('update_fields')
        if self.pk:
            self.fecha_modificacion = datetime.now()
            if usuario_id:
                self.usuario_modificacion_id = usuario_id
            if update_fields is not None:
                kwargs['update_fields'] = list(
                    set([*update_fields, 'usuario_modificacion_id', 'fecha_modificacion'])
                )
        elif usuario_id:
            self.usuario_creacion_id = usuario_id

        models.Model.save(self, update_fields=kwargs.get('update_fields'))

    def eliminar_logico(self, request=None):
        self.status = False
        self.save(request)


class FormError(Exception):
    """Traduce los errores de un form a la respuesta JSON estandar del sistema."""

    def __init__(self, form):
        self.form = form
        errores = []
        for campo, mensajes in form.errors.items():
            etiqueta = form.fields[campo].label if campo in form.fields else campo
            errores.append({'campo': campo, 'label': etiqueta, 'mensajes': list(mensajes)})
        self.dict_error = {
            'error': True,
            'message': 'Revisa los datos del formulario.',
            'errores': errores,
        }
        super().__init__(self.dict_error['message'])
