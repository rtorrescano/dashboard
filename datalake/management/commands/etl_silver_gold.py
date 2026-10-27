from django.core.management.base import BaseCommand
from django.db import connection

from datalake.services.etl import etl_silver_a_gold


VISTAS = (
    'marts.mv_rmm_anual_entidad',
    'marts.mv_causas_agrupadas',
    'marts.mv_distribucion_edad',
    'marts.mv_series_tiempo',
)


class Command(BaseCommand):
    help = 'ETL Silver -> Gold: puebla dimensiones, hechos y refresca vistas materializadas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sin-refresh',
            action='store_true',
            help='Omite el REFRESH MATERIALIZED VIEW (útil en pruebas).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Ejecutando ETL Silver -> Gold...'))
        r = etl_silver_a_gold()
        self.stdout.write(self.style.SUCCESS(
            f"✔ Hechos insertados: {r['hechos_insertados']}"
        ))

        if options['sin_refresh']:
            self.stdout.write(self.style.WARNING('Refresh de vistas omitido.'))
            return

        self.stdout.write(self.style.NOTICE('Refrescando vistas materializadas...'))
        with connection.cursor() as cur:
            for vista in VISTAS:
                try:
                    cur.execute(f'REFRESH MATERIALIZED VIEW {vista};')
                    self.stdout.write(f'  ✔ {vista}')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'  ⚠ {vista}: {e}'
                    ))