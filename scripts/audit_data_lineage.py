$script = @'
from django.db import connection

def auditar_flujo_datos():
    print("=========================================================")
    print("   AUDITORIA DE CALIDAD DE DATOS Y FLUJO ETL (BIRMM)")
    print("=========================================================")
    
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_mortalidad_raw")
        total_bronze = cur.fetchone()[0]
        print(f"1. CAPA BRONZE (Datos Crudos): {total_bronze:,} registros")
        
        cur.execute("SELECT COUNT(*) FROM silver.silver_mortalidad_limpia")
        total_silver = cur.fetchone()[0]
        print(f"2. CAPA SILVER (Limpios y >= 2014): {total_silver:,} registros")
        
        descartados = total_bronze - total_silver
        porcentaje_descarte = (descartados / total_bronze) * 100 if total_bronze > 0 else 0
        print(f"   -> Registros descartados (Anios < 2014 o errores): {descartados:,} ({porcentaje_descarte:.2f}%)")
        
        cur.execute("SELECT COUNT(*) FROM gold.mortalidad_consolidada")
        total_gold = cur.fetchone()[0]
        print(f"3. CAPA GOLD (Consolidado para Tableros): {total_gold:,} registros")
        
        perdida_geografica = total_silver - total_gold
        print(f"   -> Registros no cruzados con mapa: {perdida_geografica:,}")
        
        print("---------------------------------------------------------")
        print("   CATALOGOS GEOGRAFICOS INTEGRADOS")
        print("---------------------------------------------------------")
        cur.execute("SELECT COUNT(*) FROM gold.dim_localidad")
        total_geo = cur.fetchone()[0]
        print(f"   - Catalogo Geografico (AGEEML): {total_geo:,} localidades cargadas.")
        
        print("---------------------------------------------------------")
        print("   DATOS EXPLOTABLES EN VISTAS MATERIALIZADAS")
        print("---------------------------------------------------------")
        cur.execute("SELECT SUM(total) FROM gold.agg_mm_por_estado")
        total_mvs = cur.fetchone()[0]
        print(f"   - Suma total en Vistas Materializadas: {total_mvs:,} casos explotables.")
        
    print("=========================================================")
    print("   FIN DE LA AUDITORIA")
    print("=========================================================")

if __name__ == "__main__":
    auditar_flujo_datos()
'@

Set-Content -Path "audit_data_lineage.py" -Value $script -Encoding ascii
Write-Host "Archivo audit_data_lineage.py creado limpio (ASCII)." -ForegroundColor Green