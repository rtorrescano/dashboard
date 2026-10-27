import csv
import io
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from datalake.models import NacimientosEstimados
from datalake.services.ingesta import _detectar_encoding


class Command(BaseCommand):
    help = 'Carga nacimientos estimados por año y entidad desde CSV.'

    def add_arguments(self, parser):
        parser.add_argument('ruta', type=str, help='Ruta al CSV.')
        parser.add_argument(
            '--fuente', type=str, default='CONAPO',
            help='Fuente de los datos (default: CONAPO).'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        ruta = Path(options['ruta'])
        if not ruta.is_absolute():
            ruta = Path.cwd() / ruta
        if not ruta.exists():
            raise CommandError(f'No existe: {ruta}')

        fuente = options['fuente']

        # 1. Detectar codificación real del archivo
        encoding = _detectar_encoding(ruta)
        self.stdout.write(self.style.NOTICE(
            f'Codificación detectada: {encoding}'
        ))

        # 2. Leer el contenido y autodetectar separador
        try:
            with open(ruta, encoding=encoding, newline='') as f:
                contenido = f.read()
        except UnicodeDecodeError:
            # Fallback: latin-1 nunca falla
            with open(ruta, encoding='latin-1', newline='') as f:
                contenido = f.read()

        # Autodetectar separador: cuenta apariciones en la primera línea
        primera_linea = contenido.splitlines()[0] if contenido else ''
        separador = max([',', ';', '\t'], key=primera_linea.count)
        self.stdout.write(f'Separador detectado: {separador!r}')

        reader = csv.DictReader(io.StringIO(contenido), delimiter=separador)
        fieldnames = [c.lower().strip() for c in (reader.fieldnames or [])]

        requeridas = {'anio', 'id_entidad', 'nacimientos'}
        if not requeridas.issubset(fieldnames):
            raise CommandError(
                f'El CSV debe tener columnas: {", ".join(sorted(requeridas))}. '
                f'Encontradas: {fieldnames}'
            )

        creados = actualizados = 0
        for fila in reader:
            try:
                anio        = int(fila['anio'])
                id_entidad  = int(fila['id_entidad'])
                nacimientos = int(fila['nacimientos'])
            except (ValueError, KeyError) as e:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Fila omitida ({e}): {fila}'
                ))
                continue

            obj, creado = NacimientosEstimados.objects.update_or_create(
                anio=anio,
                id_entidad=id_entidad,
                defaults={'nacimientos': nacimientos, 'fuente': fuente},
            )
            if creado:
                creados += 1
            else:
                actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'✔ Nacimientos: {creados} creados, {actualizados} actualizados.'
        ))

        