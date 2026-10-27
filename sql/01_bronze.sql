CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE bronze.bronze_mortalidad_raw (
    id_carga              BIGSERIAL PRIMARY KEY,
    anio_defuncion        VARCHAR(10),
    entidad_residencia    VARCHAR(10),
    entidad_residenciad   VARCHAR(200),
    causa_cie_4           VARCHAR(20),
    causa_cie_4d          VARCHAR(300),
    edad                  VARCHAR(10),
    edad_quinquenal       VARCHAR(20),
    razon_mortalidad_materna  VARCHAR(50),
    razon_mortalidad_maternad VARCHAR(100),
    mes_defuncion         VARCHAR(10),
    tamanio_localidad     VARCHAR(50),
    -- metadatos
    nombre_archivo_original VARCHAR(255) NOT NULL,
    hash_archivo          CHAR(64) NOT NULL,
    fecha_carga           TIMESTAMPTZ DEFAULT now(),
    estatus_procesamiento VARCHAR(20) DEFAULT 'PENDIENTE',
    version_archivo       VARCHAR(20) DEFAULT 'v1',
    CONSTRAINT uq_hash_archivo UNIQUE (hash_archivo)
);

CREATE INDEX idx_bronze_estatus ON bronze.bronze_mortalidad_raw (estatus_procesamiento);
CREATE INDEX idx_bronze_hash ON bronze.bronze_mortalidad_raw (hash_archivo);