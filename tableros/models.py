from django.db import models

class ConfiguracionTablero(models.Model):
    OPCIONES_MAPA = (
        ('ESTADO', 'Nivel Estatal'),
        ('MUNICIPIO', 'Nivel Municipal / Localidad'),
    )
    nivel_mapa = models.CharField(max_length=20, choices=OPCIONES_MAPA, default='ESTADO', verbose_name="Nivel de detalle del Mapa")

    class Meta:
        verbose_name = "Configuración del Tablero"
        verbose_name_plural = "Configuración del Tablero"

    def __str__(self):
        return f"Configuración actual: {self.get_nivel_mapa_display()}"