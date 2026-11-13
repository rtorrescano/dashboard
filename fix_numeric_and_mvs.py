# fix_numeric_and_mvs.py
from django.db import connection

MV_NAMES = ["gold.dim_localidad", "gold.agg_municipio"]

cur = connection.cursor()

# ---------------------------------------------------------------
# 1. Guardar DDL + índices de cada MV ANTES de dropear
# ---------------------------------------------------------------
ddl = {}
indexes = {}
for mv in MV_NAMES:
    schema, name = mv.split(".")
    cur.execute(
        "SELECT pg_get_viewdef(%s::regclass, true)", [mv]
    )
    ddl[mv] = cur.fetchone()[0]

    cur.execute("""
        SELECT indexdef
        FROM pg_indexes
        WHERE schemaname = %s AND tablename = %s
    """, [schema, name])
    indexes[mv] = [r[0] for r in cur.fetchall()]

    print(f"\n=== {mv} — {len(indexes[mv])} índices ===")
    for i in indexes[mv]:
        print("  ", i[:120])

# ---------------------------------------------------------------
# 2. DROP de las MVs (CASCADE no hace falta: nada depende de ellas)
# ---------------------------------------------------------------
for mv in MV_NAMES:
    cur.execute(f"DROP MATERIALIZED VIEW IF EXISTS {mv} CASCADE")
    print(f"DROP {mv}")

# ---------------------------------------------------------------
# 3. ALTER de tipos en silver.localidad
# ---------------------------------------------------------------
cur.execute("""
    ALTER TABLE silver.localidad
      ALTER COLUMN lat_decimal TYPE numeric(12,8),
      ALTER COLUMN lon_decimal TYPE numeric(12,8)
""")
print("\nALTER silver.localidad lat_decimal, lon_decimal -> numeric(12,8)")

# ---------------------------------------------------------------
# 4. Recrear MVs con su DDL original
# ---------------------------------------------------------------
for mv in MV_NAMES:
    cur.execute(f"CREATE MATERIALIZED VIEW {mv} AS {ddl[mv]}")
    print(f"CREATE {mv}")

# ---------------------------------------------------------------
# 5. Recrear índices (incluye el UNIQUE que necesita CONCURRENTLY)
# ---------------------------------------------------------------
for mv in MV_NAMES:
    for idx_def in indexes[mv]:
        try:
            cur.execute(idx_def)
            print(f"INDEX {mv}: {idx_def[:60]}…")
        except Exception as e:
            print(f"  WARN índice {mv}: {e}")

# ---------------------------------------------------------------
# 6. Refresh inicial (sin CONCURRENTLY porque están vacías)
# ---------------------------------------------------------------
for mv in MV_NAMES:
    cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
    print(f"REFRESH {mv}")

print("\nOK")