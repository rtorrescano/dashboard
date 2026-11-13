# datalake/models.py
"""
Modelos del datalake (Bronze / Silver / Gold) para mortalidad materna.

Reglas de versionado:
- Bronze: 1 registro vigente por hash_registro. Al cambiar se actualiza
  in-place y se guarda snapshot en BronzeMortalidadAuditoria.
- Silver: 1 registro vigente por id_carga_origen. Al actualizarse se
  guarda snapshot en SilverMortalidadAuditoria y se marca
  requiere_recalculo_gold=True para que Gold reconstruya el hecho.
- Gold: 1 hecho por Silver vigente (OneToOne). Se regenera cuando
  Silver cambia.
"""
from django.db import models
from django.db.models import Q


# ============================================================
# BRONZE
# ============================================================
class BronzeMortalidadRaw(models.Model):
    ESTATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESADO', 'Procesado'),
        ('RECHAZADO', 'Rechazado'),
    ]

    # --- Metadata de la carga ---
    id_carga = models.AutoField(primary_key=True)
    nombre_archivo_original = models.CharField(max_length=500)
    hash_archivo = models.CharField(max_length=64, db_index=True)
    version_archivo = models.CharField(max_length=20)
    hash_registro = models.CharField(max_length=64, db_index=True)
    estatus_procesamiento = models.CharField(
        max_length=20, choices=ESTATUS_CHOICES, default='PENDIENTE', db_index=True,
    )
    es_vigente = models.BooleanField(default=True, db_index=True)
    version_registro = models.IntegerField(default=1)
    fecha_carga = models.DateTimeField(auto_now_add=True)

    # --- Datos crudos del CSV (todos string; la limpieza ocurre en Silver) ---
    anio_nacimiento = models.CharField(max_length=10, null=True, blank=True)
    mes_nacimiento = models.CharField(max_length=10, null=True, blank=True)
    mes_nacimientod = models.CharField(max_length=50, null=True, blank=True)
    dia_nacimiento = models.CharField(max_length=10, null=True, blank=True)
    edad = models.CharField(max_length=10, null=True, blank=True)
    estado_conyugal = models.CharField(max_length=10, null=True, blank=True)
    estado_conyugald = models.CharField(max_length=200, null=True, blank=True)
    entidad_residencia = models.CharField(max_length=10, null=True, blank=True)
    entidad_residenciad = models.CharField(max_length=200, null=True, blank=True)
    municipio_residencia = models.CharField(max_length=10, null=True, blank=True)
    municipio_residenciad = models.CharField(max_length=200, null=True, blank=True)
    localidad_residencia = models.CharField(max_length=200, null=True, blank=True)
    localidad_residenciad = models.CharField(max_length=300, null=True, blank=True)
    tamanio_localidad = models.CharField(max_length=50, null=True, blank=True)
    tamanio_localidadd = models.CharField(max_length=100, null=True, blank=True)
    ocupacion_habitual = models.CharField(max_length=10, null=True, blank=True)
    ocupacion_habituald = models.CharField(max_length=300, null=True, blank=True)
    escolaridad = models.CharField(max_length=10, null=True, blank=True)
    escolaridadd = models.CharField(max_length=300, null=True, blank=True)
    derechohabiencia = models.CharField(max_length=10, null=True, blank=True)
    derechohabiendad = models.CharField(max_length=200, null=True, blank=True)
    entidad_ocurrencia = models.CharField(max_length=10, null=True, blank=True)
    entidad_ocurrenciad = models.CharField(max_length=200, null=True, blank=True)
    municipio_ocurrencia = models.CharField(max_length=10, null=True, blank=True)
    municipio_ocurrenciad = models.CharField(max_length=200, null=True, blank=True)
    localidad_ocurrencia = models.CharField(max_length=200, null=True, blank=True)
    localidad_ocurrenciad = models.CharField(max_length=300, null=True, blank=True)
    sitio_defuncion = models.CharField(max_length=10, null=True, blank=True)
    sitio_defunciond = models.CharField(max_length=200, null=True, blank=True)
    anio_defuncion = models.CharField(max_length=10, null=True, blank=True)
    mes_defuncion = models.CharField(max_length=10, null=True, blank=True)
    mes_defunciond = models.CharField(max_length=50, null=True, blank=True)
    dia_defuncion = models.CharField(max_length=10, null=True, blank=True)
    hora_defuncion = models.CharField(max_length=10, null=True, blank=True)
    minutos_defuncion = models.CharField(max_length=10, null=True, blank=True)
    asistencia_medica = models.CharField(max_length=10, null=True, blank=True)
    asistencia_medicad = models.CharField(max_length=100, null=True, blank=True)
    causa_cie_4 = models.CharField(max_length=20, null=True, blank=True)
    causa_cie_4d = models.CharField(max_length=300, null=True, blank=True)
    certifico = models.CharField(max_length=10, null=True, blank=True)
    certificod = models.CharField(max_length=100, null=True, blank=True)
    entidad_registro = models.CharField(max_length=10, null=True, blank=True)
    entidad_registrod = models.CharField(max_length=200, null=True, blank=True)
    municipio_registro = models.CharField(max_length=10, null=True, blank=True)
    municipio_registrod = models.CharField(max_length=200, null=True, blank=True)
    anio_registro = models.CharField(max_length=10, null=True, blank=True)
    mes_registro = models.CharField(max_length=10, null=True, blank=True)
    mes_registrod = models.CharField(max_length=50, null=True, blank=True)
    dia_registro = models.CharField(max_length=10, null=True, blank=True)
    anio_certificacion = models.CharField(max_length=10, null=True, blank=True)
    mes_certificacion = models.CharField(max_length=10, null=True, blank=True)
    mes_certificaciond = models.CharField(max_length=50, null=True, blank=True)
    dia_certificacion = models.CharField(max_length=10, null=True, blank=True)
    anio_base_datos = models.CharField(max_length=10, null=True, blank=True)
    razon_mortalidad_materna = models.CharField(max_length=50, null=True, blank=True)
    razon_mortalidad_maternad = models.CharField(max_length=100, null=True, blank=True)
    edad_quinquenal = models.CharField(max_length=20, null=True, blank=True)
    edad_quinquenald = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'bronze_mortalidad_raw'
        constraints = [
            models.UniqueConstraint(
                fields=['hash_registro'],
                condition=Q(es_vigente=True),
                name='unique_bronze_hash_vigente',
            ),
        ]
        indexes = [
            models.Index(fields=['estatus_procesamiento', 'es_vigente']),
            models.Index(fields=['hash_archivo']),
        ]


class BronzeMortalidadAuditoria(models.Model):
    """Snapshot del Bronze ANTES de ser actualizado in-place."""
    id_auditoria = models.AutoField(primary_key=True)
    id_registro_original = models.ForeignKey(
        BronzeMortalidadRaw,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias',
        db_column='id_registro_original',
    )
    hash_registro = models.CharField(max_length=64, db_index=True)
    version_registro = models.IntegerField()
    datos_anteriores = models.JSONField()
    hash_archivo_nuevo = models.CharField(max_length=64)
    nombre_archivo_nuevo = models.CharField(max_length=500)
    motivo = models.CharField(max_length=100)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bronze_mortalidad_auditoria'
        ordering = ['-fecha_cambio']


# ============================================================
# SILVER
# ============================================================
class SilverMortalidadLimpia(models.Model):
    id_registro = models.AutoField(primary_key=True)
    id_carga_origen = models.ForeignKey(
        BronzeMortalidadRaw,
        on_delete=models.PROTECT,
        related_name='silvers',
        db_column='id_carga_origen',
    )

    anio_defuncion = models.IntegerField(null=True, db_index=True)   # None = desconocido
    entidad_residencia = models.IntegerField(null=True)
    entidad_nombre = models.CharField(max_length=200, null=True, blank=True)
    municipio_residencia = models.IntegerField(null=True)
    municipio_nombre = models.CharField(max_length=200, null=True, blank=True)
    localidad_nombre = models.CharField(max_length=300, null=True, blank=True)
    causa_cie_4 = models.CharField(max_length=20, null=True, blank=True)
    causa_descripcion = models.TextField(null=True, blank=True)
    edad = models.IntegerField(null=True)                # None = desconocido
    edad_quinquenal = models.CharField(max_length=50, null=True, blank=True)
    mes_defuncion = models.IntegerField(null=True)       # 1-12 o None
    dia_defuncion = models.IntegerField(null=True)       # 1-31 o None
    tamanio_localidad = models.CharField(max_length=100, null=True, blank=True)
    sitio_defuncion = models.CharField(max_length=200, null=True, blank=True)
    escolaridad = models.CharField(max_length=300, null=True, blank=True)
    ocupacion = models.CharField(max_length=300, null=True, blank=True)
    estado_conyugal = models.CharField(max_length=200, null=True, blank=True)
    derechohabiencia = models.CharField(max_length=200, null=True, blank=True)
    incluida_en_rmm = models.BooleanField(default=False)

    hash_registro = models.CharField(max_length=64, db_index=True)
    es_vigente = models.BooleanField(default=True, db_index=True)
    version_registro = models.IntegerField(default=1)
    requiere_recalculo_gold = models.BooleanField(default=True, db_index=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'silver_mortalidad_limpia'
        constraints = [
            models.UniqueConstraint(
                fields=['id_carga_origen'],
                condition=Q(es_vigente=True),
                name='unique_silver_bronze_vigente',
            ),
            models.UniqueConstraint(
                fields=['hash_registro'],
                condition=Q(es_vigente=True),
                name='unique_silver_hash_vigente',
            ),
        ]
        indexes = [
            models.Index(fields=['es_vigente', 'requiere_recalculo_gold']),
        ]


class SilverMortalidadAuditoria(models.Model):
    """Snapshot del Silver ANTES de ser actualizado in-place."""
    id_auditoria = models.AutoField(primary_key=True)
    id_registro_original = models.ForeignKey(
        SilverMortalidadLimpia,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias',
        db_column='id_registro_original',
    )
    id_carga_origen = models.ForeignKey(
        BronzeMortalidadRaw,
        on_delete=models.SET_NULL,
        null=True,
        related_name='silver_auditorias',
        db_column='id_carga_origen',
    )
    version_registro = models.IntegerField()
    hash_registro_anterior = models.CharField(max_length=64, db_index=True)
    datos_anteriores = models.JSONField()
    motivo = models.CharField(max_length=100)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'silver_mortalidad_auditoria'
        ordering = ['-fecha_cambio']


# ============================================================
# GOLD - Dimensiones
# ============================================================
class DimTiempo(models.Model):
    """
    anio=0 / mes=0 / trimestre=0 representan 'desconocido'.
    """
    id_tiempo = models.AutoField(primary_key=True)
    anio = models.IntegerField()
    mes = models.IntegerField()
    trimestre = models.IntegerField()

    class Meta:
        db_table = 'dim_tiempo'
        constraints = [
            models.UniqueConstraint(
                fields=['anio', 'mes'],
                name='unique_dim_tiempo_anio_mes',
            ),
        ]

    def __str__(self):
        if self.anio == 0:
            return 'Desconocido'
        return f"{self.anio}-{self.mes:02d}"


class DimGeografia(models.Model):
    """
    - id_municipio = 0 -> registro a nivel entidad.
    - id_municipio > 0 -> registro a nivel municipio.
    """
    id_geografia = models.AutoField(primary_key=True)
    id_entidad = models.IntegerField()
    id_municipio = models.IntegerField(default=0)
    entidad_nombre = models.CharField(max_length=200)
    municipio_nombre = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = 'dim_geografia'
        constraints = [
            models.UniqueConstraint(
                fields=['id_entidad', 'id_municipio'],
                name='unique_dim_geo_ent_mun',
            ),
        ]
        indexes = [
            models.Index(fields=['id_entidad']),
        ]

    def __str__(self):
        if self.id_municipio:
            return f"{self.entidad_nombre} / {self.municipio_nombre}"
        return self.entidad_nombre


class DimCausa(models.Model):
    id_causa = models.AutoField(primary_key=True)
    codigo_cie10 = models.CharField(max_length=20, unique=True)
    descripcion_causa = models.TextField(null=True, blank=True)
    grupo_causa = models.CharField(max_length=100)

    class Meta:
        db_table = 'dim_causa'

    def __str__(self):
        return f"{self.codigo_cie10} - {self.grupo_causa}"


class DimEdad(models.Model):
    id_edad = models.AutoField(primary_key=True)
    edad_quinquenal = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'dim_edad'

    def __str__(self):
        return self.edad_quinquenal


# ============================================================
# GOLD - Hechos
# ============================================================
class FactMortalidadMaterna(models.Model):
    id_hecho = models.AutoField(primary_key=True)
    id_tiempo = models.ForeignKey(DimTiempo, on_delete=models.PROTECT)
    id_geografia = models.ForeignKey(DimGeografia, on_delete=models.PROTECT)
    id_causa = models.ForeignKey(DimCausa, on_delete=models.PROTECT)
    id_edad = models.ForeignKey(DimEdad, on_delete=models.PROTECT)
    numero_defunciones = models.IntegerField(default=1)
    incluida_en_rmm = models.BooleanField(default=False)
    id_registro_silver = models.OneToOneField(
        SilverMortalidadLimpia,
        on_delete=models.CASCADE,
        related_name='hecho_mortalidad',
        db_column='id_registro_silver',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fact_mortalidad_materna'
        indexes = [
            models.Index(fields=['id_tiempo']),
            models.Index(fields=['id_geografia']),
            models.Index(fields=['incluida_en_rmm']),
        ]


# ============================================================
# CONTROL DE CARGAS
# ============================================================
class ControlCargas(models.Model):
    ESTATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESADO', 'Procesado'),
        ('RECHAZADO', 'Rechazado'),
        ('DUPLICADO', 'Duplicado'),
        ('PDF_NO_PROCESABLE', 'PDF no procesable'),
        ('JSON_NO_PROCESABLE', 'JSON no procesable'),
    ]

    id_carga = models.AutoField(primary_key=True)
    nombre_archivo_original = models.CharField(max_length=500)
    hash_archivo = models.CharField(max_length=64, unique=True)
    version_archivo = models.CharField(max_length=20)
    estatus_procesamiento = models.CharField(max_length=30, choices=ESTATUS_CHOICES)
    filas_cargadas = models.IntegerField(default=0)
    mensaje = models.TextField(blank=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'control_cargas'
        ordering = ['-fecha_carga']

    def __str__(self):
        return f"{self.nombre_archivo_original} ({self.version_archivo}) - {self.estatus_procesamiento}"