from django.contrib.auth.views import LoginView
from .models import Usuario

class CustomLoginView(LoginView):
    template_name = 'tableros/login.html'

    def get_success_url(self):
        user = self.request.user
        
        # Redirección inteligente según el Rol
        if user.rol == Usuario.Rol.ADMINISTRADOR or user.is_superuser:
            return '/tableros/admin-dashboard/' # <-- Panel de control
            
        elif user.rol == Usuario.Rol.DIRECTIVO:
            return '/tableros/directivo/'
            
        elif user.rol == Usuario.Rol.OPERADOR:
            return '/tableros/subir-datos/' # <-- Directo a la carga de archivos
            
        else:
            # Periodistas / Ciudadanos
            return '/'