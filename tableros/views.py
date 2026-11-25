import os
import json
import csv
import hashlib
import io
from datetime import datetime, timezone

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection, transaction
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse

from usuarios.models import Usuario
from tableros.services import consultas as q
from mvs_helpers import cargar_kpis_numeradores
from .models import ConfiguracionTablero

def _es_directivo(user):
    return user.rol in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.DIRECTIVO) or user.is_superuser

def _es_admin(user):
    return user.rol == Usuario.Rol.ADMINISTRADOR or user.is_superuser

def _puede_cargar_datos(user):
    return user.rol in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR) or user.is_superuser

def _limpiar_datos_json(obj):
    if isinstance(obj, dict): return {k: _limpiar_datos_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [_limpiar_datos_json(v) for v in obj]
    elif hasattr(obj, 'as_tuple'): return float(obj)
    return obj

@login_required
def admin_dashboard(request):
    if not _es_admin(request.user): 
        raise PermissionDenied
    return render(request, 'tableros/admin_dashboard.html')

@login_required
def directivo(request):
    if not _es_directivo(request.user): raise PermissionDenied
    config, _ = ConfiguracionTablero.objects.get_or_create(id=1)
    nivel_mapa = config.nivel_mapa
    
    cur = connection.cursor()
    cur.execute("SELECT DISTINCT anio FROM gold.mortalidad_consolidada ORDER BY anio DESC")
    anios_disponibles = [r[0] for r in cur.fetchall()]
    anio_default = anios_disponibles[0] if anios_disponibles else 2024
    
    # Filtro para evitar valores 'None' en el combo
    cur.execute("SELECT DISTINCT entidad_cve, entidad_nombre FROM gold.mortalidad_consolidada WHERE entidad_nombre IS NOT NULL AND entidad_nombre != '' ORDER BY entidad_nombre")
    entidades = [{'id_entidad': r[0], 'entidad_nombre': r[1]} for r in cur.fetchall()]

    anio_str = request.GET.get('anio')
    entidad_str = request.GET.get('id_entidad')

    es_historico = (anio_str == 'historico')
    anio = int(anio_str) if anio_str and anio_str.isdigit() else (None if es_historico else anio_default)
    entidad_id = entidad_str if entidad_str else None
    anio_para_graficas_viejas = anio_default if es_historico else anio

    kpi, causas, edades, mapa_estados, mapa_municipios, mapa_localidades = None, [], [], [], [], []
    sitios, escolaridad, ocupacion, derecho = [], [], [], []
    grafica_edad_causa, grafica_ranking, grafica_asistencia, grafica_escolaridad_der = {}, [], [], []
    nivel_socio, grafica_marginados = [], []

    try: kpi = q.kpi_rmm_ultimo_anio(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error KPI: {e}")

    try: causas = q.causas_agrupadas(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Causas: {e}")

    try: edades = q.distribucion_edad(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Edades: {e}")

    try: mapa_estados = q.datos_mapa(anio_para_graficas_viejas, 'ESTADO', entidad_id)
    except Exception as e: print(f"Error Mapa Estados: {e}")

    try: mapa_municipios = q.datos_mapa(anio_para_graficas_viejas, 'MUNICIPIO', entidad_id)
    except Exception as e: print(f"Error Mapa Municipios: {e}")

    try: mapa_localidades = q.datos_mapa(anio_para_graficas_viejas, 'LOCALIDAD', entidad_id)
    except Exception as e: print(f"Error Mapa Localidades: {e}")

    try: grafica_edad_causa = q.edad_por_causa(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Edad vs Causa: {e}")

    try: grafica_ranking = q.ranking_estados_rmm(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Ranking: {e}")

    try: sitios = q.distribucion_sitio(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Sitios: {e}")

    try: escolaridad = q.distribucion_escolaridad(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Escolaridad: {e}")

    try: ocupacion = q.distribucion_ocupacion(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Ocupacion: {e}")

    try: derecho = q.distribucion_derechohabiencia(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Derechohabiencia: {e}")

    try: grafica_asistencia = q.asistencia_vs_sitio(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Asistencia: {e}")

    try: grafica_escolaridad_der = q.escolaridad_vs_derecho(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Escolaridad vs Derecho: {e}")
    
    try: nivel_socio = q.distribucion_nivel_socioeconomico(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Nivel Socioeconomico: {e}")

    try: grafica_marginados = q.top_municipios_marginados(anio_para_graficas_viejas, entidad_id)
    except Exception as e: print(f"Error Top Marginados: {e}")

    anio_para_helper = 'historico' if es_historico else anio
    try:
        kpi_nuevo, serie_temporal, ranking_volumen = cargar_kpis_numeradores(anio_para_helper, entidad_id)
        kpi = {**(kpi or {}), **kpi_nuevo}
    except Exception as e:
        print(f"Error helper MVs: {e}")
        serie_temporal, ranking_volumen = [], []

    datos_graficas = {
        'kpis': _limpiar_datos_json(kpi or {}),
        'causas': {'labels': [str(r['etiqueta']) for r in causas], 'valores': [int(r['valor']) for r in causas]},
        'edades': {'labels': [str(r['etiqueta']) for r in edades], 'valores': [int(r['valor']) for r in edades]},
        'sitio': {'labels': [str(r['etiqueta']) for r in sitios], 'valores': [int(r['valor']) for r in sitios]},
        'escolaridad': {'labels': [str(r['etiqueta']) for r in escolaridad], 'valores': [int(r['valor']) for r in escolaridad]},
        'ocupacion': {'labels': [str(r['etiqueta']) for r in ocupacion], 'valores': [int(r['valor']) for r in ocupacion]},
        'derecho': {'labels': [str(r['etiqueta']) for r in derecho], 'valores': [int(r['valor']) for r in derecho]},
        'edad_causa': _limpiar_datos_json(grafica_edad_causa) if grafica_edad_causa else {},
        'ranking_estados': {'labels': [str(r['etiqueta']) for r in grafica_ranking], 'valores': [int(r['valor']) for r in grafica_ranking]},
        'asistencia_sitio': {'labels': [str(r['etiqueta']) for r in grafica_asistencia], 'valores': [int(r['valor']) for r in grafica_asistencia]},
        'escolaridad_derecho': _limpiar_datos_json(grafica_escolaridad_der) if grafica_escolaridad_der else {},
        'nivel_socio': {'labels': [str(r['etiqueta']) for r in nivel_socio], 'valores': [int(r['valor']) for r in nivel_socio]},
        'municipios_marginados': {'labels': [str(r['etiqueta']) for r in grafica_marginados], 'valores': [int(r['valor']) for r in grafica_marginados]},
    }

    context = {
        'titulo': 'Tablero Directivo', 'anios': anios_disponibles, 'entidades': entidades,
        'anio_seleccionado': 'historico' if es_historico else anio, 'entidad_seleccionada': entidad_id,
        'nivel_mapa': nivel_mapa, 
        'mapa_estados': _limpiar_datos_json(mapa_estados),
        'mapa_municipios': _limpiar_datos_json(mapa_municipios),
        'mapa_localidades': _limpiar_datos_json(mapa_localidades),
        'datos_graficas_json': _limpiar_datos_json(datos_graficas), 'kpi': kpi,
        'serie_temporal_json':  serie_temporal, 'ranking_volumen_json': ranking_volumen,
    }
    return render(request, 'tableros/directivo.html', context)


def publico(request):
    datos = q.datos_publicos_historicos()
    pct_sin_atencion = round((datos['total_sin_atencion'] / datos['total_muertes']) * 100, 1) if datos['total_muertes'] > 0 else 0

    context = {
        'titulo': 'Tablero Público - Mortalidad Materna',
        'total_muertes': datos['total_muertes'],
        'total_sin_atencion': datos['total_sin_atencion'],
        'pct_sin_atencion': pct_sin_atencion,
        'top_estado_nombre': datos['top_estado']['nombre'],
        'top_estado_total': datos['top_estado']['total'],
        'serie_anual_json': datos['serie_anual'],
        'por_edad_json': datos['por_edad'],
        'por_sitio_json': datos['por_sitio'],
        'por_estado_json': datos['por_estado'],
    }
    return render(request, 'tableros/publico.html', context)

@login_required
def descargar_excel(request):
    if not _es_directivo(request.user): raise PermissionDenied
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reporte_mortalidad.csv"'
    response.write('\ufeff') 
    
    writer = csv.writer(response)
    writer.writerow(['Año', 'Entidad', 'Municipio', 'Causa', 'Casos'])
    
    with connection.cursor() as cur:
        cur.execute("""
            SELECT anio, entidad_nombre, municipio_nombre, causa_desc, COUNT(*) as total
            FROM gold.mortalidad_consolidada
            GROUP BY anio, entidad_nombre, municipio_nombre, causa_desc
            ORDER BY total DESC
            LIMIT 5000
        """)
        for row in cur.fetchall():
            writer.writerow(row)
            
    return response

@login_required
def cargar_datos_csv(request):
    if not _es_directivo(request.user): 
        raise PermissionDenied

    if request.method == 'POST' and request.FILES.get('archivo_csv'):
        archivo = request.FILES['archivo_csv']
        
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
        filename = fs.save(archivo.name, archivo)
        file_path = fs.path(filename)
        
        try:
            with transaction.atomic():
                cur = connection.cursor()
                file_hash = hashlib.sha256(open(file_path, 'rb').read()).hexdigest()
                
                with open(file_path, encoding="utf-8-sig", newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader)
                    cols = [h.lower() for h in header]
                    
                    es_catalogo = 'cvegeo' in cols or 'cve_ent' in cols
                    es_mortalidad = 'anio_defuncion' in cols or 'anio_nacimiento' in cols

                if es_catalogo:
                    cur.execute("TRUNCATE TABLE gold.dim_localidad CASCADE")
                    with open(file_path, encoding="utf-8-sig", newline="") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            cur.execute("""
                                INSERT INTO gold.dim_localidad (cvegeo, cve_ent, nom_ent, cve_mun, nom_mun, cve_loc, nom_loc, lat_decimal, lon_decimal, geom)
                                VALUES (LPAD(%s, 9, '0'), LPAD(%s, 2, '0'), %s, LPAD(%s, 3, '0'), %s, LPAD(%s, 4, '0'), %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                                ON CONFLICT (cvegeo) DO NOTHING
                            """, [
                                row.get('CVEGEO'), row.get('CVE_ENT'), row.get('NOM_ENT'),
                                row.get('CVE_MUN'), row.get('NOM_MUN'), row.get('CVE_LOC'), row.get('NOM_LOC'),
                                row.get('LAT_DECIMAL'), row.get('LON_DECIMAL'),
                                row.get('LON_DECIMAL'), row.get('LAT_DECIMAL')
                            ])
                    messages.success(request, "¡Catálogo Geográfico cargado exitosamente! Ahora puedes subir el archivo de mortalidad.")

                elif es_mortalidad:
                    cur.execute("SELECT COUNT(*) FROM gold.dim_localidad")
                    if cur.fetchone()[0] == 0:
                        messages.error(request, "Error: Debes cargar primero el Catálogo Geográfico (AGEEML) antes de subir los datos de mortalidad.")
                        return redirect('/tableros/subir-datos/')

                    cur.execute("SELECT id_carga FROM bronze.control_cargas WHERE hash_archivo = %s AND estatus_procesamiento = 'completado'", [file_hash])
                    if cur.fetchone():
                        messages.warning(request, "Este archivo de mortalidad ya fue procesado anteriormente.")
                        return redirect('/tableros/subir-datos/')

                    cur.execute("""
                        INSERT INTO bronze.control_cargas (nombre_archivo_original, hash_archivo, version_archivo, estatus_procesamiento, fecha_carga)
                        VALUES (%s, %s, 'v1', 'cargando', now()) RETURNING id_carga
                    """, [filename, file_hash])
                    id_carga = cur.fetchone()[0]

                    with open(file_path, encoding="utf-8-sig", newline="") as f:
                        reader = csv.reader(f)
                        header = next(reader)
                        cols = [h.lower() for h in header]
                        all_cols = ["id_carga", "fila_origen", "nombre_archivo_original", "hash_archivo", "vigente", "es_vigente", "fecha_vigencia_desde", "version_registro"] + cols
                        copy_sql = f"COPY bronze.bronze_mortalidad_raw ({', '.join(all_cols)}) FROM STDIN WITH (FORMAT CSV, NULL '')"
                        
                        buf = io.StringIO()
                        w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
                        for i, row in enumerate(reader, start=2):
                            extras = [id_carga, i, filename, file_hash, "true", "true", datetime.now(timezone.utc).isoformat(), "1"]
                            w.writerow(extras + row)
                        buf.seek(0)
                        with cur.copy(copy_sql) as cp:
                            cp.write(buf.getvalue())
                            
                    cur.execute("UPDATE bronze.control_cargas SET estatus_procesamiento='completado', filas_cargadas=%s WHERE id_carga=%s", [i-1, id_carga])

                    cur.execute("""
                        INSERT INTO silver.silver_mortalidad_limpia (
                            id_carga_origen, anio_defuncion, entidad_residencia, causa_cie_4, causa_descripcion,
                            edad, edad_quinquenal, mes_defuncion, municipio_residencia, localidad_ocurrencia,
                            fila_origen, incluida_en_rmm, fecha_procesamiento, sitio_defuncion, escolaridad, 
                            ocupacion, estado_conyugal, derechohabiencia, razon_mortalidad_texto,
                            asistencia_medica, certifico, hora_defuncion, minutos_defuncion, clave_natural, hash_fila, vigente
                        )
                        SELECT 
                            id_carga, 
                            CASE WHEN anio_defuncion ~ '^[0-9]+$' THEN anio_defuncion::int ELSE NULL END,
                            TRIM(entidad_residencia)::int,
                            causa_cie_4, causa_cie_4d,
                            CASE WHEN edad ~ '^[0-9]+$' THEN edad::int ELSE NULL END,
                            edad_quinquenald,
                            CASE WHEN mes_defuncion ~ '^[0-9]+$' THEN mes_defuncion::int ELSE NULL END,
                            TRIM(municipio_residencia)::int,
                            localidad_residencia,
                            fila_origen,
                            (razon_mortalidad_materna = '1'),
                            now(),
                            sitio_defunciond, escolaridad, ocupacion_habitual, estado_conyugal, derechohabiencia, razon_mortalidad_materna,
                            asistencia_medica, certifico, hora_defuncion, minutos_defuncion, 
                            anio_defuncion || '-' || entidad_residencia || '-' || municipio_residencia || '-' || localidad_residencia || '-' || causa_cie_4 || '-' || edad || '-' || fila_origen,
                            md5(ROW(anio_defuncion, entidad_residencia, municipio_residencia, localidad_residencia, causa_cie_4, edad)::text),
                            true
                        FROM bronze.bronze_mortalidad_raw b
                        -- AQUÍ EL CAMBIO A 2002
                        WHERE id_carga = %s AND TRIM(anio_defuncion) ~ '^[0-9]+$' AND TRIM(anio_defuncion)::int >= 2002
                        ON CONFLICT (hash_fila) DO NOTHING
                    """, [id_carga])

                    cur.execute("TRUNCATE TABLE gold.mortalidad_consolidada")
                    cur.execute("""
                        INSERT INTO gold.mortalidad_consolidada (
                            anio, entidad_cve, entidad_nombre, municipio_cve, municipio_nombre,
                            localidad_cve, localidad_nombre, causa_cve, causa_desc, edad, edad_quinquenal,
                            asistencia_medica, sitio_defuncion, derechohabiencia, escolaridad, ocupacion, incluida_rmm
                        )
                        SELECT 
                            s.anio_defuncion,
                            LPAD(s.entidad_residencia::text, 2, '0'),
                            dl.nom_ent,
                            LPAD(s.municipio_residencia::text, 3, '0'),
                            dl.nom_mun,
                            '0001', 
                            dl.nom_loc,
                            s.causa_cie_4, s.causa_descripcion, s.edad, s.edad_quinquenal,
                            s.asistencia_medica, s.sitio_defuncion, s.derechohabiencia, s.escolaridad, s.ocupacion, s.incluida_en_rmm
                        FROM silver.silver_mortalidad_limpia s
                        LEFT JOIN gold.dim_localidad dl 
                               ON dl.cve_ent = LPAD(s.entidad_residencia::text, 2, '0')
                              AND dl.cve_mun = LPAD(s.municipio_residencia::text, 3, '0')
                              AND dl.cve_loc = '0001'
                    """)
                    messages.success(request, f"¡Datos de Mortalidad cargados y consolidados exitosamente desde 2002!")
                
                else:
                    messages.error(request, "Archivo no reconocido. Debe ser el Catálogo Geográfico (AGEEML) o el archivo de Mortalidad.")
                    return redirect('/tableros/subir-datos/')

        except Exception as e:
            messages.error(request, f"Error al procesar el archivo: {e}")
            
        return redirect('/tableros/subir-datos/')

    ultima_carga = None
    with connection.cursor() as cur:
        try:
            cur.execute("SELECT nombre_archivo_original, filas_cargadas, fecha_carga FROM bronze.control_cargas ORDER BY fecha_carga DESC LIMIT 1")
            ultima_carga = cur.fetchone()
        except Exception:
            pass

    return render(request, 'tableros/subir_datos.html', {'ultima_carga': ultima_carga})