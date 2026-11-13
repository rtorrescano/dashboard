-- ============================================================
-- 02_silver.sql
-- Capa Silver: tipado, limpieza, deduplicación
-- ============================================================
CREATE TABLE silver.silver_mortalidad_limpia (
    id_registro               BIGSERIAL PRIMARY KEY,
    id_carga_origen           BIGINT REFERENCES bronze.bronze_mortalidad_raw(id_carga),
    fila_origen               INTEGER,

    -- Tiempo defunción
    anio_defuncion            INTEGER,
    mes_defuncion             INTEGER CHECK (mes_defuncion BETWEEN 1 AND 12),
    dia_defuncion             INTEGER CHECK (dia_defuncion BETWEEN 1 AND 31),
    trimestre                 INTEGER CHECK (trimestre BETWEEN 1 AND 4),

    -- Geografía residencia
    entidad_residencia        INTEGER,
    entidad_nombre            VARCHAR(200),
    municipio_residencia      INTEGER,
    municipio_nombre          VARCHAR(200),
    localidad_nombre          VARCHAR(300),
    tamanio_localidad         VARCHAR(100),

    -- Geografía ocurrencia
    entidad_ocurrencia        INTEGER,
    municipio_ocurrencia      INTEGER,
    localidad_ocurrencia      VARCHAR(300),
    sitio_defuncion           VARCHAR(100),

    -- Causa
    causa_cie_4               VARCHAR(20),
    causa_descripcion         VARCHAR(300),

    -- Persona
    edad                      INTEGER,
    edad_quinquenal           VARCHAR(20),
    estado_conyugal           VARCHAR(50),
    escolaridad               VARCHAR(200),
    ocupacion                 VARCHAR(200),
    derechohabiencia          VARCHAR(200),
    asistencia_medica         VARCHAR(100),
    certifico                 VARCHAR(100),

    -- Registro / certificación
    anio_registro             INTEGER,
    mes_registro              INTEGER,
    anio_certificacion        INTEGER,
    mes_certificacion         INTEGER,

    -- Flag RMM
    incluida_en_rmm           BOOLEAN NOT NULL DEFAULT TRUE,
    razon_mortalidad_texto    VARCHAR(200),

    fecha_procesamiento       TIMESTAMPTZ DEFAULT now(),

    -- Deduplicación robusta con COALESCE (NULL no colisiona en UNIQUE)
    CONSTRAINT uq_silver_dedup UNIQUE (
        anio_defuncion,
        entidad_residencia,
        COALESCE(mes_defuncion, 0),
        COALESCE(dia_defuncion, 0),
        COALESCE(edad, -1),
        COALESCE(causa_cie_4, 'NA')
    )
);

CREATE INDEX idx_silver_anio     ON silver.silver_mortalidad_limpia (anio_defuncion);
CREATE INDEX idx_silver_trim     ON silver.silver_mortalidad_limpia (anio_defuncion, trimestre);
CREATE INDEX idx_silver_entidad  ON silver.silver_mortalidad_limpia (entidad_residencia);
CREATE INDEX idx_silver_causa    ON silver.silver_mortalidad_limpia (causa_cie_4);
CREATE INDEX idx_silver_rmm      ON silver.silver_mortalidad_limpia (incluida_en_rmm);

COMMENT ON TABLE silver.silver_mortalidad_limpia IS 'Datos limpios y tipados de mortalidad materna';