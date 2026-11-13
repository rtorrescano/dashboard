"""
Convierte mortalidad_materna_2002_2024.xlsx (o .xls / .csv) -> CSV para \\copy de psql.
- Acepta .xlsx, .xls o .csv automáticamente.
- Hoja única consolidada (solo aplica a Excel).
- Encabezado en la fila OFFSET_FILA (0 = primera fila del archivo).
- Agrega columna 'fila_origen' = fila física del archivo (1-based, sin encabezado).
- Quita 'anio_nacimiento' porque no existe en public.staging_mortalidad.
- Imprime SHA256, XLSX, CSV, FILAS, COLUMNAS y COLNAMES para que los use PowerShell.
"""
import hashlib
import re
from pathlib import Path

import pandas as pd

# --- Rutas (raw strings, portables en Windows) ---
BASE = Path(r"C:\Users\raul.torrescano\Personal\Dashboards")
NOMBRE_BASE = "mortalidad_materna_2002_2024"
OUT = BASE / "mortalidad_staging.csv"

OFFSET_FILA = 0   # fila donde empieza el encabezado (0 = primera)
SHEET = 0         # solo aplica a .xlsx / .xls

# Extensiones soportadas, en orden de preferencia
EXTENSIONES = (".xlsx", ".xls", ".csv")

# Columnas del archivo fuente que NO existen en public.staging_mortalidad.
# Se eliminan antes de escribir el CSV para que el \copy no falle.
COLUMNAS_A_QUITAR = ("anio_nacimiento",)


def localizar_archivo(base: Path, nombre_sin_ext: str) -> Path:
    """Busca el archivo con cualquiera de las extensiones soportadas."""
    for ext in EXTENSIONES:
        candidato = base / f"{nombre_sin_ext}{ext}"
        if candidato.exists():
            return candidato
    existentes = sorted(
        p.name for p in base.glob(f"{nombre_sin_ext}.*") if p.is_file()
    )
    detalle = f" Encontrados: {existentes}" if existentes else ""
    raise FileNotFoundError(
        f"No se encontró '{nombre_sin_ext}' con extensión "
        f"{', '.join(EXTENSIONES)} en {base}.{detalle}"
    )


def leer_archivo(ruta: Path) -> pd.DataFrame:
    """Lee un .xlsx/.xls/.csv en modo texto, respetando OFFSET_FILA como encabezado."""
    ext = ruta.suffix.lower()

    if ext in (".xlsx", ".xls"):
        return pd.read_excel(
            ruta,
            sheet_name=SHEET,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            header=OFFSET_FILA,
        )

    if ext == ".csv":
        kwargs = dict(
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            skiprows=OFFSET_FILA,
            sep=None,          # autodetecta separador (, ; tab)
            engine="python",   # necesario para sep=None
        )
        try:
            return pd.read_csv(ruta, encoding="utf-8", **kwargs)
        except UnicodeDecodeError:
            return pd.read_csv(ruta, encoding="latin-1", **kwargs)

    raise ValueError(f"Formato no soportado: {ruta.suffix}")


def snake(c: str) -> str:
    c = re.sub(r"[^\w]+", "_", c.strip().lower())
    return re.sub(r"_+", "_", c).strip("_")


def main() -> None:
    # 0) localizar archivo de entrada
    src = localizar_archivo(BASE, NOMBRE_BASE)

    # 1) hash del archivo original
    with src.open("rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    # 2) leer (Excel o CSV según extensión)
    df = leer_archivo(src)

    # 3) fila_origen
    df.insert(0, "fila_origen", range(OFFSET_FILA + 2, OFFSET_FILA + 2 + len(df)))

    # 4) normalizar encabezados
    df.columns = [snake(c) for c in df.columns]

    # 5) quitar columnas que no existen en staging_mortalidad
    for col in COLUMNAS_A_QUITAR:
        if col in df.columns:
            df = df.drop(columns=[col])

    # 6) escribir CSV (UTF-8, todo entre comillas)
    df.to_csv(OUT, index=False, encoding="utf-8", quoting=1)

    # 7) imprimir lo que necesita PowerShell
    print(f"SHA256={sha}")
    # Nota: mantengo la clave XLSX= por compatibilidad con cargar_todo.ps1,
    # aunque el archivo real pueda ser CSV. Si prefieres renombrarla,
    # recuerda ajustar el .ps1 que la consume.
    print(f"XLSX={src}")
    print(f"CSV={OUT}")
    print(f"FILAS={len(df)}")
    print(f"COLUMNAS={len(df.columns)}")
    print("COLNAMES=" + ",".join(df.columns))


if __name__ == "__main__":
    main()