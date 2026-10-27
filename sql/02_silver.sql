CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE silver.silver_mortalidad_limpia (
    id_registro           BIGSERIAL PRIMARY KEY,
    id_carga_origen       BIGINT REFERENCES bronze.bronze_mortalidad_raw(id_carga),
    anio_defuncion        INTEGER NOT NULL,
    entidad_residencia    INTEGER,
    entidad_nombre        VARCHAR(200),
    causa_cie_4           VARCHAR(20),
    causa_descripcion     VARCHAR(300),
    edad                  INTEGER,
    edad_quinquenal       VARCHAR(20),
    mes_defuncion         INTEGER,
    dia_defuncion         INTEGER,           -- si existe en el CSV original
    tamanio_localidad     VARCHAR(50),
    incluida_en_rmm       BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_procesamiento   TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_silver_dedup UNIQUE (
        anio_defuncion, entidad_residencia, mes_defuncion, dia_defuncion,
        edad, causa_cie_4
    )
);

CREATE INDEX idx_silver_anio ON silver.silver_mortalidad_limpia (anio_defuncion);
CREATE INDEX idx_silver_entidad ON silver.silver_mortalidad_limpia (entidad_residencia);
CREATE INDEX idx_silver_rmm ON silver.silver_mortalidad_limpia (incluida_en_rmm);