from django.db import models


# ---------------------------------------------------------------------------
# CAPA BRONZE
# ---------------------------------------------------------------------------
class ControlCargas(models.Model):
    """
    Maestro de cargas: una fila por archivo cargado.
    Aquí vive la unicidad del hash y el versionado.
    """
    id_carga                = models.BigAutoField(primary_key=True)
    nombre_archivo_original = models.CharField(max_length=255)
    hash_archivo            = models.CharField(max_length=64, unique=True)
    version_archivo         = models.CharField(max_length=20)
    estatus_procesamiento   = models.CharField(max_length=20, default='PENDIENTE')
    filas_cargadas          = models.IntegerField(default=0)
    fecha_carga             = models.DateTimeField(auto_now_add=True)
    mensaje                 = models.TextField(null=True, blank=True)

    class Meta:
        db_table = '"bronze"."control_cargas"'
        managed  = False
        verbose_name = 'Control de Carga'
        verbose_name_plural = 'Control de Cargas'

    def __str__(self):
        return f'{self.nombre_archivo_original} ({self.version_archivo})'


class BronzeMortalidadRaw(models.Model):
    id_carga                  = models.BigAutoField(primary_key=True)
    anio_defuncion            = models.CharField(max_length=10, null=True, blank=True)
    entidad_residencia        = models.CharField(max_length=10, null=True, blank=True)
    entidad_residenciad       = models.CharField(max_length=200, null=True, blank=True)
    municipio_residenciad     = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    causa_cie_4               = models.CharField(max_length=20, null=True, blank=True)
    causa_cie_4d              = models.CharField(max_length=300, null=True, blank=True)
    edad                      = models.CharField(max_length=10, null=True, blank=True)
    edad_quinquenal           = models.CharField(max_length=20, null=True, blank=True)
    razon_mortalidad_materna  = models.CharField(max_length=50, null=True, blank=True)
    razon_mortalidad_maternad = models.CharField(max_length=100, null=True, blank=True)
    mes_defuncion             = models.CharField(max_length=10, null=True, blank=True)
    tamanio_localidad         = models.CharField(max_length=50, null=True, blank=True)
    sitio_defuncion           = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    escolaridad               = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    ocupacion                 = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    estado_conyugal           = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    derechohabiencia          = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    
    nombre_archivo_original   = models.CharField(max_length=255)
    hash_archivo              = models.CharField(max_length=64)
    fecha_carga               = models.DateTimeField(auto_now_add=True)
    estatus_procesamiento     = models.CharField(max_length=20, default='PENDIENTE')
    version_archivo           = models.CharField(max_length=20, default='v1')

    class Meta:
        db_table = '"bronze"."bronze_mortalidad_raw"'
        managed  = False

# ---------------------------------------------------------------------------
# CAPA SILVER
# ---------------------------------------------------------------------------
class SilverMortalidadLimpia(models.Model):
    id_registro          = models.BigAutoField(primary_key=True)
    id_carga_origen      = models.ForeignKey(
        BronzeMortalidadRaw,
        on_delete=models.DO_NOTHING,
        db_column='id_carga_origen',
        related_name='registros_silver',
    )
    anio_defuncion       = models.IntegerField()
    entidad_residencia   = models.IntegerField(null=True, blank=True)
    entidad_nombre       = models.CharField(max_length=200, null=True, blank=True)
    municipio_nombre     = models.CharField(max_length=200, null=True, blank=True) # NUEVO
    causa_cie_4          = models.CharField(max_length=20, null=True, blank=True)
    causa_descripcion    = models.CharField(max_length=300, null=True, blank=True)
    edad                 = models.IntegerField(null=True, blank=True)
    edad_quinquenal      = models.CharField(max_length=20, null=True, blank=True)
    mes_defuncion        = models.IntegerField(null=True, blank=True)
    dia_defuncion        = models.IntegerField(null=True, blank=True)
    tamanio_localidad    = models.CharField(max_length=50, null=True, blank=True)
    
    # NUEVOS CAMPOS
    sitio_defuncion      = models.CharField(max_length=200, null=True, blank=True)
    escolaridad          = models.CharField(max_length=200, null=True, blank=True)
    ocupacion            = models.CharField(max_length=200, null=True, blank=True)
    estado_conyugal      = models.CharField(max_length=200, null=True, blank=True)
    derechohabiencia     = models.CharField(max_length=200, null=True, blank=True)
    
    incluida_en_rmm      = models.BooleanField(default=True)
    fecha_procesamiento  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"silver"."silver_mortalidad_limpia"'
        managed  = False

# ---------------------------------------------------------------------------
# CAPA GOLD - DIMENSIONES
# ---------------------------------------------------------------------------
class DimTiempo(models.Model):
    id_tiempo = models.AutoField(primary_key=True)
    anio      = models.IntegerField()
    mes       = models.IntegerField()
    trimestre = models.IntegerField()

    class Meta:
        db_table = '"gold"."dim_tiempo"'
        managed  = False
        unique_together = (('anio', 'mes'),)
        verbose_name = 'Dimensión Tiempo'
        verbose_name_plural = 'Dimensión Tiempo'


class DimGeografia(models.Model):
    id_geografia      = models.AutoField(primary_key=True)
    id_entidad        = models.IntegerField()
    entidad_nombre    = models.CharField(max_length=200)
    id_municipio      = models.IntegerField(null=True, blank=True)
    municipio_nombre  = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = '"gold"."dim_geografia"'
        managed  = False
        unique_together = (('id_entidad', 'id_municipio'),)
        verbose_name = 'Dimensión Geografía'
        verbose_name_plural = 'Dimensión Geografía'


class DimCausa(models.Model):
    id_causa          = models.AutoField(primary_key=True)
    codigo_cie10      = models.CharField(max_length=20, unique=True)
    descripcion_causa = models.CharField(max_length=300, null=True, blank=True)
    grupo_causa       = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = '"gold"."dim_causa"'
        managed  = False
        verbose_name = 'Dimensión Causa'
        verbose_name_plural = 'Dimensión Causa'


class DimEdad(models.Model):
    id_edad          = models.AutoField(primary_key=True)
    edad_quinquenal  = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = '"gold"."dim_edad"'
        managed  = False
        verbose_name = 'Dimensión Edad'
        verbose_name_plural = 'Dimensión Edad'


# ---------------------------------------------------------------------------
# CAPA GOLD - TABLA DE HECHOS
# ---------------------------------------------------------------------------
class FactMortalidadMaterna(models.Model):
    id_hecho           = models.BigAutoField(primary_key=True)
    id_tiempo          = models.ForeignKey(
        DimTiempo, on_delete=models.DO_NOTHING,
        db_column='id_tiempo', related_name='hechos',
    )
    id_geografia       = models.ForeignKey(
        DimGeografia, on_delete=models.DO_NOTHING,
        db_column='id_geografia', related_name='hechos',
    )
    id_causa           = models.ForeignKey(
        DimCausa, on_delete=models.DO_NOTHING,
        db_column='id_causa', related_name='hechos',
    )
    id_edad            = models.ForeignKey(
        DimEdad, on_delete=models.DO_NOTHING,
        db_column='id_edad', related_name='hechos',
    )
    numero_defunciones = models.IntegerField(default=1)
    incluida_en_rmm    = models.BooleanField(default=True)
    id_registro_silver = models.ForeignKey(
        SilverMortalidadLimpia, on_delete=models.DO_NOTHING,
        db_column='id_registro_silver', related_name='hechos',
        null=True, blank=True,
    )

    class Meta:
        db_table = '"gold"."fact_mortalidad_materna"'
        managed  = False
        verbose_name = 'Hecho Mortalidad Materna'
        verbose_name_plural = 'Hechos Mortalidad Materna'


# ---------------------------------------------------------------------------
# CAPA GOLD - TABLA PARAMÉTRICA
# ---------------------------------------------------------------------------
class NacimientosEstimados(models.Model):
    anio        = models.IntegerField(primary_key=True)
    id_entidad  = models.IntegerField()
    nacimientos = models.IntegerField()
    fuente      = models.CharField(max_length=100, null=True, blank=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"gold"."nacimientos_estimados"'
        managed  = False
        unique_together = (('anio', 'id_entidad'),)
        verbose_name = 'Nacimientos Estimados'
        verbose_name_plural = 'Nacimientos Estimados'