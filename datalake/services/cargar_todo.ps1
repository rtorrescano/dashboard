# ============================================================
# cargar_todo.ps1
# Flujo: xlsx/csv -> csv -> staging -> bronze -> silver -> marts
# Requiere: python, psql en PATH, pgpass.conf configurado.
# ============================================================

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipMarts,
    [switch]$SkipSilver
)

$ErrorActionPreference = "Stop"

# --- Configuración ---
$PGHOST  = "localhost"
$PGPORT  = "5432"
$PGUSER  = "postgres"
$PGDB    = "tableros"
$SCRIPTS = "C:\Users\raul.torrescano\Personal\Dashboards\desarrollo\aplicativo_tlaberos\datalake\services"

$PY_SCRIPT     = Join-Path $SCRIPTS "cargar_excel.py"
$SILVER_SCRIPT = Join-Path $SCRIPTS "09_silver_merge.sql"
$MARTS_SCRIPT  = Join-Path $SCRIPTS "10_refresh_marts.sql"

# --- Encoding ---
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding           = [System.Text.Encoding]::UTF8
$env:PGCLIENTENCODING     = "UTF8"

# --- Helpers ---
function Write-Step { param([string]$Msg) Write-Host ""; Write-Host "== $Msg ==" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Msg) Write-Host "   OK: $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "   WARN: $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "   ERR: $Msg" -ForegroundColor Red }

function Invoke-Psql {
    param([string]$Arguments, [string]$Descripcion = "psql")
    if ($DryRun) { Write-Host "   [DryRun] psql $Arguments"; return }
    $cmd = "psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDB -v ON_ERROR_STOP=1 $Arguments"
    Write-Host "   > $cmd"
    Invoke-Expression $cmd
    if ($LASTEXITCODE -ne 0) { throw "$Descripcion falló (exit $LASTEXITCODE)" }
}

function Invoke-PsqlQuery {
    param([string]$Sql)
    if ($DryRun) { return "" }
    $cmd = "psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDB -t -A -v ON_ERROR_STOP=1 -c `"$Sql`""
    return Invoke-Expression $cmd
}

# --- 0) Validaciones ---
Write-Step "0) Validaciones previas"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python no está en PATH" }
Write-Ok "python encontrado"
if (-not (Get-Command psql -ErrorAction SilentlyContinue)) { throw "psql no está en PATH" }
Write-Ok "psql encontrado"
if (-not (Test-Path $PY_SCRIPT)) { throw "No existe $PY_SCRIPT" }
Write-Ok "cargar_excel.py encontrado"
if (-not $SkipSilver -and -not (Test-Path $SILVER_SCRIPT)) { throw "No existe $SILVER_SCRIPT (o usa -SkipSilver)" }
if (-not $SkipMarts  -and -not (Test-Path $MARTS_SCRIPT))  { throw "No existe $MARTS_SCRIPT (o usa -SkipMarts)" }

$ping = Invoke-PsqlQuery "SELECT 1;"
if (-not $DryRun -and $ping.Trim() -ne "1") { throw "No se pudo conectar a PostgreSQL ($PGHOST`:$PGPORT/$PGDB)" }
Write-Ok "conexión a PostgreSQL verificada"

$fn = Invoke-PsqlQuery "SELECT pg_get_function_arguments(oid) FROM pg_proc WHERE proname='cargar_mortalidad_consolidado';"
if (-not $DryRun) {
    if ($fn -notmatch "p_hash") { throw "La función bronze.cargar_mortalidad_consolidado no tiene la firma (text, char(64), text)." }
    Write-Ok "función cargar_mortalidad_consolidado OK"
}

# --- 1) xlsx/csv -> csv ---
Write-Step "1) Excel/CSV -> CSV"
$out = & python $PY_SCRIPT
if ($LASTEXITCODE -ne 0) { throw "cargar_excel.py falló (exit $LASTEXITCODE)" }
$out | ForEach-Object { Write-Host "   $_" }

$sha   = ($out | Select-String '^SHA256='   | Select-Object -First 1).Line -replace '^SHA256=',''
$csv   = ($out | Select-String '^CSV='      | Select-Object -First 1).Line -replace '^CSV=',''
$xlsx  = ($out | Select-String '^XLSX='     | Select-Object -First 1).Line -replace '^XLSX=',''
$filas = ($out | Select-String '^FILAS='    | Select-Object -First 1).Line -replace '^FILAS=',''
$cols  = ($out | Select-String '^COLUMNAS=' | Select-Object -First 1).Line -replace '^COLUMNAS=',''
$columnasCsv = ($out | Select-String '^COLNAMES=' | Select-Object -First 1).Line -replace '^COLNAMES=',''

if (-not $sha -or -not $csv) { throw "No se pudo obtener SHA256 o CSV de la salida de Python." }
if ([string]::IsNullOrWhiteSpace($columnasCsv)) { throw "No se pudo obtener COLNAMES de la salida de Python." }
Write-Ok "CSV: $cols columnas (staging_mortalidad se carga con las del CSV)"

$csvF  = $csv  -replace '\\','/'
$xlsxF = if ($xlsx) { $xlsx -replace '\\','/' } else { $csvF }

Write-Ok "SHA256 = $sha"
Write-Ok "CSV    = $csvF ($filas filas, $cols columnas)"
Write-Ok "XLSX   = $xlsxF"

# --- 2) staging ---
Write-Step "2) Cargar staging con \copy"
Invoke-Psql -Arguments "-c `"TRUNCATE public.staging_mortalidad;`"" -Descripcion "TRUNCATE staging"

# 2a) \copy solo de las columnas del CSV
$stgSql  = Join-Path $env:TEMP "stg_mortalidad.sql"
$copyCmd = "\copy public.staging_mortalidad ($columnasCsv) FROM '$csvF' WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8')"
Set-Content -Path $stgSql -Encoding UTF8 -Value $copyCmd
Invoke-Psql -Arguments "-f `"$stgSql`"" -Descripcion "\copy staging"

# 2b) rellenar 'ocupacion' desde 'ocupacion_habitual' (para que bronze tenga valor)
$auditSql = @"
UPDATE public.staging_mortalidad
   SET ocupacion = COALESCE(NULLIF(TRIM(ocupacion_habitual),''),'NO ESPECIFICADO');
"@
$auditFile = Join-Path $env:TEMP "stg_mortalidad_audit.sql"
Set-Content -Path $auditFile -Encoding UTF8 -Value $auditSql
Invoke-Psql -Arguments "-f `"$auditFile`"" -Descripcion "UPDATE ocupacion en staging"

$stgCount = Invoke-PsqlQuery "SELECT count(*) FROM public.staging_mortalidad;"
if (-not $DryRun) {
    if ([int]$stgCount -ne [int]$filas) { throw "Staging tiene $stgCount filas; el CSV tenía $filas." }
    Write-Ok "staging: $stgCount filas cargadas"
}

# --- 3) Bronze ---
Write-Step "3) Normalizar Bronze"
$sqlFunc = "SELECT bronze.cargar_mortalidad_consolidado('$xlsxF', '$sha', 'v1');"
$idCarga = Invoke-PsqlQuery $sqlFunc
if (-not $DryRun) {
    if ([string]::IsNullOrWhiteSpace($idCarga)) { Write-Warn "La función devolvió NULL: el archivo ya estaba cargado (mismo hash)." }
    else { Write-Ok "id_carga = $($idCarga.Trim())" }
}

# --- 4) Silver ---
if ($SkipSilver) {
    Write-Step "4) Silver (OMITIDO por -SkipSilver)"
} else {
    Write-Step "4) Sincronizar Silver"
    Invoke-Psql -Arguments "-f `"$SILVER_SCRIPT`"" -Descripcion "09_silver_merge.sql"
    Write-Ok "Silver sincronizado"
}

# --- 5) Marts ---
if ($SkipMarts) {
    Write-Step "5) Marts (OMITIDO por -SkipMarts)"
} else {
    Write-Step "5) Refrescar Marts"
    Invoke-Psql -Arguments "-f `"$MARTS_SCRIPT`"" -Descripcion "10_refresh_marts.sql"
    Write-Ok "Marts refrescados"
}

# --- 6) Verificaciones ---
if (-not $DryRun) {
    Write-Step "6) Verificaciones"

    $ctrl = Invoke-PsqlQuery "SELECT id_carga || '|' || filas_cargadas || '|' || filas_nuevas || '|' || filas_modificadas || '|' || filas_baja || '|' || filas_sin_cambio || '|' || estatus_procesamiento FROM bronze.control_cargas ORDER BY id_carga DESC LIMIT 1;"
    $parts = $ctrl.Trim() -split '\|'
    Write-Host "   control_cargas: id=$($parts[0]) cargadas=$($parts[1]) nuevas=$($parts[2]) modificadas=$($parts[3]) bajas=$($parts[4]) sin_cambio=$($parts[5]) estatus=$($parts[6])"
    if ($parts[6] -ne "CARGADO") { throw "control_cargas.estatus = $($parts[6]); se esperaba CARGADO" }
    Write-Ok "control_cargas OK"

    $cuadre = Invoke-PsqlQuery "SELECT (SELECT count(*) FROM bronze.bronze_mortalidad_raw WHERE vigente) || '|' || (SELECT count(*) FROM silver.silver_mortalidad_limpia WHERE vigente);"
    $b, $s = $cuadre.Trim() -split '\|'
    Write-Host "   bronze_vig = $b silver_vig = $s"
    if (-not $SkipSilver) {
        if ([int]$b -ne [int]$s) { throw "Bronze vigentes ($b) != Silver vigentes ($s). Revisa el MERGE." }
        Write-Ok "Bronze y Silver cuadran"
    }

    if (-not [string]::IsNullOrWhiteSpace($idCarga)) {
        Write-Host "   Diff por año de la carga $($idCarga.Trim()):"
        $diff = Invoke-PsqlQuery "SELECT anio || ' | ' || tipo_cambio || ' | ' || filas FROM bronze.vw_diff_por_anio WHERE id_carga = $($idCarga.Trim()) ORDER BY anio, tipo_cambio;"
        if ([string]::IsNullOrWhiteSpace($diff)) { Write-Host "     (sin altas/modificaciones/bajas registradas)" }
        else { $diff -split "`n" | ForEach-Object { Write-Host "     $_" } }
    }

    $causasNoCat = Invoke-PsqlQuery "SELECT count(*) FROM bronze.vw_causas_no_catalogadas;"
    Write-Host "   causas no catalogadas: $($causasNoCat.Trim())"
    if ([int]$causasNoCat -gt 0) { Write-Warn "Hay $causasNoCat causas CIE-10 fuera de gold.dim_causa." }
    else { Write-Ok "todas las causas están catalogadas" }

    if (-not $SkipMarts) {
        $mvCount = Invoke-PsqlQuery "SELECT count(*) FROM marts.mv_rmm_anual_entidad;"
        Write-Host "   mv_rmm_anual_entidad: $($mvCount.Trim()) filas"
        if ([int]$mvCount -le 0) { throw "mv_rmm_anual_entidad está vacía tras el refresh." }
        Write-Ok "Marts con datos"
    }
}

# --- 7) Resumen ---
Write-Step "7) Resumen"
$silverEstado = if ($SkipSilver) { "OMITIDO" } else { "OK" }
$martsEstado  = if ($SkipMarts)  { "OMITIDO" } else { "OK" }
$idCargaTxt   = if ([string]::IsNullOrWhiteSpace($idCarga)) { "NULL (ya cargado)" } else { $idCarga.Trim() }

Write-Host "   SHA256        : $sha"
Write-Host "   CSV           : $csvF ($filas filas)"
Write-Host "   id_carga      : $idCargaTxt"
Write-Host "   Silver        : $silverEstado"
Write-Host "   Marts         : $martsEstado"
Write-Host ""
Write-Host "== FIN ==" -ForegroundColor Green