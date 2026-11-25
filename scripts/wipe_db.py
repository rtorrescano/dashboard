import os
from django.db import connection
from django.core.management import call_command

def reset_database():
    print("--- 1. INICIANDO BORRADO TOTAL DE LA BASE DE DATOS ---")
    with connection.cursor() as cur:
        # Eliminar esquemas para borrar TODO
        cur.execute("DROP SCHEMA IF EXISTS bronze CASCADE;")
        cur.execute("DROP SCHEMA IF EXISTS silver CASCADE;")
        cur.execute("DROP SCHEMA IF EXISTS gold CASCADE;")
        cur.execute("DROP SCHEMA IF EXISTS marts CASCADE;")
        
        # Eliminar esquema público (Core de Django)
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
        cur.execute("CREATE SCHEMA public;")
        print("--- 2. Esquemas eliminados y 'public' recreado. ---")
        
        # Recrear esquemas del Data Lake
        cur.execute("CREATE SCHEMA bronze;")
        cur.execute("CREATE SCHEMA silver;")
        cur.execute("CREATE SCHEMA gold;")
        print("--- 3. Esquemas 'bronze', 'silver' y 'gold' recreados. ---")
        
        # Habilitar extensiones
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        print("--- 4. Extensiones PostGIS y pgcrypto habilitadas. ---")

    print("--- 5. Ejecutando migraciones de Django (Usuarios, Sesiones, etc.) ---")
    call_command('migrate', interactive=False)
    
    print("--- 6. Creando tablas maestras del Data Lake ---")
    with connection.cursor() as cur:
        # A. Tabla de Control de Cargas (Bronze)
        cur.execute("""
            CREATE TABLE bronze.control_cargas (
                id_carga BIGSERIAL PRIMARY KEY,
                nombre_archivo_original VARCHAR(255),
                hash_archivo VARCHAR(64) UNIQUE,
                version_archivo VARCHAR(50),
                estatus_procesamiento VARCHAR(50),
                filas_cargadas INT,
                fecha_carga TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # B. Tabla Cruda (Bronze - 77 columnas del CSV del INEGI)
        cur.execute("""
            CREATE TABLE bronze.bronze_mortalidad_raw (
                id_carga BIGINT, fila_origen INT, nombre_archivo_original VARCHAR, hash_archivo VARCHAR,
                vigente BOOLEAN, es_vigente BOOLEAN, fecha_vigencia_desde TIMESTAMPTZ, version_registro VARCHAR,
                anio_nacimiento VARCHAR, mes_nacimiento VARCHAR, mes_nacimientod VARCHAR, dia_nacimiento VARCHAR,
                edad VARCHAR, estado_conyugal VARCHAR, estado_conyugald VARCHAR, entidad_residencia VARCHAR, entidad_residenciad VARCHAR,
                municipio_residencia VARCHAR, municipio_residenciad VARCHAR, localidad_residencia VARCHAR, localidad_residenciad VARCHAR,
                tamanio_localidad VARCHAR, tamanio_localidadd VARCHAR, ocupacion_habitual VARCHAR, ocupacion_habituald VARCHAR,
                escolaridad VARCHAR, escolaridadd VARCHAR, derechohabiencia VARCHAR, derechohabienciad VARCHAR,
                entidad_ocurrencia VARCHAR, entidad_ocurrenciad VARCHAR, municipio_ocurrencia VARCHAR, municipio_ocurrenciad VARCHAR,
                localidad_ocurrencia VARCHAR, localidad_ocurrenciad VARCHAR, sitio_defuncion VARCHAR, sitio_defunciond VARCHAR,
                anio_defuncion VARCHAR, mes_defuncion VARCHAR, mes_defunciond VARCHAR, dia_defuncion VARCHAR,
                hora_defuncion VARCHAR, minutos_defuncion VARCHAR, asistencia_medica VARCHAR, asistencia_medicad VARCHAR,
                causa_cie_4 VARCHAR, causa_cie_4d VARCHAR, certifico VARCHAR, certificod VARCHAR,
                entidad_registro VARCHAR, entidad_registrod VARCHAR, municipio_registro VARCHAR, municipio_registrod VARCHAR,
                anio_registro VARCHAR, mes_registro VARCHAR, mes_registrod VARCHAR, dia_registro VARCHAR,
                anio_certificacion VARCHAR, mes_certificacion VARCHAR, mes_certificaciond VARCHAR, dia_certificacion VARCHAR,
                anio_base_datos VARCHAR, razon_mortalidad_materna VARCHAR, razon_mortalidad_maternad VARCHAR,
                edad_quinquenal VARCHAR, edad_quinquenald VARCHAR
            );
        """)

        # C. Tabla Limpia (Silver)
        cur.execute("""
            CREATE TABLE silver.silver_mortalidad_limpia (
                id_registro BIGSERIAL PRIMARY KEY, id_carga_origen BIGINT, anio_defuncion INT, entidad_residencia INT,
                causa_cie_4 VARCHAR(10), causa_descripcion VARCHAR(255), edad INT, edad_quinquenal VARCHAR(50),
                mes_defuncion INT, municipio_residencia INT, localidad_ocurrencia VARCHAR(10), fila_origen INT,
                incluida_en_rmm BOOLEAN, fecha_procesamiento TIMESTAMPTZ, sitio_defuncion VARCHAR(255), escolaridad VARCHAR(255),
                ocupacion VARCHAR(255), estado_conyugal VARCHAR(255), derechohabiencia VARCHAR(255), razon_mortalidad_texto VARCHAR(255),
                asistencia_medica VARCHAR(255), certifico VARCHAR(255), hora_defuncion VARCHAR(10), minutos_defuncion VARCHAR(10),
                clave_natural VARCHAR(255), hash_fila VARCHAR(64) UNIQUE, vigente BOOLEAN
            );
        """)

        # D. Tablas Consolidadas (Gold)
        cur.execute("""
            CREATE TABLE gold.mortalidad_consolidada (
                id BIGSERIAL PRIMARY KEY, anio INT, entidad_cve VARCHAR(2), entidad_nombre VARCHAR(255),
                municipio_cve VARCHAR(3), municipio_nombre VARCHAR(255), localidad_cve VARCHAR(4), localidad_nombre VARCHAR(255),
                causa_cve VARCHAR(10), causa_desc VARCHAR(255), edad INT, edad_quinquenal VARCHAR(50),
                asistencia_medica VARCHAR(255), sitio_defuncion VARCHAR(255), derechohabiencia VARCHAR(255),
                escolaridad VARCHAR(255), ocupacion VARCHAR(255), incluida_rmm BOOLEAN
            );
        """)
        
        cur.execute("""
            CREATE TABLE gold.dim_localidad (
                cvegeo VARCHAR(9) PRIMARY KEY, cve_ent VARCHAR(2), nom_ent VARCHAR(255), 
                cve_mun VARCHAR(3), nom_mun VARCHAR(255), cve_loc VARCHAR(4), nom_loc VARCHAR(255),
                lat_decimal NUMERIC(12,8), lon_decimal NUMERIC(12,8), geom geometry(Point, 4326)
            );
        """)
        
    print("--- 7. Todas las tablas del Data Lake han sido creadas. ---")
    print("--- ¡BASE DE DATOS LIMPIA Y LISTA PARA RECIBIR ARCHIVOS DESDE LA WEB! ---")

if __name__ == "__main__":
    reset_database()