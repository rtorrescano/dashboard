import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from usuarios.models import Usuario
from tableros.services import consultas as q
from .models import ConfiguracionTablero

def _es_directivo(user):
    return user.rol in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.DIRECTIVO)

def _limpiar_datos_json(obj):
    if isinstance(obj, dict): return {k: _limpiar_datos_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [_limpiar_datos_json(v) for v in obj]
    elif hasattr(obj, 'as_tuple'): return float(obj)
    return obj

@login_required
def directivo(request):
    if not _es_directivo(request.user): raise PermissionDenied

    # 1. Leer configuración del administrador
    config, _ = ConfiguracionTablero.objects.get_or_create(id=1)
    nivel_mapa = config.nivel_mapa

    anios_disponibles = q.anios_disponibles() 
    anio_default = anios_disponibles[0] if anios_disponibles else 2024

    anio_str = request.GET.get('anio')
    entidad_str = request.GET.get('id_entidad')
    
    es_historico = (anio_str == 'historico')
    anio = int(anio_str) if anio_str and anio_str.isdigit() else (None if es_historico else anio_default)
    entidad_id = int(entidad_str) if entidad_str and entidad_str.isdigit() else None

    try:
        kpi = q.kpi_rmm_ultimo_anio(anio, entidad_id)
        causas = q.causas_agrupadas(anio, entidad_id)
        edades = q.distribucion_edad(anio, entidad_id)
        mapa = q.datos_mapa(anio, nivel_mapa)
        
        sitios = q.distribucion_sitio(anio, entidad_id)
        escolaridad = q.distribucion_escolaridad(anio, entidad_id)
        ocupacion = q.distribucion_ocupacion(anio, entidad_id)
        derecho = q.distribucion_derechohabiencia(anio, entidad_id)
    except Exception as e:
        print(f"Error BD: {e}")
        kpi, causas, edades, mapa, sitios, escolaridad, ocupacion, derecho = None, [], [], [], [], [], [], []

    datos_graficas = {
        'kpis': _limpiar_datos_json(kpi or {}),
        'causas': {'labels': [r['etiqueta'] for r in causas], 'valores': [r['valor'] for r in causas]},
        'edades': {'labels': [r['etiqueta'] for r in edades], 'valores': [r['valor'] for r in edades]},
        'sitio': {'labels': [r['etiqueta'] for r in sitios], 'valores': [r['valor'] for r in sitios]},
        'escolaridad': {'labels': [r['etiqueta'] for r in escolaridad], 'valores': [r['valor'] for r in escolaridad]},
        'ocupacion': {'labels': [r['etiqueta'] for r in ocupacion], 'valores': [r['valor'] for r in ocupacion]},
        'derecho': {'labels': [r['etiqueta'] for r in derecho], 'valores': [r['valor'] for r in derecho]}
    }

    context = {
        'titulo': 'Tablero Directivo',
        'anios': anios_disponibles,
        'entidades': q.entidades_disponibles(),
        'anio_seleccionado': 'historico' if es_historico else anio,
        'entidad_seleccionada': entidad_id,
        'nivel_mapa': nivel_mapa,
        'mapa_entidades': _limpiar_datos_json(mapa), 
        'datos_graficas_json': _limpiar_datos_json(datos_graficas),
        'kpi': kpi,
    }
    return render(request, 'tableros/directivo.html', context)

@login_required
def publico(request):
    anio_str = request.GET.get('anio')
    anio = int(anio_str) if anio_str and anio_str.isdigit() else 2014
    if anio < 2014: anio = 2014

    entidad_str = request.GET.get('id_entidad')
    entidad_id = int(entidad_str) if entidad_str and entidad_str.isdigit() else None

    kpi = q.kpi_rmm_ultimo_anio(anio, entidad_id)
    causas = q.causas_agrupadas(anio, entidad_id)
    edades = q.distribucion_edad(anio, entidad_id)
    entidades = q.entidades_disponibles()

    entidad_sel = None
    if entidad_id:
        entidad_sel = next((e for e in entidades if e['id_entidad'] == entidad_id), None)

    datos_publicos = {
        'kpi': _limpiar_datos_json(kpi or {}),
        'causas': {'labels': [r['etiqueta'] for r in causas], 'valores': [r['valor'] for r in causas]},
        'edades': {'labels': [r['etiqueta'] for r in edades], 'valores': [r['valor'] for r in edades]}
    }

    context = {
        'kpi': kpi, 'entidades': entidades,
        'anio': anio, 'id_entidad': entidad_id, 'entidad_sel': entidad_sel,
        'anios': [a for a in q.anios_disponibles() if a >= 2014],
        'titulo': 'Tablero Público — Mortalidad Materna',
        'disclaimer': 'Datos preliminares.',
        'datos_publicos_json': _limpiar_datos_json(datos_publicos)
    }
    return render(request, 'tableros/publico.html', context)