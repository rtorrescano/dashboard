from django.db import connection

def _fetchall_dict(cur):
    columns = [col[0] for col in cur.description]
    return [dict(zip(columns, row)) for row in cur.fetchall()]

def _build_where(anio, entidad_id):
    # AQUÍ EL CAMBIO A 2002
    where = ["anio >= 2002"]
    params = []
    if anio:
        where.append("anio = %s")
        params.append(anio)
    if entidad_id:
        where.append("entidad_cve = %s")
        params.append(str(entidad_id).zfill(2))
    return " WHERE " + " AND ".join(where), params

MAP_ESCOLARIDAD = {
    '1': 'Sin instrucción', '2': 'Preescolar', '3': 'Primaria', '4': 'Secundaria', 
    '5': 'Preparatoria', '6': 'Normal/Bachillerato', '7': 'Carrera técnica', '8': 'Licenciatura', 
    '9': 'Posgrado', '99': 'No especificado'
}

MAP_DERECHO = {
    '1': 'Ninguna', '2': 'IMSS', '3': 'ISSSTE', '4': 'PEMEX/Marina', 
    '5': 'Privada', '6': 'Otra', '7': 'IMSS Bienestar', '8': 'No especificado', '9': 'No aplica'
}

MAP_OCUPACION = {
    '1': 'Funcionarios', '2': 'Profesionistas', '3': 'Técnicos', '4': 'Educadores',
    '5': 'Artesanos', '6': 'Operadores', '7': 'Agrícolas', '8': 'Vigilancia',
    '9': 'Ventas', '10': 'Transporte', '11': 'Empleados/Hogar', '12': 'Trabajadores',
    '13': 'No aplica', '98': 'No especificado', '99': 'No especificado'
}

def _safe_map(val, mapping):
    if val is None: return 'No especificado'
    val_str = str(val).strip()
    if val_str.endswith('.0'): val_str = val_str[:-2]
    return mapping.get(val_str, f"Código {val_str}")

def datos_publicos_historicos():
    cur = connection.cursor()
    # AQUÍ EL CAMBIO A 2002
    where_base = "WHERE anio BETWEEN 2002 AND 2024"

    cur.execute(f"SELECT COUNT(*) FROM gold.mortalidad_consolidada {where_base}")
    total_muertes = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(*) FROM gold.mortalidad_consolidada {where_base} AND (asistencia_medica ILIKE '%%SIN ATENCI%%' OR asistencia_medica = '2')")
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

    return {
        'total_muertes': total_muertes, 'total_sin_atencion': total_sin_atencion,
        'serie_anual': serie_anual, 'por_edad': por_edad, 'por_sitio': por_sitio,
        'por_estado': por_estado, 'top_estado': top_estado
    }

def anios_disponibles():
    with connection.cursor() as cur:
        cur.execute("SELECT DISTINCT anio FROM gold.mortalidad_consolidada WHERE anio >= 2002 ORDER BY 1 DESC")
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
        res = _fetchall_dict(cur)
        for r in res: r['etiqueta'] = _safe_map(r['etiqueta'], MAP_ESCOLARIDAD)
        return res

def distribucion_ocupacion(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(ocupacion, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        res = _fetchall_dict(cur)
        for r in res: r['etiqueta'] = _safe_map(r['etiqueta'], MAP_OCUPACION)
        return res

def distribucion_derechohabiencia(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT COALESCE(derechohabiencia, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        res = _fetchall_dict(cur)
        for r in res: r['etiqueta'] = _safe_map(r['etiqueta'], MAP_DERECHO)
        return res

def datos_mapa(anio, nivel_mapa, entidad_id=None):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        if nivel_mapa == 'ESTADO':
            cur.execute(f"SELECT entidad_cve AS id, UPPER(entidad_nombre) AS nombre, COUNT(*) AS total FROM gold.mortalidad_consolidada {where} GROUP BY 1, 2", params)
        elif nivel_mapa == 'MUNICIPIO':
            cur.execute(f"""
                SELECT g.entidad_cve || '-' || g.municipio_cve AS id, 
                       UPPER(COALESCE(dl.nom_mun, g.municipio_nombre, 'Desconocido')) AS nombre, 
                       dl.lat_decimal, dl.lon_decimal, 
                       COUNT(g.id) AS total
                FROM gold.mortalidad_consolidada g
                LEFT JOIN gold.dim_localidad dl 
                       ON dl.cve_ent = g.entidad_cve 
                      AND dl.cve_mun = g.municipio_cve 
                      AND dl.cve_loc = '0001'
                {where} 
                GROUP BY 1, 2, 3, 4
                ORDER BY total DESC
            """, params)
        else:
            cur.execute(f"""
                SELECT entidad_cve || '-' || municipio_cve || '-' || localidad_cve AS id, UPPER(localidad_nombre) AS nombre, dl.lat_decimal, dl.lon_decimal, COUNT(*) AS total
                FROM gold.mortalidad_consolidada g
                JOIN gold.dim_localidad dl ON dl.cve_ent = g.entidad_cve AND dl.cve_mun = g.municipio_cve AND dl.cve_loc = g.localidad_cve
                {where} AND dl.lat_decimal IS NOT NULL GROUP BY 1, 2, 3, 4
            """, params)
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
        cur.execute(f"""
            SELECT COALESCE(sitio_defuncion, 'No esp.') AS etiqueta, COUNT(*) AS valor 
            FROM gold.mortalidad_consolidada 
            {where} AND (asistencia_medica ILIKE '%%SIN ATENCI%%' OR asistencia_medica = '2') 
            GROUP BY 1 ORDER BY 2 DESC LIMIT 5
        """, params)
        res = _fetchall_dict(cur)
        if not res:
            cur.execute(f"SELECT COALESCE(sitio_defuncion, 'No esp.') AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
            res = _fetchall_dict(cur)
        return res

def edad_por_causa(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT causa_desc, COUNT(*) as total FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 5", params)
        top_causas = [r[0] for r in cur.fetchall()]
        if not top_causas: return {'labels': [], 'datasets': []}

        placeholders = ', '.join(['%s'] * len(top_causas))
        params_causas = params + top_causas
        cur.execute(f"SELECT edad_quinquenal AS edad, causa_desc AS causa, COUNT(*) AS count FROM gold.mortalidad_consolidada {where} AND causa_desc IN ({placeholders}) GROUP BY 1, 2 ORDER BY 1", params_causas)
        rows = cur.fetchall()
    
    edades = sorted(list(set([str(r[0]) for r in rows if r[0]])))
    datasets = []
    for c in top_causas:
        data = [0] * len(edades)
        for r in rows:
            if str(r[1]) == c and str(r[0]) in edades:
                data[edades.index(str(r[0]))] = r[2]
        datasets.append({'label': c, 'data': data})
    return {'labels': edades, 'datasets': datasets}

def escolaridad_vs_derecho(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT escolaridad AS esc, derechohabiencia AS der, COUNT(*) AS count FROM gold.mortalidad_consolidada {where} GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15", params)
        rows = cur.fetchall()
    
    escs = sorted(list(set([_safe_map(r[0], MAP_ESCOLARIDAD) for r in rows])))
    derechs = list(set([_safe_map(r[1], MAP_DERECHO) for r in rows]))[:3]
    datasets = []
    for d in derechs:
        data = [0] * len(escs)
        for r in rows:
            esc_mapped = _safe_map(r[0], MAP_ESCOLARIDAD)
            der_mapped = _safe_map(r[1], MAP_DERECHO)
            if der_mapped == d and esc_mapped in escs:
                data[escs.index(esc_mapped)] = r[2]
        datasets.append({'label': d, 'data': data})
    return {'labels': escs, 'datasets': datasets}

def distribucion_nivel_socioeconomico(anio, entidad_id):
    return [{'etiqueta': 'Bajo', 'valor': 40}, {'etiqueta': 'Medio', 'valor': 35}, {'etiqueta': 'Alto', 'valor': 25}]

def top_municipios_marginados(anio, entidad_id):
    where, params = _build_where(anio, entidad_id)
    with connection.cursor() as cur:
        cur.execute(f"SELECT UPPER(municipio_nombre) AS etiqueta, COUNT(*) AS valor FROM gold.mortalidad_consolidada {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 10", params)
        return _fetchall_dict(cur)