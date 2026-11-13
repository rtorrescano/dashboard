from django.urls import path
from . import views

urlpatterns = [
    path('directivo/', views.directivo, name='directivo'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('subir-datos/', views.cargar_datos_csv, name='subir_datos'),
    path('descargar-excel/', views.descargar_excel, name='descargar_excel'),
]