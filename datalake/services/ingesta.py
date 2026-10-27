"""
Servicio de ingesta a la capa Bronze.

Responsabilidades:
- Calcular SHA-256 del archivo.
- Rechazar duplicados exactos (mismo hash) usando bronze.control_cargas.
- Versionar archivos con el mismo nombre pero distinto contenido (v1, v2, ...).
- Insertar una fila por registro del CSV/Excel en bronze.bronze_mortalidad_raw.
- Registrar PDF/JSON sin procesarlos (solo metadatos en control_cargas).
- Detectar codificación (UTF-8, Latin-1, Windows-1252) y separador (coma, ;).
"""

import hashlib
from pathlib import Path

import chardet
import pandas as pd
from django.db import transaction

from datalake.models import BronzeMortalidadRaw, ControlCargas


# Columnas esperadas del CSV -> campo del modelo Bronze
MAPA_COLUMNAS = {
    'ANIO_DEFUNCION':              'anio_defuncion',
    'ENTIDAD_RESIDENCIA':          'entidad_residencia',
    'ENTIDAD_RESIDENCIAD':         'entidad_residenciad',
    'MUNICIPIO_RESIDENCIAD':       'municipio_residenciad', # NUEVO
    'CAUSA_CIE_4':                 'causa_cie_4',
    'CAUSA_CIE_4D':                'causa_cie_4d',
    'EDAD':                        'edad',
    'EDAD_QUINQUENAL':             'edad_quinquenal',
    'RAZON_MORTALIDAD_MATERNA':    'razon_mortalidad_materna',
    'RAZON_MORTALIDAD_MATERNAD':   'razon_mortalidad_maternad',
    'MES_DEFUNCION':               'mes_defuncion',
    'TAMANIO_LOCALIDAD':           'tamanio_localidad',
    'SITIO_DEFUNCIOND':            'sitio_defuncion',      # NUEVO
    'ESCOLARIDADD':                'escolaridad',          # NUEVO
    'OCUPACION_HABITUALD':         'ocupacion',            # NUEVO
    'ESTADO_CONYUGALD':            'estado_conyugal',      # NUEVO
    'DERECHOHABIENCIAD':           'derechohabiencia',     # NUEVO
}


class ResultadoIngesta:
    """Objeto de retorno con el resultado de la operación."""

    def __init__(self, estado, mensaje, id_carga=None, filas=0, version=None):
        self.estado   = estado    # 'OK' | 'DUPLICADO' | 'ERROR' | 'NO_PROCESABLE'
        self.mensaje  = mensaje
        self.id_carga = id_carga
        self.filas    = filas
        self.version  = version

    def __repr__(self):
        return f'<Ingesta {self.estado}: {self.mensaje}>'


def calcular_hash(ruta_archivo: Path) -> str:
    """Calcula SHA-256 en bloques para archivos grandes."""
    sha = hashlib.sha256()
    with open(ruta_archivo, 'rb') as f:
        for bloque in iter(lambda: f.read(8192), b''):
            sha.update(bloque)
    return sha.hexdigest()


def _siguiente_version(nombre_archivo: str) -> str:
    """
    Calcula la siguiente versión para un nombre de archivo dado.
    v1 si no existe; v2, v3, ... si ya hay versiones previas.
    """
    existentes = (
        ControlCargas.objects
        .filter(nombre_archivo_original=nombre_archivo)
        .values_list('version_archivo', flat=True)
    )
    if not existentes:
        return 'v1'
    nums = []
    for v in existentes:
        try:
            nums.append(int(v.lstrip('v')))
        except ValueError:
            continue
    return f'v{max(nums) + 1}' if nums else 'v1'


def _detectar_encoding(ruta_archivo: Path) -> str:
    """
    Detecta la codificación leyendo los primeros 64 KB.
    Fallback a 'cp1252' si la confianza es baja (típico en archivos mexicanos).
    """
    with open(ruta_archivo, 'rb') as f:
        muestra = f.read(65536)
    deteccion = chardet.detect(muestra)
    encoding = deteccion.get('encoding') or 'latin-1'
    confianza = deteccion.get('confidence') or 0
    if confianza < 0.7:
        encoding = 'cp1252'
    return encoding


def _leer_archivo(ruta_archivo: Path) -> pd.DataFrame:
    """Lee CSV o Excel en un DataFrame, todo como string."""
    ext = ruta_archivo.suffix.lower()

    if ext == '.csv':
        encoding = _detectar_encoding(ruta_archivo)
        try:
            return pd.read_csv(
                ruta_archivo,
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
                sep=None,          # autodetecta ',' o ';'
                engine='python',
            )
        except UnicodeDecodeError:
            return pd.read_csv(
                ruta_archivo,
                dtype=str,
                keep_default_na=False,
                encoding='latin-1',
                sep=None,
                engine='python',
            )

    if ext in ('.xlsx', '.xls'):
        return pd.read_excel(ruta_archivo, dtype=str, keep_default_na=False)

    raise ValueError(f'Extensión no soportada para procesamiento: {ext}')


@transaction.atomic
def ingestar_archivo(ruta_archivo: str) -> ResultadoIngesta:
    """
    Punto de entrada principal. Devuelve un ResultadoIngesta.
    """
    ruta = Path(ruta_archivo).resolve()
    if not ruta.exists():
        return ResultadoIngesta('ERROR', f'Archivo no encontrado: {ruta}')

    nombre = ruta.name
    extension = ruta.suffix.lower()
    hash_archivo = calcular_hash(ruta)

    # 1. Duplicado exacto (verifica en la tabla de control)
    if ControlCargas.objects.filter(hash_archivo=hash_archivo).exists():
        return ResultadoIngesta(
            'DUPLICADO',
            f'El archivo ya fue cargado previamente (hash {hash_archivo[:12]}...).',
        )

    version = _siguiente_version(nombre)

    # 2. PDF / JSON: solo registrar metadatos en control_cargas
    if extension in ('.pdf', '.json'):
        estatus = 'PDF_NO_PROCESABLE' if extension == '.pdf' else 'JSON_NO_PROCESABLE'
        control = ControlCargas.objects.create(
            nombre_archivo_original=nombre,
            hash_archivo=hash_archivo,
            version_archivo=version,
            estatus_procesamiento=estatus,
            filas_cargadas=0,
            mensaje=f'{extension[1:].upper()} almacenado sin procesamiento',
        )
        return ResultadoIngesta(
            'NO_PROCESABLE',
            f'{extension[1:].upper()} registrado sin procesamiento. Versión {version}.',
            id_carga=control.id_carga,
            version=version,
        )

    # 3. CSV / Excel: leer y validar columnas
    try:
        df = _leer_archivo(ruta)
    except Exception as e:
        return ResultadoIngesta('ERROR', f'Error al leer el archivo: {e}')

    df.columns = [str(c).strip().upper() for c in df.columns]

    faltantes = [c for c in MAPA_COLUMNAS if c not in df.columns]
    if faltantes:
        return ResultadoIngesta(
            'ERROR',
            f'Faltan columnas obligatorias: {", ".join(faltantes)}',
        )

    # 4. Crear registro de control PRIMERO (para tener id_carga)
    control = ControlCargas.objects.create(
        nombre_archivo_original=nombre,
        hash_archivo=hash_archivo,
        version_archivo=version,
        estatus_procesamiento='PENDIENTE',
    )


    # 5. Construir filas Bronze (una por registro del CSV)
    registros = []
    for _, fila in df.iterrows():
        registros.append(BronzeMortalidadRaw(
            anio_defuncion            = str(fila.get('ANIO_DEFUNCION', ''))[:10],
            entidad_residencia        = str(fila.get('ENTIDAD_RESIDENCIA', ''))[:10],
            entidad_residenciad       = str(fila.get('ENTIDAD_RESIDENCIAD', ''))[:200],
            municipio_residenciad     = str(fila.get('MUNICIPIO_RESIDENCIAD', ''))[:200],
            causa_cie_4               = str(fila.get('CAUSA_CIE_4', ''))[:20],
            causa_cie_4d              = str(fila.get('CAUSA_CIE_4D', ''))[:300],
            edad                      = str(fila.get('EDAD', ''))[:10],
            edad_quinquenal           = str(fila.get('EDAD_QUINQUENAL', ''))[:20],
            razon_mortalidad_materna  = str(fila.get('RAZON_MORTALIDAD_MATERNA', ''))[:50],
            razon_mortalidad_maternad = str(fila.get('RAZON_MORTALIDAD_MATERNAD', ''))[:100],
            mes_defuncion             = str(fila.get('MES_DEFUNCION', ''))[:10],
            tamanio_localidad         = str(fila.get('TAMANIO_LOCALIDAD', ''))[:50],
            sitio_defuncion           = str(fila.get('SITIO_DEFUNCIOND', ''))[:200],
            escolaridad               = str(fila.get('ESCOLARIDADD', ''))[:200],
            ocupacion                 = str(fila.get('OCUPACION_HABITUALD', ''))[:200],
            estado_conyugal           = str(fila.get('ESTADO_CONYUGALD', ''))[:200],
            derechohabiencia          = str(fila.get('DERECHOHABIENCIAD', ''))[:200],
            nombre_archivo_original   = nombre,
            hash_archivo              = hash_archivo,
            estatus_procesamiento     = 'PENDIENTE',
            version_archivo           = version,
        ))

    BronzeMortalidadRaw.objects.bulk_create(registros, batch_size=1000)

    
    # 6. Actualizar control
    control.filas_cargadas = len(registros)
    control.estatus_procesamiento = 'PROCESADO'
    control.mensaje = f'{len(registros)} filas insertadas en Bronze'
    control.save(update_fields=['filas_cargadas', 'estatus_procesamiento', 'mensaje'])

    return ResultadoIngesta(
        'OK',
        f'Archivo procesado. {len(registros)} filas cargadas en Bronze.',
        id_carga=control.id_carga,
        filas=len(registros),
        version=version,
    )