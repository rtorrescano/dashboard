from django.db import connection
from pathlib import Path

cur = connection.cursor()

# 1. Comandos disponibles en el proyecto
print("=== management/commands ===")
for p in Path("catalogos/management/commands").glob("*.py"):
    print("  ", p.stem)

# 2. Columnas de las tablas de mortalidad
def show(schema, table):
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
        ORDER BY ordinal_position
    """, [schema, table])
    rows = cur.fetchall()
    print(f"\n=== {schema}.{table} ({len(rows)} cols) ===")
    for c, t in rows:
        print(f"  {c:<32} {t}")

for s, t in [
    ("bronze", "bronze_mortalidad_raw"),
    ("bronze", "control_cargas"),
    ("bronze", "mortalidad_cambios"),
    ("silver", "silver_mortalidad_limpia"),
    ("gold",   "fact_mortalidad_materna"),
    ("gold",   "dim_persona"),
    ("gold",   "dim_causa"),
    ("gold",   "dim_edad"),
    ("gold",   "dim_tiempo"),
    ("gold",   "dim_geografia"),
    ("gold",   "dim_localidad"),
]:
    show(s, t)

# 3. ¿Tienen datos ya?
for s, t in [("bronze", "bronze_mortalidad_raw"),
             ("silver", "silver_mortalidad_limpia"),
             ("gold",   "fact_mortalidad_materna")]:
    cur.execute(f"SELECT count(*) FROM {s}.{t}")
    print(f"\n{s}.{t}: {cur.fetchone()[0]} filas")