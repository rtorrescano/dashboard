# =====================================================================
# SCRIPT DE LIMPIEZA DE DATOS - SISTEMA DE MORTALIDAD MATERNA
# =====================================================================

$ErrorActionPreference = "Stop"

$DbHost = "localhost"
$DbUser = "postgres"
$DbName = "tableros"

Write-Host "Iniciando limpieza de datos en la base de datos '$DbName'..." -ForegroundColor Cyan

# 1. Definir el script SQL de limpieza
$SqlLimpieza = @"
-- 1. Limpiar Capa Gold (Hechos y Dimensiones)
TRUNCATE TABLE gold.fact_mortalidad_materna CASCADE;
TRUNCATE TABLE gold.dim_tiempo CASCADE;
TRUNCATE TABLE gold.dim_geografia CASCADE;
TRUNCATE TABLE gold.dim_causa CASCADE;
TRUNCATE TABLE gold.dim_edad CASCADE;

-- 2. Limpiar Capa Silver
TRUNCATE TABLE silver.silver_mortalidad_limpia CASCADE;

-- 3. Limpiar Capa Bronze
TRUNCATE TABLE bronze.bronze_mortalidad_raw CASCADE;
TRUNCATE TABLE bronze.control_cargas CASCADE;

-- 4. Refrescar TODAS las Vistas Materializadas para que queden vacías
REFRESH MATERIALIZED VIEW marts.mv_rmm_anual_entidad;
REFRESH MATERIALIZED VIEW marts.mv_causas_agrupadas;
REFRESH MATERIALIZED VIEW marts.mv_distribucion_edad;
REFRESH MATERIALIZED VIEW marts.mv_series_tiempo;
REFRESH MATERIALIZED VIEW marts.mv_subclasificacion;
REFRESH MATERIALIZED VIEW marts.mv_sitio_defuncion;
REFRESH MATERIALIZED VIEW marts.mv_escolaridad;
REFRESH MATERIALIZED VIEW marts.mv_ocupacion;
REFRESH MATERIALIZED VIEW marts.mv_derechohabiencia;
REFRESH MATERIALIZED VIEW marts.mv_estado_conyugal;

-- Nota: NO tocamos gold.nacimientos_estimados para conservar los denominadores
-- Si también quieres borrar los nacimientos, descomenta la siguiente línea:
-- TRUNCATE TABLE gold.nacimientos_estimados CASCADE;
"@

# 2. Guardar el SQL en un archivo temporal
$TempSqlFile = [System.IO.Path]::GetTempFileName() + ".sql"
$SqlLimpieza | Out-File -FilePath $TempSqlFile -Encoding utf8

# 3. Ejecutar el script con psql
try {
    $env:PGPASSWORD = "admin"
    
    # Ejecutar psql apuntando al archivo temporal
    & psql -U $DbUser -h $DbHost -d $DbName -f $TempSqlFile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Base de datos limpiada correctamente. Todos los datos han sido eliminados." -ForegroundColor Green
    } else {
        Write-Host "Hubo un error al ejecutar la limpieza. Revisa los mensajes de psql arriba." -ForegroundColor Red
    }
}
catch {
    Write-Host "Error crítico: $_" -ForegroundColor Red
}
finally {
    # 4. Limpieza de archivos temporales y variables
    Remove-Item $TempSqlFile -ErrorAction SilentlyContinue
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}