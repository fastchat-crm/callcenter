from django.contrib import admin

from .models import AsesorHumano, AudioSistema, NumeroTelefonico, ProveedorTelefonia, TroncalSIP


@admin.register(ProveedorTelefonia)
class ProveedorTelefoniaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'driver', 'activo', 'costo_minuto_entrante')
    list_filter = ('driver', 'activo')
    search_fields = ('nombre',)


@admin.register(TroncalSIP)
class TroncalSIPAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'proveedor', 'host', 'puerto', 'transporte', 'activo')
    list_filter = ('transporte', 'activo')


@admin.register(NumeroTelefonico)
class NumeroTelefonicoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'pais_iso', 'proveedor', 'flujo', 'idioma', 'activo')
    list_filter = ('pais_iso', 'tipo', 'activo')
    search_fields = ('numero', 'ciudad')


@admin.register(AsesorHumano)
class AsesorHumanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero_destino', 'extension_sip', 'departamento', 'prioridad', 'disponible')
    list_filter = ('disponible', 'horario')
    search_fields = ('nombre', 'numero_destino')


admin.site.register(AudioSistema)
