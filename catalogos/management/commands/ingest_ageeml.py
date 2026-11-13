"""
Ingesta incremental del AGEEML.

Uso:
    python manage.py ingest_ageeml /ruta/AGEEML_YYYYMMDD.csv
    python manage.py ingest_ageeml /ruta/AGEEML.csv --dry-run
    python manage.py ingest_ageeml /ruta/AGEEML.csv --force
"""
import csv
import hashlib
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

#from catalogos.services.ageeml import parse_and_validate_file
from catalogos.services.ageeml import parse_and_validate_file



class Command(BaseCommand):
    help = 'Ingesta incremental (SCD2) del catálogo AGEEML del INEGI.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo parsea y valida, no escribe.')
        parser.add_argument('--force', action='store_true',
                            help='Reingesta aunque el file_hash ya exista.')
        parser.add_argument('--no-mark-removals', action='store_true',
                            help='No cerrar CVEGEO ausentes del archivo nuevo.')
        parser.add_argument('--max-reject-ratio', type=float, default=0.05,
                            help='Aborta si > este ratio de filas es inválido.')

    # ---------------------------------------------------------------

    def handle(self, *args, **opts):
        path = Path(opts['csv_path']).resolve()
        if not path.exists():
            raise CommandError(f'No existe: {path}')

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        self.stdout.write(f'Archivo: {path.name}')
        self.stdout.write(f'sha256 : {file_hash}')

        # --- Idempotencia por archivo ---
        with connection.cursor() as cur:
            cur.execute(
                'SELECT ingestion_id, status FROM bronze.file_ingestion '
                'WHERE file_hash = %s', [file_hash],
            )
            prior = cur.fetchone()

        if prior and not opts['force']:
            raise CommandError(
                f'Archivo ya ingestado previamente '
                f'(ingestion_id={prior[0]}, status={prior[1]}). '
                f'Usa --force si quieres reingestarlo.'
            )

        # --- Parse + validación ---
        self.stdout.write('Parseando y validando…')
        parsed, rejected = parse_and_validate_file(path)
        total = len(parsed) + len(rejected)
        self.stdout.write(
            f'Filas totales={total}  válidas={len(parsed)}  rechazadas={len(rejected)}'
        )
        if total == 0:
            raise CommandError('Archivo sin filas.')
        if rejected:
            ratio = len(rejected) / total
            for row_num, reason in rejected[:20]:
                self.stderr.write(f'  fila {row_num}: {reason}')
            if ratio > opts['max_reject_ratio']:
                raise CommandError(
                    f'Ratio de rechazo {ratio:.2%} > límite '
                    f'{opts["max_reject_ratio"]:.2%}. Abortando.'
                )
            self.stdout.write(self.style.WARNING(
                f'Se ignorarán {len(rejected)} filas inválidas.'
            ))

        if opts['dry_run']:
            self.stdout.write(self.style.SUCCESS('DRY-RUN: sin escrituras.'))
            return

        # --- Ingesta ---
        ingestion_id = uuid.uuid4()
        started_at = datetime.now(timezone.utc)
        self.stdout.write(f'Ingestionando… id={ingestion_id}')

        try:
            stats = self._run_in_transaction(
                ingestion_id=ingestion_id,
                started_at=started_at,
                path=path,
                file_hash=file_hash,
                parsed=parsed,
                mark_removals=not opts['no_mark_removals'],
            )
        except Exception:
            self._mark_failed(ingestion_id, file_hash, path, total)
            raise

        # --- Refresh de MVs fuera de la transacción (CONCURRENTLY) ---
        self._refresh_mvs()

        self.stdout.write(self.style.SUCCESS(
            f"OK ingestion_id={ingestion_id}\n"
            f"  cerradas  : {stats['closed']}\n"
            f"  insertadas: {stats['inserted']}\n"
            f"  removidas : {stats['removed']}"
        ))

    # ---------------------------------------------------------------
    #  Transacción única: bronce + plata
    # ---------------------------------------------------------------

    def _run_in_transaction(self, *, ingestion_id, started_at, path,
                            file_hash, parsed, mark_removals):

        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    """INSERT INTO bronze.file_ingestion
                          (ingestion_id, source_file, file_hash, file_path,
                           row_count, ingested_at, status)
                       VALUES (%s, %s, %s, %s, %s, %s, 'running')""",
                    [str(ingestion_id), path.name, file_hash, str(path),
                     len(parsed), started_at],
                )

            self._insert_bronze(ingestion_id, parsed)
            self._create_and_fill_staging(parsed)
            stats = self._apply_scd2(
                ingestion_id=ingestion_id,
                now=started_at,
                source_file=path.name,
                mark_removals=mark_removals,
            )

            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE bronze.file_ingestion SET status='success' "
                    "WHERE ingestion_id=%s", [str(ingestion_id)],
                )
        return stats

    # ---------------------------------------------------------------

    def _insert_bronze(self, ingestion_id, parsed):
        cols = (
            "bronze.ageeml_raw ("
            "ingestion_id, source_row_num, cvegeo, estatus, cve_ent, "
            "nom_ent, nom_abr, cve_mun, nom_mun, cve_loc, nom_loc, ambito, "
            "latitud, longitud, lat_decimal, lon_decimal, altitud, "
            "cve_carta, pob_total, pob_masculina, pob_femenina, "
            "total_viviendas_habitadas)"
        )
        rows = [
            (
                str(ingestion_id), i, r.raw['cvegeo'], r.raw['estatus'],
                r.raw['cve_ent'], r.raw['nom_ent'], r.raw['nom_abr'],
                r.raw['cve_mun'], r.raw['nom_mun'], r.raw['cve_loc'],
                r.raw['nom_loc'], r.raw['ambito'], r.raw['latitud'],
                r.raw['longitud'], r.raw['lat_decimal_raw'],
                r.raw['lon_decimal_raw'], r.raw['altitud_raw'],
                r.raw['cve_carta'], r.raw['pob_total_raw'],
                r.raw['pob_masculina_raw'], r.raw['pob_femenina_raw'],
                r.raw['total_viviendas_raw'],
            )
            for i, r in enumerate(parsed, start=1)
        ]
        with connection.cursor() as cur:
            _copy(cur, f"COPY {cols} FROM STDIN WITH (FORMAT CSV, NULL '')", rows)

    # ---------------------------------------------------------------

    def _create_and_fill_staging(self, parsed):
        with connection.cursor() as cur:
            cur.execute("""
                CREATE TEMP TABLE stg_ageeml (
                    cvegeo           char(9) PRIMARY KEY,
                    estatus          char(1),
                    cve_ent          char(2) NOT NULL,
                    nom_ent          text    NOT NULL,
                    nom_abr          text,
                    cve_mun          char(3) NOT NULL,
                    nom_mun          text    NOT NULL,
                    cve_loc          char(4) NOT NULL,
                    nom_loc          text    NOT NULL,
                    ambito           char(1),
                    latitud_dms      text,
                    longitud_dms     text,
                    lat_decimal      numeric(12,8),
                    lon_decimal      numeric(12,8),
                    altitud          integer,
                    cve_carta        text,
                    pob_total        integer,
                    pob_masculina    integer,
                    pob_femenina     integer,
                    total_viviendas  integer,
                    record_hash      char(64) NOT NULL
                ) ON COMMIT DROP
            """)

        cols = (
            "stg_ageeml (cvegeo, estatus, cve_ent, nom_ent, nom_abr, "
            "cve_mun, nom_mun, cve_loc, nom_loc, ambito, latitud_dms, "
            "longitud_dms, lat_decimal, lon_decimal, altitud, cve_carta, "
            "pob_total, pob_masculina, pob_femenina, total_viviendas, "
            "record_hash)"
        )
        rows = [
            (
                p.norm['cvegeo'], p.norm['estatus'], p.norm['cve_ent'],
                p.norm['nom_ent'], p.norm['nom_abr'], p.norm['cve_mun'],
                p.norm['nom_mun'], p.norm['cve_loc'], p.norm['nom_loc'],
                p.norm['ambito'], p.norm['latitud_dms'],
                p.norm['longitud_dms'], p.norm['lat_decimal'],
                p.norm['lon_decimal'], p.norm['altitud'],
                p.norm['cve_carta'], p.norm['pob_total'],
                p.norm['pob_masculina'], p.norm['pob_femenina'],
                p.norm['total_viviendas'], p.record_hash,
            )
            for p in parsed
        ]
        with connection.cursor() as cur:
            _copy(cur, f"COPY {cols} FROM STDIN WITH (FORMAT CSV, NULL '')", rows)
            cur.execute('ANALYZE stg_ageeml')

    # ---------------------------------------------------------------
    #  SCD2 en tres pasos atómicos
    # ---------------------------------------------------------------

    def _apply_scd2(self, *, ingestion_id, now, source_file, mark_removals):

        with connection.cursor() as cur:
            # --- 1. Cerrar filas vigentes cuyo hash cambió ---
            cur.execute("""
                UPDATE silver.localidad s
                   SET valid_to  = %s,
                       is_current = false
                  FROM stg_ageeml stg
                 WHERE s.cvegeo      = stg.cvegeo
                   AND s.is_current
                   AND s.record_hash <> stg.record_hash
            """, [now])
            closed = cur.rowcount

            # --- 2. Insertar nuevas versiones / filas nuevas ---
            cur.execute("""
                INSERT INTO silver.localidad
                  (cvegeo, estatus, cve_ent, nom_ent, nom_abr, cve_mun,
                   nom_mun, cve_loc, nom_loc, ambito, latitud_dms,
                   longitud_dms, lat_decimal, lon_decimal, altitud,
                   cve_carta, pob_total, pob_masculina, pob_femenina,
                   total_viviendas, geom, record_hash, valid_from,
                   is_current, ingestion_id, source_file)
                SELECT
                  stg.cvegeo, stg.estatus, stg.cve_ent, stg.nom_ent,
                  stg.nom_abr, stg.cve_mun, stg.nom_mun, stg.cve_loc,
                  stg.nom_loc, stg.ambito, stg.latitud_dms,
                  stg.longitud_dms, stg.lat_decimal, stg.lon_decimal,
                  stg.altitud, stg.cve_carta, stg.pob_total,
                  stg.pob_masculina, stg.pob_femenina,
                  stg.total_viviendas,
                  CASE
                    WHEN stg.lat_decimal IS NOT NULL
                     AND stg.lon_decimal IS NOT NULL
                    THEN ST_SetSRID(
                           ST_MakePoint(stg.lon_decimal::float8,
                                        stg.lat_decimal::float8),
                           4326)
                    ELSE NULL
                  END,
                  stg.record_hash, %s, true, %s, %s
                  FROM stg_ageeml stg
                 WHERE NOT EXISTS (
                     SELECT 1 FROM silver.localidad s
                      WHERE s.cvegeo      = stg.cvegeo
                        AND s.is_current
                        AND s.record_hash = stg.record_hash
                 )
                ON CONFLICT (cvegeo) WHERE is_current DO NOTHING
            """, [now, str(ingestion_id), source_file])
            inserted = cur.rowcount

            # --- 3. Cerrar CVEGEO ausentes del archivo (dentro del scope) ---
            removed = 0
            if mark_removals:
                cur.execute("""
                    UPDATE silver.localidad s
                       SET valid_to  = %s,
                           is_current = false,
                           estatus   = COALESCE(s.estatus, 'B')
                     WHERE s.is_current
                       AND s.cve_ent IN (SELECT DISTINCT cve_ent
                                           FROM stg_ageeml)
                       AND NOT EXISTS (
                           SELECT 1 FROM stg_ageeml stg
                            WHERE stg.cvegeo = s.cvegeo
                       )
                """, [now])
                removed = cur.rowcount

        return {'closed': closed, 'inserted': inserted, 'removed': removed}

    # ---------------------------------------------------------------

    def _refresh_mvs(self):
        if not connection.get_autocommit():
            connection.set_autocommit(True)
        self.stdout.write('Refrescando MVs (CONCURRENTLY)…')
        with connection.cursor() as cur:
            cur.execute(
                'REFRESH MATERIALIZED VIEW CONCURRENTLY gold.dim_localidad'
            )
            cur.execute(
                'REFRESH MATERIALIZED VIEW CONCURRENTLY gold.agg_municipio'
            )

    # ---------------------------------------------------------------

    def _mark_failed(self, ingestion_id, file_hash, path, row_count):
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """INSERT INTO bronze.file_ingestion
                          (ingestion_id, source_file, file_hash, file_path,
                           row_count, status)
                       VALUES (%s, %s, %s, %s, %s, 'failed')
                       ON CONFLICT (file_hash) DO UPDATE
                          SET status = 'failed'""",
                    [str(ingestion_id), path.name, file_hash, str(path),
                     row_count],
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
#  Helper COPY (funciona con psycopg2 por defecto en Django;
#  si usas psycopg3, reemplaza por cur.copy(sql) + cp.write_row(...))
# ---------------------------------------------------------------------------

def _copy(cur, sql, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    for r in rows:
        writer.writerow(['' if v is None else str(v) for v in r])
    payload = buf.getvalue()

    if hasattr(cur, "copy_expert"):
        # psycopg2
        cur.copy_expert(sql, io.StringIO(payload))
    else:
        # psycopg3
        with cur.copy(sql) as copy:
            copy.write(payload)
