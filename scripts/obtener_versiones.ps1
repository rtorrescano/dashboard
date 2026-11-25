Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "   INVENTARIO DE COMPONENTES TECNOLÓGICOS" -ForegroundColor Cyan
Write-Host "===============================================`n" -ForegroundColor Cyan

Write-Host "[1] SISTEMA OPERATIVO" -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "    - Nombre: $($os.Caption)"
Write-Host "    - Versión: $($os.Version)"
Write-Host "    - Arquitectura: $($os.OSArchitecture)`n"

Write-Host "[2] PYTHON Y DJANGO" -ForegroundColor Yellow
try { $pythonVersion = python --version 2>&1; Write-Host "    - $pythonVersion" } catch { Write-Host "    - ERROR: Python no encontrado." -ForegroundColor Red }
try { $djangoVersion = python -m django --version 2>&1; Write-Host "    - Django versión: $djangoVersion" } catch { Write-Host "    - ERROR: Django no instalado." -ForegroundColor Red }

Write-Host "`n[3] BASE DE DATOS (POSTGRESQL Y POSTGIS)" -ForegroundColor Yellow
$dbCheckScript = @'
from django.db import connection
try:
    cur = connection.cursor()
    cur.execute('SELECT version()')
    pg_full = cur.fetchone()[0]
    pg_version = " ".join(pg_full.split(' ')[:2])
    cur.execute('SELECT PostGIS_Version()')
    postgis_version = cur.fetchone()[0].split(' ')[0]
    print(f"    - PostgreSQL: {pg_version}")
    print(f"    - PostGIS: {postgis_version}")
except Exception as e:
    print(f"    - ERROR consultando BD: {e}")
'@
$tempFile = "temp_db_check.py"
$dbCheckScript | Out-File -FilePath $tempFile -Encoding ascii
try { python manage.py shell < $tempFile } catch { Write-Host "    - ERROR ejecutando el script de BD." -ForegroundColor Red }
Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Host "`n[4] LIBRERÍAS FRONTEND (CDNs)" -ForegroundColor Yellow
$htmlPath = "tableros\templates\tableros\base.html"
if (Test-Path $htmlPath) {
    $leaflet = (Select-String -Path $htmlPath -Pattern 'leaflet@([0-9\.]+)').Matches.Groups[1].Value | Select-Object -First 1
    if ($leaflet) { Write-Host "    - Leaflet (Mapas): v$leaflet" }
    
    $chart = (Select-String -Path $htmlPath -Pattern 'chart\.js@([0-9\.]+)').Matches.Groups[1].Value | Select-Object -First 1
    if ($chart) { Write-Host "    - Chart.js (Gráficas): v$chart" }
    
    $bootstrap = (Select-String -Path $htmlPath -Pattern 'bootstrap@([0-9\.]+)').Matches.Groups[1].Value | Select-Object -First 1
    if ($bootstrap) { Write-Host "    - Bootstrap: v$bootstrap" }
    
    $gobmx = (Select-String -Path $htmlPath -Pattern 'framework-gb\.cdn\.gob\.mx/gm/(v[0-9]+)').Matches.Groups[1].Value | Select-Object -First 1
    if ($gobmx) { Write-Host "    - Framework GOB.mx: $gobmx" }
} else { Write-Host "    - No se encontró base.html." }

Write-Host "`n[5] DEPENDENCIAS DE PYTHON (PIP)" -ForegroundColor Yellow
try {
    pip freeze > requirements.txt
    $totalPkgs = (Get-Content requirements.txt).Count
    Write-Host "    - ¡Éxito! Se registraron $totalPkgs librerías en requirements.txt" -ForegroundColor Green
} catch { Write-Host "    - ERROR generando requirements.txt" -ForegroundColor Red }

Write-Host "`n===============================================" -ForegroundColor Cyan
Write-Host "   FIN DEL REPORTE" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan