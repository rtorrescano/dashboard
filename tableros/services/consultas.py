from django.db import connection

def dictfetchall(cursor):
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]

# --- KPIs ---
def kpi_rmm_ultimo_anio(anio=None, entidad_id=None):
    where_clause = "WHERE 1=1"
    params = []
    if anio:
        where_clause += " AND anio = %s"
        params.append(anio)
    if entidad_id:
        where_clause += " AND id_entidad = %s"
        params.append(entidad_id)

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT MAX(anio) AS anio, SUM(defunciones_incluidas) AS defunciones,
                   SUM(nacimientos_estimados) AS nacimientos,
                   CASE WHEN SUM(nacimientos_estimados) > 0
                        THEN ROUND(SUM(defunciones_incluidas)::numeric / SUM(nacimientos_estimados) * 100000, 2)
                        ELSE NULL END AS rmm
            FROM marts.mv_rmm_anual_entidad {where_clause}
        """, params)
        filas = dictfetchall(cur)
        return filas[0] if filas and filas[0]['defunciones'] is not None else None

# --- Agrupaciones BIRMM ---
def causas_agrupadas(anio=None, entidad_id=None):
    where_clause = "WHERE f.incluida_en_rmm = TRUE"
    params = []
    if anio:
        where_clause += " AND dt.anio = %s"
        params.append(anio)
    if entidad_id:
        where_clause += " AND dg.id_entidad = %s"
        params.append(entidad_id)

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT 
                CASE 
                    WHEN dc.codigo_cie10 ~* '^O0[0-8]' THEN 'Aborto'
                    WHEN dc.codigo_cie10 ~* '^O1[0-6]' THEN 'Hipertensión'
                    WHEN dc.codigo_cie10 ~* '^(O2[0-9]|O3[0-9]|O4[0-8]|O6[0-9]|O7[0-5])' THEN 'Hemorragia'
                    WHEN dc.codigo_cie10 ~* '^(O85|O86|O88|A34)' THEN 'Sepsis'
                    WHEN dc.codigo_cie10 ~* '^(O98|O99|B2[0-4]|U07)' THEN 'Indirectas'
                    ELSE 'Otras' 
                END AS etiqueta, 
                COUNT(*) AS valor
            FROM gold.fact_mortalidad_materna f
            JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
            JOIN gold.dim_geografia dg ON dg.id_geografia = f.id_geografia
            JOIN gold.dim_causa dc ON dc.id_causa = f.id_causa
            {where_clause}
            GROUP BY etiqueta ORDER BY valor DESC
        """, params)
        return dictfetchall(cur)

def distribucion_edad(anio=None, entidad_id=None):
    where_clause = "WHERE f.incluida_en_rmm = TRUE"
    params = []
    if anio:
        where_clause += " AND dt.anio = %s"
        params.append(anio)
    if entidad_id:
        where_clause += " AND dg.id_entidad = %s"
        params.append(entidad_id)

    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT COALESCE(de.edad_quinquenal, 'No especificada') AS etiqueta, COUNT(*) AS valor
            FROM gold.fact_mortalidad_materna f
            JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
            JOIN gold.dim_geografia dg ON dg.id_geografia = f.id_geografia
            JOIN gold.dim_edad de ON de.id_edad = f.id_edad
            {where_clause} GROUP BY de.edad_quinquenal ORDER BY etiqueta
        """, params)
        return dictfetchall(cur)

# --- Gráficas Secundarias (Sitio, Escolaridad, etc.) ---
def _query_categorico(tabla, columna, anio=None, entidad_id=None):
    where_clause = "WHERE 1=1"
    params = []
    if anio:
        where_clause += " AND anio = %s"
        params.append(anio)
    if entidad_id:
        where_clause += " AND id_entidad = %s"
        params.append(entidad_id)

    with connection.cursor() as cur:
        cur.execute(f"SELECT {columna} AS etiqueta, SUM(total) AS valor FROM {tabla} {where_clause} GROUP BY {columna} ORDER BY valor DESC LIMIT 5", params)
        return dictfetchall(cur)

def distribucion_sitio(anio=None, entidad_id=None): return _query_categorico('marts.mv_sitio_defuncion', 'sitio', anio, entidad_id)
def distribucion_escolaridad(anio=None, entidad_id=None): return _query_categorico('marts.mv_escolaridad', 'nivel', anio, entidad_id)
def distribucion_ocupacion(anio=None, entidad_id=None): return _query_categorico('marts.mv_ocupacion', 'ocupacion', anio, entidad_id)
def distribucion_derechohabiencia(anio=None, entidad_id=None): return _query_categorico('marts.mv_derechohabiencia', 'derecho', anio, entidad_id)

# --- Mapa (Soporta Estados o Municipios) ---
def datos_mapa(anio=None, nivel='ESTADO'):
    where_clause = "WHERE f.incluida_en_rmm = TRUE"
    params = []
    if anio:
        where_clause += " AND dt.anio = %s"
        params.append(anio)

    with connection.cursor() as cur:
        if nivel == 'MUNICIPIO':
            # Agrupación por Municipio (requiere que dim_geografia tenga id_municipio)
            cur.execute(f"""
                SELECT dg.id_entidad, dg.id_municipio, dg.municipio_nombre, dg.entidad_nombre, COUNT(*) AS total_defunciones
                FROM gold.fact_mortalidad_materna f
                JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
                JOIN gold.dim_geografia dg ON dg.id_geografia = f.id_geografia
                {where_clause}
                GROUP BY dg.id_entidad, dg.id_municipio, dg.municipio_nombre, dg.entidad_nombre
                ORDER BY total_defunciones DESC
            """, params)
        else:
            # Agrupación por Estado (Default)
            cur.execute(f"""
                SELECT dg.id_entidad, dg.entidad_nombre, COUNT(*) AS total_defunciones
                FROM gold.fact_mortalidad_materna f
                JOIN gold.dim_tiempo dt ON dt.id_tiempo = f.id_tiempo
                JOIN gold.dim_geografia dg ON dg.id_geografia = f.id_geografia
                {where_clause}
                GROUP BY dg.id_entidad, dg.entidad_nombre
                ORDER BY total_defunciones DESC
            """, params)
        return dictfetchall(cur)

def anios_disponibles():
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT anio FROM marts.mv_rmm_anual_entidad WHERE anio >= 2014 ORDER BY anio DESC")
        return [r[0] for r in cur.fetchall()]

def entidades_disponibles():
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT id_entidad, entidad_nombre FROM marts.mv_rmm_anual_entidad ORDER BY entidad_nombre")
        return dictfetchall(cur)