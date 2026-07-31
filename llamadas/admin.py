from django.contrib import admin

from .models import GrabacionLlamada, Llamada, TransferenciaLlamada, TurnoLlamada


class TurnoInline(admin.TabularInline):
    model = TurnoLlamada
    extra = 0
    readonly_fields = ('rol', 'texto', 'dtmf', 'paso_codigo', 'latencia_ms', 'fecha')
    can_delete = False


@admin.register(Llamada)
class LlamadaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_inicio', 'numero_origen', 'numero_destino', 'estado',
                    'resultado', 'duracion_segundos')
    list_filter = ('estado', 'resultado', 'driver', 'pais_iso')
    search_fields = ('numero_origen', 'numero_destino', 'call_id', 'transcripcion')
    inlines = [TurnoInline]


@admin.register(TransferenciaLlamada)
class TransferenciaLlamadaAdmin(admin.ModelAdmin):
    list_display = ('llamada', 'asesor', 'motivo', 'estado', 'fecha_solicitud')
    list_filter = ('motivo', 'estado')


admin.site.register(GrabacionLlamada)
