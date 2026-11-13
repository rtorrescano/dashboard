# create_mv_mortalidad.py
# ASCII puro, sin acentos, para evitar problemas de encoding en Windows.

from django.db import connection

cur = connection.cursor()

cur.execute("DROP MATERIALIZED VIEW IF EXISTS gold.agg_mortalidad_por_municipio CASCADE")
print("MV anterior dropeada (si existia)")

cur.execute("""
    CREATE MATERIALIZED VIEW gold.agg_mortalidad_por_municipio AS
    SELECT
        dl.cve_ent,
        dl.nom_ent,
        dl.cve_mun,
        dl.nom_mun,
        dl.lat_decimal,
        dl.lon_decimal,
        dl.geom,
        CAST(b.anio_defuncion AS integer) AS anio,
        COUNT(*)                                                    AS total_defunciones,
        COUNT(*) FILTER (WHERE b.razon_mortalidad_materna = '1')   AS maternas_rmm,
        COUNT(*) FILTER (WHERE b.razon_mortalidad_materna = '0')   AS excluidas_rmm
    FROM bronze.bronze_mortalidad_raw b
    JOIN LATERAL (
        SELECT cve_ent, cve_mun, nom_mun, nom_ent,
               lat_decimal, lon_decimal, geom
        FROM gold.dim_localidad dl2
        WHERE dl2.cve_ent = TRIM(b.entidad_residencia)
          AND dl2.cve_mun = TRIM(b.municipio_residencia)
        ORDER BY (dl2.cve_loc = '0001') DESC, dl2.cve_loc ASC
        LIMIT 1
    ) dl ON TRUE
    WHERE CAST(b.anio_defuncion AS integer) BETWEEN 2002 AND 2024
    GROUP BY 1,2,3,4,5,6,7,8
""")
print("MV creada")

cur.execute("""
    CREATE UNIQUE INDEX uq_agg_mort_mun
        ON gold.agg_mortalidad_por_municipio (cve_ent, cve_mun, anio)
""")
print("Indice unico creado (necesario para REFRESH CONCURRENTLY)")

cur.execute("""
    CREATE INDEX ix_agg_mort_mun_geom
        ON gold.agg_mortalidad_por_municipio USING GIST (geom)
""")
print("Indice espacial creado")

cur.execute("REFRESH MATERIALIZED VIEW gold.agg_mortalidad_por_municipio")
print("MV poblada")

cur.execute("SELECT count(*) FROM gold.agg_mortalidad_por_municipio")
print(f"Filas en MV: {cur.fetchone()[0]}")

cur.execute("""
    SELECT sum(total_defunciones), sum(maternas_rmm), sum(excluidas_rmm)
    FROM gold.agg_mortalidad_por_municipio
""")
totales = cur.fetchone()
print(f"Totales en MV: defunciones={totales[0]}, rmm={totales[1]}, excluidas={totales[2]}")

print("OK")