from django.urls import path
from . import views

app_name = 'datalake'

urlpatterns = [
    path('cargar/', views.cargar_archivo_view, name='cargar'),
]