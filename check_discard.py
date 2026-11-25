from django.db import connection
cur = connection.cursor()

print("--- REGISTROS DESCARTADOS POR ANIO (< 2014) ---")
cur.execute("""
    SELECT anio_defuncion, COUNT(*)
    FROM bronze.bronze_mortalidad_raw
    WHERE TRIM(anio_defuncion) ~ '^[0-9]+$' AND TRIM(anio_defuncion)::int < 2014
    GROUP BY anio_defuncion
    ORDER BY TRIM(anio_defuncion)::int
""")
for r in cur.fetchall():
    print(f"Anio {r[0]}: {r[1]} registros")

print("\n--- REGISTROS CON ANIO INVALIDO ---")
cur.execute("""
    SELECT anio_defuncion, COUNT(*)
    FROM bronze.bronze_mortalidad_raw
    WHERE NOT (TRIM(anio_defuncion) ~ '^[0-9]+$')
    GROUP BY anio_defuncion
""")
for r in cur.fetchall():
    print(f"Valor en CSV: '{r[0]}' -> {r[1]} registros")
print("-------------------------------------------------")
