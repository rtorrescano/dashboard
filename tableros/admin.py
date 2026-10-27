from django.contrib import admin
from .models import ConfiguracionTablero

@admin.register(ConfiguracionTablero)
class ConfiguracionTableroAdmin(admin.ModelAdmin):
    list_display = ('id', 'nivel_mapa')
    
    def has_add_permission(self, request):
        # Evitar que creen múltiples configuraciones, solo debe haber una
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)