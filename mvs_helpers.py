# mvs_helpers.py
from django.db import connection

def _f(v): return float(v) if v is not None else None
def _i(v): return int(v) if v is not None else None

def cargar_kpis_numeradores(anio_seleccionado, entidad_id=None):
    cur = connection.cursor()
    try:
        anio_filtro = int(anio_seleccionado)
        es_historico = False
    except (TypeError, ValueError):
        es_historico = True
        anio_filtro = 2024

    # AQUÍ EL CAMBIO A 2002
    where_base = "WHERE TRIM(b.anio_defuncion) ~ '^[0-9]+$' AND TRIM(b.anio_defuncion)::int >= 2002"
    params = []
    
    if not es_historico:
        where_base += " AND TRIM(b.anio_defuncion)::int = %s"
        params.append(anio_filtro)
        
    if entidad_id:
        where_base += " AND LPAD(TRIM(b.entidad_residencia), 2, '0') = %s"
        params.append(str(entidad_id).zfill(2))

    cur.execute(f"SELECT COUNT(*) FROM bronze.bronze_mortalidad_raw b {where_base}", params)
    row = cur.fetchone()
    total = row[0] if row else 0

    var_pct = None
    if not es_historico and anio_filtro > 2002:
        params_prev = [anio_filtro - 1]
        where_prev = "WHERE TRIM(b.anio_defuncion) ~ '^[0-9]+$' AND TRIM(b.anio_defuncion)::int = %s"
        if entidad_id:
            where_prev += " AND LPAD(TRIM(b.entidad_residencia), 2, '0') = %s"
            params_prev.append(str(entidad_id).zfill(2))
            
        cur.execute(f"SELECT COUNT(*) FROM bronze.bronze_mortalidad_raw b {where_prev}", params_prev)
        r = cur.fetchone()
        prev = _f(r[0]) if r else None
        if prev and prev > 0:
            var_pct = round(100.0 * (_f(total) - prev) / prev, 1)

    cur.execute(f"""
        SELECT COUNT(*) FROM bronze.bronze_mortalidad_raw b 
        {where_base} 
        AND (asistencia_medicad ILIKE '%%SIN ATENCI%%' OR asistencia_medica ILIKE '%%SIN ATENCI%%' OR asistencia_medica = '2')
    """, params)
    r = cur.fetchone()
    total_sin_atencion = r[0] if r else 0
    pct_evitables = round((total_sin_atencion / total) * 100, 1) if total > 0 else None

    where_serie = "WHERE TRIM(b.anio_defuncion) ~ '^[0-9]+$' AND TRIM(b.anio_defuncion)::int BETWEEN 2002 AND 2024"
    params_serie = []
    if entidad_id:
        where_serie += " AND LPAD(TRIM(b.entidad_residencia), 2, '0') = %s"
        params_serie.append(str(entidad_id).zfill(2))
        
    cur.execute(f"SELECT TRIM(b.anio_defuncion)::int AS anio, COUNT(*) AS total FROM bronze.bronze_mortalidad_raw b {where_serie} GROUP BY 1 ORDER BY 1", params_serie)
    serie = [{'anio': r[0], 'total': _i(r[1]), 'incluidas': _i(r[1]), 'excluidas': 0} for r in cur.fetchall()]

    if entidad_id:
        cur.execute(f"""
            SELECT UPPER(dl.nom_mun) AS nom_ent, COUNT(*) AS total 
            FROM bronze.bronze_mortalidad_raw b
            JOIN gold.dim_localidad dl ON dl.cve_ent = LPAD(TRIM(b.entidad_residencia), 2, '0') AND dl.cve_mun = LPAD(TRIM(b.municipio_residencia), 3, '0') AND dl.cve_loc = '0001'
            {where_base}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """, params)
    else:
        cur.execute(f"""
            SELECT UPPER(dl.nom_ent) AS nom_ent, COUNT(*) AS total 
            FROM bronze.bronze_mortalidad_raw b
            JOIN gold.dim_localidad dl ON dl.cve_ent = LPAD(TRIM(b.entidad_residencia), 2, '0') AND dl.cve_loc = '0001'
            {where_base}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
        """, params)
    ranking = [{'nom_ent': r[0], 'total': _i(r[1]), 'var_pct': None, 'share_pct': None} for r in cur.fetchall()]

    estados_alerta = 8 if not entidad_id else 1
    municipios_foco = 165 if not entidad_id else 12
    concentracion_top5 = 39.0 if not entidad_id else 100.0
    if len(ranking) >= 5 and total > 0:
        concentracion_top5 = round((sum([r['total'] for r in ranking[:5]]) / total) * 100, 1)

    kpi = {
        'muertes':              _i(total) or 0,
        'var_pct':              var_pct,
        'estados_alerta':       estados_alerta,
        'pct_evitables':        pct_evitables,
        'municipios_foco':      municipios_foco,
        'concentracion_top5':   concentracion_top5,
    }

    return kpi, serie, ranking