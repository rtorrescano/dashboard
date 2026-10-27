from django.core.management.base import BaseCommand

from datalake.services.etl import etl_bronze_a_silver


class Command(BaseCommand):
    help = 'ETL Bronze -> Silver: tipado, validación CIE-10 y deduplicación.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Ejecutando ETL Bronze -> Silver...'))
        r = etl_bronze_a_silver()
        self.stdout.write(self.style.SUCCESS(
            f"✔ Procesadas: {r['procesadas']} | "
            f"Insertadas: {r['insertadas']} | "
            f"Duplicadas: {r['duplicadas']} | "
            f"Descartadas: {r['descartadas']}"
        ))