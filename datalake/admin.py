from django.contrib import admin

from .models import (
    BronzeMortalidadRaw,
    SilverMortalidadLimpia,
    DimTiempo,
    DimGeografia,
    DimCausa,
    DimEdad,
    FactMortalidadMaterna,
    NacimientosEstimados,
)


class SoloLecturaAdmin(admin.ModelAdmin):
    """
    Mixin: registra un modelo como inspección de solo lectura.
    - Todos los campos aparecen en el detalle como readonly.
    - Se bloquean alta, edición y borrado desde el admin.
    - Permite búsqueda, filtros y paginación para explorar los datos.
    """
    list_per_page = 50
    show_full_result_count = False

    def get_readonly_fields(self, request, obj=None):
        # Todos los campos del modelo, sin excepción
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# BRONZE
# ---------------------------------------------------------------------------
@admin.register(BronzeMortalidadRaw)
class BronzeMortalidadRawAdmin(SoloLecturaAdmin):
    list_display = (
        'id_carga', 'nombre_archivo_original', 'version_archivo',
        'hash_archivo', 'fecha_carga', 'estatus_procesamiento',
    )
    list_filter   = ('estatus_procesamiento', 'version_archivo')
    search_fields = ('nombre_archivo_original', 'hash_archivo')
    date_hierarchy = 'fecha_carga'
    ordering = ('-fecha_carga',)


# ---------------------------------------------------------------------------
# SILVER
# ---------------------------------------------------------------------------
@admin.register(SilverMortalidadLimpia)
class SilverMortalidadLimpiaAdmin(SoloLecturaAdmin):
    list_display = (
        'id_registro', 'anio_defuncion', 'entidad_nombre',
        'causa_cie_4', 'edad_quinquenal', 'incluida_en_rmm',
    )
    list_filter   = ('anio_defuncion', 'incluida_en_rmm', 'entidad_nombre')
    search_fields = ('entidad_nombre', 'causa_cie_4', 'causa_descripcion')
    ordering = ('-anio_defuncion', 'entidad_nombre')
    list_select_related = ('id_carga_origen',)


# ---------------------------------------------------------------------------
# GOLD - DIMENSIONES
# ---------------------------------------------------------------------------
@admin.register(DimTiempo)
class DimTiempoAdmin(SoloLecturaAdmin):
    list_display  = ('id_tiempo', 'anio', 'mes', 'trimestre')
    list_filter   = ('anio', 'trimestre')
    ordering      = ('-anio', '-mes')


@admin.register(DimGeografia)
class DimGeografiaAdmin(SoloLecturaAdmin):
    list_display  = ('id_geografia', 'id_entidad', 'entidad_nombre', 'id_municipio', 'municipio_nombre')
    list_filter   = ('id_entidad',)
    search_fields = ('entidad_nombre', 'municipio_nombre')
    ordering      = ('id_entidad', 'id_municipio')


@admin.register(DimCausa)
class DimCausaAdmin(SoloLecturaAdmin):
    list_display  = ('id_causa', 'codigo_cie10', 'grupo_causa', 'descripcion_causa')
    list_filter   = ('grupo_causa',)
    search_fields = ('codigo_cie10', 'descripcion_causa')
    ordering      = ('codigo_cie10',)


@admin.register(DimEdad)
class DimEdadAdmin(SoloLecturaAdmin):
    list_display  = ('id_edad', 'edad_quinquenal')
    ordering      = ('id_edad',)


# ---------------------------------------------------------------------------
# GOLD - HECHOS
# ---------------------------------------------------------------------------
@admin.register(FactMortalidadMaterna)
class FactMortalidadMaternaAdmin(SoloLecturaAdmin):
    list_display = (
        'id_hecho', 'id_tiempo', 'id_geografia', 'id_causa',
        'id_edad', 'numero_defunciones', 'incluida_en_rmm',
    )
    list_filter   = ('incluida_en_rmm',)
    ordering      = ('-id_hecho',)
    list_select_related = ('id_tiempo', 'id_geografia', 'id_causa', 'id_edad')


# ---------------------------------------------------------------------------
# GOLD - PARAMÉTRICA
# ---------------------------------------------------------------------------
@admin.register(NacimientosEstimados)
class NacimientosEstimadosAdmin(SoloLecturaAdmin):
    """
    Solo lectura desde el admin. La carga de nacimientos se hace por
    management command o SQL directo para preservar la fuente oficial.
    """
    list_display   = ('anio', 'id_entidad', 'nacimientos', 'fuente', 'fecha_carga')
    list_filter    = ('anio', 'fuente')
    search_fields  = ('fuente',)
    ordering       = ('-anio', 'id_entidad')