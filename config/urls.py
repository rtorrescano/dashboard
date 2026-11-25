from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from tableros import views as tableros_views
from usuarios.views import CustomLoginView # Importamos tu vista personalizada
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # PÁGINA PRINCIPAL
    path('', tableros_views.publico, name='home'), 
    
    # AUTENTICACIÓN
    # Usamos la vista personalizada para que enrute según el rol
    path('login/', CustomLoginView.as_view(), name='login'), 
    
    # LOGOUT: next_page='login' asegura que al salir te mande directo al login
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'), 
    
    # APLICACIONES
    path('admin/', admin.site.urls),
    #path('datalake/', include('datalake.urls')),
    path('tableros/', include('tableros.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)