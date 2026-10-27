#!/usr/bin/env python3
"""Exporta del CSV del formulario de registro a los datos públicos de la web.

    python scripts/import_members.py export.csv [--photos]

Lee el CSV exportado de la hoja del formulario (más una columna "Publicar") y escribe:
  data/members.json  SOLO perfiles con Publicar = sí. Sin correo, teléfono ni propuestas de nombre.
  data/network.json  Agregados de TODOS los registros (conteos). No contiene datos personales.

El CSV con datos personales NO debe estar dentro del repo (el historial de git es público y permanente).
Las columnas se reconocen por el comienzo del encabezado, así que sirve el export tal cual del formulario.
Columna opcional "Idioma de la presentación" (es/en/fr/pt); por defecto es.
--as-of AAAA-MM-DD fija la fecha de corte de data/network.json (por defecto, hoy); úsala si los registros no cambiaron.
--photos descarga la foto (enlace de Drive compartido) de quien se publica y la guarda en 256x256 WebP.
"""
import csv
import io
import json
import re
import sys
import unicodedata
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").casefold().strip()


COLUMNS = {  # clave -> comienzo del encabezado normalizado
    "name": "nombre", "institution": "institucion", "role": "cargo", "country": "pais", "city": "ciudad",
    "linkedin": "linkedin", "orcid": "orcid", "areas": "area de trabajo", "tools": "herramientas",
    "other_affiliation": "otra afiliacion", "bio": "presentacion", "photo": "fotografia",
    "publish": "publicar", "bio_lang": "idioma de la presentacion",
}
COUNTRIES = {"argentina": "AR", "bolivia": "BO", "brasil": "BR", "brazil": "BR", "chile": "CL", "colombia": "CO", "costa rica": "CR",
             "ecuador": "EC", "francia": "FR", "france": "FR", "mexico": "MX", "paraguay": "PY", "peru": "PE"}
CITY_FALLBACK = {"paris": "FR"}  # el formulario pone "Otro" como país; se resuelve por ciudad conocida
AREAS = {  # normalizado -> slug (los nombres de i18n/*.json "areas")
    "calidad del aire urbana": "urban_aq", "modelacion atmosferica": "atm_modelling", "modelacion regional": "atm_modelling",
    "integracion con cmaq": "atm_modelling", "sensores de bajo costo": "low_cost", "monitoreo de calidad de aire": "monitoring",
    "monitoreo de calidad del aire": "monitoring", "inventarios de emisiones": "emissions", "especiacion": "emissions",
    "emisiones biogenicas": "biogenic", "quimica atmosferica": "chemistry", "salud y calidad del aire": "health",
    "observacion satelital": "satellite", "pronostico meteorologico y de calidad del aire": "forecasting",
}
TOOLS = {norm(t): t for t in (  # grafía canónica
    "WRF", "WRF-Chem", "CMAQ", "CHIMERE", "MEGAN", "HERMES", "AERMOD", "CALPUFF", "HYSPLIT", "EMEP", "MODIS", "Landsat",
    "Sentinel-5P", "GOES-19", "Meteosat", "Wingridds", "Python", "R", "Matlab", "HTML", "CSS", "JS", "TypeScript")}
TOOLS.update({"matlab": "Matlab", "controle de versoes com git": "Git", "machine learning python packages": "Python ML"})
YES = {"si", "sim", "yes", "oui", "true", "1", "x"}


def split(s):
    return [p.strip() for p in re.split(r"[,;\n]", s or "") if p.strip()]


def clean_orcid(s):
    m = re.search(r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]", s or "")
    return m.group(0).upper() if m else ""


def clean_linkedin(s):
    """Devuelve (url, motivo_si_se_descarta)."""
    s = (s or "").strip()
    if not s:
        return "", ""
    md = re.fullmatch(r"\[[^\]]*\]\((https?://[^)]+)\)\s*(.*)", s)
    if md:
        if md.group(2):
            return "", "enlace Markdown con texto sobrante"
        s = md.group(1)
    if not re.match(r"https?://", s):
        if re.match(r"(www\.|[a-z]{2}\.)?linkedin\.com/", s):
            s = "https://" + s
        else:
            return "", f"no es una URL de LinkedIn ({s!r})"
    s = re.sub(r"[?#].*$", "", s)
    return (s, "") if re.match(r"https://([a-z]{2,3}\.)?linkedin\.com/in/[^/\s]+/?$", s) else ("", "URL de LinkedIn con forma inesperada")


def fetch_photo(url, dest):
    from PIL import Image
    fid = re.search(r"[?&]id=([\w-]+)", url) or re.search(r"/d/([\w-]+)", url)
    if not fid:
        raise ValueError("enlace de Drive sin id")
    data = urllib.request.urlopen(f"https://drive.google.com/uc?export=download&id={fid.group(1)}", timeout=30).read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2, (im.width + s) // 2, (im.height + s) // 2)).resize((256, 256), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=82)


def main():
    argv = sys.argv[1:]
    as_of = argv[argv.index("--as-of") + 1] if "--as-of" in argv else date.today().isoformat()
    args = [a for a in argv if not a.startswith("--") and a != as_of]
    want_photos = "--photos" in argv
    if len(args) != 1:
        sys.exit(__doc__)
    rows = list(csv.DictReader(open(args[0], encoding="utf-8-sig", newline="")))
    heads = {}
    for h in rows[0]:
        for key, start in COLUMNS.items():
            if norm(h).startswith(start) and key not in heads:
                heads[key] = h
    missing = {"name", "country", "areas", "publish"} - heads.keys()
    if missing:
        sys.exit(f"Faltan columnas: {sorted(missing)}. Encabezados leídos: {list(rows[0])}")

    members, counts_country, counts_area, counts_tool, report = [], Counter(), Counter(), Counter(), []
    registered = 0
    for r in rows:
        g = lambda k: (r.get(heads[k]) or "").strip() if k in heads else ""
        name = re.sub(r"\s+", " ", g("name"))
        if not name:
            continue
        country = COUNTRIES.get(norm(g("country"))) or (CITY_FALLBACK.get(norm(g("city"))) if norm(g("country")) == "otro" else None)
        if not country:
            report.append(f"{name}: país no reconocido ({g('country')!r}); fila omitida")
            continue
        registered += 1
        areas = []
        for a in split(g("areas")):
            slug = AREAS.get(norm(a))
            if slug:
                if slug not in areas:
                    areas.append(slug)
            else:
                report.append(f"{name}: área desconocida {a!r} (agrégala a AREAS e i18n)")
        tools = []
        for x in split(g("tools")):
            x = TOOLS.get(norm(x), x)
            if x not in tools:
                tools.append(x)
        counts_country[country] += 1
        counts_area.update(areas)
        counts_tool.update(tools)

        if norm(g("publish")) not in YES:
            continue
        linkedin, why = clean_linkedin(g("linkedin"))
        if why:
            report.append(f"{name}: LinkedIn descartado, {why}")
        orcid = clean_orcid(g("orcid"))
        if g("orcid") and not orcid:
            report.append(f"{name}: ORCID descartado ({g('orcid')!r})")
        mid = re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-")
        photo = None
        if want_photos and g("photo"):
            dest = ROOT / "static/img/members" / f"{mid}.webp"
            try:
                fetch_photo(g("photo"), dest)
                photo = f"static/img/members/{mid}.webp"
            except Exception as e:  # sin foto no es un error: se muestran las iniciales
                report.append(f"{name}: foto no descargada ({e})")
        members.append({
            "id": mid, "name": name, "institution": g("institution"), "role": g("role"), "country": country, "city": g("city"),
            "areas": areas, "tools": tools, "other_affiliation": g("other_affiliation"), "bio": g("bio").replace("\r\n", "\n"),
            "bio_lang": g("bio_lang") or "es", "orcid": orcid, "linkedin": linkedin, "photo": photo,
        })

    (ROOT / "data/members.json").write_text(json.dumps(members, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    network = {"as_of": as_of, "members": registered, "countries": dict(sorted(counts_country.items())),
               "areas": dict(counts_area.most_common()), "tools": dict(counts_tool.most_common())}
    (ROOT / "data/network.json").write_text(json.dumps(network, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Registrados: {registered} · publicados: {len(members)} · países: {len(counts_country)} · áreas: {len(counts_area)}")
    for line in report:
        print("  aviso:", line)


if __name__ == "__main__":
    main()
