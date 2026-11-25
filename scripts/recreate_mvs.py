# scripts/recreate_mvs.py
from django.db import connection

def recreate_mvs():
    print('Reconstruyendo Vistas Materializadas (Solo 2002 en adelante)...')
    with connection.cursor() as cur:
        cur.execute('DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_evitabilidad CASCADE')
        cur.execute('DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_por_municipio CASCADE')
        cur.execute('DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_por_estado CASCADE')
        cur.execute('DROP MATERIALIZED VIEW IF EXISTS gold.agg_mm_nacional_anual CASCADE')

        # 1. Nacional Anual
        cur.execute("""
            CREATE MATERIALIZED VIEW gold.agg_mm_nacional_anual AS
            SELECT anio, 
                   COUNT(*) AS total_maternas, 
                   COUNT(*) FILTER (WHERE incluida_rmm) AS incluidas_rmm,
                   COUNT(*) FILTER (WHERE NOT incluida_rmm) AS excluidas_rmm
            FROM gold.mortalidad_consolidada
            WHERE anio >= 2002
            GROUP BY anio
        """)
        cur.execute('CREATE UNIQUE INDEX uq_mm_nac_anio ON gold.agg_mm_nacional_anual (anio)')

        # 2. Por Estado
        cur.execute("""
            CREATE MATERIALIZED VIEW gold.agg_mm_por_estado AS
            SELECT entidad_cve AS cve_ent, 
                   MAX(entidad_nombre) AS nom_ent, 
                   anio, 
                   COUNT(*) AS total, 
                   COUNT(*) FILTER (WHERE incluida_rmm) AS incluidas,
                   COUNT(*) FILTER (WHERE NOT incluida_rmm) AS excluidas
            FROM gold.mortalidad_consolidada
            WHERE anio >= 2002
            GROUP BY entidad_cve, anio
        """)
        cur.execute('CREATE UNIQUE INDEX uq_mm_estado_anio ON gold.agg_mm_por_estado (cve_ent, anio)')

        # 3. Por Municipio
        cur.execute("""
            CREATE MATERIALIZED VIEW gold.agg_mm_por_municipio AS
            SELECT entidad_cve AS cve_ent, 
                   MAX(entidad_nombre) AS nom_ent, 
                   municipio_cve AS cve_mun, 
                   MAX(municipio_nombre) AS nom_mun, 
                   anio, 
                   COUNT(*) AS total, 
                   COUNT(*) FILTER (WHERE incluida_rmm) AS incluidas
            FROM gold.mortalidad_consolidada
            WHERE anio >= 2002
            GROUP BY entidad_cve, municipio_cve, anio
        """)
        cur.execute('CREATE UNIQUE INDEX uq_mm_mun_anio ON gold.agg_mm_por_municipio (cve_ent, cve_mun, anio)')

        # 4. Evitabilidad
        cur.execute("""
            CREATE MATERIALIZED VIEW gold.agg_mm_evitabilidad AS
            SELECT anio, entidad_cve AS cve_ent,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE asistencia_medica ILIKE '%SIN ATENCI%' OR asistencia_medica = '2') AS sin_atencion
            FROM gold.mortalidad_consolidada
            WHERE anio >= 2002
            GROUP BY anio, entidad_cve
        """)
        cur.execute('CREATE UNIQUE INDEX uq_evit_estado_anio ON gold.agg_mm_evitabilidad (cve_ent, anio)')

        print('¡Vistas Materializadas creadas exitosamente!')

recreate_mvs()