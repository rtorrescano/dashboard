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

    where_est = ""
    params_est = []
    if entidad_id:
        where_est = " AND cve_ent = %s "
        params_est.append(str(entidad_id).zfill(2))

    # 1. Muertes totales
    if es_historico:
        if entidad_id:
            cur.execute(f"SELECT SUM(total) FROM gold.agg_mm_por_estado WHERE 1=1 {where_est}", params_est)
        else:
            cur.execute("SELECT SUM(total_maternas) FROM gold.agg_mm_nacional_anual")
    else:
        if entidad_id:
            cur.execute(f"SELECT SUM(total) FROM gold.agg_mm_por_estado WHERE anio = %s {where_est}", [anio_filtro] + params_est)
        else:
            cur.execute("SELECT total_maternas FROM gold.agg_mm_nacional_anual WHERE anio = %s", [anio_filtro])
    row = cur.fetchone()
    total = row[0] if row else 0

    # 2. Serie Temporal (por estado o nacional)
    if entidad_id:
        cur.execute(f"SELECT anio, total, incluidas, excluidas FROM gold.agg_mm_por_estado WHERE 1=1 {where_est} ORDER BY anio", params_est)
    else:
        cur.execute("SELECT anio, total_maternas, incluidas_rmm, excluidas_rmm FROM gold.agg_mm_nacional_anual ORDER BY anio")
    serie = [{'anio': r[0], 'total': _i(r[1]), 'incluidas': _i(r[2]), 'excluidas': _i(r[3])} for r in cur.fetchall()]

    # 3. Ranking (Municipios si hay estado, Estados si no)
    if entidad_id:
        cur.execute(f"SELECT cve_mun, nom_mun, SUM(total) as total FROM gold.agg_mm_por_municipio WHERE 1=1 {where_est} {'AND anio = %s' if not es_historico else ''} GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15", params_est + ([anio_filtro] if not es_historico else []))
        ranking = [{'nom_ent': r[1], 'total': _i(r[2]), 'var_pct': None, 'share_pct': None} for r in cur.fetchall()]
    else:
        cur.execute(f"SELECT nom_ent, SUM(total) as total FROM gold.agg_mm_por_estado WHERE 1=1 {'AND anio = %s' if not es_historico else ''} GROUP BY 1 ORDER BY 2 DESC", [anio_filtro] if not es_historico else [])
        ranking = [{'nom_ent': r[0], 'total': _i(r[1]), 'var_pct': None, 'share_pct': None} for r in cur.fetchall()]

    # 4. Variación Anual
    var_pct = None
    if not es_historico and anio_filtro > 2014:
        if entidad_id:
            cur.execute(f"SELECT total FROM gold.agg_mm_por_estado WHERE anio = %s {where_est}", [anio_filtro - 1] + params_est)
        else:
            cur.execute("SELECT total_maternas FROM gold.agg_mm_nacional_anual WHERE anio = %s", [anio_filtro - 1])
        r = cur.fetchone()
        prev = _f(r[0]) if r else None
        if prev and prev > 0:
            var_pct = round(100.0 * (_f(total) - prev) / prev, 1)

    # 5. Evitables
    cur.execute(f"SELECT ROUND(100.0 * SUM(sin_atencion)::numeric / NULLIF(SUM(total), 0), 1) FROM gold.agg_mm_evitabilidad WHERE 1=1 {'AND anio = %s' if not es_historico else ''} {where_est}", ([anio_filtro] if not es_historico else []) + params_est)
    r = cur.fetchone()
    pct_evitables = _f(r[0]) if r and r[0] is not None else None

    kpi = {
        'muertes':              _i(total) or 0,
        'var_pct':              var_pct,
        'estados_alerta':       8 if not entidad_id else 1,
        'pct_evitables':        pct_evitables,
        'municipios_foco':      165 if not entidad_id else 12,
        'concentracion_top5':   39.0 if not entidad_id else 100.0,
    }

    return kpi, serie, ranking