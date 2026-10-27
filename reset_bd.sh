#!/bin/bash

# Colores para la terminal
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "Iniciando limpieza de datos en 'tableros'..."

# Variable de entorno para evitar pedir contraseña
export PGPASSWORD="admin"

psql -U postgres -h localhost -d tableros <<EOF
TRUNCATE TABLE gold.fact_mortalidad_materna CASCADE;
TRUNCATE TABLE gold.dim_tiempo CASCADE;
TRUNCATE TABLE gold.dim_geografia CASCADE;
TRUNCATE TABLE gold.dim_causa CASCADE;
TRUNCATE TABLE gold.dim_edad CASCADE;

TRUNCATE TABLE silver.silver_mortalidad_limpia CASCADE;
TRUNCATE TABLE bronze.bronze_mortalidad_raw CASCADE;
TRUNCATE TABLE bronze.control_cargas CASCADE;

REFRESH MATERIALIZED VIEW marts.mv_rmm_anual_entidad;
REFRESH MATERIALIZED VIEW marts.mv_causas_agrupadas;
REFRESH MATERIALIZED VIEW marts.mv_distribucion_edad;
REFRESH MATERIALIZED VIEW marts.mv_series_tiempo;
REFRESH MATERIALIZED VIEW marts.mv_subclasificacion;
REFRESH MATERIALIZED VIEW marts.mv_sitio_defuncion;
REFRESH MATERIALIZED VIEW marts.mv_escolaridad;
REFRESH MATERIALIZED VIEW marts.mv_ocupacion;
REFRESH MATERIALIZED VIEW marts.mv_derechohabiencia;
REFRESH MATERIALIZED VIEW marts.mv_estado_conyugal;
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Base de datos limpiada correctamente.${NC}"
else
    echo -e "${RED}Hubo un error al ejecutar la limpieza.${NC}"
fi

unset PGPASSWORD