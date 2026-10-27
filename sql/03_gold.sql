CREATE SCHEMA IF NOT EXISTS gold;

-- Dimensión tiempo
CREATE TABLE gold.dim_tiempo (
    id_tiempo    SERIAL PRIMARY KEY,
    anio         INTEGER NOT NULL,
    mes          INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    trimestre    INTEGER NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    CONSTRAINT uq_tiempo UNIQUE (anio, mes)
);

-- Dimensión geografía
CREATE TABLE gold.dim_geografia (
    id_geografia   SERIAL PRIMARY KEY,
    id_entidad     INTEGER NOT NULL,
    entidad_nombre VARCHAR(200) NOT NULL,
    id_municipio   INTEGER,
    municipio_nombre VARCHAR(200),
    CONSTRAINT uq_geo UNIQUE (id_entidad, id_municipio)
);

-- Dimensión causa (agrupada según DGE)
CREATE TABLE gold.dim_causa (
    id_causa         SERIAL PRIMARY KEY,
    codigo_cie10     VARCHAR(20) NOT NULL,
    descripcion_causa VARCHAR(300),
    grupo_causa      VARCHAR(100),  -- Hemorragia, Hipertensión, Aborto, Sepsis, Indirectas, Otras
    CONSTRAINT uq_causa UNIQUE (codigo_cie10)
);

-- Dimensión edad
CREATE TABLE gold.dim_edad (
    id_edad         SERIAL PRIMARY KEY,
    edad_quinquenal VARCHAR(20) NOT NULL UNIQUE
);

-- Tabla de hechos
CREATE TABLE gold.fact_mortalidad_materna (
    id_hecho         BIGSERIAL PRIMARY KEY,
    id_tiempo        INTEGER REFERENCES gold.dim_tiempo(id_tiempo),
    id_geografia     INTEGER REFERENCES gold.dim_geografia(id_geografia),
    id_causa         INTEGER REFERENCES gold.dim_causa(id_causa),
    id_edad          INTEGER REFERENCES gold.dim_edad(id_edad),
    numero_defunciones INTEGER NOT NULL DEFAULT 1,
    incluida_en_rmm  BOOLEAN NOT NULL DEFAULT TRUE,
    id_registro_silver BIGINT REFERENCES silver.silver_mortalidad_limpia(id_registro)
);

CREATE INDEX idx_fact_tiempo ON gold.fact_mortalidad_materna (id_tiempo);
CREATE INDEX idx_fact_geo ON gold.fact_mortalidad_materna (id_geografia);
CREATE INDEX idx_fact_causa ON gold.fact_mortalidad_materna (id_causa);

-- Tabla paramétrica de nacimientos estimados (cargable por operador)
CREATE TABLE gold.nacimientos_estimados (
    anio         INTEGER NOT NULL,
    id_entidad   INTEGER NOT NULL,
    nacimientos  INTEGER NOT NULL CHECK (nacimientos > 0),
    fuente       VARCHAR(100),
    fecha_carga  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (anio, id_entidad)
);