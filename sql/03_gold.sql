-- ============================================================
-- 03_gold.sql
-- Capa Gold: modelo estrella para RMM
-- ============================================================

-- ---------- Dimensión tiempo ----------
CREATE TABLE gold.dim_tiempo (
    id_tiempo    SERIAL PRIMARY KEY,
    anio         INTEGER NOT NULL,
    mes          INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    trimestre    INTEGER NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    CONSTRAINT uq_tiempo UNIQUE (anio, mes)
);

-- ---------- Dimensión geografía ----------
CREATE TABLE gold.dim_geografia (
    id_geografia       SERIAL PRIMARY KEY,
    id_entidad         INTEGER NOT NULL,
    entidad_nombre     VARCHAR(200) NOT NULL,
    id_municipio       INTEGER,
    municipio_nombre   VARCHAR(200),
    localidad_nombre   VARCHAR(300),
    tamanio_localidad  VARCHAR(100),
    CONSTRAINT uq_geo UNIQUE (id_entidad, COALESCE(id_municipio, -1), COALESCE(localidad_nombre, 'NA'))
);

-- ---------- Dimensión causa ----------
CREATE TABLE gold.dim_causa (
    id_causa           SERIAL PRIMARY KEY,
    codigo_cie10       VARCHAR(20) NOT NULL,
    descripcion_causa  VARCHAR(300),
    grupo_causa        VARCHAR(100) NOT NULL,
    incluida_rmm       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_causa UNIQUE (codigo_cie10)
);

CREATE INDEX idx_dim_causa_grupo ON gold.dim_causa (grupo_causa);

-- ---------- Dimensión edad ----------
CREATE TABLE gold.dim_edad (
    id_edad          SERIAL PRIMARY KEY,
    edad_quinquenal  VARCHAR(20) NOT NULL UNIQUE,
    edad_min         INTEGER,
    edad_max         INTEGER
);

-- ---------- Dimensión persona ----------
CREATE TABLE gold.dim_persona (
    id_persona          SERIAL PRIMARY KEY,
    estado_conyugal     VARCHAR(50),
    escolaridad         VARCHAR(200),
    ocupacion           VARCHAR(200),
    derechohabiencia    VARCHAR(200),
    asistencia_medica   VARCHAR(100),
    certifico           VARCHAR(100),
    CONSTRAINT uq_persona UNIQUE (
        COALESCE(estado_conyugal,'NA'),
        COALESCE(escolaridad,'NA'),
        COALESCE(ocupacion,'NA'),
        COALESCE(derechohabiencia,'NA'),
        COALESCE(asistencia_medica,'NA'),
        COALESCE(certifico,'NA')
    )
);

-- ---------- Tabla de hechos ----------
CREATE TABLE gold.fact_mortalidad_materna (
    id_hecho             BIGSERIAL PRIMARY KEY,
    id_tiempo            INTEGER REFERENCES gold.dim_tiempo(id_tiempo),
    id_geografia_res     INTEGER REFERENCES gold.dim_geografia(id_geografia),
    id_geografia_ocur    INTEGER REFERENCES gold.dim_geografia(id_geografia),
    id_causa             INTEGER REFERENCES gold.dim_causa(id_causa),
    id_edad              INTEGER REFERENCES gold.dim_edad(id_edad),
    id_persona           INTEGER REFERENCES gold.dim_persona(id_persona),
    numero_defunciones   INTEGER NOT NULL DEFAULT 1,
    incluida_en_rmm      BOOLEAN NOT NULL DEFAULT TRUE,
    id_registro_silver   BIGINT REFERENCES silver.silver_mortalidad_limpia(id_registro)
);

CREATE INDEX idx_fact_tiempo   ON gold.fact_mortalidad_materna (id_tiempo);
CREATE INDEX idx_fact_geo_res  ON gold.fact_mortalidad_materna (id_geografia_res);
CREATE INDEX idx_fact_geo_ocur ON gold.fact_mortalidad_materna (id_geografia_ocur);
CREATE INDEX idx_fact_causa    ON gold.fact_mortalidad_materna (id_causa);
CREATE INDEX idx_fact_edad     ON gold.fact_mortalidad_materna (id_edad);
CREATE INDEX idx_fact_rmm      ON gold.fact_mortalidad_materna (incluida_en_rmm);

-- ---------- Nacimientos estimados ----------
CREATE TABLE gold.nacimientos_estimados (
    anio         INTEGER NOT NULL,
    id_entidad   INTEGER NOT NULL,
    nacimientos  INTEGER NOT NULL CHECK (nacimientos > 0),
    fuente       VARCHAR(100),
    fecha_carga  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (anio, id_entidad)
);