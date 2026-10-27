from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from datalake.services.ingesta import ingestar_archivo


class Command(BaseCommand):
    help = 'Carga un archivo CSV/XLSX/JSON/PDF a la capa Bronze con hash y versionado.'

    def add_arguments(self, parser):
        parser.add_argument(
            'ruta',
            type=str,
            help='Ruta al archivo (absoluta o relativa al directorio del proyecto).',
        )

    def handle(self, *args, **options):
        ruta = Path(options['ruta'])
        if not ruta.is_absolute():
            ruta = Path.cwd() / ruta

        self.stdout.write(self.style.NOTICE(f'Procesando: {ruta}'))
        resultado = ingestar_archivo(str(ruta))

        if resultado.estado == 'OK':
            self.stdout.write(self.style.SUCCESS(
                f'✔ {resultado.mensaje} (versión {resultado.version}, id_carga={resultado.id_carga or "batch"})'
            ))
        elif resultado.estado == 'DUPLICADO':
            self.stdout.write(self.style.WARNING(f'⚠ {resultado.mensaje}'))
        elif resultado.estado == 'PDF_REGISTRADO':
            self.stdout.write(self.style.NOTICE(f'ℹ {resultado.mensaje}'))
        else:
            raise CommandError(resultado.mensaje)