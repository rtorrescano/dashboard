from django.db import connection

def _fetchall_dict(cur):
    columns = [col[0] for col in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]

def _build_where(anio, entidad_id):
    where = ["anio >= 2014"]
    params = []
    if anio:
        where.append("anio = %s")
        params.append(anio)
    if entidad_id:
        where.append("entidad_cve = %s")
        params.append(str(entidad_id).zfill(2))
    return " WHERE " + " AND ".join(where), params

def datos_publicos_historicos():
    cur = connection.cursor()
    where_base = "WHERE anio BETWEEN 2014 AND 2024"
    cur.execute(f"SELECT COUNT(*) FROM gold.mortalidad_consolidada {where_base}")
    total_muertes = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM gold.mortalidad_consolidada {where_base} AND asistencia_medica ILIKE '%%SIN ATENCI%%'")
    total_sin_atencion = cur.fetchone()[0]
    cur.execute(f"SELECT anio, COUNT(*) AS total FROM gold.mortalidad_consolidada {where_base} GROUP BY 1 ORDER BY 1")
    serie_anual = _fetchall_dict(cur)
    cur.execute(f"SELECT COALESCE(edad_quinquenal, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where_base} GROUP BY 1 ORDER BY 1")
    por_edad = _fetchall_dict(cur)
    cur.execute(f"SELECT COALESCE(sitio_defuncion, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where_base} GROUP BY 1 ORDER BY 2 DESC LIMIT 4")
    por_sitio = _fetchall_dict(cur)
    cur.execute(f"SELECT entidad_cve AS id, COUNT(*) AS total FROM gold.mortalidad_consolidada {where_base} GROUP BY 1")
    por_estado = _fetchall_dict(cur)
    cur.execute(f"SELECT entidad_nombre AS nombre, COUNT(*) AS total FROM gold.mortalidad_consolidada {where_base} GROUP BY 1 ORDER BY 2 DESC LIMIT 1")
    row = cur.fetchone()
    top_estado = {'nombre': row[0] if row else 'N/A', 'total': row[1] if row else 0}
    return {'total_muertes': total_muertes, 'total_sin_atencion': total_sin_atencion, 'serie_anual': serie_anual, 'por_edad': por_edad, 'por_sitio': por_sitio, 'por_estado': por_estado, 'top_estado': top_estado}

def anios_disponibles():
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT anio FROM gold.mortalidad_consolidada WHERE anio >= 2014 ORDER BY 1 DESC")
        return [r[0] for r in cur.fetchall()]

def entidades_disponibles():
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT entidad_cve AS id_entidad, UPPER(entidad_nombre) AS entidad_nombre FROM gold.mortalidad_consolidada WHERE entidad_nombre IS NOT NULL ORDER BY 2")
        return _fetchall_dict(cur)

def kpi_rmm_ultimo_anio(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM gold.mortalidad_consolidada {where}", params)
        return {'defunciones': cur.fetchone()[0], 'rmm': 'N/A'}

def causas_agrupadas(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(causa_desc, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 8", params)
        return _fetchall_dict(cur)

def distribucion_edad(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(edad_quinquenal, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 1", params)
        return _fetchall_dict(cur)

def distribucion_sitio(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(sitio_defuncion, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        return _fetchall_dict(cur)

def distribucion_escolaridad(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(escolaridad, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        return _fetchall_dict(cur)

def distribucion_ocupacion(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(ocupacion, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        return _fetchall_dict(cur)

def distribucion_derechohabiencia(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(derechohabiencia, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        return _fetchall_dict(cur)

def datos_mapa(anio, nivel_mapa, entidad_id=None):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        if nivel_mapa == 'ESTADO':
            cur.execute(f"SELECT entidad_cve AS id, UPPER(entidad_nombre) AS nombre, COUNT(*) AS total FROM gold.mortalidad_consolidada {where} GROUP BY 1, 2", params)
        else:
            cur.execute(f"SELECT entidad_cve || '-' || municipio_cve AS id, UPPER(municipio_nombre) AS nombre, dl.lat_decimal, dl.lon_decimal, COUNT(*) AS total FROM gold.mortalidad_consolidada g JOIN gold.dim_localidad dl ON dl.cve_ent = g.entidad_cve AND dl.cve_mun = g.municipio_cve AND dl.cve_loc = '0001' {where} AND dl.lat_decimal IS NOT NULL GROUP BY 1, 2, 3, 4", params)
        return _fetchall_dict(cur)

def ranking_estados_rmm(anio, entidad_id=None):
    where, params = _build_where(anio, entidad_id)
    group_by = "UPPER(municipio_nombre)" if entidad_id else "UPPER(entidad_nombre)"
    with connection.cursor() as cur:
        cur.execute(f"SELECT {group_by} AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 10", params)
        return _fetchall_dict(cur)

def asistencia_vs_sitio(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(sitio_defuncion, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} AND asistencia_medica ILIKE '%%SIN ATENCI%%' GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        return _fetchall_dict(cur)

def edad_por_causa(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT edad_quinquenal AS edad, causa_desc AS causa, COUNT(*) AS count FROM gold.mortalidad_consolidada {where} GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15", params)
        rows = cur.fetchall()
    edades = sorted(list(set([r[0] for r in rows])))
    causas = list(set([r[1] for r in rows]))[:5]
    datasets = []
    for c in causas:
        data = [0] * len(edades)
        for r in rows:
            if r[1] == c and r[0] in edades: data[edades.index(r[0])] = r[2]
        datasets.append({'label': c, 'data': data})
    return {'labels': edades, 'datasets': datasets}

def escolaridad_vs_derecho(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT escolaridad AS esc, derechohabiencia AS der, COUNT(*) AS count FROM gold.mortalidad_consolidada {where} GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15", params)
        rows = cur.fetchall()
    escs = sorted(list(set([r[0] for r in rows])))
    derechs = list(set([r[1] for r in rows]))[:3]
    datasets = []
    for d in derechs:
        data = [0] * len(escs)
        for r in rows:
            if r[1] == d and r[0] in escs: data[escs.index(r[0])] = r[2]
        datasets.append({'label': d, 'data': data})
    return {'labels': escs, 'datasets': datasets}

# --- NUEVAS FUNCIONES ---
def distribucion_nivel_socioeconomico(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(nivel_socioeconomico, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC", params)
        return _fetchall_dict(cur)

def top_municipios_marginados(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"""
            SELECT municipio_nombre || ' (' || entidad_nombre || ')' AS etiqueta, 
                   COUNT(*) FILTER (WHERE nivel_socioeconomico = 'Baja') AS valor,
                   ROUND((COUNT(*) FILTER (WHERE nivel_socioeconomico = 'Baja')::numeric / COUNT(*)) * 100, 1) AS pct
            FROM gold.mortalidad_consolidada 
            {where}
            GROUP BY municipio_nombre, entidad_nombre
            HAVING COUNT(*) >= 3
            ORDER BY pct DESC, valor DESC
            LIMIT 10
        """, params)
        return _fetchall_dict(cur)