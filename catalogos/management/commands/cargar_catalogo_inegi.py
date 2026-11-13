import requests
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from catalogos.models import CatalogoGeografico

BASE_URL = "https://gaia.inegi.org.mx/wscatgeo/v2"

def _extraer_lista(respuesta_json):
    if isinstance(respuesta_json, list):
        return respuesta_json
    if isinstance(respuesta_json, dict):
        if 'datos' in respuesta_json:
            return respuesta_json['datos']
        if 'features' in respuesta_json:
            return respuesta_json['features']
    return []

class Command(BaseCommand):
    help = 'Descarga el catálogo geográfico (Estados, Municipios, Localidades) del INEGI'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando descarga del Catálogo Único de INEGI...")
        
        dicc_catalogo = {}

        # 1. Descargar Estados
        try:
            res = requests.get(f"{BASE_URL}/mgee/")
            res.raise_for_status()
            data_edos = _extraer_lista(res.json())
            
            if not data_edos:
                self.stdout.write(self.style.ERROR("La API no devolvió estados."))
                return
                
            self.stdout.write(f"✔ {len(data_edos)} Estados encontrados.")

            for edo in data_edos:
                props = edo.get('properties', edo)
                cve_ent = str(props.get('cvegeo', props.get('cve_ent', '')))
                nom_ent = props.get('nomgeo', props.get('nom_ent', 'Desconocido'))

                dicc_catalogo[cve_ent] = {
                    'cve_ent': cve_ent,
                    'nom_ent': nom_ent,
                    'cve_mun': None, 'nom_mun': None, 'cve_loc': None, 'nom_loc': None,
                    'latitud': props.get('latitud'), 'longitud': props.get('longitud')
                }

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al descargar estados: {e}"))
            return

        # 2. Iterar sobre CADA ESTADO (usando .copy() para no modificar el diccionario original)
        for cve_ent, info_ent in dicc_catalogo.copy().items():
            self.stdout.write(f"Descargando datos de {info_ent['nom_ent']} ({cve_ent})...")

            # Municipios
            try:
                res_muns = requests.get(f"{BASE_URL}/mgem/{cve_ent}")
                if res_muns.status_code == 200:
                    data_muns = _extraer_lista(res_muns.json())
                    for mun in data_muns:
                        props = mun.get('properties', mun)
                        cve_mun_completo = str(props.get('cvegeo', props.get('cve_ent', '')))
                        if len(cve_mun_completo) >= 5:
                            dicc_catalogo[cve_mun_completo] = {
                                'cve_ent': cve_mun_completo[:2],
                                'nom_ent': info_ent['nom_ent'],
                                'cve_mun': cve_mun_completo[2:5],
                                'nom_mun': props.get('nomgeo', props.get('nom_mun', 'Desconocido')),
                                'cve_loc': None, 'nom_loc': None,
                                'latitud': props.get('latitud'), 'longitud': props.get('longitud')
                            }
                time.sleep(0.2)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ Error en municipios de {cve_ent}: {e}"))

            # Localidades
            try:
                res_locs = requests.get(f"{BASE_URL}/mgloc/{cve_ent}")
                if res_locs.status_code == 200:
                    data_locs = _extraer_lista(res_locs.json())
                    for loc in data_locs:
                        props = loc.get('properties', loc)
                        cve_loc_completo = str(props.get('cvegeo', props.get('cve_loc', '')))
                        if len(cve_loc_completo) >= 9 and cve_loc_completo not in dicc_catalogo:
                            dicc_catalogo[cve_loc_completo] = {
                                'cve_ent': cve_loc_completo[:2],
                                'nom_ent': info_ent['nom_ent'],
                                'cve_mun': cve_loc_completo[2:5],
                                'nom_mun': None,
                                'cve_loc': cve_loc_completo[5:],
                                'nom_loc': props.get('nomgeo', props.get('nom_loc', 'Desconocido')),
                                'latitud': props.get('latitud'), 'longitud': props.get('longitud')
                            }
                time.sleep(0.2)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ Error en localidades de {cve_ent}: {e}"))

        # 3. Guardar en base de datos
        self.stdout.write("Guardando en base de datos (esto puede tardar un poco)...")
        registros = [CatalogoGeografico(**data) for data in dicc_catalogo.values()]
        
        with transaction.atomic():
            CatalogoGeografico.objects.all().delete()
            CatalogoGeografico.objects.bulk_create(registros, batch_size=5000, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(f"¡Catálogo completado! {len(registros)} registros insertados."))