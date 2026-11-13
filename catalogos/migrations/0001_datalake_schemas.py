from django.db import migrations


SQL_UP = r"""
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ============================================================
-- BRONCE
-- ============================================================
CREATE TABLE IF NOT EXISTS bronze.file_ingestion (
    ingestion_id uuid PRIMARY KEY,
    source_file  text NOT NULL,
    file_hash    char(64) NOT NULL UNIQUE,
    file_path    text,
    row_count    integer,
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    status       text NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS bronze.ageeml_raw (
    ingestion_id               uuid NOT NULL REFERENCES bronze.file_ingestion(ingestion_id),
    source_row_num             integer NOT NULL,
    cvegeo                     text,
    estatus                    text,
    cve_ent                    text,
    nom_ent                    text,
    nom_abr                    text,
    cve_mun                    text,
    nom_mun                    text,
    cve_loc                    text,
    nom_loc                    text,
    ambito                     text,
    latitud                    text,
    longitud                   text,
    lat_decimal                text,
    lon_decimal                text,
    altitud                    text,
    cve_carta                  text,
    pob_total                  text,
    pob_masculina              text,
    pob_femenina               text,
    total_viviendas_habitadas  text,
    PRIMARY KEY (ingestion_id, source_row_num)
);

CREATE INDEX IF NOT EXISTS idx_bronze_raw_cvegeo
    ON bronze.ageeml_raw (cvegeo);

-- ============================================================
-- PLATA (SCD2)
-- ============================================================
CREATE TABLE IF NOT EXISTS silver.localidad (
    id               bigserial PRIMARY KEY,
    cvegeo           char(9) NOT NULL,
    estatus          char(1),
    cve_ent          char(2) NOT NULL,
    nom_ent          text    NOT NULL,
    nom_abr          text,
    cve_mun          char(3) NOT NULL,
    nom_mun          text    NOT NULL,
    cve_loc          char(4) NOT NULL,
    nom_loc          text    NOT NULL,
    ambito           char(1) CHECK (ambito IN ('U','R') OR ambito IS NULL),
    latitud_dms      text,
    longitud_dms     text,
    lat_decimal      numeric(10,8),
    lon_decimal      numeric(10,8),
    altitud          integer,
    cve_carta        text,
    pob_total        integer,
    pob_masculina    integer,
    pob_femenina     integer,
    total_viviendas  integer,
    geom             geometry(Point,4326),
    record_hash      char(64) NOT NULL,
    valid_from       timestamptz NOT NULL,
    valid_to         timestamptz,
    is_current       boolean NOT NULL DEFAULT true,
    ingestion_id     uuid NOT NULL,
    source_file      text NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_localidad_current
    ON silver.localidad (cvegeo) WHERE is_current;

CREATE INDEX IF NOT EXISTS idx_localidad_ent_mun_loc
    ON silver.localidad (cve_ent, cve_mun, cve_loc);

CREATE INDEX IF NOT EXISTS idx_localidad_record_hash
    ON silver.localidad (record_hash);

CREATE INDEX IF NOT EXISTS idx_localidad_geom
    ON silver.localidad USING GIST (geom);

-- ============================================================
-- ORO
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.dim_localidad AS
SELECT cvegeo, cve_ent, nom_ent, cve_mun, nom_mun, cve_loc, nom_loc,
       ambito, lat_decimal, lon_decimal, altitud, geom,
       pob_total, pob_masculina, pob_femenina, total_viviendas
FROM silver.localidad
WHERE is_current;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_localidad_cvegeo
    ON gold.dim_localidad (cvegeo);

CREATE INDEX IF NOT EXISTS idx_dim_localidad_ent
    ON gold.dim_localidad (cve_ent);

CREATE INDEX IF NOT EXISTS idx_dim_localidad_ent_mun
    ON gold.dim_localidad (cve_ent, cve_mun);

CREATE INDEX IF NOT EXISTS idx_dim_localidad_geom
    ON gold.dim_localidad USING GIST (geom);

CREATE MATERIALIZED VIEW IF NOT EXISTS gold.agg_municipio AS
SELECT cve_ent, nom_ent, cve_mun, nom_mun,
       COUNT(*)                              AS num_localidades,
       COALESCE(SUM(pob_total), 0)           AS pob_total,
       COUNT(*) FILTER (WHERE ambito = 'U')  AS loc_urbanas,
       COUNT(*) FILTER (WHERE ambito = 'R')  AS loc_rurales
FROM silver.localidad
WHERE is_current
GROUP BY 1, 2, 3, 4;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agg_municipio
    ON gold.agg_municipio (cve_ent, cve_mun);
"""


SQL_DOWN = r"""
DROP MATERIALIZED VIEW IF EXISTS gold.agg_municipio;
DROP MATERIALIZED VIEW IF EXISTS gold.dim_localidad;
DROP TABLE IF EXISTS silver.localidad CASCADE;
DROP TABLE IF EXISTS bronze.ageeml_raw CASCADE;
DROP TABLE IF EXISTS bronze.file_ingestion CASCADE;
DROP SCHEMA IF EXISTS gold CASCADE;
DROP SCHEMA IF EXISTS silver CASCADE;
DROP SCHEMA IF EXISTS bronze CASCADE;
"""


class Migration(migrations.Migration):
    dependencies = []
    operations = [migrations.RunSQL(SQL_UP, SQL_DOWN)]