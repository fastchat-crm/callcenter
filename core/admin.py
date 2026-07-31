from django.contrib import admin

from .models import Bitacora, Configuracion


@admin.register(Bitacora)
class BitacoraAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'accion', 'descripcion', 'ip')
    list_filter = ('accion',)
    search_fields = ('descripcion', 'ruta')
    readonly_fields = ('usuario', 'accion', 'descripcion', 'ruta', 'ip', 'objeto_id', 'fecha')


admin.site.register(Configuracion)
