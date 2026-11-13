# cleanup_db.py
from django.db import connection

def ejecutar_limpieza():
    db_name = connection.settings_dict['NAME']
    print(f"=== INICIANDO DEPURACION DE LA BD: {db_name} ===")
    
    # Lista de comandos SQL en orden estricto
    sql_commands = [
        # 1. Eliminar esquemas obsoletos
        "DROP SCHEMA IF EXISTS marts CASCADE;",
        
        # 2. Eliminar tablas de staging (basura de pruebas en public)
        "DROP TABLE IF EXISTS public.staging_estados CASCADE;",
        "DROP TABLE IF EXISTS public.staging_geo CASCADE;",
        "DROP TABLE IF EXISTS public.staging_localidades CASCADE;",
        "DROP TABLE IF EXISTS public.staging_mortalidad CASCADE;",
        "DROP TABLE IF EXISTS public.staging_municipios CASCADE;",
        "DROP TABLE IF EXISTS public._migracion_conteos_pre CASCADE;",
        "DROP TABLE IF EXISTS public._migracion_conteos_post CASCADE;",
        
        # 3. Eliminar tablas duplicadas de Django que se crearon por error en bronze
        "DROP TABLE IF EXISTS bronze.auth_group CASCADE;",
        "DROP TABLE IF EXISTS bronze.auth_group_permissions CASCADE;",
        "DROP TABLE IF EXISTS bronze.auth_permission CASCADE;",
        "DROP TABLE IF EXISTS bronze.django_admin_log CASCADE;",
        "DROP TABLE IF EXISTS bronze.django_content_type CASCADE;",
        "DROP TABLE IF EXISTS bronze.django_migrations CASCADE;",
        "DROP TABLE IF EXISTS bronze.django_session CASCADE;",
        "DROP TABLE IF EXISTS bronze.usuarios_usuario CASCADE;",
        "DROP TABLE IF EXISTS bronze.usuarios_usuario_groups CASCADE;",
        "DROP TABLE IF EXISTS bronze.usuarios_usuario_user_permissions CASCADE;",
        "DROP TABLE IF EXISTS bronze.tableros_configuraciontablero CASCADE;",
        
        # 4. Eliminar vistas viejas en bronze
        "DROP VIEW IF EXISTS bronze.vw_causas_no_catalogadas CASCADE;",
        "DROP VIEW IF EXISTS bronze.vw_diff_por_anio CASCADE;",
        
        # 5. Eliminar Vistas Materializadas redundantes en gold
        "DROP MATERIALIZED VIEW IF EXISTS gold.agg_municipio CASCADE;",
        "DROP MATERIALIZED VIEW IF EXISTS gold.agg_mortalidad_por_municipio CASCADE;",
        
        # 6. Eliminar tablas viejas en public
        "DROP TABLE IF EXISTS public.bronze_mortalidad_auditoria CASCADE;",
        "DROP TABLE IF EXISTS public.catalogo_geografico CASCADE;",
    ]
    
    try:
        with connection.cursor() as cur:
            for sql in sql_commands:
                print(f"Ejecutando: {sql}")
                cur.execute(sql)
        
        # 7. Corregir el search_path a nivel de base de datos
        print("Corrigiendo search_path...")
        with connection.cursor() as cur:
            cur.execute(f"ALTER DATABASE {db_name} SET search_path TO public, bronze, silver, gold;")
            
        # 8. VACUUM FULL y ANALYZE (Requiere autocommit, no puede ir en transaccion)
        print("Reclamando espacio en disco (VACUUM FULL)... Esto puede tardar.")
        connection.set_autocommit(True) # Obligatorio para VACUUM
        with connection.cursor() as cur:
            cur.execute("VACUUM FULL;")
            cur.execute("ANALYZE;")
            
        print("=== LIMPIEZA Y MANTENIMIENTO COMPLETADOS CON EXITO ===")
        
    except Exception as e:
        print(f"ERROR CRITICO DURANTE LA LIMPIEZA: {e}")
        print("La transaccion ha sido revertida (Rollback).")

# Llamada directa para que se ejecute al leer el archivo
ejecutar_limpieza()