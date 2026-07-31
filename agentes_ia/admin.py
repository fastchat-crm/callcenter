from django.contrib import admin

from .models import AgenteIA, ApiKeyIA, ColeccionConocimiento, ConsumoIA, DocumentoConocimiento


@admin.register(ApiKeyIA)
class ApiKeyIAAdmin(admin.ModelAdmin):
    list_display = ('alias', 'proveedor', 'modelo', 'activo')
    list_filter = ('proveedor', 'activo')


@admin.register(AgenteIA)
class AgenteIAAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apikey', 'coleccion', 'usar_rag', 'activo')
    list_filter = ('activo', 'usar_rag', 'tono')
    search_fields = ('nombre', 'descripcion')


class DocumentoInline(admin.TabularInline):
    model = DocumentoConocimiento
    extra = 0
    fields = ('titulo', 'archivo')


@admin.register(ColeccionConocimiento)
class ColeccionConocimientoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug', 'fragmentos_indexados', 'fecha_indexacion')
    inlines = [DocumentoInline]


@admin.register(ConsumoIA)
class ConsumoIAAdmin(admin.ModelAdmin):
    list_display = ('agente', 'modelo', 'tokens_entrada', 'tokens_salida', 'latencia_ms', 'fecha')
    list_filter = ('agente',)
