from django.db import connection

cur = connection.cursor()

def q(label, sql):
    cur.execute(sql)
    print(f"\n=== {label} ===")
    for row in cur.fetchall():
        print(" ", row)

# 1. Estado de la ingesta
q("file_ingestion",
  "SELECT ingestion_id, status, row_count, ingested_at "
  "FROM bronze.file_ingestion ORDER BY ingested_at DESC LIMIT 3")

# 2. Conteos por capa
q("Conteos",
  "SELECT 'bronze.ageeml_raw' AS tabla, count(*) FROM bronze.ageeml_raw "
  "UNION ALL SELECT 'silver.localidad', count(*) FROM silver.localidad "
  "UNION ALL SELECT 'gold.dim_geografia', count(*) FROM gold.dim_geografia")

# 3. Estados únicos (debería haber 32)
cur.execute("SELECT count(DISTINCT cve_ent) FROM silver.localidad")
print(f"\nEstados distintos en silver.localidad: {cur.fetchone()[0]} (esperado 32)")

# 4. Muestra Aguascalientes
q("Aguascalientes (primeros 3)",
  "SELECT cvegeo, cve_ent, nom_ent, cve_mun, nom_mun, cve_loc, nom_loc, pob_total "
  "FROM silver.localidad WHERE cve_ent='01' ORDER BY cvegeo LIMIT 3")

# 5. CDMX — cve_loc/nom_loc normalizados (no '----')
q("CDMX (primeros 3)",
  "SELECT cvegeo, cve_mun, nom_mun, cve_loc, nom_loc, pob_total "
  "FROM silver.localidad WHERE cve_ent='09' ORDER BY cvegeo LIMIT 3")

# 6. Filas con pob_total NULL (esperado: San Felipe BC, Dzitbalché, etc.)
q("Filas con pob_total NULL",
  "SELECT cvegeo, nom_ent, nom_mun, nom_loc FROM silver.localidad "
  "WHERE pob_total IS NULL ORDER BY cvegeo")

# 7. Geometría — todas NULL (esperado con cabeceras)
cur.execute("SELECT count(*) FILTER (WHERE geom IS NULL), "
            "count(*) FILTER (WHERE geom IS NOT NULL) FROM silver.localidad")
nulos, no_nulos = cur.fetchone()
print(f"\nGeometrías: NULL={nulos}  con_geom={no_nulos} (esperado con_geom=0)")

# 8. MVs refrescadas
q("gold.dim_geografia (muestra)",
  "SELECT * FROM gold.dim_geografia WHERE entidad_nombre='Aguascalientes' LIMIT 3")