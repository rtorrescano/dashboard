# audit_data_lineage.py
from django.db import connection

def auditar_flujo_datos():
    print("=========================================================")
    print("   AUDITORÍA DE CALIDAD DE DATOS Y FLUJO ETL (BIRMM)")
    print("=========================================================\n")
    
    with connection.cursor() as cur:
        # 1. Capa Bronze (Datos Crudos)
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_mortalidad_raw")
        total_bronze = cur.fetchone()[0]
        print(f"1. CAPA BRONZE (Datos Crudos): {total_bronze:,} registros")
        
        # 2. Capa Silver (Datos Limpios y Filtrados)
        cur.execute("SELECT COUNT(*) FROM silver.silver_mortalidad_limpia")
        total_silver = cur.fetchone()[0]
        print(f"2. CAPA SILVER (Limpios y >= 2014): {total_silver:,} registros")
        
        # 3. Cálculo de Descartes
        descartados = total_bronze - total_silver
        porcentaje_descarte = (descartados / total_bronze) * 100 if total_bronze > 0 else 0
        print(f"   -> Registros descartados (Años < 2014 o errores de captura): {descartados:,} ({porcentaje_descarte:.2f}%)")
        
        # 4. Capa Gold (Datos Consolidados y Enriquecidos)
        cur.execute("SELECT COUNT(*) FROM gold.mortalidad_consolidada")
        total_gold = cur.fetchone()[0]
        print(f"3. CAPA GOLD (Consolidado para Tableros): {total_gold:,} registros")
        
        perdida_geografica = total_silver - total_gold
        print(f"   -> Registros no cruzados con mapa (Pérdida geográfica): {perdida_geografica:,}")
        
        # 5. Catálogos Integrados
        print("\n---------------------------------------------------------")
        print("   CATÁLOGOS GEOGRÁFICOS INTEGRADOS")
        print("---------------------------------------------------------")
        cur.execute("SELECT COUNT(*) FROM gold.dim_localidad")
        total_geo = cur.fetchone()[0]
        print(f"   - Catálogo Geográfico (AGEEML): {total_geo:,} localidades cargadas.")
        
        # 6. Vistas Materializadas (El caché que ven los directivos)
        print("\n---------------------------------------------------------")
        print("   DATOS EXPLOTABLES EN VISTAS MATERIALIZADAS (FRONTEND)")
        print("---------------------------------------------------------")
        cur.execute("SELECT SUM(total) FROM gold.agg_mm_por_estado")
        total_mvs = cur.fetchone()[0]
        print(f"   - Suma total en Vistas Materializadas: {total_mvs:,} casos explotables.")
        
    print("\n=========================================================")

if __name__ == "__main__":
    auditar_flujo_datos()