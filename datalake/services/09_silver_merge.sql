-- ============================================================
-- 09_silver_merge.sql
-- Sincroniza Silver desde Bronze (solo filas vigentes).
-- Requiere: 09a + 09b aplicados.
-- ============================================================

BEGIN;

MERGE INTO silver.silver_mortalidad_limpia AS tgt
USING (
    SELECT
        b.clave_natural,
        b.hash_fila,
        b.id_carga                                    AS id_carga_origen,
        NULLIF(TRIM(b.anio_defuncion),'')::int        AS anio_defuncion,
        NULLIF(TRIM(b.entidad_residencia),'')::int    AS entidad_residencia,
        NULLIF(TRIM(b.entidad_residenciad),'')::text  AS entidad_nombre,
        NULLIF(TRIM(b.causa_cie_4),'')::text          AS causa_cie_4,
        NULLIF(TRIM(b.causa_cie_4d),'')::text         AS causa_descripcion,
        NULLIF(TRIM(b.edad),'')::int                  AS edad,
        NULLIF(TRIM(b.edad_quinquenal),'')::text      AS edad_quinquenal,
        NULLIF(TRIM(b.mes_defuncion),'')::int         AS mes_defuncion,
        NULLIF(TRIM(b.dia_registro),'')::int          AS dia_defuncion,
        NULLIF(TRIM(b.tamanio_localidad),'')::text    AS tamanio_localidad,
        NULLIF(TRIM(b.sitio_defuncion),'')::text      AS sitio_defuncion,
        NULLIF(TRIM(b.escolaridad),'')::text          AS escolaridad,
        NULLIF(TRIM(b.ocupacion),'')::text            AS ocupacion,
        NULLIF(TRIM(b.estado_conyugal),'')::text      AS estado_conyugal,
        NULLIF(TRIM(b.derechohabiencia),'')::text     AS derechohabiencia,
        NULLIF(TRIM(b.municipio_residenciad),'')::text AS municipio_nombre,
        NULLIF(TRIM(b.municipio_residencia),'')::int  AS municipio_residencia,
        NULLIF(TRIM(b.localidad_residencia),'')::text AS localidad_nombre,
        b.fila_origen,
        NULLIF(TRIM(b.trimestre),'')::int             AS trimestre,
        NULLIF(TRIM(b.entidad_ocurrencia),'')::int    AS entidad_ocurrencia,
        NULLIF(TRIM(b.municipio_ocurrencia),'')::int  AS municipio_ocurrencia,
        NULLIF(TRIM(b.localidad_ocurrencia),'')::text AS localidad_ocurrencia,
        NULLIF(TRIM(b.razon_mortalidad_materna),'')::text AS razon_mortalidad_texto,
        NULLIF(TRIM(b.asistencia_medica),'')::text    AS asistencia_medica,
        NULLIF(TRIM(b.certifico),'')::text            AS certifico,
        NULLIF(TRIM(b.hora_defuncion),'')::text       AS hora_defuncion,
        NULLIF(TRIM(b.minutos_defuncion),'')::text    AS minutos_defuncion
      FROM bronze.bronze_mortalidad_raw b
     WHERE b.vigente
) AS src
ON tgt.clave_natural = src.clave_natural

-- 1) Existe y no cambió → no hacer nada
WHEN MATCHED AND tgt.hash_fila IS NOT DISTINCT FROM src.hash_fila
    THEN DO NOTHING

-- 2) Existe y cambió → actualizar columnas de negocio + hash
WHEN MATCHED AND tgt.hash_fila IS DISTINCT FROM src.hash_fila
    THEN UPDATE SET
        id_carga_origen      = src.id_carga_origen,
        anio_defuncion       = src.anio_defuncion,
        entidad_residencia   = src.entidad_residencia,
        entidad_nombre       = src.entidad_nombre,
        causa_cie_4          = src.causa_cie_4,
        causa_descripcion    = src.causa_descripcion,
        edad                 = src.edad,
        edad_quinquenal      = src.edad_quinquenal,
        mes_defuncion        = src.mes_defuncion,
        dia_defuncion        = src.dia_defuncion,
        tamanio_localidad    = src.tamanio_localidad,
        sitio_defuncion      = src.sitio_defuncion,
        escolaridad          = src.escolaridad,
        ocupacion            = src.ocupacion,
        estado_conyugal      = src.estado_conyugal,
        derechohabiencia     = src.derechohabiencia,
        municipio_nombre     = src.municipio_nombre,
        municipio_residencia = src.municipio_residencia,
        localidad_nombre     = src.localidad_nombre,
        fila_origen          = src.fila_origen,
        trimestre            = src.trimestre,
        entidad_ocurrencia   = src.entidad_ocurrencia,
        municipio_ocurrencia = src.municipio_ocurrencia,
        localidad_ocurrencia = src.localidad_ocurrencia,
        razon_mortalidad_texto = src.razon_mortalidad_texto,
        asistencia_medica    = src.asistencia_medica,
        certifico            = src.certifico,
        hora_defuncion       = src.hora_defuncion,
        minutos_defuncion    = src.minutos_defuncion,
        hash_fila            = src.hash_fila,
        vigente              = true,
        fecha_procesamiento  = now()

-- 3) No existe → insertar
WHEN NOT MATCHED
    THEN INSERT (
        id_carga_origen, anio_defuncion, entidad_residencia, entidad_nombre,
        causa_cie_4, causa_descripcion, edad, edad_quinquenal,
        mes_defuncion, dia_defuncion, tamanio_localidad,
        sitio_defuncion, escolaridad, ocupacion, estado_conyugal,
        derechohabiencia, municipio_nombre, municipio_residencia,
        localidad_nombre, fila_origen, trimestre,
        entidad_ocurrencia, municipio_ocurrencia, localidad_ocurrencia,
        razon_mortalidad_texto, asistencia_medica, certifico,
        hora_defuncion, minutos_defuncion,
        clave_natural, hash_fila, vigente
    ) VALUES (
        src.id_carga_origen, src.anio_defuncion, src.entidad_residencia, src.entidad_nombre,
        src.causa_cie_4, src.causa_descripcion, src.edad, src.edad_quinquenal,
        src.mes_defuncion, src.dia_defuncion, src.tamanio_localidad,
        src.sitio_defuncion, src.escolaridad, src.ocupacion, src.estado_conyugal,
        src.derechohabiencia, src.municipio_nombre, src.municipio_residencia,
        src.localidad_nombre, src.fila_origen, src.trimestre,
        src.entidad_ocurrencia, src.municipio_ocurrencia, src.localidad_ocurrencia,
        src.razon_mortalidad_texto, src.asistencia_medica, src.certifico,
        src.hora_defuncion, src.minutos_defuncion,
        src.clave_natural, src.hash_fila, true
    );

-- 4) Política de bajas: filas de Silver que ya no están vigentes en Bronze
UPDATE silver.silver_mortalidad_limpia s
   SET vigente = false,
       fecha_procesamiento = now()
 WHERE s.vigente
   AND NOT EXISTS (
       SELECT 1
         FROM bronze.bronze_mortalidad_raw b
        WHERE b.clave_natural = s.clave_natural
          AND b.vigente
   );

COMMIT;