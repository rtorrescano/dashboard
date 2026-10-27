"""
Servicios ETL: Bronze -> Silver -> Gold.

Reglas de negocio:
- Solo procesar filas Bronze con estatus_procesamiento='PENDIENTE'.
- Tipar anio/mes/edad a enteros; ignorar filas sin año válido.
- Validar código CIE-10 con patrón O\\d{2} (capítulo XV, O00-O99).
- Deduplicar por (anio, entidad, mes, dia, edad, causa).
- incluida_en_rmm = True si RAZON_MORTALIDAD_MATERNAD contiene
  "MUERTES MATERNAS PARA LA RAZON".
- Agrupar causa según criterios DGE (Hemorragia, Hipertensión, Aborto,
  Sepsis, Indirectas, Otras).
"""

import re
from collections import defaultdict

from django.db import transaction
from django.db.models import Max

from datalake.models import (
    BronzeMortalidadRaw,
    SilverMortalidadLimpia,
    DimTiempo,
    DimGeografia,
    DimCausa,
    DimEdad,
    FactMortalidadMaterna,
)


PATRON_CIE10 = re.compile(r'^O\d{2}', re.IGNORECASE)


# Mapeo de prefijos CIE-10 a grupos DGE
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
    """Devuelve el grupo DGE para un código CIE-10. 'Otras' si no coincide."""
    if not codigo:
        return 'Otras'
    codigo = codigo.strip().upper()
    for patron, grupo in GRUPOS_CAUSA:
        if patron.match(codigo):
            return grupo
    return 'Otras'


def _to_int(valor, default=None):
    try:
        return int(str(valor).strip())
    except (ValueError, TypeError):
        return default


def _incluida_en_rmm(razon_maternad: str) -> bool:
    """True si el texto indica que la defunción cuenta para la RMM oficial."""
    if not razon_maternad:
        return False
    return 'MUERTES MATERNAS PARA LA RAZON' in razon_maternad.upper()


# ---------------------------------------------------------------------------
# BRONZE -> SILVER
# ---------------------------------------------------------------------------
@transaction.atomic
def etl_bronze_a_silver() -> dict:
    pendientes = BronzeMortalidadRaw.objects.filter(
        estatus_procesamiento='PENDIENTE'
    ).order_by('id_carga')

    procesadas = insertadas = descartadas = duplicadas = 0
    ids_procesados = []

    for br in pendientes.iterator(chunk_size=1000):
        procesadas += 1
        ids_procesados.append(br.id_carga)

        anio = _to_int(br.anio_defuncion)
        if anio is None or anio < 1990 or anio > 2100:
            descartadas += 1
            continue

        entidad_id  = _to_int(br.entidad_residencia)
        mes         = _to_int(br.mes_defuncion)
        edad        = _to_int(br.edad)
        causa_codigo = (br.causa_cie_4 or '').strip().upper()

        try:
            SilverMortalidadLimpia.objects.create(
                id_carga_origen      = br,
                anio_defuncion       = anio,
                entidad_residencia   = entidad_id,
                entidad_nombre       = (br.entidad_residenciad or '').strip(),
                municipio_nombre     = (br.municipio_residenciad or '').strip(), # NUEVO
                causa_cie_4          = causa_codigo or None,
                causa_descripcion    = (br.causa_cie_4d or '').strip() or None,
                edad                 = edad,
                edad_quinquenal      = (br.edad_quinquenal or '').strip() or None,
                mes_defuncion        = mes,
                dia_defuncion        = None,
                tamanio_localidad    = (br.tamanio_localidad or '').strip() or None,
                
                # NUEVOS CAMPOS
                sitio_defuncion      = (br.sitio_defuncion or '').strip() or 'No especificado',
                escolaridad          = (br.escolaridad or '').strip() or 'No especificado',
                ocupacion            = (br.ocupacion or '').strip() or 'No especificado',
                estado_conyugal      = (br.estado_conyugal or '').strip() or 'No especificado',
                derechohabiencia     = (br.derechohabiencia or '').strip() or 'No especificado',
                
                incluida_en_rmm      = _incluida_en_rmm(br.razon_mortalidad_maternad),
            )
            insertadas += 1
        except Exception as e:
            if 'uq_silver_dedup' in str(e) or 'duplicate key' in str(e).lower():
                duplicadas += 1
            else:
                descartadas += 1
            continue

    # Marcar Bronze como procesado
    if ids_procesados:
        BronzeMortalidadRaw.objects.filter(
            id_carga__in=ids_procesados
        ).update(estatus_procesamiento='PROCESADO')

    return {
        'procesadas': procesadas,
        'insertadas': insertadas,
        'descartadas': descartadas,
        'duplicadas': duplicadas,
    }


# ---------------------------------------------------------------------------
# SILVER -> GOLD
# ---------------------------------------------------------------------------
def _get_or_create_tiempo(anio: int, mes: int) -> DimTiempo:
    mes = mes if 1 <= mes <= 12 else 1
    trimestre = (mes - 1) // 3 + 1
    obj, _ = DimTiempo.objects.get_or_create(
        anio=anio, mes=mes, defaults={'trimestre': trimestre}
    )
    return obj


def _get_or_create_geografia(entidad_id, entidad_nombre) -> DimGeografia:
    obj, _ = DimGeografia.objects.get_or_create(
        id_entidad=entidad_id or 0,
        id_municipio=None,
        defaults={'entidad_nombre': entidad_nombre or 'DESCONOCIDA'},
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
    etiqueta = edad_quinquenal or 'DESCONOCIDA'
    obj, _ = DimEdad.objects.get_or_create(edad_quinquenal=etiqueta)
    return obj


@transaction.atomic
def etl_silver_a_gold() -> dict:
    """
    Puebla dimensiones y hechos desde Silver.
    Solo inserta hechos para registros Silver que aún no tienen hecho asociado.
    Devuelve {'hechos_insertados': N}.
    """
    ya_en_gold = set(
        FactMortalidadMaterna.objects
        .exclude(id_registro_silver__isnull=True)
        .values_list('id_registro_silver_id', flat=True)
    )

    pendientes = (
        SilverMortalidadLimpia.objects
        .exclude(id_registro__in=ya_en_gold)
        .order_by('id_registro')
    )

    hechos = []
    for sr in pendientes.iterator(chunk_size=1000):
        tiempo    = _get_or_create_tiempo(sr.anio_defuncion, sr.mes_defuncion or 1)
        geografia = _get_or_create_geografia(sr.entidad_residencia, sr.entidad_nombre)
        causa     = _get_or_create_causa(sr.causa_cie_4, sr.causa_descripcion)
        edad      = _get_or_create_edad(sr.edad_quinquenal)

        hechos.append(FactMortalidadMaterna(
            id_tiempo          = tiempo,
            id_geografia       = geografia,
            id_causa           = causa,
            id_edad            = edad,
            numero_defunciones = 1,
            incluida_en_rmm    = sr.incluida_en_rmm,
            id_registro_silver = sr,
        ))

    FactMortalidadMaterna.objects.bulk_create(hechos, batch_size=1000)
    return {'hechos_insertados': len(hechos)}