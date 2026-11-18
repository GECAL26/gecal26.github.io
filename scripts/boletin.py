#!/usr/bin/env python3
"""Arma el boletín de la lista de difusión con lo que ya está publicado en el sitio.

    python scripts/boletin.py                        # novedades de los últimos 30 días + próximas reuniones
    python scripts/boletin.py --desde 2026-11-01     # desde una fecha
    python scripts/boletin.py --dias 60
    python scripts/boletin.py --ids beca-x,curso-y   # solo esas novedades
    python scripts/boletin.py --sin-reuniones        # sin la sección de reuniones del grupo
    python scripts/boletin.py --idioma pt
    python scripts/boletin.py --html boletin.html    # además, versión con formato para pegar en Gmail

Imprime el asunto y el cuerpo en texto. Con --html deja un archivo para abrir en el navegador,
seleccionar todo (Ctrl+A), copiar y pegar en un correo nuevo a la lista: Gmail conserva el formato.
No manda nada ni toca el sitio. Solo biblioteca estándar.
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://gecal26.github.io"


def cargar(nombre):
    return json.loads((ROOT / nombre).read_text("utf-8"))


def texto(valor, lang):
    return valor if isinstance(valor, str) else (valor.get(lang) or valor["es"])


def fecha_larga(d, i18n, corta=True):
    f = i18n["date"]["fmt_short" if corta else "fmt"]
    return f.format(weekday=i18n["date"]["weekdays"][d.weekday()], day=d.day,
                    month=i18n["date"]["months"][d.month - 1], year=d.year)


def main():
    ap = argparse.ArgumentParser(description="Arma el boletín de novedades de GECAL.")
    ap.add_argument("--desde", help="fecha AAAA-MM-DD: novedades publicadas desde ese día")
    ap.add_argument("--dias", type=int, default=30, help="novedades de los últimos N días (por defecto 30)")
    ap.add_argument("--ids", help="lista de ids separados por coma, en vez de filtrar por fecha")
    ap.add_argument("--idioma", default="es", choices=["es", "en", "fr", "pt"])
    ap.add_argument("--sin-reuniones", action="store_true", help="no incluir las próximas reuniones del grupo")
    ap.add_argument("--html", help="archivo donde dejar la versión con formato")
    args = ap.parse_args()

    lang = args.idioma
    i18n = cargar(f"i18n/{lang}.json")
    site = cargar("data/site.json")
    hoy = datetime.now(timezone.utc).date()
    desde = date.fromisoformat(args.desde) if args.desde else hoy - timedelta(days=args.dias)
    ids = {x.strip() for x in args.ids.split(",")} if args.ids else None

    novedades = []
    for it in cargar("data/news.json")["news"]:
        if it.get("draft"):
            continue
        if ids is not None:
            if it["id"] not in ids:
                continue
        elif date.fromisoformat(it["published"]) < desde:
            continue
        limite = date.fromisoformat(it["deadline"]) if it.get("deadline") else None
        if limite and limite < hoy:
            continue  # ya cerró: no tiene sentido anunciarla
        novedades.append((it, limite))
    novedades.sort(key=lambda x: (x[1] or date.max, x[0]["published"]))

    reuniones = []
    if not args.sin_reuniones:
        ahora = datetime.now(timezone.utc)
        for ev in cargar("data/events.json")["events"]:
            if ev.get("draft") or not ev.get("start"):
                continue
            inicio = datetime.fromisoformat(ev["start"])
            if inicio >= ahora:
                reuniones.append((ev, inicio))
        reuniones.sort(key=lambda x: x[1])

    if not novedades and not reuniones:
        print("No hay novedades ni reuniones para incluir. Probá con --dias 90 o cargá novedades en data/news.json.",
              file=sys.stderr)
        return 1

    nt = i18n["news"]["types"]
    pagina = f"{SITE_URL}/{lang}/news/"
    asunto = f"GECAL · {i18n['news']['overline']}: " + ", ".join(
        dict.fromkeys(nt[it["type"]].lower() for it, _ in novedades[:3])) if novedades else f"GECAL · {i18n['activities']['upcoming'].lower()}"
    if len(novedades) > 3:
        asunto += " y más"

    # ---- texto plano ----
    L = [asunto, "=" * len(asunto), ""]
    if novedades:
        L += [i18n["news"]["title"].upper(), ""]
        for it, limite in novedades:
            datos = [x for x in (it.get("org"), texto(it["place"], lang) if it.get("place") else (i18n["news"]["virtual"] if it.get("virtual") else None),
                                 texto(it["when"], lang) if it.get("when") else None) if x]
            L.append(f"· [{nt[it['type']]}] {texto(it['title'], lang)}")
            if datos:
                L.append(f"  {' · '.join(datos)}")
            if limite:
                dias = (limite - hoy).days
                queda = i18n["news"]["last_day"] if dias == 0 else i18n["news"]["days_one" if dias == 1 else "days_other"].format(n=dias)
                L.append(f"  {i18n['news']['deadline'].format(date=fecha_larga(limite, i18n))} ({queda})")
            if it.get("summary"):
                L.append(f"  {texto(it['summary'], lang)}")
            if it.get("link"):
                L.append(f"  {it['link']}")
            L.append("")
    if reuniones:
        L += [i18n["activities"]["upcoming"].upper(), ""]
        for ev, inicio in reuniones:
            titulo = texto(ev["title"], lang)
            L.append(f"· {fecha_larga(inicio.date(), i18n)}, {inicio:%H:%M} ({i18n['countries'][ev['tz_ref']]})")
            L.append(f"  {titulo}" + (f" — {ev['presenter']}" if ev.get("presenter") else ""))
            if ev.get("link"):
                L.append(f"  {ev['link']}")
            L.append("")
        L.append(f"{i18n['activities']['title']}: {SITE_URL}/{lang}/activities/")
        L.append("")
    L.append(f"{i18n['news']['title']}: {pagina}")
    if site.get("news_group_email"):
        L.append(f"Para darse de baja: {site['news_group_email'].replace('@', '+unsubscribe@')}")
    cuerpo = "\n".join(L)

    print(f"ASUNTO: {asunto}\n")
    print(cuerpo)

    # ---- versión con formato ----
    if args.html:
        H = ['<!doctype html><meta charset="utf-8">',
             f"<title>{escape(asunto)}</title>",
             '<div style="font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color:#15233b;max-width:640px">']
        if novedades:
            H.append(f'<h2 style="font-size:20px;color:#0b2a4a;border-bottom:3px solid #0775b7;padding-bottom:6px">{escape(i18n["news"]["title"])}</h2>')
            for it, limite in novedades:
                datos = [x for x in (it.get("org"), texto(it["place"], lang) if it.get("place") else (i18n["news"]["virtual"] if it.get("virtual") else None),
                                     texto(it["when"], lang) if it.get("when") else None) if x]
                H.append('<div style="margin:0 0 22px">')
                H.append(f'<div style="font:600 12px/16px sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#0d8484">{escape(nt[it["type"]])}</div>')
                H.append(f'<div style="font-size:18px;font-weight:700;margin:2px 0 4px">{escape(texto(it["title"], lang))}</div>')
                if datos:
                    H.append(f'<div style="color:#44587a;font-size:14px">{escape(" · ".join(datos))}</div>')
                if limite:
                    dias = (limite - hoy).days
                    queda = i18n["news"]["last_day"] if dias == 0 else i18n["news"]["days_one" if dias == 1 else "days_other"].format(n=dias)
                    color = "#86550a" if dias <= 15 else "#1c7230"
                    H.append(f'<div style="color:{color};font-size:14px;font-weight:600">'
                             f'{escape(i18n["news"]["deadline"].format(date=fecha_larga(limite, i18n)))} ({escape(queda)})</div>')
                if it.get("summary"):
                    H.append(f'<div style="margin:6px 0">{escape(texto(it["summary"], lang))}</div>')
                if it.get("link"):
                    H.append(f'<div><a href="{escape(it["link"])}" style="color:#0775b7">{escape(i18n["news"]["link"])}</a></div>')
                H.append("</div>")
        if reuniones:
            H.append(f'<h2 style="font-size:20px;color:#0b2a4a;border-bottom:3px solid #0775b7;padding-bottom:6px">{escape(i18n["activities"]["upcoming"])}</h2>')
            for ev, inicio in reuniones:
                H.append('<div style="margin:0 0 18px">')
                H.append(f'<div style="font-weight:700">{escape(fecha_larga(inicio.date(), i18n))}, {inicio:%H:%M} '
                         f'({escape(i18n["countries"][ev["tz_ref"]])})</div>')
                H.append(f'<div>{escape(texto(ev["title"], lang))}'
                         + (f' — <span style="color:#44587a">{escape(ev["presenter"])}</span>' if ev.get("presenter") else "") + "</div>")
                if ev.get("link"):
                    H.append(f'<div><a href="{escape(ev["link"])}" style="color:#0775b7">{escape(i18n["activities"]["join_meeting"])}</a></div>')
                H.append("</div>")
        H.append(f'<p style="color:#44587a;font-size:13px;border-top:1px solid #d7e2ee;padding-top:10px">'
                 f'<a href="{pagina}" style="color:#0775b7">{escape(i18n["news"]["title"])}</a>'
                 + (f' · <a href="mailto:{escape(site["news_group_email"].replace("@", "+unsubscribe@"))}" style="color:#44587a">baja</a>'
                    if site.get("news_group_email") else "") + "</p></div>")
        Path(args.html).write_text("\n".join(H), encoding="utf-8")
        print(f"\n[versión con formato en {args.html}: abrirla en el navegador, Ctrl+A, Ctrl+C y pegar en el correo]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
