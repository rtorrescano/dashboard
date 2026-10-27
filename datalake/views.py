import tempfile
from pathlib import Path
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection

from usuarios.models import Usuario
from datalake.forms import CargarArchivoForm
from datalake.services.ingesta import ingestar_archivo
from datalake.services.etl import etl_bronze_a_silver, etl_silver_a_gold

def _puede_cargar(user):
    return user.rol in (Usuario.Rol.ADMINISTRADOR, Usuario.Rol.OPERADOR)

def _refrescar_vistas_materializadas():
    """Refresca todas las vistas de la capa marts."""
    vistas = (
        'marts.mv_rmm_anual_entidad',
        'marts.mv_causas_agrupadas',
        'marts.mv_distribucion_edad',
        'marts.mv_series_tiempo',
        'marts.mv_subclasificacion',
        'marts.mv_sitio_defuncion',
        'marts.mv_escolaridad',
        'marts.mv_ocupacion',
        'marts.mv_derechohabiencia',
        'marts.mv_estado_conyugal',
    )
    with connection.cursor() as cur:
        for v in vistas:
            try:
                cur.execute(f'REFRESH MATERIALIZED VIEW {v};')
            except Exception:
                pass # Ignorar si la vista no existe aún


@login_required
def cargar_archivo_view(request):
    if not _puede_cargar(request.user):
        raise PermissionDenied('Solo operadores y administradores pueden cargar archivos.')

    if request.method == 'POST':
        form = CargarArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = form.cleaned_data['archivo']

            # 1. Guardar en archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(archivo.name).suffix) as tmp:
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                ruta_tmp = tmp.name

            try:
                # 2. Ingestar a Bronze
                resultado = ingestar_archivo(ruta_tmp)
            finally:
                Path(ruta_tmp).unlink(missing_ok=True)

            # 3. Si la carga fue exitosa, ejecutar ETL automáticamente
            if resultado.estado == 'OK':
                try:
                    # Pasar de Bronze a Silver
                    etl_bronze_a_silver()
                    # Pasar de Silver a Gold
                    etl_silver_a_gold()
                    # Actualizar las gráficas
                    _refrescar_vistas_materializadas()
                    
                    messages.success(
                        request,
                        f'✔ {resultado.mensaje} (versión {resultado.version}). '
                        f'Datos procesados y tableros actualizados correctamente.'
                    )
                except Exception as e:
                    messages.warning(
                        request,
                        f'⚠ El archivo se subió a Bronze, pero hubo un error en el ETL: {str(e)}'
                    )
            elif resultado.estado == 'DUPLICADO':
                messages.warning(request, f'⚠ {resultado.mensaje}')
            elif resultado.estado == 'NO_PROCESABLE':
                messages.info(request, f'ℹ {resultado.mensaje}')
            else:
                messages.error(request, f'✖ {resultado.mensaje}')

            return redirect('datalake:cargar')
    else:
        form = CargarArchivoForm()

    return render(request, 'datalake/cargar.html', {
        'form': form,
        'titulo': 'Carga de archivos al Datalake',
    })