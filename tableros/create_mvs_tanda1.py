=== INICIO ===
# create_mvs_tanda1.py
# MVs SOLO con numeradores de mortalidad materna (sin nacimientos)
# ASCII puro para evitar problemas de encoding en Windows.

from django.db import connection

cur = connection.cursor()

# ---------- MV 1: Serie nacional anual ----------
cur.execute("DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_nacional_anual CASCADE")
cur.execute("""
    CREATE MATERIALIZED VIEW gold.agg_mm_nacional_anual AS
    SELECT
        anio,
        SUM(total_defunciones)  AS total_maternas,
        SUM(maternas_rmm)       AS incluidas_rmm,
        SUM(excluidas_rmm)      AS excluidas_rmm,
        COUNT(DISTINCT cve_ent) AS estados_con_casos,
        COUNT(DISTINCT cve_mun) AS municipios_con_casos
    FROM gold.agg_mortalidad_por_municipio
    WHERE anio BETWEEN 2014 AND 2024
    GROUP BY anio
    ORDER BY anio
""")
cur.execute("CREATE UNIQUE INDEX uq_mm_nac_anio ON gold.agg_mm_nacional_anual (anio)")
cur.execute("REFRESH MATERIALIZED VIEW gold.agg_mm_nacional_anual")
cur.execute("SELECT count(*) FROM gold.agg_mm_nacional_anual")
print("agg_mm_nacional_anual: %s filas" % cur.fetchone()[0])

# ---------- MV 2: Conteo por estado/anio + variacion ----------
cur.execute("DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_por_estado CASCADE")
cur.execute("""
    CREATE MATERIALIZED VIEW gold.agg_mm_por_estado AS
    WITH m AS (
        SELECT
            cve_ent, nom_ent, anio,
            SUM(total_defunciones) AS total,
            SUM(maternas_rmm)      AS incluidas,
            SUM(excluidas_rmm)     AS excluidas,
            COUNT(DISTINCT cve_mun) AS municipios
        FROM gold.agg_mortalidad_por_municipio
        WHERE anio BETWEEN 2014 AND 2024
        GROUP BY cve_ent, nom_ent, anio
    )
    SELECT
        cve_ent, nom_ent, anio, total, incluidas, excluidas, municipios,
        LAG(total) OVER (PARTITION BY cve_ent ORDER BY anio) AS total_previo,
        CASE
          WHEN LAG(total) OVER (PARTITION BY cve_ent ORDER BY anio) > 0
          THEN ROUND(
            100.0 * (total - LAG(total) OVER (PARTITION BY cve_ent ORDER BY anio))
            / LAG(total) OVER (PARTITION BY cve_ent ORDER BY anio), 1)
          ELSE NULL
        END AS var_pct,
        ROUND(
          100.0 * total / NULLIF(SUM(total) OVER (PARTITION BY anio), 0), 2
        ) AS share_nacional_pct
    FROM m
""")
cur.execute("CREATE UNIQUE INDEX uq_mm_estado_anio ON gold.agg_mm_por_estado (cve_ent, anio)")
cur.execute("REFRESH MATERIALIZED VIEW gold.agg_mm_por_estado")
cur.execute("SELECT count(*) FROM gold.agg_mm_por_estado")
print("agg_mm_por_estado: %s filas" % cur.fetchone()[0])

# ---------- MV 3: Conteo por municipio/anio ----------
cur.execute("DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_por_municipio CASCADE")
cur.execute("""
    CREATE MATERIALIZED VIEW gold.agg_mm_por_municipio AS
    WITH m AS (
        SELECT
            cve_ent, nom_ent, cve_mun, nom_mun, anio,
            SUM(total_defunciones) AS total,
            SUM(maternas_rmm)      AS incluidas,
            SUM(excluidas_rmm)     AS excluidas
        FROM gold.agg_mortalidad_por_municipio
        WHERE anio BETWEEN 2014 AND 2024
        GROUP BY cve_ent, nom_ent, cve_mun, nom_mun, anio
    )
    SELECT
        m.*,
        LAG(m.total) OVER (PARTITION BY m.cve_ent, m.cve_mun ORDER BY m.anio) AS total_previo,
        CASE
          WHEN LAG(m.total) OVER (PARTITION BY m.cve_ent, m.cve_mun ORDER BY m.anio) > 0
          THEN ROUND(
            100.0 * (m.total - LAG(m.total) OVER (PARTITION BY m.cve_ent, m.cve_mun ORDER BY m.anio))
            / LAG(m.total) OVER (PARTITION BY m.cve_ent, m.cve_mun ORDER BY m.anio), 1)
          ELSE NULL
        END AS var_pct
    FROM m
""")
cur.execute("CREATE UNIQUE INDEX uq_mm_municipio_anio ON gold.agg_mm_por_municipio (cve_ent, cve_mun, anio)")
cur.execute("REFRESH MATERIALIZED VIEW gold.agg_mm_por_municipio")
cur.execute("SELECT count(*) FROM gold.agg_mm_por_municipio")
print("agg_mm_por_municipio: %s filas" % cur.fetchone()[0])

# ---------- MV 4: Evitabilidad (agregado estado/anio) ----------
cur.execute("DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_evitabilidad CASCADE")
cur.execute("""
    CREATE MATERIALIZED VIEW gold.agg_mm_evitabilidad AS
    SELECT
        b.anio_defuncion::int                       AS anio,
        TRIM(b.entidad_residencia)                  AS cve_ent,
        COUNT(*)                                    AS total,
        COUNT(*) FILTER (
            WHERE b.asistencia_medica = 'SIN ATENCION MEDICA'
               OR b.asistencia_medica IS NULL
        )                                           AS sin_atencion,
        COUNT(*) FILTER (WHERE b.sitio_defuncion = 'DOMICILIO')    AS en_domicilio,
        COUNT(*) FILTER (WHERE b.sitio_defuncion = 'VIA PUBLICA')  AS via_publica,
        COUNT(*) FILTER (
            WHERE b.sitio_defuncion ILIKE '%HOSPITAL%'
               OR b.sitio_defuncion ILIKE '%CLINICA%'
               OR b.sitio_defuncion ILIKE '%UNIDAD%'
        )                                           AS en_unidad_medica
    FROM bronze.bronze_mortalidad_raw b
    WHERE b.anio_defuncion::int BETWEEN 2014 AND 2024
      AND b.razon_mortalidad_materna IN ('0','1')
    GROUP BY 1, 2
""")
cur.execute("CREATE UNIQUE INDEX uq_evit_estado_anio ON gold.agg_mm_evitabilidad (cve_ent, anio)")
cur.execute("REFRESH MATERIALIZED VIEW gold.agg_mm_evitabilidad")
cur.execute("SELECT count(*) FROM gold.agg_mm_evitabilidad")
print("agg_mm_evitabilidad: %s filas" % cur.fetchone()[0])

print("")
print("OK")
=== FIN ===