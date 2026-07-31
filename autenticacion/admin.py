from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'nombre_completo', 'email', 'perfil', 'is_active', 'is_staff')
    list_filter = ('perfil', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'cedula')
    fieldsets = UserAdmin.fieldsets + (
        ('Datos del callcenter', {'fields': ('cedula', 'telefono', 'perfil', 'foto', 'cambiar_clave')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Datos del callcenter', {'fields': ('first_name', 'last_name', 'email', 'perfil')}),
    )
