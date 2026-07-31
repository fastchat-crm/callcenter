from django.contrib import admin

from .models import FlujoVoz, OpcionPaso, PasoVoz


class PasoInline(admin.TabularInline):
    model = PasoVoz
    fk_name = 'flujo'
    extra = 0
    fields = ('orden', 'codigo', 'nombre', 'tipo', 'variable', 'paso_siguiente')


@admin.register(FlujoVoz)
class FlujoVozAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'agente_ia', 'asesor_respaldo', 'activo')
    list_filter = ('activo', 'idioma')
    search_fields = ('nombre',)
    inlines = [PasoInline]


@admin.register(PasoVoz)
class PasoVozAdmin(admin.ModelAdmin):
    list_display = ('flujo', 'orden', 'codigo', 'nombre', 'tipo')
    list_filter = ('tipo', 'flujo')
    search_fields = ('codigo', 'nombre')


@admin.register(OpcionPaso)
class OpcionPasoAdmin(admin.ModelAdmin):
    list_display = ('paso', 'tecla', 'etiqueta', 'paso_destino')
