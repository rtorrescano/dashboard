# ingesta.py
"""
Ingesta incremental de archivos CSV a la capa Bronze.

Reglas:
- El hash de negocio (hash_registro) identifica un HECHO. Se calcula SOLO
  sobre CAMPOS_CLAVE_NEGOCIO (fecha + lugar + demografía). Los campos
  descriptivos (causa, escolaridad, etc.) son actualizables y NO forman
  parte de la clave: si cambian, se actualiza el registro in-place y se
  guarda snapshot en BronzeMortalidadAuditoria.
- Se rechazan archivos cuyo hash_archivo ya exista (constraint único).
- Se procesa en lotes; no se hace una query por fila.
"""
import hashlib
from pathlib import Path

import chardet
import pandas as pd
from django.db import transaction

from datalake.models import (
    BronzeMortalidadRaw,
    BronzeMortalidadAuditoria,
    ControlCargas,
)


MAPA_COLUMNAS = {
    'ANIO_NACIMIENTO': 'anio_nacimiento',
    'MES_NACIMIENTO': 'mes_nacimiento',
    'MES_NACIMIENTOD': 'mes_nacimientod',
    'DIA_NACIMIENTO': 'dia_nacimiento',
    'EDAD': 'edad',
    'ESTADO_CONYUGAL': 'estado_conyugal',
    'ESTADO_CONYUGAL_D': 'estado_conyugald',
    'ENTIDAD_RESIDENCIA': 'entidad_residencia',
    'ENTIDAD_RESIDENCIAD': 'entidad_residenciad',
    'MUNICIPIO_RESIDENCIA': 'municipio_residencia',
    'MUNICIPIO_RESIDENCIAD': 'municipio_residenciad',
    'LOCALIDAD_RESIDENCIA': 'localidad_residencia',
    'LOCALIDAD_RESIDENCIAD': 'localidad_residenciad',
    'TAMANIO_LOCALIDAD': 'tamanio_localidad',
    'TAMANIO_LOCALIDADD': 'tamanio_localidadd',
    'OCUPACION_HABITUAL': 'ocupacion_habitual',
    'OCUPACION_HABITUALD': 'ocupacion_habituald',
    'ESCOLARIDAD': 'escolaridad',
    'ESCOLARIDADD': 'escolaridadd',
    'DERECHOHABIENCIA': 'derechohabiencia',
    'DERECHOHABIENCIAD': 'derechohabiendad',
    'ENTIDAD_OCURRENCIA': 'entidad_ocurrencia',
    'ENTIDAD_OCURRENCIAD': 'entidad_ocurrenciad',
    'MUNICIPIO_OCURRENCIA': 'municipio_ocurrencia',
    'MUNICIPIO_OCURRENCIAD': 'municipio_ocurrenciad',
    'LOCALIDAD_OCURRENCIA': 'localidad_ocurrencia',
    'LOCALIDAD_OCURRENCIAD': 'localidad_ocurrenciad',
    'SITIO_DEFUNCION': 'sitio_defuncion',
    'SITIO_DEFUNCIOND': 'sitio_defunciond',
    'ANIO_DEFUNCION': 'anio_defuncion',
    'MES_DEFUNCION': 'mes_defuncion',
    'MES_DEFUNCIOND': 'mes_defunciond',
    'DIA_DEFUNCION': 'dia_defuncion',
    'HORA_DEFUNCION': 'hora_defuncion',
    'MINUTOS_DEFUNCION': 'minutos_defuncion',
    'ASISTENCIA_MEDICA': 'asistencia_medica',
    'ASISTENCIA_MEDICAD': 'asistencia_medicad',
    'CAUSA_CIE_4': 'causa_cie_4',
    'CAUSA_CIE_4D': 'causa_cie_4d',
    'CERTIFICO': 'certifico',
    'CERTIFICOD': 'certificod',
    'ENTIDAD_REGISTRO': 'entidad_registro',
    'ENTIDAD_REGISTROD': 'entidad_registrod',
    'MUNICIPIO_REGISTRO': 'municipio_registro',
    'MUNICIPIO_REGISTROD': 'municipio_registrod',
    'ANIO_REGISTRO': 'anio_registro',
    'MES_REGISTRO': 'mes_registro',
    'MES_REGISTROD': 'mes_registrod',
    'DIA_REGISTRO': 'dia_registro',
    'ANIO_CERTIFICACION': 'anio_certificacion',
    'MES_CERTIFICACION': 'mes_certificacion',
    'MES_CERTIFICACIOND': 'mes_certificaciond',
    'DIA_CERTIFICACION': 'dia_certificacion',
    'ANIO_BASE_DATOS': 'anio_base_datos',
    'RAZON_MORTALIDAD_MATERNA': 'razon_mortalidad_materna',
    'RAZON_MORTALIDAD_MATERNAD': 'razon_mortalidad_maternad',
    'EDAD_QUINQUENAL': 'edad_quinquenal',
    'EDAD_QUINQUENALD': 'edad_quinquenald',
}

# Clave de negocio: identifica un HECHO (muerte).
# NO incluye causa_cie_4 porque una re-clasificación forense debe actualizar,
# no crear un nuevo hecho.
CAMPOS_CLAVE_NEGOCIO = [
    'anio_defuncion', 'mes_defuncion', 'dia_defuncion',
    'hora_defuncion', 'minutos_defuncion',
    'anio_nacimiento', 'mes_nacimiento', 'dia_nacimiento',
    'entidad_residencia', 'municipio_residencia', 'localidad_residencia',
    'edad',
]

MAX_LONGITUDES = {
    'anio_nacimiento': 10, 'mes_nacimiento': 10, 'mes_nacimientod': 50,
    'dia_nacimiento': 10, 'edad': 10, 'estado_conyugal': 10,
    'estado_conyugald': 200, 'entidad_residencia': 10,
    'entidad_residenciad': 200, 'municipio_residencia': 10,
    'municipio_residenciad': 200, 'localidad_residencia': 200,
    'localidad_residenciad': 300, 'tamanio_localidad': 50,
    'tamanio_localidadd': 100, 'ocupacion_habitual': 10,
    'ocupacion_habituald': 300, 'escolaridad': 10, 'escolaridadd': 300,
    'derechohabiencia': 10, 'derechohabiendad': 200,
    'entidad_ocurrencia': 10, 'entidad_ocurrenciad': 200,
    'municipio_ocurrencia': 10, 'municipio_ocurrenciad': 200,
    'localidad_ocurrencia': 200, 'localidad_ocurrenciad': 300,
    'sitio_defuncion': 10, 'sitio_defunciond': 200,
    'anio_defuncion': 10, 'mes_defuncion': 10, 'mes_defunciond': 50,
    'dia_defuncion': 10, 'hora_defuncion': 10, 'minutos_defuncion': 10,
    'asistencia_medica': 10, 'asistencia_medicad': 100,
    'causa_cie_4': 20, 'causa_cie_4d': 300,
    'certifico': 10, 'certificod': 100,
    'entidad_registro': 10, 'entidad_registrod': 200,
    'municipio_registro': 10, 'municipio_registrod': 200,
    'anio_registro': 10, 'mes_registro': 10, 'mes_registrod': 50,
    'dia_registro': 10, 'anio_certificacion': 10,
    'mes_certificacion': 10, 'mes_certificaciond': 50,
    'dia_certificacion': 10, 'anio_base_datos': 10,
    'razon_mortalidad_materna': 50, 'razon_mortalidad_maternad': 100,
    'edad_quinquenal': 20, 'edad_quinquenald': 50,
}


class ResultadoIngesta:
    def __init__(self, estado, mensaje, id_carga=None, filas=0, version=None,
                 nuevas=0, actualizadas=0, sin_cambios=0):
        self.estado = estado
        self.mensaje = mensaje
        self.id_carga = id_carga
        self.filas = filas
        self.version = version
        self.nuevas = nuevas
        self.actualizadas = actualizadas
        self.sin_cambios = sin_cambios

    def __repr__(self):
        return (f"ResultadoIngesta(estado={self.estado!r}, filas={self.filas}, "
                f"nuevas={self.nuevas}, actualizadas={self.actualizadas}, "
                f"sin_cambios={self.sin_cambios}, version={self.version!r})")


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def calcular_hash(ruta_archivo: Path) -> str:
    sha = hashlib.sha256()
    with open(ruta_archivo, 'rb') as f:
        for bloque in iter(lambda: f.read(8192), b''):
            sha.update(bloque)
    return sha.hexdigest()


def _siguiente_version(nombre_archivo: str) -> str:
    existentes = ControlCargas.objects.filter(
        nombre_archivo_original=nombre_archivo
    ).values_list('version_archivo', flat=True)
    if not existentes:
        return 'v1'
    nums = [int(v.lstrip('v')) for v in existentes
            if v.startswith('v') and v.lstrip('v').isdigit()]
    return f'v{max(nums) + 1}' if nums else 'v1'


def _detectar_encoding(ruta_archivo: Path) -> str:
    with open(ruta_archivo, 'rb') as f:
        muestra = f.read(65536)
    deteccion = chardet.detect(muestra)
    encoding = deteccion.get('encoding') or 'latin-1'
    if (deteccion.get('confidence') or 0) < 0.7:
        encoding = 'cp1252'
    return encoding


def _leer_archivo(ruta_archivo: Path) -> pd.DataFrame:
    ext = ruta_archivo.suffix.lower()
    if ext == '.csv':
        encoding = _detectar_encoding(ruta_archivo)
        try:
            return pd.read_csv(
                ruta_archivo, dtype=str, keep_default_na=False,
                encoding=encoding, sep=None, engine='python',
            )
        except UnicodeDecodeError:
            return pd.read_csv(
                ruta_archivo, dtype=str, keep_default_na=False,
                encoding='latin-1', sep=None, engine='python',
            )
    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(ruta_archivo, dtype=str, keep_default_na=False)
    raise ValueError(f'Extensión no soportada: {ext}')


def _calcular_hash_registro(datos: dict) -> str:
    """Hash sobre la CLAVE DE NEGOCIO (identifica un hecho, no la carga)."""
    payload = '|'.join(str(datos.get(c) or '') for c in CAMPOS_CLAVE_NEGOCIO)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _normalizar_fila(fila: pd.Series) -> dict:
    datos = {}
    for col_csv, campo_modelo in MAPA_COLUMNAS.items():
        valor = str(fila.get(col_csv, '') or '').strip()
        max_len = MAX_LONGITUDES.get(campo_modelo, 300)
        datos[campo_modelo] = valor[:max_len] if valor else None
    return datos


def _snapshot(registro: BronzeMortalidadRaw) -> dict:
    return {
        c.name: getattr(registro, c.name)
        for c in BronzeMortalidadRaw._meta.fields
        if c.name != 'id_carga'
    }


# ------------------------------------------------------------
# Ingesta principal
# ------------------------------------------------------------
@transaction.atomic
def ingestar_archivo(ruta_archivo: str, batch_size: int = 1000) -> ResultadoIngesta:
    ruta = Path(ruta_archivo).resolve()
    if not ruta.exists():
        return ResultadoIngesta('ERROR', f'Archivo no encontrado: {ruta}')

    nombre = ruta.name
    extension = ruta.suffix.lower()
    hash_archivo = calcular_hash(ruta)

    # Rechazo de archivos idénticos (mismo binario)
    if ControlCargas.objects.filter(hash_archivo=hash_archivo).exists():
        return ResultadoIngesta('DUPLICADO', 'El archivo ya fue cargado previamente.')

    version = _siguiente_version(nombre)

    if extension in ('.pdf', '.json'):
        estatus = 'PDF_NO_PROCESABLE' if extension == '.pdf' else 'JSON_NO_PROCESABLE'
        ControlCargas.objects.create(
            nombre_archivo_original=nombre,
            hash_archivo=hash_archivo,
            version_archivo=version,
            estatus_procesamiento=estatus,
            filas_cargadas=0,
            mensaje=f'{extension[1:].upper()} sin procesamiento',
        )
        return ResultadoIngesta(
            'NO_PROCESABLE',
            f'{extension[1:].upper()} registrado. Versión {version}.',
            version=version,
        )

    try:
        df = _leer_archivo(ruta)
    except Exception as e:
        return ResultadoIngesta('ERROR', f'Error al leer: {e}')

    df.columns = [str(c).strip().upper() for c in df.columns]

    if 'ANIO_DEFUNCION' not in df.columns:
        return ResultadoIngesta('ERROR', 'Falta la columna obligatoria: ANIO_DEFUNCION')

    control = ControlCargas.objects.create(
        nombre_archivo_original=nombre,
        hash_archivo=hash_archivo,
        version_archivo=version,
        estatus_procesamiento='PENDIENTE',
    )

    # Paso 1: normalizar y calcular hash de negocio para todas las filas
    filas = []
    for _, fila in df.iterrows():
        datos = _normalizar_fila(fila)
        hash_registro = _calcular_hash_registro(datos)
        filas.append((datos, hash_registro))

    # Paso 2: precargar existentes en un solo query (evita O(n) round-trips)
    hashes_unicos = {h for _, h in filas}
    existentes = {
        obj.hash_registro: obj
        for obj in BronzeMortalidadRaw.objects.filter(
            es_vigente=True, hash_registro__in=hashes_unicos
        )
    }

    # Paso 3: clasificar y actualizar
    nuevas = actualizadas = sin_cambios = 0
    registros_a_crear = []
    actualizaciones = []
    snapshots_auditoria = []

    for datos, hash_registro in filas:
        existente = existentes.get(hash_registro)

        if existente is None:
            registros_a_crear.append(BronzeMortalidadRaw(
                **datos,
                nombre_archivo_original=nombre,
                hash_archivo=hash_archivo,
                version_archivo=version,
                hash_registro=hash_registro,
                estatus_procesamiento='PENDIENTE',
                es_vigente=True,
                version_registro=1,
            ))
            nuevas += 1
            continue

        datos_anteriores_negocio = {
            campo: getattr(existente, campo) for campo in datos.keys()
        }
        if datos_anteriores_negocio == datos:
            sin_cambios += 1
            continue

        # Auditoría
        snapshots_auditoria.append(BronzeMortalidadAuditoria(
            id_registro_original=existente.id_carga,
            hash_registro=existente.hash_registro,
            version_registro=existente.version_registro,
            datos_anteriores=_snapshot(existente),
            hash_archivo_nuevo=hash_archivo,
            nombre_archivo_nuevo=nombre,
            motivo='ACTUALIZACION_INCREMENTAL',
        ))

        for campo, valor in datos.items():
            setattr(existente, campo, valor)
        existente.hash_archivo = hash_archivo
        existente.nombre_archivo_original = nombre
        existente.version_archivo = version
        existente.version_registro += 1
        existente.estatus_procesamiento = 'PENDIENTE'  # forzar reproceso en Silver
        actualizaciones.append(existente)
        actualizadas += 1

    # Paso 4: persistir en lotes (evita transacciones gigantes)
    def _chunks(seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    if registros_a_crear:
        for lote in _chunks(registros_a_crear, batch_size):
            BronzeMortalidadRaw.objects.bulk_create(lote, batch_size=batch_size)

    if actualizaciones:
        for lote in _chunks(actualizaciones, batch_size):
            BronzeMortalidadRaw.objects.bulk_update(
                lote,
                fields=list(MAPA_COLUMNAS.values()) + [
                    'hash_archivo', 'nombre_archivo_original', 'version_archivo',
                    'version_registro', 'estatus_procesamiento',
                ],
                batch_size=batch_size,
            )

    if snapshots_auditoria:
        for lote in _chunks(snapshots_auditoria, batch_size):
            BronzeMortalidadAuditoria.objects.bulk_create(lote, batch_size=batch_size)

    control.filas_cargadas = len(df)
    control.estatus_procesamiento = 'PROCESADO'
    control.mensaje = (
        f'{len(df)} filas leídas. Nuevas: {nuevas}, '
        f'actualizadas: {actualizadas}, sin cambios: {sin_cambios}.'
    )
    control.save()

    return ResultadoIngesta(
        'OK',
        control.mensaje,
        id_carga=control.id_carga,
        filas=len(df),
        version=version,
        nuevas=nuevas,
        actualizadas=actualizadas,
        sin_cambios=sin_cambios,
    )