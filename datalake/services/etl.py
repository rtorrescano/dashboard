# etl.py
"""
ETL Bronze -> Silver -> Gold.

Reglas:
- Bronze -> Silver:
    * Solo procesa Bronze VIGENTES y PENDIENTES.
    * Normaliza centinelas INEGI (99, 998, 9999) a None.
    * Si ya existe un Silver para este Bronze, hace snapshot en
      SilverMortalidadAuditoria y actualiza in-place, marcando
      requiere_recalculo_gold=True.
    * Marca PROCESADO solo a los que efectivamente se procesaron;
      los fallidos van a RECHAZADO.
    * Transacciones por lote.
- Silver -> Gold:
    * Procesa Silver vigentes que (a) aún no tienen fact o
      (b) tienen requiere_recalculo_gold=True.
    * Antes de recrear el fact borra el anterior.
    * DimTiempo usa anio=0 / mes=0 para desconocido.
    * DimGeografia guarda granularidad municipal (id_municipio=0 para
      nivel entidad).
"""
import re

from django.db import transaction

from datalake.models import (
    BronzeMortalidadRaw,
    SilverMortalidadLimpia,
    SilverMortalidadAuditoria,
    DimTiempo,
    DimGeografia,
    DimCausa,
    DimEdad,
    FactMortalidadMaterna,
)
from catalogos.models import CatalogoGeografico


PATRON_CIE10 = re.compile(r'^O\d{2}', re.IGNORECASE)

GRUPOS_CAUSA = [
    (re.compile(r'^O0[0-8]', re.I), 'Aborto'),
    (re.compile(r'^O1[0-6]', re.I), 'Hipertensión'),
    (re.compile(r'^O2[0-9]', re.I), 'Hemorragia'),
    (re.compile(r'^O3[0-9]', re.I), 'Hemorragia'),
    (re.compile(r'^O4[0-8]', re.I), 'Hemorragia'),
    (re.compile(r'^O6[0-9]', re.I), 'Hemorragia'),
    (re.compile(r'^O7[0-5]', re.I), 'Hemorragia'),
    (re.compile(r'^O8[5-6]', re.I), 'Sepsis'),
    (re.compile(r'^O8[7-9]', re.I), 'Sepsis'),
    (re.compile(r'^O9[0-9]', re.I), 'Indirectas'),
]


def clasificar_causa(codigo: str) -> str:
    if not codigo:
        return 'No especificada'
    codigo = codigo.strip().upper()
    for patron, grupo in GRUPOS_CAUSA:
        if patron.match(codigo):
            return grupo
    return 'Las demás complicaciones'


# ============================================================
# Helpers generales
# ============================================================
def _to_int(valor, default=None):
    try:
        return int(str(valor).strip())
    except (ValueError, TypeError):
        return default


def _incluida_en_rmm(br: BronzeMortalidadRaw) -> bool:
    """Se apoya en el indicador 0/1 que ya trae el CSV (más robusto que el texto)."""
    return _to_int(br.razon_mortalidad_materna) == 1


def _normalizar_anio(valor) -> int | None:
    anio = _to_int(valor)
    if anio is None or anio < 1900 or anio > 2100:
        return None
    return anio


def _normalizar_mes(valor) -> int | None:
    mes = _to_int(valor)
    if mes is None or mes < 1 or mes > 12:
        return None
    return mes


def _normalizar_dia(valor) -> int | None:
    dia = _to_int(valor)
    if dia is None or dia < 1 or dia > 31:
        return None
    return dia


def _normalizar_edad(valor) -> int | None:
    edad = _to_int(valor)
    if edad is None or edad < 0 or edad > 120:
        return None
    return edad


def _snapshot_silver(registro: SilverMortalidadLimpia) -> dict:
    return {
        c.name: getattr(registro, c.name)
        for c in SilverMortalidadLimpia._meta.fields
        if c.name != 'id_registro'
    }


# ============================================================
# Helpers de dimensiones
# ============================================================
def _get_or_create_tiempo(anio: int | None, mes: int | None) -> DimTiempo:
    """Usa (0, 0, 0) como 'desconocido' para no sesgar análisis."""
    anio = anio if anio and 1900 <= anio <= 2100 else 0
    mes = mes if mes and 1 <= mes <= 12 else 0
    trimestre = (mes - 1) // 3 + 1 if mes else 0
    obj, _ = DimTiempo.objects.get_or_create(
        anio=anio, mes=mes, defaults={'trimestre': trimestre}
    )
    return obj


def _get_or_create_geografia(entidad_id, entidad_nombre,
                             mun_id, mun_nombre) -> DimGeografia:
    """
    - Usa cve_ent del catálogo cuando se puede, en lugar de match por nombre
      (evita problemas con acentos).
    - Guarda el municipio cuando existe; id_municipio=0 para nivel entidad.
    """
    nombre_ent = (entidad_nombre or '').strip().upper() or 'DESCONOCIDA'

    # 1. Resolver entidad
    cat_estado = CatalogoGeografico.objects.filter(
        nom_ent__iexact=nombre_ent, cve_mun__isnull=True
    ).first()
    if cat_estado:
        eid = int(cat_estado.cve_ent)
        ent_oficial = cat_estado.nom_ent
    else:
        eid = entidad_id or 0
        ent_oficial = entidad_nombre or 'DESCONOCIDA'

    # 2. Intentar resolver municipio
    mid = 0
    mun_oficial = None
    if mun_id:
        cat_mun = CatalogoGeografico.objects.filter(
            cve_ent=str(eid).zfill(2),
            cve_mun=str(mun_id).zfill(3),
        ).first()
        if cat_mun:
            mid = int(cat_mun.cve_mun)
            mun_oficial = cat_mun.nom_mun
        else:
            mid = mun_id
            mun_oficial = (mun_nombre or '').strip() or None

    obj, _ = DimGeografia.objects.get_or_create(
        id_entidad=eid,
        id_municipio=mid,
        defaults={
            'entidad_nombre': ent_oficial[:200],
            'municipio_nombre': (mun_oficial[:200] if mun_oficial else None),
        },
    )
    return obj


def _get_or_create_causa(codigo, descripcion) -> DimCausa:
    codigo = codigo or 'SIN_CODIGO'
    obj, _ = DimCausa.objects.get_or_create(
        codigo_cie10=codigo,
        defaults={
            'descripcion_causa': descripcion,
            'grupo_causa': clasificar_causa(codigo),
        },
    )
    return obj


def _get_or_create_edad(edad_quinquenal) -> DimEdad:
    etiqueta = (edad_quinquenal or '').strip() or 'DESCONOCIDA'
    obj, _ = DimEdad.objects.get_or_create(edad_quinquenal=etiqueta)
    return obj


# ============================================================
# BRONZE -> SILVER
# ============================================================
def etl_bronze_a_silver(batch_size: int = 1000) -> dict:
    """
    Procesa Bronze PENDIENTE + vigentes en lotes.
    """
    stats = {'procesadas': 0, 'insertadas': 0, 'actualizadas': 0,
             'descartadas': 0, 'rechazadas': 0}

    pendientes_ids = list(
        BronzeMortalidadRaw.objects
        .filter(estatus_procesamiento='PENDIENTE', es_vigente=True)
        .order_by('id_carga')
        .values_list('id_carga', flat=True)
    )

    for i in range(0, len(pendientes_ids), batch_size):
        chunk = pendientes_ids[i:i + batch_size]
        with transaction.atomic():
            _procesar_chunk_bronze(chunk, stats)

    return stats


def _procesar_chunk_bronze(ids: list, stats: dict) -> None:
    procesados = []
    rechazados = []

    bronces = BronzeMortalidadRaw.objects.filter(id_carga__in=ids)
    for br in bronces:
        stats['procesadas'] += 1
        try:
            silver_existente = SilverMortalidadLimpia.objects.filter(
                id_carga_origen=br, es_vigente=True
            ).first()

            datos = {
                'anio_defuncion':       _normalizar_anio(br.anio_defuncion),
                'entidad_residencia':   _to_int(br.entidad_residencia),
                'entidad_nombre':       (br.entidad_residenciad or '').strip() or 'Desconocida',
                'municipio_residencia': _to_int(br.municipio_residencia),
                'municipio_nombre':     (br.municipio_residenciad or '').strip() or None,
                'localidad_nombre':     (br.localidad_residencia or '').strip() or None,
                'causa_cie_4':          (br.causa_cie_4 or '').strip().upper() or None,
                'causa_descripcion':    (br.causa_cie_4d or '').strip() or None,
                'edad':                 _normalizar_edad(br.edad),
                'edad_quinquenal':      (br.edad_quinquenal or '').strip() or None,
                'mes_defuncion':        _normalizar_mes(br.mes_defuncion),
                'dia_defuncion':        _normalizar_dia(br.dia_defuncion),
                'tamanio_localidad':    (br.tamanio_localidad or '').strip() or None,
                'sitio_defuncion':      (br.sitio_defunciond or '').strip() or 'No especificado',
                'escolaridad':          (br.escolaridadd or '').strip() or 'No especificado',
                'ocupacion':            (br.ocupacion_habituald or '').strip() or 'No especificado',
                'estado_conyugal':      (br.estado_conyugald or '').strip() or 'No especificado',
                'derechohabiencia':     (br.derechohabiendad or '').strip() or 'No especificado',
                'incluida_en_rmm':      _incluida_en_rmm(br),
                'hash_registro':        br.hash_registro,
            }

            if silver_existente is None:
                SilverMortalidadLimpia.objects.create(
                    id_carga_origen=br,
                    es_vigente=True,
                    version_registro=1,
                    requiere_recalculo_gold=True,
                    **datos,
                )
                stats['insertadas'] += 1
            else:
                # Snapshot ANTES de modificar
                SilverMortalidadAuditoria.objects.create(
                    id_registro_original=silver_existente,
                    id_carga_origen=br,
                    version_registro=silver_existente.version_registro,
                    hash_registro_anterior=silver_existente.hash_registro,
                    datos_anteriores=_snapshot_silver(silver_existente),
                    motivo='ACTUALIZACION_INCREMENTAL',
                )
                for campo, valor in datos.items():
                    setattr(silver_existente, campo, valor)
                silver_existente.version_registro += 1
                silver_existente.requiere_recalculo_gold = True
                silver_existente.save()
                stats['actualizadas'] += 1

            procesados.append(br.id_carga)
        except Exception:
            rechazados.append(br.id_carga)

    if procesados:
        BronzeMortalidadRaw.objects.filter(id_carga__in=procesados).update(
            estatus_procesamiento='PROCESADO'
        )
    if rechazados:
        BronzeMortalidadRaw.objects.filter(id_carga__in=rechazados).update(
            estatus_procesamiento='RECHAZADO'
        )
        stats['rechazadas'] += len(rechazados)


# ============================================================
# SILVER -> GOLD
# ============================================================
def etl_silver_a_gold(batch_size: int = 1000) -> dict:
    """
    Construye hechos para:
    - Silver vigentes sin fact asociado.
    - Silver vigentes con requiere_recalculo_gold=True (fueron actualizados).
    Antes de recrear el fact, borra el anterior.
    """
    stats = {'hechos_insertados': 0, 'hechos_reemplazados': 0}

    ids_con_fact = set(
        FactMortalidadMaterna.objects.values_list('id_registro_silver_id', flat=True)
    )

    silver_nuevos_ids = list(
        SilverMortalidadLimpia.objects
        .filter(es_vigente=True)
        .exclude(id_registro__in=ids_con_fact)
        .values_list('id_registro', flat=True)
    )
    silver_modificados_ids = list(
        SilverMortalidadLimpia.objects
        .filter(es_vigente=True, requiere_recalculo_gold=True)
        .exclude(id_registro__in=silver_nuevos_ids)  # evitar duplicar
        .values_list('id_registro', flat=True)
    )

    todos_ids = silver_nuevos_ids + silver_modificados_ids

    for i in range(0, len(todos_ids), batch_size):
        chunk = todos_ids[i:i + batch_size]
        with transaction.atomic():
            _procesar_chunk_gold(chunk, set(silver_nuevos_ids), stats)

    return stats


def _procesar_chunk_gold(ids: list, nuevos_ids: set, stats: dict) -> None:
    hechos = []
    for sr in SilverMortalidadLimpia.objects.filter(id_registro__in=ids):
        tiempo    = _get_or_create_tiempo(sr.anio_defuncion, sr.mes_defuncion)
        geografia = _get_or_create_geografia(
            sr.entidad_residencia, sr.entidad_nombre,
            sr.municipio_residencia, sr.municipio_nombre,
        )
        causa = _get_or_create_causa(sr.causa_cie_4, sr.causa_descripcion)
        edad  = _get_or_create_edad(sr.edad_quinquenal)

        # Reemplazo idempotente
        if sr.id_registro in nuevos_ids:
            stats['hechos_insertados'] += 1
        else:
            FactMortalidadMaterna.objects.filter(id_registro_silver=sr).delete()
            stats['hechos_reemplazados'] += 1

        hechos.append(FactMortalidadMaterna(
            id_tiempo=tiempo,
            id_geografia=geografia,
            id_causa=causa,
            id_edad=edad,
            numero_defunciones=1,
            incluida_en_rmm=sr.incluida_en_rmm,
            id_registro_silver=sr,
        ))
        sr.requiere_recalculo_gold = False

    if hechos:
        FactMortalidadMaterna.objects.bulk_create(hechos, batch_size=1000)
    if ids:
        SilverMortalidadLimpia.objects.filter(id_registro__in=ids).update(
            requiere_recalculo_gold=False
        )