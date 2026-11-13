-- ============================================================
-- 01_bronze.sql
-- Capa Bronze: 58 columnas del CSV + metadatos de ingesta
-- ============================================================
CREATE TABLE bronze.bronze_mortalidad_raw (
    id_carga                   BIGSERIAL PRIMARY KEY,

    -- ===== 58 columnas del CSV (todas TEXT) =====
    anio_nacimiento            VARCHAR(10),
    mes_nacimiento             VARCHAR(10),
    mes_nacimientod            VARCHAR(50),
    dia_nacimiento             VARCHAR(10),
    edad                       VARCHAR(10),
    estado_conyugal            VARCHAR(10),
    estado_conyugald           VARCHAR(50),
    entidad_residencia         VARCHAR(10),
    entidad_residenciad        VARCHAR(200),
    municipio_residencia       VARCHAR(10),
    municipio_residenciad      VARCHAR(200),
    localidad_residencia       VARCHAR(10),
    localidad_residenciad      VARCHAR(300),
    tamanio_localidad          VARCHAR(10),
    tamanio_localidadd         VARCHAR(100),
    ocupacion_habitual         VARCHAR(10),
    ocupacion_habituald        VARCHAR(200),
    escolaridad                VARCHAR(10),
    escolaridadd               VARCHAR(200),
    derechohabiencia           VARCHAR(10),
    derechohabienciad          VARCHAR(200),
    entidad_ocurrencia         VARCHAR(10),
    entidad_ocurrenciad        VARCHAR(200),
    municipio_ocurrencia       VARCHAR(10),
    municipio_ocurrenciad      VARCHAR(200),
    localidad_ocurrencia       VARCHAR(10),
    localidad_ocurrenciad      VARCHAR(300),
    sitio_defuncion            VARCHAR(10),
    sitio_defunciond           VARCHAR(200),
    anio_defuncion             VARCHAR(10),
    mes_defuncion              VARCHAR(10),
    mes_defunciond             VARCHAR(50),
    dia_defuncion              VARCHAR(10),
    hora_defuncion             VARCHAR(10),
    minutos_defuncion          VARCHAR(10),
    asistencia_medica          VARCHAR(10),
    asistencia_medicad         VARCHAR(100),
    causa_cie_4                VARCHAR(20),
    causa_cie_4d               VARCHAR(300),
    certifico                  VARCHAR(10),
    certificod                 VARCHAR(100),
    entidad_registro           VARCHAR(10),
    entidad_registrod          VARCHAR(200),
    municipio_registro         VARCHAR(10),
    municipio_registrod        VARCHAR(200),
    anio_registro              VARCHAR(10),
    mes_registro               VARCHAR(10),
    mes_registrod              VARCHAR(50),
    dia_registro               VARCHAR(10),
    anio_certificacion         VARCHAR(10),
    mes_certificacion          VARCHAR(10),
    mes_certificaciond         VARCHAR(50),
    dia_certificacion          VARCHAR(10),
    anio_base_datos            VARCHAR(10),
    razon_mortalidad_materna   VARCHAR(10),
    razon_mortalidad_maternaD  VARCHAR(200),
    edad_quinquenal            VARCHAR(10),
    edad_quinquenald           VARCHAR(50),

    -- ===== Metadatos =====
    nombre_archivo_original    VARCHAR(255) NOT NULL,
    hash_archivo               CHAR(64) NOT NULL,
    fecha_carga                TIMESTAMPTZ DEFAULT now(),
    estatus_procesamiento      VARCHAR(20) DEFAULT 'PENDIENTE',
    version_archivo            VARCHAR(20) DEFAULT 'v1',
    fila_origen                INTEGER,
    error_carga                TEXT,

    CONSTRAINT uq_hash_fila UNIQUE (hash_archivo, fila_origen)
);

CREATE INDEX idx_bronze_estatus ON bronze.bronze_mortalidad_raw (estatus_procesamiento);
CREATE INDEX idx_bronze_hash    ON bronze.bronze_mortalidad_raw (hash_archivo);
CREATE INDEX idx_bronze_anio    ON bronze.bronze_mortalidad_raw (anio_defuncion);
CREATE INDEX idx_bronze_causa   ON bronze.bronze_mortalidad_raw (causa_cie_4);

COMMENT ON TABLE bronze.bronze_mortalidad_raw IS 'Datos raw del CSV de mortalidad materna 2002-2024, sin transformar';