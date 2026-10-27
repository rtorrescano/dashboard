from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        ADMINISTRADOR = 'ADMIN', 'Administrador'
        OPERADOR      = 'OPER',  'Operador'
        DIRECTIVO     = 'DIR',   'Directivo'
        PERIODISTA    = 'PER',   'Periodista/Ciudadano'

    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.PERIODISTA)

    class Meta:
        db_table = 'usuarios_usuario'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.username} ({self.get_rol_display()})'