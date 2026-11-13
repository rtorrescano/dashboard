# load_defunciones_bronze.py
import csv, hashlib, io
from datetime import datetime, timezone
from pathlib import Path
from django.db import connection

CSV = Path(r"C:\Users\raul.torrescano\Personal\Dashboards\mortalidad_materna_2002_2024.csv")

with open(CSV, encoding="utf-8-sig", newline="") as f:
    csv_header = next(csv.reader(f))

csv_to_bronze = [(h, h.lower()) for h in csv_header]

with connection.cursor() as cur:
    cur.execute("""
        SELECT column_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema='bronze' AND table_name='bronze_mortalidad_raw'
    """)
    cols_info = {r[0]: {"nullable": r[1], "default": r[2]} for r in cur.fetchall()}

# Columnas del CSV que sí existen en bronze
bronze_cols = [b for _, b in csv_to_bronze]
faltantes = [(c, b) for c, b in csv_to_bronze if b not in cols_info]
if faltantes:
    raise SystemExit(f"Columnas CSV sin equivalente en bronze: {faltantes}")

file_hash = hashlib.sha256(CSV.read_bytes()).hexdigest()
now_iso = datetime.now(timezone.utc).isoformat()

# Columnas NOT NULL sin default y sin fuente en el CSV → constantes
extras = [
    ("nombre_archivo_original", CSV.name),
    ("hash_archivo",             file_hash),
    ("vigente",                  "true"),
    ("es_vigente",               "true"),
    ("fecha_vigencia_desde",     now_iso),
    ("version_registro",         "1"),
]
extras_names = [e[0] for e in extras]
extras_values = [e[1] for e in extras]

# Verificar que no falte ninguna NOT NULL sin default
requeridas = {"id_carga", "fila_origen"} | set(extras_names) | set(bronze_cols)
for col, info in cols_info.items():
    if info["nullable"] == "NO" and info["default"] is None and col not in requeridas:
        raise SystemExit(f"Falta cubrir NOT NULL sin default: {col}")

# Limpieza de intentos previos con el mismo hash
with connection.cursor() as cur:
    cur.execute(
        "DELETE FROM bronze.control_cargas WHERE hash_archivo = %s",
        [file_hash],
    )
    print(f"control_cargas previas borradas: {cur.rowcount}")

# Registrar nueva carga
with connection.cursor() as cur:
    cur.execute("""
        INSERT INTO bronze.control_cargas
            (nombre_archivo_original, hash_archivo, version_archivo,
             estatus_procesamiento, fecha_carga)
        VALUES (%s, %s, 'v1', 'cargando', now())
        RETURNING id_carga
    """, [CSV.name, file_hash])
    id_carga = cur.fetchone()[0]
    print(f"id_carga = {id_carga}")

    all_cols = (
        ["id_carga", "fila_origen"]
        + extras_names
        + bronze_cols
    )
    copy_sql = (
        f"COPY bronze.bronze_mortalidad_raw ({', '.join(all_cols)}) "
        f"FROM STDIN WITH (FORMAT CSV, NULL '')"
    )

    with open(CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        buf = io.StringIO()
        w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        n = 0
        for i, row in enumerate(reader, start=2):
            if len(row) != len(csv_header):
                raise SystemExit(
                    f"Fila {i}: {len(row)} valores ≠ {len(csv_header)} columnas"
                )
            w.writerow([id_carga, i] + extras_values + row)
            n = i
        buf.seek(0)

        if hasattr(cur, "copy_expert"):
            cur.copy_expert(copy_sql, buf)
        else:
            with cur.copy(copy_sql) as cp:
                cp.write(buf.getvalue())

    print(f"Filas cargadas: {n - 1}")

    cur.execute("""
        UPDATE bronze.control_cargas
           SET estatus_procesamiento = 'completado',
               filas_cargadas        = %s
         WHERE id_carga = %s
    """, [n - 1, id_carga])

print("OK")