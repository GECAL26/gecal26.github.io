#!/usr/bin/env python3
"""Genera el sitio estático de GECAL en dist/ (es, en, fr, pt).

    python build.py                      # producción: sin eventos en borrador
    INCLUDE_DRAFTS=1 python build.py     # incluye eventos con "draft": true
    SITE_URL=https://... python build.py # URL absoluta (canonical, hreflang, sitemap)
    BUILD_NOW=2026-10-27T12:00:00+00:00  # fija "ahora" para probar próximas/pasadas

Los enlaces entre páginas y a los assets son relativos: el sitio funciona igual en
gecal26.github.io, en gecal26.github.io/<repo>/ o en un dominio propio.
"""
import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import zoneinfo
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup

try:  # preferir el paquete tzdata (versión fijada en requirements.txt) a la base del sistema, que puede estar desactualizada
    import tzdata  # noqa: F401
    zoneinfo.reset_tzpath(to=[])
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
LANGS = ["es", "pt", "fr", "en"]  # orden del selector de idioma: español, portugués, francés, inglés
LANG_NATIVE = {"es": "Español", "en": "English", "fr": "Français", "pt": "Português"}
PAGES = {"home": "", "community": "community", "activities": "activities", "join": "join", "about": "about"}  # clave -> carpeta bajo /<lang>/
SITE_URL = os.environ.get("SITE_URL", "https://gecal26.github.io").rstrip("/")
DRAFTS = os.environ.get("INCLUDE_DRAFTS") == "1"
NOW = datetime.fromisoformat(os.environ["BUILD_NOW"]) if "BUILD_NOW" in os.environ else datetime.now(timezone.utc)

# Zona IANA de cada país. Brasil: hora de Brasilia (São Paulo); México: Ciudad de México; Chile: continental.
COUNTRY_TZ = {
    "AR": "America/Argentina/Buenos_Aires", "BO": "America/La_Paz", "BR": "America/Sao_Paulo", "CL": "America/Santiago",
    "CO": "America/Bogota", "CR": "America/Costa_Rica", "EC": "America/Guayaquil", "FR": "Europe/Paris",
    "MX": "America/Mexico_City", "PY": "America/Asuncion", "PE": "America/Lima",
}
COUNTRY_ORDER = sorted(COUNTRY_TZ)
COLORS = ["cyan", "blue", "teal", "green", "lime", "orange"]  # decorativos; el nombre del país siempre va escrito


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def sort_key(s):
    return strip_accents(s).lower()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", sort_key(s)).strip("-")


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def utc_label(offset):
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "−"  # U+2212, como exige el sistema (UTC−5)
    h, m = divmod(abs(minutes), 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")


def flat(d, prefix=""):
    for k, v in d.items():
        yield from flat(v, f"{prefix}{k}.") if isinstance(v, dict) else [f"{prefix}{k}"]


# ---------- Datos ----------
I18N = {l: json.loads((ROOT / "i18n" / f"{l}.json").read_text("utf-8")) for l in LANGS}
base_keys = set(flat(I18N["es"]))
for l in LANGS[1:]:
    keys = set(flat(I18N[l]))
    if keys != base_keys:
        raise SystemExit(f"i18n/{l}.json no coincide con es.json. Faltan: {sorted(base_keys - keys)}. Sobran: {sorted(keys - base_keys)}")

site = json.loads((ROOT / "data/site.json").read_text("utf-8"))
members_raw = json.loads((ROOT / "data/members.json").read_text("utf-8"))
net = json.loads((ROOT / "data/network.json").read_text("utf-8"))
events_raw = json.loads((ROOT / "data/events.json").read_text("utf-8"))["events"]
map_data = json.loads((ROOT / "data/map.json").read_text("utf-8"))
published = Counter(m["country"] for m in members_raw)
zone_codes = [c for c in site.get("zone_countries") or sorted(net["countries"]) if c in COUNTRY_TZ]


def make_t(lang):
    def lookup(key):
        v = I18N[lang]
        for part in key.split("."):
            v = v[part]
        return v

    def t(key, **kw):
        s = lookup(key)
        return Markup(s.format_map(kw) if kw else s)

    def t_list(key):
        return [Markup(s) for s in lookup(key)]

    return t, t_list, lookup


def fmt_date(d, lang, short=False):
    lk = make_t(lang)[2]
    return lk("date.fmt_short" if short else "date.fmt").format(
        weekday=lk("date.weekdays")[d.weekday()], day=d.day, month=lk("date.months")[d.month - 1], year=d.year)


YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}


def check_youtube(url, where):
    if url and not (url.startswith("https://") and url.split("/")[2] in YOUTUBE_HOSTS):
        raise SystemExit(f"data/events.json: {where}: 'recording' debe ser un enlace https de YouTube, no {url!r}")
    return url or ""


def event_views(lang):
    t = make_t(lang)[0]
    cname = I18N[lang]["countries"]
    upcoming, past_dated, past_undated = [], [], []
    for ev in events_raw:
        if ev.get("draft") and not DRAFTS:
            continue
        title = ev["title"]
        view = {
            "type": ev["type"], "link": ev.get("link") or "", "presenter": ev.get("presenter") or "",
            "recording": check_youtube(ev.get("recording"), ev["id"]),
            "title": title if isinstance(title, str) else title.get(lang) or title["es"],
            "date_text": "", "host_time": "", "host_text": "", "zones": [], "start": None,
        }
        if not ev.get("start"):  # reunión ya realizada: basta la fecha ("date"), sin inventar hora
            if ev.get("date"):
                d = date.fromisoformat(ev["date"])
                view.update(start=datetime(d.year, d.month, d.day, tzinfo=timezone.utc), date_text=fmt_date(d, lang))
                past_dated.append(view)
            else:
                past_undated.append(view)
            continue
        start = datetime.fromisoformat(ev["start"])
        host = start.astimezone(ZoneInfo(COUNTRY_TZ[ev["tz_ref"]]))
        boxes = {}
        for c in zone_codes:
            loc = start.astimezone(ZoneInfo(COUNTRY_TZ[c]))
            b = boxes.setdefault(loc.utcoffset(), {"time": loc.strftime("%H:%M"), "day_shift": (loc.date() - host.date()).days, "codes": []})
            b["codes"].append(c)
        view["zones"] = [{
            "time": boxes[off]["time"], "day_shift": boxes[off]["day_shift"], "utc": utc_label(off),
            "flags": "".join(flag(c) for c in sorted(boxes[off]["codes"])),
            "names": ", ".join(sorted((cname[c] for c in boxes[off]["codes"]), key=sort_key)),
        } for off in sorted(boxes)]
        view.update(start=start, date_text=fmt_date(host, lang), host_time=host.strftime("%H:%M"),
                    host_text=t("activities.host_time", country=cname[ev["tz_ref"]], utc=utc_label(host.utcoffset())))
        end = start + timedelta(minutes=ev.get("duration_min", 90))
        (upcoming if end >= NOW else past_dated).append(view)
    upcoming.sort(key=lambda e: e["start"])
    past_dated.sort(key=lambda e: e["start"], reverse=True)
    return upcoming, past_dated + past_undated


# ---------- Render ----------
env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
if DIST.exists():
    shutil.rmtree(DIST)
shutil.copytree(ROOT / "static", DIST / "static")
(DIST / ".nojekyll").write_text("")
# GitHub Pages cachea 10 min y no deja fijar cabeceras: sin versión en la URL, un navegador puede mezclar HTML nuevo con CSS viejo.
ASSET_V = {str(f.relative_to(DIST)): hashlib.sha1(f.read_bytes()).hexdigest()[:8] for f in (DIST / "static").rglob("*") if f.suffix in (".css", ".js")}

for lang in LANGS:
    t, t_list, lookup = make_t(lang)
    cname, aname = I18N[lang]["countries"], I18N[lang]["areas"]
    upcoming, past = event_views(lang)

    members = []
    for m in members_raw:
        m = dict(m)
        m["initials"] = (m["name"].split()[0][0] + m["name"].split()[-1][0]).upper()
        m["color"] = COLORS[sum(map(ord, m["id"])) % 6]
        m["tool_slugs"] = [slug(x) for x in m["tools"]]
        m["search"] = sort_key(" ".join([m["name"], m["institution"], m["role"], m["city"], m["other_affiliation"], cname[m["country"]],
                                         *m["tools"], *(aname[a] for a in m["areas"])]))
        members.append(m)
    members.sort(key=lambda m: sort_key(m["name"]))

    def plural(key, n):
        return t(key + ("_one" if n == 1 else "_other"), n=n)

    country_list = sorted(
        ({"code": c, "name": cname[c], "n": n, "color": COLORS[COUNTRY_ORDER.index(c) % 6], "n_text": plural("map.n", n),
          "published": published[c], "profiles_text": plural("map.profiles", published[c]) if published[c] else "",
          "label": f"{cname[c]} · {plural('map.n', n)}"} for c, n in net["countries"].items()),
        key=lambda c: sort_key(c["name"]))
    filter_countries = sorted(({"code": c, "name": cname[c]} for c in {m["country"] for m in members}), key=lambda c: sort_key(c["name"]))
    filter_areas = sorted(({"slug": a, "name": aname[a]} for a in {a for m in members for a in m["areas"]}), key=lambda a: sort_key(a["name"]))
    tools = {slug(x): x for m in members for x in m["tools"]}
    filter_tools = sorted(({"slug": s, "name": n} for s, n in tools.items()), key=lambda x: sort_key(x["name"]))
    top_tools = [{"name": n, "n": c, "pct": round(100 * c / net["members"])}
                 for n, c in sorted(net["tools"].items(), key=lambda kv: (-kv[1], sort_key(kv[0])))[:10]]

    names = sorted((cname[c] for c in net["countries"]), key=sort_key)
    countries_text = f"{', '.join(names[:-1])} {I18N[lang]['about']['conj']} {names[-1]}"

    for page, folder in PAGES.items():
        outdir = DIST / lang / folder

        def rel(path, outdir=outdir):
            return os.path.relpath(DIST / path, outdir)

        def asset(path, rel=rel):
            return f"{rel(path)}?v={ASSET_V[path]}"

        def link(page_key, l=None, lang=lang, outdir=outdir):
            r = os.path.relpath(DIST / (l or lang) / PAGES[page_key], outdir)
            return "./" if r == "." else r + "/"

        def abs_url(l, page=page):
            return f"{SITE_URL}/{l}/" + (PAGES[page] + "/" if PAGES[page] else "")

        key = page
        html = env.get_template(f"{page}.html").render(
            lang=lang, langs=LANGS, lang_names=LANG_NATIVE, page=page, t=t, t_list=t_list, rel=rel, asset=asset, link=link, abs_url=abs_url,
            site_url=SITE_URL, site=site, net=net, map_data=map_data, countries=cname, areas=aname,
            title=t(f"meta.{key}.title"), description=t(f"meta.{key}.desc"),
            members=members, countries_text=countries_text, country_list=country_list, filter_countries=filter_countries, filter_areas=filter_areas,
            filter_tools=filter_tools, top_tools=top_tools, upcoming=upcoming, past=past,
            next_event=upcoming[0] if upcoming else None,
            as_of_text=fmt_date(datetime.fromisoformat(net["as_of"]).date(), lang, short=True),
        )
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "index.html").write_text(html, encoding="utf-8")

# ---------- Raíz: redirección por idioma, 404, sitemap, robots ----------
links = " · ".join(f'<a href="{l}/" hreflang="{l}" lang="{l}">{LANG_NATIVE[l]}</a>' for l in LANGS)
(DIST / "index.html").write_text(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GECAL</title>
<link rel="canonical" href="{SITE_URL}/es/">
<noscript><meta http-equiv="refresh" content="0;url=es/"></noscript>
<script>
(function(){{var ok={{es:1,en:1,fr:1,pt:1}},s=null;try{{s=localStorage.getItem("gecal-lang")}}catch(e){{}}
var l=s||(navigator.language||"es").slice(0,2).toLowerCase();location.replace((ok[l]?l:"es")+"/"+location.hash)}})();
</script></head>
<body style="font-family:system-ui,sans-serif;padding:2rem"><p>{links}</p></body></html>
""", encoding="utf-8")
(DIST / "404.html").write_text(f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>404 · GECAL</title></head>
<body style="font-family:system-ui,sans-serif;padding:2rem"><h1>404</h1><p><a href="{SITE_URL}/">GECAL</a></p></body></html>
""", encoding="utf-8")

urls = []
for page, folder in PAGES.items():
    for l in LANGS:
        alt = "".join(f'<xhtml:link rel="alternate" hreflang="{x}" href="{SITE_URL}/{x}/{folder + "/" if folder else ""}"/>' for x in LANGS)
        urls.append(f'<url><loc>{SITE_URL}/{l}/{folder + "/" if folder else ""}</loc>{alt}</url>')
(DIST / "sitemap.xml").write_text(
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
    + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
(DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")

print(f"OK: {len(LANGS) * len(PAGES)} páginas en dist/ · {len(members_raw)} perfiles publicados · eventos próximos: {len(upcoming)} · SITE_URL={SITE_URL}")
