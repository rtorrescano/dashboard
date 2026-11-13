from django.db import connection

cur = connection.cursor()

def show(schema, table):
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, [schema, table])
    rows = cur.fetchall()
    print(f"\n=== {schema}.{table} ({len(rows)} columnas) ===")
    for col, typ, nullable in rows:
        flag = "NOT NULL" if nullable == "NO" else ""
        print(f"  {col:<32} {typ:<22} {flag}")

show("silver", "localidad")
show("gold",   "dim_localidad")
show("gold",   "agg_municipio")
show("gold",   "dim_geografia")