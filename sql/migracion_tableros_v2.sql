-- ============================================================
-- migracion_tableros_v2.sql
-- Plan de migración incremental: BD tableros (dump) → diseño completo
-- Idempotente. Ejecutable con psql -f.
-- Duración estimada: 60–90 min. Downtime: 0.
-- ============================================================
\set ON_ERROR_STOP on
\timing on

-- ============================================================
-- FASE 0 — Pre-requisitos
-- ============================================================
\echo '=== FASE 0 — Pre-requisitos ==='

-- 0.1 Snapshot de conteos (idempotente)
CREATE TABLE IF NOT EXISTS public._migracion_conteos_pre (
    momento  TIMESTAMPTZ DEFAULT now(),
    tabla    TEXT,
    filas    BIGINT
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public._migracion_conteos_pre) THEN
        INSERT INTO public._migracion_conteos_pre (tabla, filas) VALUES
        ('bronze.bronze_mortalidad_raw',   (SELECT count(*) FROM bronze.bronze_mortalidad_raw)),
        ('silver.silver_mortalidad_limpia',(SELECT count(*) FROM silver.silver_mortalidad_limpia)),
        ('gold.dim_tiempo',                (SELECT count(*) FROM gold.dim_tiempo)),
        ('gold.dim_geografia',             (SELECT count(*) FROM gold.dim_geografia)),
        ('gold.dim_causa',                 (SELECT count(*) FROM gold.dim_causa)),
        ('gold.dim_edad',                  (SELECT count(*) FROM gold.dim_edad)),
        ('gold.fact_mortalidad_materna',   (SELECT count(*) FROM gold.fact_mortalidad_materna)),
        ('gold.nacimientos_estimados',     (SELECT count(*) FROM gold.nacimientos_estimados));
    END IF;
END $$;

-- 0.2 Verificar esquemas
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name='bronze')
       OR NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name='silver')
       OR NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name='gold')
       OR NOT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name='marts')
    THEN
        RAISE EXCEPTION 'Faltan esquemas bronze/silver/gold/marts. Verifica la BD.';
    END IF;
END $$;


-- ============================================================
-- FASE 1 — Ampliar bronze a 58 columnas
-- ============================================================
\echo '=== FASE 1 — Ampliar bronze ==='

DO $$
DECLARE
    cols TEXT[][] := ARRAY[
        ['mes_nacimiento',        'VARCHAR(10)'],
        ['mes_nacimientod',       'VARCHAR(50)'],
        ['dia_nacimiento',        'VARCHAR(10)'],
        ['estado_conyugald',      'VARCHAR(50)'],
        ['localidad_residencia',  'VARCHAR(10)'],
        ['localidad_residenciad', 'VARCHAR(300)'],
        ['tamanio_localidadd',    'VARCHAR(100)'],
        ['ocupacion_habitual',    'VARCHAR(10)'],
        ['ocupacion_habituald',   'VARCHAR(200)'],
        ['escolaridadd',          'VARCHAR(200)'],
        ['derechohabienciad',     'VARCHAR(200)'],
        ['entidad_ocurrencia',    'VARCHAR(10)'],
        ['entidad_ocurrenciad',   'VARCHAR(200)'],
        ['municipio_ocurrencia',  'VARCHAR(10)'],
        ['municipio_ocurrenciad', 'VARCHAR(200)'],
        ['localidad_ocurrencia',  'VARCHAR(10)'],
        ['localidad_ocurrenciad', 'VARCHAR(300)'],
        ['sitio_defunciond',      'VARCHAR(200)'],
        ['mes_defunciond',        'VARCHAR(50)'],
        ['hora_defuncion',        'VARCHAR(10)'],
        ['minutos_defuncion',     'VARCHAR(10)'],
        ['asistencia_medica',     'VARCHAR(10)'],
        ['asistencia_medicad',    'VARCHAR(100)'],
        ['certifico',             'VARCHAR(10)'],
        ['certificod',            'VARCHAR(100)'],
        ['entidad_registro',      'VARCHAR(10)'],
        ['entidad_registrod',     'VARCHAR(200)'],
        ['municipio_registro',    'VARCHAR(10)'],
        ['municipio_registrod',   'VARCHAR(200)'],
        ['anio_registro',         'VARCHAR(10)'],
        ['mes_registro',          'VARCHAR(10)'],
        ['mes_registrod',         'VARCHAR(50)'],
        ['dia_registro',          'VARCHAR(10)'],
        ['anio_certificacion',    'VARCHAR(10)'],
        ['mes_certificacion',     'VARCHAR(10)'],
        ['mes_certificaciond',    'VARCHAR(50)'],
        ['dia_certificacion',     'VARCHAR(10)'],
        ['anio_base_datos',       'VARCHAR(10)'],
        ['edad_quinquenald',      'VARCHAR(50)'],
        ['error_carga',           'TEXT']
    ];
    r RECORD;
BEGIN
    FOR i IN 1 .. array_length(cols, 1) LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='bronze'
              AND table_name='bronze_mortalidad_raw'
              AND column_name=cols[i][1]
        ) THEN
            EXECUTE format('ALTER TABLE bronze.bronze_mortalidad_raw ADD COLUMN %I %s',
                           cols[i][1], cols[i][2]);
        END IF;
    END LOOP;
END $$;


-- ============================================================
-- FASE 2 — Ampliar silver
-- ============================================================
\echo '=== FASE 2 — Ampliar silver ==='

DO $$
DECLARE
    cols TEXT[][] := ARRAY[
        ['fila_origen',            'INTEGER'],
        ['trimestre',              'INTEGER'],
        ['entidad_ocurrencia',     'INTEGER'],
        ['municipio_ocurrencia',   'INTEGER'],
        ['localidad_ocurrencia',   'VARCHAR(300)'],
        ['razon_mortalidad_texto', 'VARCHAR(200)']
    ];
BEGIN
    FOR i IN 1 .. array_length(cols, 1) LOOP
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='silver'
              AND table_name='silver_mortalidad_limpia'
              AND column_name=cols[i][1]
        ) THEN
            EXECUTE format('ALTER TABLE silver.silver_mortalidad_limpia ADD COLUMN %I %s',
                           cols[i][1], cols[i][2]);
        END IF;
    END LOOP;
END $$;

-- 2.1 Backfill trimestre
UPDATE silver.silver_mortalidad_limpia
SET trimestre = CASE
    WHEN mes_defuncion BETWEEN 1 AND 3 THEN 1
    WHEN mes_defuncion BETWEEN 4 AND 6 THEN 2
    WHEN mes_defuncion BETWEEN 7 AND 9 THEN 3
    WHEN mes_defuncion BETWEEN 10 AND 12 THEN 4
    ELSE NULL
END
WHERE trimestre IS NULL AND mes_defuncion IS NOT NULL;

-- 2.2 Constraint trimestre
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_silver_trimestre'
          AND conrelid = 'silver.silver_mortalidad_limpia'::regclass
    ) THEN
        ALTER TABLE silver.silver_mortalidad_limpia
            ADD CONSTRAINT chk_silver_trimestre
            CHECK (trimestre BETWEEN 1 AND 4);
    END IF;
END $$;

-- 2.3 Índice trimestre
CREATE INDEX IF NOT EXISTS idx_silver_trim
    ON silver.silver_mortalidad_limpia (anio_defuncion, trimestre);

-- 2.4 Backfill ocurrencia desde bronze (solo si bronze tiene la columna)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='bronze' AND table_name='bronze_mortalidad_raw'
          AND column_name='entidad_ocurrencia'
    ) THEN
        UPDATE silver.silver_mortalidad_limpia s
        SET entidad_ocurrencia   = NULLIF(b.entidad_ocurrencia, '')::INTEGER,
            municipio_ocurrencia = NULLIF(b.municipio_ocurrencia, '')::INTEGER,
            localidad_ocurrencia = b.localidad_ocurrenciad
        FROM bronze.bronze_mortalidad_raw b
        WHERE s.id_carga_origen = b.id_carga
          AND s.entidad_ocurrencia IS NULL
          AND b.entidad_ocurrencia IS NOT NULL;
    END IF;
END $$;


-- ============================================================
-- FASE 3 — Ampliar gold
-- ============================================================
\echo '=== FASE 3 — Ampliar gold ==='

-- 3.1 dim_geografia
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='dim_geografia' AND column_name='localidad_nombre')
    THEN ALTER TABLE gold.dim_geografia ADD COLUMN localidad_nombre VARCHAR(300); END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='dim_geografia' AND column_name='tamanio_localidad')
    THEN ALTER TABLE gold.dim_geografia ADD COLUMN tamanio_localidad VARCHAR(100); END IF;
END $$;

-- 3.2 dim_causa
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='dim_causa' AND column_name='incluida_rmm')
    THEN ALTER TABLE gold.dim_causa ADD COLUMN incluida_rmm BOOLEAN; END IF;
END $$;
UPDATE gold.dim_causa SET incluida_rmm = TRUE WHERE incluida_rmm IS NULL;
ALTER TABLE gold.dim_causa ALTER COLUMN incluida_rmm SET DEFAULT TRUE;
ALTER TABLE gold.dim_causa ALTER COLUMN incluida_rmm SET NOT NULL;

-- 3.3 dim_edad
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='dim_edad' AND column_name='edad_min')
    THEN ALTER TABLE gold.dim_edad ADD COLUMN edad_min INTEGER; END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='dim_edad' AND column_name='edad_max')
    THEN ALTER TABLE gold.dim_edad ADD COLUMN edad_max INTEGER; END IF;
END $$;

UPDATE gold.dim_edad
SET edad_min = split_part(edad_quinquenal, '-', 1)::INTEGER,
    edad_max = split_part(edad_quinquenal, '-', 2)::INTEGER
WHERE edad_min IS NULL
  AND edad_quinquenal ~ '^[0-9]{2}-[0-9]{2}$';

-- 3.4 fact: id_geografia_ocur
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='fact_mortalidad_materna' AND column_name='id_geografia_ocur')
    THEN ALTER TABLE gold.fact_mortalidad_materna ADD COLUMN id_geografia_ocur INTEGER; END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'fk_fact_geo_ocur'
                     AND conrelid = 'gold.fact_mortalidad_materna'::regclass)
    THEN
        ALTER TABLE gold.fact_mortalidad_materna
            ADD CONSTRAINT fk_fact_geo_ocur
            FOREIGN KEY (id_geografia_ocur)
            REFERENCES gold.dim_geografia(id_geografia);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fact_geo_ocur
    ON gold.fact_mortalidad_materna (id_geografia_ocur);

-- 3.5 dim_persona (índice único con COALESCE, no CONSTRAINT)
CREATE TABLE IF NOT EXISTS gold.dim_persona (
    id_persona          SERIAL PRIMARY KEY,
    estado_conyugal     VARCHAR(50),
    escolaridad         VARCHAR(200),
    ocupacion           VARCHAR(200),
    derechohabiencia    VARCHAR(200),
    asistencia_medica   VARCHAR(100),
    certifico           VARCHAR(100)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_persona
    ON gold.dim_persona (
        COALESCE(estado_conyugal,   'NA'),
        COALESCE(escolaridad,       'NA'),
        COALESCE(ocupacion,         'NA'),
        COALESCE(derechohabiencia,  'NA'),
        COALESCE(asistencia_medica, 'NA'),
        COALESCE(certifico,         'NA')
    );

-- 3.6 fact: id_persona
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema='gold' AND table_name='fact_mortalidad_materna' AND column_name='id_persona')
    THEN ALTER TABLE gold.fact_mortalidad_materna ADD COLUMN id_persona INTEGER; END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'fk_fact_persona'
                     AND conrelid = 'gold.fact_mortalidad_materna'::regclass)
    THEN
        ALTER TABLE gold.fact_mortalidad_materna
            ADD CONSTRAINT fk_fact_persona
            FOREIGN KEY (id_persona)
            REFERENCES gold.dim_persona(id_persona);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fact_persona
    ON gold.fact_mortalidad_materna (id_persona);


-- ============================================================
-- FASE 4 — Re-poblar dim_persona y enriquecer fact
-- ============================================================
\echo '=== FASE 4 — Re-poblar dim_persona y enriquecer fact ==='

-- 4.1 Poblar dim_persona
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

-- 4.2 Actualizar fact.id_persona
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

-- 4.3 Actualizar fact.id_geografia_ocur
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
    END IF;
END $$;

-- 4.4 Sincronizar dim_causa.incluida_rmm con catálogo
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema='gold' AND table_name='cat_cie10') THEN
        UPDATE gold.dim_causa dc
        SET incluida_rmm = c.incluida_rmm
        FROM gold.cat_cie10 c
        WHERE dc.codigo_cie10 = c.codigo_cie10
          AND dc.incluida_rmm IS DISTINCT FROM c.incluida_rmm;
    END IF;
END $$;

-- 4.5 Poblar dim_geografia.localidad_nombre / tamanio_localidad desde silver
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='silver' AND table_name='silver_mortalidad_limpia'
          AND column_name='localidad_nombre'
    ) THEN
        UPDATE gold.dim_geografia g
        SET localidad_nombre  = s.localidad_nombre,
            tamanio_localidad = s.tamanio_localidad
        FROM silver.silver_mortalidad_limpia s
        WHERE g.id_entidad   = s.entidad_residencia
          AND COALESCE(g.id_municipio,-1) = COALESCE(s.municipio_residencia,-1)
          AND g.localidad_nombre IS NULL;
    END IF;
END $$;


-- ============================================================
-- FASE 5 — Re-REFRESH de las MVs (orden de dependencia)
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
-- FASE 6 — Validación post-migración
-- ============================================================
\echo '=== FASE 6 — Validación ==='

DROP TABLE IF EXISTS public._migracion_conteos_post;
CREATE TABLE public._migracion_conteos_post AS
SELECT now() AS momento, 'bronze.bronze_mortalidad_raw'   AS tabla, count(*) AS filas FROM bronze.bronze_mortalidad_raw
UNION ALL SELECT now(), 'silver.silver_mortalidad_limpia', count(*) FROM silver.silver_mortalidad_limpia
UNION ALL SELECT now(), 'gold.dim_tiempo',                 count(*) FROM gold.dim_tiempo
UNION ALL SELECT now(), 'gold.dim_geografia',              count(*) FROM gold.dim_geografia
UNION ALL SELECT now(), 'gold.dim_causa',                  count(*) FROM gold.dim_causa
UNION ALL SELECT now(), 'gold.dim_edad',                   count(*) FROM gold.dim_edad
UNION ALL SELECT now(), 'gold.fact_mortalidad_materna',    count(*) FROM gold.fact_mortalidad_materna
UNION ALL SELECT now(), 'gold.nacimientos_estimados',      count(*) FROM gold.nacimientos_estimados;

\echo '--- 6.1 Diff de conteos (delta debe ser >= 0) ---'
SELECT p.tabla, p.filas AS antes, q.filas AS despues, q.filas - p.filas AS delta
FROM public._migracion_conteos_pre p
JOIN public._migracion_conteos_post q USING (tabla)
ORDER BY p.tabla;

\echo '--- 6.2 Cobertura nuevos campos en silver ---'
SELECT
  round(100.0 * count(*) FILTER (WHERE trimestre IS NOT NULL) / count(*), 2) AS pct_trimestre,
  round(100.0 * count(*) FILTER (WHERE entidad_ocurrencia IS NOT NULL) / count(*), 2) AS pct_ocurrencia,
  round(100.0 * count(*) FILTER (WHERE razon_mortalidad_texto IS NOT NULL) / count(*), 2) AS pct_razon
FROM silver.silver_mortalidad_limpia;

\echo '--- 6.3 Cobertura nuevas FKs en fact ---'
SELECT
  round(100.0 * count(*) FILTER (WHERE id_persona IS NOT NULL) / count(*), 2) AS pct_persona,
  round(100.0 * count(*) FILTER (WHERE id_geografia_ocur IS NOT NULL) / count(*), 2) AS pct_geo_ocur,
  round(100.0 * count(*) FILTER (WHERE id_causa IS NOT NULL) / count(*), 2) AS pct_causa
FROM gold.fact_mortalidad_materna;

\echo '--- 6.4 Filas por MV ---'
SELECT 'mv_rmm_anual_entidad' AS mv, count(*) FROM marts.mv_rmm_anual_entidad
UNION ALL SELECT 'mv_causas_agrupadas',    count(*) FROM marts.mv_causas_agrupadas
UNION ALL SELECT 'mv_distribucion_edad',   count(*) FROM marts.mv_distribucion_edad
UNION ALL SELECT 'mv_subclasificacion',    count(*) FROM marts.mv_subclasificacion
UNION ALL SELECT 'mv_series_tiempo',       count(*) FROM marts.mv_series_tiempo
UNION ALL SELECT 'mv_derechohabiencia',    count(*) FROM marts.mv_derechohabiencia
UNION ALL SELECT 'mv_escolaridad',         count(*) FROM marts.mv_escolaridad
UNION ALL SELECT 'mv_estado_conyugal',     count(*) FROM marts.mv_estado_conyugal
UNION ALL SELECT 'mv_ocupacion',           count(*) FROM marts.mv_ocupacion
UNION ALL SELECT 'mv_sitio_defuncion',     count(*) FROM marts.mv_sitio_defuncion;

\echo '=== MIGRACIÓN COMPLETADA ==='


-- ============================================================
-- FASE 7 — (Opcional) Rollback completo
-- ============================================================
-- Descomentar y ejecutar SOLO si necesitas revertir.
-- NOTA: requiere haber hecho backup previo (pg_dump -Fc).
--
-- \echo '=== ROLLBACK ==='
-- ALTER TABLE gold.fact_mortalidad_materna DROP CONSTRAINT IF EXISTS fk_fact_persona;
-- ALTER TABLE gold.fact_mortalidad_materna DROP CONSTRAINT IF EXISTS fk_fact_geo_ocur;
-- ALTER TABLE gold.fact_mortalidad_materna DROP COLUMN IF EXISTS id_persona;
-- ALTER TABLE gold.fact_mortalidad_materna DROP COLUMN IF EXISTS id_geografia_ocur;
-- DROP INDEX IF EXISTS gold.idx_fact_persona;
-- DROP INDEX IF EXISTS gold.idx_fact_geo_ocur;
-- DROP TABLE IF EXISTS gold.dim_persona;
-- ALTER TABLE gold.dim_edad DROP COLUMN IF EXISTS edad_min;
-- ALTER TABLE gold.dim_edad DROP COLUMN IF EXISTS edad_max;
-- ALTER TABLE gold.dim_causa DROP COLUMN IF EXISTS incluida_rmm;
-- ALTER TABLE gold.dim_geografia DROP COLUMN IF EXISTS localidad_nombre;
-- ALTER TABLE gold.dim_geografia DROP COLUMN IF EXISTS tamanio_localidad;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP CONSTRAINT IF EXISTS chk_silver_trimestre;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP COLUMN IF EXISTS trimestre;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP COLUMN IF EXISTS fila_origen;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP COLUMN IF EXISTS entidad_ocurrencia;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP COLUMN IF EXISTS municipio_ocurrencia;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP COLUMN IF EXISTS localidad_ocurrencia;
-- ALTER TABLE silver.silver_mortalidad_limpia DROP COLUMN IF EXISTS razon_mortalidad_texto;
-- DROP INDEX IF EXISTS silver.idx_silver_trim;
-- -- Para bronze, restaurar desde pg_dump del paso 0.