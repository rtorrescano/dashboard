from django.urls import path
from . import views

app_name = 'tableros'

urlpatterns = [
    path('directivo/', views.directivo, name='directivo'),
    path('publico/',   views.publico,   name='publico'),
]