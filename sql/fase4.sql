-- ============================================================
-- fix_fase4.sql
-- Corrección de Fase 4 + Fase 5 (refresh MVs) + Fase 6 (validación)
-- Idempotente. Ejecutable múltiples veces.
-- ============================================================
\set ON_ERROR_STOP on
\timing on

\echo '=== FIX FASE 4 — Re-poblar dim_persona y enriquecer fact ==='

-- ============================================================
-- 4.0 Agregar asistencia_medica y certifico a silver
-- ============================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='silver' AND table_name='silver_mortalidad_limpia'
                     AND column_name='asistencia_medica')
    THEN ALTER TABLE silver.silver_mortalidad_limpia ADD COLUMN asistencia_medica VARCHAR(100); END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='silver' AND table_name='silver_mortalidad_limpia'
                     AND column_name='certifico')
    THEN ALTER TABLE silver.silver_mortalidad_limpia ADD COLUMN certifico VARCHAR(100); END IF;
END $$;

-- ============================================================
-- 4.0b Poblar esas columnas desde bronze (si bronze las tiene)
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='bronze' AND table_name='bronze_mortalidad_raw'
          AND column_name='asistencia_medicad'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='bronze' AND table_name='bronze_mortalidad_raw'
          AND column_name='certificod'
    ) THEN
        UPDATE silver.silver_mortalidad_limpia s
        SET asistencia_medica = COALESCE(s.asistencia_medica, b.asistencia_medicad),
            certifico         = COALESCE(s.certifico,         b.certificod)
        FROM bronze.bronze_mortalidad_raw b
        WHERE s.id_carga_origen = b.id_carga
          AND (s.asistencia_medica IS NULL OR s.certifico IS NULL);
        RAISE NOTICE 'silver.asistencia_medica y silver.certifico poblados desde bronze';
    ELSE
        RAISE NOTICE 'bronze no tiene asistencia_medicad/certificod; silver quedará con NULL en esas columnas';
    END IF;
END $$;

-- ============================================================
-- 4.0c Alinear dim_persona con 6 atributos (recrear si tiene menos)
-- ============================================================
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema='gold' AND table_name='dim_persona'
                 AND column_name='asistencia_medica')
    THEN
        RAISE NOTICE 'dim_persona ya tiene los 6 atributos; no se recrea';
    ELSE
        RAISE NOTICE 'Recreando dim_persona con 6 atributos...';
        DROP TABLE IF EXISTS gold.dim_persona CASCADE;
        CREATE TABLE gold.dim_persona (
            id_persona          SERIAL PRIMARY KEY,
            estado_conyugal     VARCHAR(50),
            escolaridad         VARCHAR(200),
            ocupacion           VARCHAR(200),
            derechohabiencia    VARCHAR(200),
            asistencia_medica   VARCHAR(100),
            certifico           VARCHAR(100)
        );
        CREATE UNIQUE INDEX uq_persona
            ON gold.dim_persona (
                COALESCE(estado_conyugal,   'NA'),
                COALESCE(escolaridad,       'NA'),
                COALESCE(ocupacion,         'NA'),
                COALESCE(derechohabiencia,  'NA'),
                COALESCE(asistencia_medica, 'NA'),
                COALESCE(certifico,         'NA')
            );
    END IF;
END $$;

-- ============================================================
-- 4.0d Re-crear FK fact.id_persona → dim_persona
-- (por si el DROP de 4.0c eliminó la constraint)
-- ============================================================
ALTER TABLE gold.fact_mortalidad_materna
    ADD COLUMN IF NOT EXISTS id_persona INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_fact_persona'
          AND conrelid = 'gold.fact_mortalidad_materna'::regclass
    ) THEN
        ALTER TABLE gold.fact_mortalidad_materna
            ADD CONSTRAINT fk_fact_persona
            FOREIGN KEY (id_persona)
            REFERENCES gold.dim_persona(id_persona);
        RAISE NOTICE 'FK fk_fact_persona creada';
    ELSE
        RAISE NOTICE 'FK fk_fact_persona ya existe';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fact_persona
    ON gold.fact_mortalidad_materna (id_persona);

-- ============================================================
-- 4.1 Poblar dim_persona desde silver
-- ============================================================
INSERT INTO gold.dim_persona
    (estado_conyugal, escolaridad, ocupacion, derechohabiencia, asistencia_medica, certifico)
SELECT DISTINCT
    s.estado_conyugal, s.escolaridad, s.ocupacion,
    s.derechohabiencia, s.asistencia_medica, s.certifico
FROM silver.silver_mortalidad_limpia s
ON CONFLICT (COALESCE(estado_conyugal,'NA'),
             COALESCE(escolaridad,'NA'),
             COALESCE(ocupacion,'NA'),
             COALESCE(derechohabiencia,'NA'),
             COALESCE(asistencia_medica,'NA'),
             COALESCE(certifico,'NA'))
DO NOTHING;

-- ============================================================
-- 4.2 Actualizar fact.id_persona
-- ============================================================
UPDATE gold.fact_mortalidad_materna f
SET id_persona = p.id_persona
FROM silver.silver_mortalidad_limpia s
JOIN gold.dim_persona p
  ON COALESCE(p.estado_conyugal,'NA')     = COALESCE(s.estado_conyugal,'NA')
 AND COALESCE(p.escolaridad,'NA')         = COALESCE(s.escolaridad,'NA')
 AND COALESCE(p.ocupacion,'NA')           = COALESCE(s.ocupacion,'NA')
 AND COALESCE(p.derechohabiencia,'NA')    = COALESCE(s.derechohabiencia,'NA')
 AND COALESCE(p.asistencia_medica,'NA')   = COALESCE(s.asistencia_medica,'NA')
 AND COALESCE(p.certifico,'NA')           = COALESCE(s.certifico,'NA')
WHERE f.id_registro_silver = s.id_registro
  AND f.id_persona IS NULL;

-- ============================================================
-- 4.3 Actualizar fact.id_geografia_ocur (si silver tiene ocurrencia)
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='silver_mortalidad_limpia'
          AND column_name='entidad_ocurrencia'
    ) THEN
        UPDATE gold.fact_mortalidad_materna f
        SET id_geografia_ocur = g.id_geografia
        FROM silver.silver_mortalidad_limpia s
        JOIN gold.dim_geografia g
          ON g.id_entidad = s.entidad_ocurrencia
         AND COALESCE(g.id_municipio,-1) = COALESCE(s.municipio_ocurrencia,-1)
        WHERE f.id_registro_silver = s.id_registro
          AND f.id_geografia_ocur IS NULL
          AND s.entidad_ocurrencia IS NOT NULL;
        RAISE NOTICE 'fact.id_geografia_ocur actualizado';
    ELSE
        RAISE NOTICE 'silver no tiene entidad_ocurrencia; fact.id_geografia_ocur queda NULL (se llenará en próxima ingesta)';
    END IF;
END $$;

-- ============================================================
-- 4.4 Sincronizar dim_causa.incluida_rmm con catálogo
-- ============================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema='gold' AND table_name='cat_cie10') THEN
        UPDATE gold.dim_causa dc
        SET incluida_rmm = c.incluida_rmm
        FROM gold.cat_cie10 c
        WHERE dc.codigo_cie10 = c.codigo_cie10
          AND dc.incluida_rmm IS DISTINCT FROM c.incluida_rmm;
        RAISE NOTICE 'dim_causa.incluida_rmm sincronizado';
    ELSE
        RAISE NOTICE 'gold.cat_cie10 no existe; se omite sincronización';
    END IF;
END $$;

-- ============================================================
-- 4.5 Poblar dim_geografia.localidad_nombre / tamanio_localidad desde silver
-- ============================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='silver_mortalidad_limpia'
          AND column_name='localidad_nombre'
    ) THEN
        UPDATE gold.dim_geografia g
        SET localidad_nombre  = COALESCE(g.localidad_nombre,  s.localidad_nombre),
            tamanio_localidad = COALESCE(g.tamanio_localidad, s.tamanio_localidad)
        FROM silver.silver_mortalidad_limpia s
        WHERE g.id_entidad = s.entidad_residencia
          AND COALESCE(g.id_municipio,-1) = COALESCE(s.municipio_residencia,-1)
          AND (g.localidad_nombre IS NULL OR g.tamanio_localidad IS NULL);
        RAISE NOTICE 'dim_geografia enriquecida con localidad/tamaño';
    END IF;
END $$;


-- ============================================================
-- FASE 5 — Refresh de las 10 MVs
-- ============================================================
\echo '=== FASE 5 — Refresh de MVs ==='

REFRESH MATERIALIZED VIEW marts.mv_rmm_anual_entidad;
REFRESH MATERIALIZED VIEW marts.mv_causas_agrupadas;
REFRESH MATERIALIZED VIEW marts.mv_distribucion_edad;
REFRESH MATERIALIZED VIEW marts.mv_subclasificacion;
REFRESH MATERIALIZED VIEW marts.mv_series_tiempo;
REFRESH MATERIALIZED VIEW marts.mv_derechohabiencia;
REFRESH MATERIALIZED VIEW marts.mv_escolaridad;
REFRESH MATERIALIZED VIEW marts.mv_estado_conyugal;
REFRESH MATERIALIZED VIEW marts.mv_ocupacion;
REFRESH MATERIALIZED VIEW marts.mv_sitio_defuncion;


-- ============================================================
-- FASE 6 — Validación
-- ============================================================
\echo '=== FASE 6 — Validación ==='

\echo '--- 6.1 Columnas nuevas en silver (deben ser 8) ---'
SELECT column_name
FROM information_schema.columns
WHERE table_schema='silver' AND table_name='silver_mortalidad_limpia'
  AND column_name IN (
      'asistencia_medica','certifico','trimestre','entidad_ocurrencia',
      'municipio_ocurrencia','localidad_ocurrencia','razon_mortalidad_texto','fila_origen'
  )
ORDER BY column_name;

\echo '--- 6.2 dim_persona: columnas y conteo ---'
SELECT column_name
FROM information_schema.columns
WHERE table_schema='gold' AND table_name='dim_persona'
ORDER BY ordinal_position;

SELECT count(*) AS filas_dim_persona FROM gold.dim_persona;

\echo '--- 6.3 FKs creadas ---'
SELECT conname, conrelid::regclass AS tabla, confrelid::regclass AS referencia
FROM pg_constraint
WHERE conname IN ('fk_fact_geo_ocur','fk_fact_persona');

\echo '--- 6.4 Índices creados ---'
SELECT indexname FROM pg_indexes
WHERE schemaname='gold'
  AND indexname IN ('idx_fact_geo_ocur','idx_fact_persona','uq_persona');

\echo '--- 6.5 Cobertura de nuevos campos en silver ---'
SELECT
  count(*)                                                                       AS total,
  count(*) FILTER (WHERE trimestre IS NOT NULL)                                  AS con_trimestre,
  count(*) FILTER (WHERE entidad_ocurrencia IS NOT NULL)                         AS con_ocurrencia,
  count(*) FILTER (WHERE razon_mortalidad_texto IS NOT NULL)                     AS con_razon,
  count(*) FILTER (WHERE asistencia_medica IS NOT NULL)                          AS con_asistencia,
  count(*) FILTER (WHERE certifico IS NOT NULL)                                  AS con_certifico
FROM silver.silver_mortalidad_limpia;

\echo '--- 6.6 Cobertura de nuevas FKs en fact ---'
SELECT
  count(*)                                                                       AS total_fact,
  count(*) FILTER (WHERE id_persona IS NOT NULL)                                 AS con_persona,
  count(*) FILTER (WHERE id_geografia_ocur IS NOT NULL)                          AS con_geo_ocur,
  count(*) FILTER (WHERE id_causa IS NOT NULL)                                   AS con_causa,
  count(*) FILTER (WHERE id_tiempo IS NOT NULL)                                  AS con_tiempo,
  count(*) FILTER (WHERE id_edad IS NOT NULL)                                    AS con_edad
FROM gold.fact_mortalidad_materna;

\echo '--- 6.7 Filas por MV ---'
SELECT 'mv_rmm_anual_entidad'   AS mv, count(*) FROM marts.mv_rmm_anual_entidad
UNION ALL SELECT 'mv_causas_agrupadas',    count(*) FROM marts.mv_causas_agrupadas
UNION ALL SELECT 'mv_distribucion_edad',   count(*) FROM marts.mv_distribucion_edad
UNION ALL SELECT 'mv_subclasificacion',    count(*) FROM marts.mv_subclasificacion
UNION ALL SELECT 'mv_series_tiempo',       count(*) FROM marts.mv_series_tiempo
UNION ALL SELECT 'mv_derechohabiencia',    count(*) FROM marts.mv_derechohabiencia
UNION ALL SELECT 'mv_escolaridad',         count(*) FROM marts.mv_escolaridad
UNION ALL SELECT 'mv_estado_conyugal',     count(*) FROM marts.mv_estado_conyugal
UNION ALL SELECT 'mv_ocupacion',           count(*) FROM marts.mv_ocupacion
UNION ALL SELECT 'mv_sitio_defuncion',     count(*) FROM marts.mv_sitio_defuncion;

\echo '=== FIX COMPLETADO ==='