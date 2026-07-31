from django.contrib import admin

from .models import GroupModulo, Modulo, ModuloGrupo


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'url', 'orden', 'visible_menu')
    list_filter = ('visible_menu',)
    search_fields = ('nombre', 'url')


@admin.register(ModuloGrupo)
class ModuloGrupoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'prioridad')
    filter_horizontal = ('modulos',)


@admin.register(GroupModulo)
class GroupModuloAdmin(admin.ModelAdmin):
    list_display = ('group', 'total_modulos', 'total_usuarios')
    filter_horizontal = ('modulos',)
