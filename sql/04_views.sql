CREATE SCHEMA IF NOT EXISTS marts;

-- RMM anual por entidad
CREATE MATERIALIZED VIEW marts.mv_rmm_anual_entidad AS
SELECT
    dt.anio,
    dg.id_entidad,
    dg.entidad_nombre,
    COUNT(*) FILTER (WHERE f.incluida_en_rmm)            AS defunciones_incluidas,
    COALESCE(ne.nacimientos, 0)                          AS nacimientos_estimados,
    CASE WHEN COALESCE(ne.nacimientos,0) > 0
         THEN ROUND((COUNT(*) FILTER (WHERE f.incluida_en_rmm)::numeric
                     / ne.nacimientos) * 100000, 2)
         ELSE NULL END                                  AS rmm
FROM gold.fact_mortalidad_materna f
JOIN gold.dim_tiempo    dt ON dt.id_tiempo = f.id_tiempo
JOIN gold.dim_geografia dg ON dg.id_geografia = f.id_geografia
LEFT JOIN gold.nacimientos_estimados ne
       ON ne.anio = dt.anio AND ne.id_entidad = dg.id_entidad
GROUP BY dt.anio, dg.id_entidad, dg.entidad_nombre, ne.nacimientos
WITH DATA;

CREATE UNIQUE INDEX idx_mv_rmm_anual ON marts.mv_rmm_anual_entidad (anio, id_entidad);

-- Causas agrupadas
CREATE MATERIALIZED VIEW marts.mv_causas_agrupadas AS
SELECT
    dt.anio,
    dc.grupo_causa,
    COUNT(*) AS total_defunciones
FROM gold.fact_mortalidad_materna f
JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
JOIN gold.dim_causa  dc ON dc.id_causa  = f.id_causa
WHERE f.incluida_en_rmm
GROUP BY dt.anio, dc.grupo_causa
WITH DATA;

CREATE UNIQUE INDEX idx_mv_causas ON marts.mv_causas_agrupadas (anio, grupo_causa);

-- Distribución por edad
CREATE MATERIALIZED VIEW marts.mv_distribucion_edad AS
SELECT
    dt.anio,
    de.edad_quinquenal,
    COUNT(*) AS total_defunciones
FROM gold.fact_mortalidad_materna f
JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
JOIN gold.dim_edad   de ON de.id_edad   = f.id_edad
WHERE f.incluida_en_rmm
GROUP BY dt.anio, de.edad_quinquenal
WITH DATA;

-- Series de tiempo
CREATE MATERIALIZED VIEW marts.mv_series_tiempo AS
SELECT
    dt.anio,
    dt.mes,
    COUNT(*) FILTER (WHERE f.incluida_en_rmm) AS defunciones,
    (SELECT rmm FROM marts.mv_rmm_anual_entidad m
      WHERE m.anio = dt.anio LIMIT 1)         AS rmm_referencia
FROM gold.fact_mortalidad_materna f
JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
GROUP BY dt.anio, dt.mes
WITH DATA;

CREATE UNIQUE INDEX idx_mv_series ON marts.mv_series_tiempo (anio, mes);