# catalogos/services/ageeml.py
import csv
import hashlib
from dataclasses import dataclass

CANONICAL_COLUMNS = [
    "CVEGEO", "Estatus", "CVE_ENT", "NOM_ENT", "NOM_ABR", "CVE_MUN", "NOM_MUN",
    "CVE_LOC", "NOM_LOC", "AMBITO", "LATITUD", "LONGITUD", "LAT_DECIMAL",
    "LON_DECIMAL", "ALTITUD", "CVE_CARTA", "POB_TOTAL", "POB_MASCULINA",
    "POB_FEMENINA", "TOTAL DE VIVIENDAS HABITADAS",
]
LOCALIDADES_HEADER = list(CANONICAL_COLUMNS)
CABECERAS_HEADER = [
    "CVEGEO", "CVE_ENT", "NOM_ENT", "NOM_ABR", "CVE_MUN", "NOM_MUN",
    "CVE_CAB", "NOM_CAB", "POB_TOTAL", "POB_MASCULINA", "POB_FEMENINA",
    "TOTAL DE VIVIENDAS HABITADAS",
]
NULL_MARKERS = {"", "-", "--", "----", "s/d", "N/D", "NA", "NULL"}


@dataclass
class ParsedRow:
    raw: dict          # strings crudos -> bronze
    norm: dict         # valores tipados -> stg_ageeml
    record_hash: str   # sha256 hex para SCD2


def _norm_header(h):
    return [c.strip().lstrip("\ufeff") for c in h]


def _detect_variant(header):
    h = _norm_header(header)
    if h == LOCALIDADES_HEADER:
        return "localidades"
    if h == CABECERAS_HEADER:
        return "cabeceras"
    raise ValueError(
        "Header inesperado.\n"
        f"  recibido:  {h}\n"
        f"  localidades esperado: {LOCALIDADES_HEADER}\n"
        f"  cabeceras esperado:   {CABECERAS_HEADER}"
    )


def _clean(v):
    if v is None:
        return None
    v = v.strip()
    return None if v in NULL_MARKERS else v


def _to_int(v):
    if v in (None, "", "-", "--", "----"):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v):
    if v in (None, "", "-", "--", "----"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pad4(v):
    if v is None:
        return "0001"
    v = str(v).strip()
    return v.zfill(4) if v.isdigit() else "0001"


def _build_norm(src, variant):
    if variant == "cabeceras":
        cve_ent = src.get("CVE_ENT")
        cve_mun = src.get("CVE_MUN")
        cve_loc = _pad4(src.get("CVE_CAB"))
        nom_loc = src.get("NOM_CAB") or src.get("NOM_MUN")
        estatus = "A"
        cvegeo_9 = f"{cve_ent}{cve_mun}{cve_loc}"
        lat_dms = src.get("LATITUD")
        lon_dms = src.get("LONGITUD")
    else:
        cve_ent = src.get("CVE_ENT")
        cve_mun = src.get("CVE_MUN")
        cve_loc = _pad4(src.get("CVE_LOC"))
        nom_loc = src.get("NOM_LOC")
        estatus = src.get("Estatus")
        cvegeo_9 = (src.get("CVEGEO") or "").ljust(9, "0")[:9]
        if not cve_ent:
            cve_ent = cvegeo_9[:2]
        if not cve_mun:
            cve_mun = cvegeo_9[2:5]
        if not cve_loc or cve_loc == "0001":
            cve_loc = _pad4(cvegeo_9[5:9])
        if not nom_loc:
            nom_loc = src.get("NOM_MUN")
        if not estatus:
            estatus = "A"
        lat_dms = src.get("LATITUD")
        lon_dms = src.get("LONGITUD")

    base = {
        "cvegeo": cvegeo_9,
        "estatus": estatus,
        "cve_ent": cve_ent,
        "nom_ent": src.get("NOM_ENT"),
        "nom_abr": src.get("NOM_ABR"),
        "cve_mun": cve_mun,
        "nom_mun": src.get("NOM_MUN"),
        "cve_loc": cve_loc,
        "nom_loc": nom_loc,
        "ambito": src.get("AMBITO"),
        "cve_carta": src.get("CVE_CARTA"),
    }

    raw = dict(base)
    raw.update({
        "latitud": lat_dms,
        "longitud": lon_dms,
        "lat_decimal_raw": src.get("LAT_DECIMAL"),
        "lon_decimal_raw": src.get("LON_DECIMAL"),
        "altitud_raw": src.get("ALTITUD"),
        "pob_total_raw": src.get("POB_TOTAL"),
        "pob_masculina_raw": src.get("POB_MASCULINA"),
        "pob_femenina_raw": src.get("POB_FEMENINA"),
        "total_viviendas_raw": src.get("TOTAL DE VIVIENDAS HABITADAS"),
    })

    norm = dict(base)
    norm.update({
        "latitud_dms": lat_dms,
        "longitud_dms": lon_dms,
        "lat_decimal": _to_float(src.get("LAT_DECIMAL")),
        "lon_decimal": _to_float(src.get("LON_DECIMAL")),
        "altitud": _to_int(src.get("ALTITUD")),
        "pob_total": _to_int(src.get("POB_TOTAL")),
        "pob_masculina": _to_int(src.get("POB_MASCULINA")),
        "pob_femenina": _to_int(src.get("POB_FEMENINA")),
        "total_viviendas": _to_int(src.get("TOTAL DE VIVIENDAS HABITADAS")),
    })

    return raw, norm


def _hash_norm(norm):
    payload = "|".join("" if v is None else str(v) for v in norm.values())
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_and_validate_file(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV vacío o sin header")
        variant = _detect_variant(reader.fieldnames)

        parsed, rejected = [], []
        for lineno, row in enumerate(reader, start=2):
            try:
                src = {k: _clean(v) for k, v in row.items() if k is not None}
                raw, norm = _build_norm(src, variant)
                if not norm["cvegeo"] or len(norm["cvegeo"]) != 9:
                    raise ValueError(f"cvegeo inválido: {norm['cvegeo']!r}")
                parsed.append(ParsedRow(
                    raw=raw, norm=norm, record_hash=_hash_norm(norm),
                ))
            except Exception as e:
                rejected.append((lineno, str(e)))

        return parsed, rejected