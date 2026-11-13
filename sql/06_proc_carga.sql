CREATE OR REPLACE FUNCTION bronze.cargar_mortalidad_consolidado(
    p_archivo        text,
    p_csv            text,
    p_layout_version text DEFAULT 'v1'
) RETURNS bigint
LANGUAGE plpgsql AS $$
DECLARE
    v_hash     char(64);
    v_id_carga bigint;
    v_filas    integer;
    v_nuevas   integer := 0;
    v_modif    integer := 0;
    v_bajas    integer := 0;
    v_sin      integer := 0;
BEGIN
    -- 1) hash del archivo Excel original
    v_hash := encode(digest(pg_read_binary_file(p_archivo), 'sha256'), 'hex');

    -- 2) registrar carga (idempotente por hash de archivo)
    INSERT INTO bronze.control_cargas
      (nombre_archivo_original, hash_archivo, version_archivo,
       layout_version, estatus_procesamiento)
    VALUES (p_archivo, v_hash, p_layout_version, p_layout_version, 'EN_PROCESO')
    ON CONFLICT (hash_archivo) DO NOTHING
    RETURNING id_carga INTO v_id_carga;

    IF v_id_carga IS NULL THEN
        RAISE NOTICE 'Archivo % ya cargado (hash %)', p_archivo, v_hash;
        RETURN NULL;
    END IF;

    -- 3) cargar CSV al staging
    TRUNCATE public.staging_mortalidad;
    EXECUTE format(
      'COPY public.staging_mortalidad FROM %L WITH (FORMAT CSV, HEADER TRUE, ENCODING ''UTF8'')',
      p_csv
    );

    SELECT count(*) INTO v_filas FROM public.staging_mortalidad;

    -- 4) staging calculado: clave natural (13 campos) + hash de 65 columnas
    CREATE TEMP TABLE _stg ON COMMIT DROP AS
    SELECT
      s.*,
      encode(digest(concat_ws('|',
          NULLIF(TRIM(s.anio_defuncion),''),
          NULLIF(TRIM(s.entidad_registro),''),
          NULLIF(TRIM(s.municipio_registro),''),
          NULLIF(TRIM(s.anio_registro),''),
          NULLIF(TRIM(s.mes_registro),''),
          NULLIF(TRIM(s.dia_registro),''),
          NULLIF(TRIM(s.causa_cie_4),''),
          NULLIF(TRIM(s.edad),''),
          NULLIF(TRIM(s.entidad_residencia),''),
          NULLIF(TRIM(s.municipio_residencia),''),
          NULLIF(TRIM(s.localidad_residencia),''),
          NULLIF(TRIM(s.hora_defuncion),''),
          NULLIF(TRIM(s.minutos_defuncion),'')
      ),'sha256'),'hex')::char(64) AS clave_natural,
      encode(digest(concat_ws('|',
          NULLIF(TRIM(s.anio_defuncion),''),           NULLIF(TRIM(s.entidad_residencia),''),
          NULLIF(TRIM(s.entidad_residenciad),''),      NULLIF(TRIM(s.causa_cie_4),''),
          NULLIF(TRIM(s.causa_cie_4d),''),             NULLIF(TRIM(s.edad),''),
          NULLIF(TRIM(s.edad_quinquenal),''),          NULLIF(TRIM(s.razon_mortalidad_materna),''),
          NULLIF(TRIM(s.razon_mortalidad_maternad),''),NULLIF(TRIM(s.mes_defuncion),''),
          NULLIF(TRIM(s.tamanio_localidad),''),        NULLIF(TRIM(s.nombre_archivo_original),''),
          NULLIF(TRIM(s.hash_archivo),''),             NULLIF(TRIM(s.fecha_carga),''),
          NULLIF(TRIM(s.estatus_procesamiento),''),    NULLIF(TRIM(s.version_archivo),''),
          NULLIF(TRIM(s.municipio_residenciad),''),    NULLIF(TRIM(s.sitio_defuncion),''),
          NULLIF(TRIM(s.escolaridad),''),              NULLIF(TRIM(s.ocupacion),''),
          NULLIF(TRIM(s.estado_conyugal),''),          NULLIF(TRIM(s.derechohabiencia),''),
          NULLIF(TRIM(s.municipio_residencia),''),     NULLIF(TRIM(s.localidad_residencia),''),
          NULLIF(TRIM(s.mes_nacimiento),''),           NULLIF(TRIM(s.mes_nacimientod),''),
          NULLIF(TRIM(s.dia_nacimiento),''),           NULLIF(TRIM(s.estado_conyugald),''),
          NULLIF(TRIM(s.localidad_residenciad),''),    NULLIF(TRIM(s.tamanio_localidadd),''),
          NULLIF(TRIM(s.ocupacion_habitual),''),       NULLIF(TRIM(s.ocupacion_habituald),''),
          NULLIF(TRIM(s.escolaridadd),''),             NULLIF(TRIM(s.derechohabienciad),''),
          NULLIF(TRIM(s.entidad_ocurrencia),''),       NULLIF(TRIM(s.entidad_ocurrenciad),''),
          NULLIF(TRIM(s.municipio_ocurrencia),''),     NULLIF(TRIM(s.municipio_ocurrenciad),''),
          NULLIF(TRIM(s.localidad_ocurrencia),''),     NULLIF(TRIM(s.localidad_ocurrenciad),''),
          NULLIF(TRIM(s.sitio_defunciond),''),         NULLIF(TRIM(s.mes_defunciond),''),
          NULLIF(TRIM(s.hora_defuncion),''),           NULLIF(TRIM(s.minutos_defuncion),''),
          NULLIF(TRIM(s.asistencia_medica),''),        NULLIF(TRIM(s.asistencia_medicad),''),
          NULLIF(TRIM(s.certifico),''),                NULLIF(TRIM(s.certificod),''),
          NULLIF(TRIM(s.entidad_registro),''),         NULLIF(TRIM(s.entidad_registrod),''),
          NULLIF(TRIM(s.municipio_registro),''),       NULLIF(TRIM(s.municipio_registrod),''),
          NULLIF(TRIM(s.anio_registro),''),            NULLIF(TRIM(s.mes_registro),''),
          NULLIF(TRIM(s.mes_registrod),''),            NULLIF(TRIM(s.dia_registro),''),
          NULLIF(TRIM(s.anio_certificacion),''),       NULLIF(TRIM(s.mes_certificacion),''),
          NULLIF(TRIM(s.mes_certificaciond),''),       NULLIF(TRIM(s.dia_certificacion),''),
          NULLIF(TRIM(s.anio_base_datos),''),          NULLIF(TRIM(s.edad_quinquenald),''),
          NULLIF(TRIM(s.error_carga),'')
      ),'sha256'),'hex')::char(64) AS hash_fila
    FROM public.staging_mortalidad s;

    -- 5) ALTAS
    INSERT INTO bronze.bronze_mortalidad_raw (
        id_carga, fila_origen, layout_version, clave_natural, hash_fila,
        vigente, fecha_vigencia_desde,
        anio_defuncion, entidad_residencia, entidad_residenciad, causa_cie_4, causa_cie_4d,
        edad, edad_quinquenal, razon_mortalidad_materna, razon_mortalidad_maternad,
        mes_defuncion, tamanio_localidad, nombre_archivo_original, hash_archivo,
        fecha_carga, estatus_procesamiento, version_archivo, municipio_residenciad,
        sitio_defuncion, escolaridad, ocupacion, estado_conyugal, derechohabiencia,
        municipio_residencia, localidad_residencia, mes_nacimiento, mes_nacimientod,
        dia_nacimiento, estado_conyugald, localidad_residenciad, tamanio_localidadd,
        ocupacion_habitual, ocupacion_habituald, escolaridadd, derechohabienciad,
        entidad_ocurrencia, entidad_ocurrenciad, municipio_ocurrencia, municipio_ocurrenciad,
        localidad_ocurrencia, localidad_ocurrenciad, sitio_defunciond, mes_defunciond,
        hora_defuncion, minutos_defuncion, asistencia_medica, asistencia_medicad,
        certifico, certificod, entidad_registro, entidad_registrod,
        municipio_registro, municipio_registrod, anio_registro, mes_registro,
        mes_registrod, dia_registro, anio_certificacion, mes_certificacion,
        mes_certificaciond, dia_certificacion, anio_base_datos, edad_quinquenald,
        error_carga
    )
    SELECT
        v_id_carga, s.fila_origen, p_layout_version, s.clave_natural, s.hash_fila,
        true, now(),
        s.anio_defuncion, s.entidad_residencia, s.entidad_residenciad, s.causa_cie_4, s.causa_cie_4d,
        s.edad, s.edad_quinquenal, s.razon_mortalidad_materna, s.razon_mortalidad_maternad,
        s.mes_defuncion, s.tamanio_localidad, s.nombre_archivo_original, s.hash_archivo,
        s.fecha_carga, s.estatus_procesamiento, s.version_archivo, s.municipio_residenciad,
        s.sitio_defuncion, s.escolaridad, s.ocupacion, s.estado_conyugal, s.derechohabiencia,
        s.municipio_residencia, s.localidad_residencia, s.mes_nacimiento, s.mes_nacimientod,
        s.dia_nacimiento, s.estado_conyugald, s.localidad_residenciad, s.tamanio_localidadd,
        s.ocupacion_habitual, s.ocupacion_habituald, s.escolaridadd, s.derechohabienciad,
        s.entidad_ocurrencia, s.entidad_ocurrenciad, s.municipio_ocurrencia, s.municipio_ocurrenciad,
        s.localidad_ocurrencia, s.localidad_ocurrenciad, s.sitio_defunciond, s.mes_defunciond,
        s.hora_defuncion, s.minutos_defuncion, s.asistencia_medica, s.asistencia_medicad,
        s.certifico, s.certificod, s.entidad_registro, s.entidad_registrod,
        s.municipio_registro, s.municipio_registrod, s.anio_registro, s.mes_registro,
        s.mes_registrod, s.dia_registro, s.anio_certificacion, s.mes_certificacion,
        s.mes_certificaciond, s.dia_certificacion, s.anio_base_datos, s.edad_quinquenald,
        s.error_carga
    FROM _stg s
    WHERE NOT EXISTS (
        SELECT 1 FROM bronze.bronze_mortalidad_raw b
         WHERE b.clave_natural = s.clave_natural AND b.vigente
    );
    GET DIAGNOSTICS v_nuevas = ROW_COUNT;

    -- 6) MODIFICACIONES: cerrar versión anterior y registrar diff
    WITH modif AS (
        SELECT b.id_carga AS id_carga_ant, b.clave_natural,
               b.hash_fila AS hash_ant, s.*
          FROM _stg s
          JOIN bronze.bronze_mortalidad_raw b
            ON b.clave_natural = s.clave_natural AND b.vigente
         WHERE b.hash_fila <> s.hash_fila
    ),
    cerradas AS (
        UPDATE bronze.bronze_mortalidad_raw b
           SET vigente = false,
               fecha_vigencia_hasta = now(),
               id_carga_modifica    = v_id_carga
          FROM modif m
         WHERE b.clave_natural = m.clave_natural AND b.vigente
        RETURNING b.clave_natural, b.id_carga
    )
    INSERT INTO bronze.mortalidad_cambios
      (id_carga, clave_natural, tipo_cambio, valor_anterior)
    SELECT v_id_carga, m.clave_natural, 'MODIFICACION',
           row_to_json(m)::jsonb
      FROM modif m;

    -- 7) Insertar la nueva versión de las modificadas
    INSERT INTO bronze.bronze_mortalidad_raw (
        id_carga, fila_origen, layout_version, clave_natural, hash_fila,
        vigente, fecha_vigencia_desde,
        anio_defuncion, entidad_residencia, entidad_residenciad, causa_cie_4, causa_cie_4d,
        edad, edad_quinquenal, razon_mortalidad_materna, razon_mortalidad_maternad,
        mes_defuncion, tamanio_localidad, nombre_archivo_original, hash_archivo,
        fecha_carga, estatus_procesamiento, version_archivo, municipio_residenciad,
        sitio_defuncion, escolaridad, ocupacion, estado_conyugal, derechohabiencia,
        municipio_residencia, localidad_residencia, mes_nacimiento, mes_nacimientod,
        dia_nacimiento, estado_conyugald, localidad_residenciad, tamanio_localidadd,
        ocupacion_habitual, ocupacion_habituald, escolaridadd, derechohabienciad,
        entidad_ocurrencia, entidad_ocurrenciad, municipio_ocurrencia, municipio_ocurrenciad,
        localidad_ocurrencia, localidad_ocurrenciad, sitio_defunciond, mes_defunciond,
        hora_defuncion, minutos_defuncion, asistencia_medica, asistencia_medicad,
        certifico, certificod, entidad_registro, entidad_registrod,
        municipio_registro, municipio_registrod, anio_registro, mes_registro,
        mes_registrod, dia_registro, anio_certificacion, mes_certificacion,
        mes_certificaciond, dia_certificacion, anio_base_datos, edad_quinquenald,
        error_carga
    )
    SELECT
        v_id_carga, s.fila_origen, p_layout_version, s.clave_natural, s.hash_fila,
        true, now(),
        s.anio_defuncion, s.entidad_residencia, s.entidad_residenciad, s.causa_cie_4, s.causa_cie_4d,
        s.edad, s.edad_quinquenal, s.razon_mortalidad_materna, s.razon_mortalidad_maternad,
        s.mes_defuncion, s.tamanio_localidad, s.nombre_archivo_original, s.hash_archivo,
        s.fecha_carga, s.estatus_procesamiento, s.version_archivo, s.municipio_residenciad,
        s.sitio_defuncion, s.escolaridad, s.ocupacion, s.estado_conyugal, s.derechohabiencia,
        s.municipio_residencia, s.localidad_residencia, s.mes_nacimiento, s.mes_nacimientod,
        s.dia_nacimiento, s.estado_conyugald, s.localidad_residenciad, s.tamanio_localidadd,
        s.ocupacion_habitual, s.ocupacion_habituald, s.escolaridadd, s.derechohabienciad,
        s.entidad_ocurrencia, s.entidad_ocurrenciad, s.municipio_ocurrencia, s.municipio_ocurrenciad,
        s.localidad_ocurrencia, s.localidad_ocurrenciad, s.sitio_defunciond, s.mes_defunciond,
        s.hora_defuncion, s.minutos_defuncion, s.asistencia_medica, s.asistencia_medicad,
        s.certifico, s.certificod, s.entidad_registro, s.entidad_registrod,
        s.municipio_registro, s.municipio_registrod, s.anio_registro, s.mes_registro,
        s.mes_registrod, s.dia_registro, s.anio_certificacion, s.mes_certificacion,
        s.mes_certificaciond, s.dia_certificacion, s.anio_base_datos, s.edad_quinquenald,
        s.error_carga
    FROM _stg s
    WHERE EXISTS (
        SELECT 1 FROM bronze.bronze_mortalidad_raw b
         WHERE b.clave_natural = s.clave_natural
           AND b.id_carga_modifica = v_id_carga
    );
    GET DIAGNOSTICS v_modif = ROW_COUNT;

    -- 8) BAJAS: vigentes que no vienen en el consolidado nuevo
    WITH bajas AS (
        UPDATE bronze.bronze_mortalidad_raw b
           SET vigente = false,
               fecha_vigencia_hasta = now(),
               id_carga_modifica    = v_id_carga
         WHERE b.vigente
           AND b.clave_natural NOT IN (SELECT clave_natural FROM _stg)
        RETURNING b.clave_natural
    )
    INSERT INTO bronze.mortalidad_cambios
      (id_carga, clave_natural, tipo_cambio)
    SELECT v_id_carga, clave_natural, 'BAJA' FROM bajas;
    GET DIAGNOSTICS v_bajas = ROW_COUNT;

    v_sin := v_filas - v_nuevas - v_modif;

    -- 9) cerrar control
    UPDATE bronze.control_cargas
       SET estatus_procesamiento = 'CARGADO',
           filas_cargadas    = v_filas,
           filas_nuevas      = v_nuevas,
           filas_modificadas = v_modif,
           filas_baja        = v_bajas,
           filas_sin_cambio  = v_sin,
           duracion_seg      = extract(epoch from now() - fecha_carga)
     WHERE id_carga = v_id_carga;

    TRUNCATE public.staging_mortalidad;
    RETURN v_id_carga;

EXCEPTION WHEN OTHERS THEN
    UPDATE bronze.control_cargas
       SET estatus_procesamiento = 'ERROR', mensaje = SQLERRM
     WHERE id_carga = v_id_carga;
    RAISE;
END;
$$;