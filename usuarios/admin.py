from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    # Columnas de la lista
    list_display   = ('username', 'first_name', 'last_name', 'email', 'rol', 'is_active', 'is_staff')
    list_filter    = ('rol', 'is_active', 'is_staff', 'is_superuser')
    search_fields  = ('username', 'first_name', 'last_name', 'email')
    ordering       = ('username',)

    # Formularios: añade 'rol' a los fieldsets nativos
    fieldsets = BaseUserAdmin.fieldsets + (
        (_('Rol institucional'), {'fields': ('rol',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_('Rol institucional'), {'fields': ('rol',)}),
    )

    # Acciones masivas útiles para el administrador
    actions = ('activar_usuarios', 'desactivar_usuarios')

    @admin.action(description='Activar usuarios seleccionados')
    def activar_usuarios(self, request, queryset):
        actualizados = queryset.update(is_active=True)
        self.message_user(request, f'{actualizados} usuario(s) activado(s).')

    @admin.action(description='Desactivar usuarios seleccionados')
    def desactivar_usuarios(self, request, queryset):
        # Evita que el admin se desactive a sí mismo
        queryset = queryset.exclude(pk=request.user.pk)
        actualizados = queryset.update(is_active=False)
        self.message_user(request, f'{actualizados} usuario(s) desactivado(s).')

    # Restringe la edición de superusuarios a otros superusuarios
    def has_change_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)