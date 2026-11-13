from django.db import connection
cur = connection.cursor()

cur.execute("SELECT count(*) FROM bronze.bronze_mortalidad_raw")
print("Total en bronze:", cur.fetchone()[0])

# Distribución completa de razon_mortalidad_materna
cur.execute("""
    SELECT razon_mortalidad_materna, count(*)
    FROM bronze.bronze_mortalidad_raw
    GROUP BY 1 ORDER BY 2 DESC
""")
print("\nDistribución razon_mortalidad_materna:")
for r in cur.fetchall():
    print("  ", r)

# Distribución de años
cur.execute("""
    SELECT anio_defuncion, count(*)
    FROM bronze.bronze_mortalidad_raw
    GROUP BY 1 ORDER BY 1
""")
print("\nAños (todos):")
for r in cur.fetchall():
    print("  ", r)

# Años con más de 100 registros (los "normales")
cur.execute("""
    SELECT anio_defuncion, count(*)
    FROM bronze.bronze_mortalidad_raw
    GROUP BY 1 HAVING count(*) > 100 ORDER BY 1
""")
print("\nAños con >100 registros:")
for r in cur.fetchall():
    print("  ", r)

# Formato de códigos geográficos
cur.execute("""
    SELECT entidad_residencia, count(*)
    FROM bronze.bronze_mortalidad_raw
    GROUP BY 1 ORDER BY 2 DESC LIMIT 5
""")
print("\nTop 5 entidad_residencia:")
for r in cur.fetchall():
    print("  ", r)

cur.execute("""
    SELECT municipio_residencia, count(*)
    FROM bronze.bronze_mortalidad_raw
    GROUP BY 1 ORDER BY 2 DESC LIMIT 5
""")
print("\nTop 5 municipio_residencia:")
for r in cur.fetchall():
    print("  ", r)

cur.execute("""
    SELECT localidad_residencia, count(*)
    FROM bronze.bronze_mortalidad_raw
    GROUP BY 1 ORDER BY 2 DESC LIMIT 5
""")
print("\nTop 5 localidad_residencia:")
for r in cur.fetchall():
    print("  ", r)

# Nulos por nivel
cur.execute("""
    SELECT
        count(*) FILTER (WHERE entidad_residencia IS NULL OR entidad_residencia = ''),
        count(*) FILTER (WHERE municipio_residencia IS NULL OR municipio_residencia = ''),
        count(*) FILTER (WHERE localidad_residencia IS NULL OR localidad_residencia = '')
    FROM bronze.bronze_mortalidad_raw
""")
print("\nNulos/vacíos (ent, mun, loc):", cur.fetchone())