#!/usr/bin/env python3
"""Lee el calendario público de GECAL (.ics) y actualiza data/events.json.

    python scripts/importar_calendario.py                 # usa calendar_ics_url de data/site.json
    python scripts/importar_calendario.py --revisar       # muestra los cambios sin escribir
    python scripts/importar_calendario.py --url <ics>     # otro calendario
    python scripts/importar_calendario.py --archivo a.ics # un .ics ya descargado (sin red)
    python scripts/importar_calendario.py --estricto      # falla si el calendario no se puede leer

El calendario manda: título, fecha, hora, duración y enlace de la reunión salen de Google
Calendar. Lo que el calendario no sabe se escribe en la descripción del evento, una línea por
dato (se aceptan con o sin acentos, en español o en inglés):

    Expositor: Pablo Lichtig (CNEA, Argentina)
    Tipo: presentación            # presentación | reunión | club de lectura
    Hora de referencia: CO        # país de la hora que se anuncia; por defecto, la zona del calendario
    Grabación: https://youtu.be/… # se puede agregar después, acá o en data/events.json

El resto de la descripción se ignora, así que puede llevar el texto que se quiera.

Al reescribir data/events.json:
  · las reuniones que no vienen del calendario (sin "uid") se conservan intactas;
  · de las que sí vienen, se conserva lo cargado a mano que el calendario no trae
    ('recording', 'draft', títulos traducidos {es,en,fr,pt} y 'presenter' si la descripción no lo dice).

Solo biblioteca estándar.
"""
import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data/events.json"
SITE = ROOT / "data/site.json"

# Mismos países que build.py, más los alias de zona que usa Google (Córdoba, Salta, Recife…).
COUNTRY_TZ = {
    "AR": "America/Argentina/Buenos_Aires", "BO": "America/La_Paz", "BR": "America/Sao_Paulo", "CL": "America/Santiago",
    "CO": "America/Bogota", "CR": "America/Costa_Rica", "EC": "America/Guayaquil", "FR": "Europe/Paris",
    "MX": "America/Mexico_City", "PY": "America/Asuncion", "PE": "America/Lima",
}
TZ_COUNTRY = {tz: c for c, tz in COUNTRY_TZ.items()}
TZ_COUNTRY.update({
    "America/Argentina/Cordoba": "AR", "America/Argentina/Salta": "AR", "America/Argentina/Mendoza": "AR",
    "America/Argentina/Tucuman": "AR", "America/Argentina/Jujuy": "AR", "America/Argentina/Catamarca": "AR",
    "America/Argentina/La_Rioja": "AR", "America/Argentina/San_Juan": "AR", "America/Argentina/San_Luis": "AR",
    "America/Argentina/Rio_Gallegos": "AR", "America/Argentina/Ushuaia": "AR", "America/Buenos_Aires": "AR",
    "America/Recife": "BR", "America/Fortaleza": "BR", "America/Bahia": "BR", "America/Belem": "BR",
    "America/Santiago": "CL", "Pacific/Easter": "CL", "America/Tijuana": "MX", "America/Monterrey": "MX",
    "America/Cancun": "MX", "America/Merida": "MX", "America/Guatemala": "CR", "America/Panama": "CO",
    "America/Lima": "PE", "America/Guayaquil": "EC", "America/Asuncion": "PY", "America/La_Paz": "BO",
    "Europe/Paris": "FR", "UTC": "AR", "Etc/UTC": "AR",
})
COUNTRY_NAMES = {  # para "Hora de referencia: Colombia"
    "argentina": "AR", "bolivia": "BO", "brasil": "BR", "brazil": "BR", "chile": "CL", "colombia": "CO",
    "costa rica": "CR", "ecuador": "EC", "francia": "FR", "france": "FR", "mexico": "MX", "méxico": "MX",
    "paraguay": "PY", "peru": "PE", "perú": "PE",
}
TYPES = {
    "presentacion": "presentation", "presentation": "presentation", "charla": "presentation", "talk": "presentation",
    "reunion": "meeting", "meeting": "meeting", "asamblea": "meeting",
    "club de lectura": "reading", "lectura": "reading", "reading": "reading", "journal club": "reading",
}
MEETING_HOSTS = ("meet.google.com", "zoom.us", "teams.microsoft.com", "teams.live.com", "meet.jit.si", "whereby.com", "bbb.")
MAX_AHEAD = timedelta(days=460)   # hasta dónde se expanden las reuniones que se repiten
MAX_OCCURRENCES = 60
WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}

avisos = []


def aviso(msg):
    avisos.append(msg)


def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", sin_acentos(s).lower()).strip("-")


# ---------- Lectura del .ics ----------
def desdoblar(texto):
    """Une las líneas continuadas (RFC 5545: empiezan con espacio o tabulación)."""
    lineas = []
    for linea in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if linea[:1] in (" ", "\t") and lineas:
            lineas[-1] += linea[1:]
        else:
            lineas.append(linea)
    return lineas


def desescapar(v):
    out, i = [], 0
    while i < len(v):
        c = v[i]
        if c == "\\" and i + 1 < len(v):
            n = v[i + 1]
            out.append({"n": "\n", "N": "\n"}.get(n, n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parsear_vevents(texto):
    """Devuelve una lista de dicts: clave -> (valor, {parámetros}). Las claves repetidas se acumulan en listas."""
    eventos, actual = [], None
    for linea in desdoblar(texto):
        if linea == "BEGIN:VEVENT":
            actual = {}
            continue
        if linea == "END:VEVENT":
            if actual is not None:
                eventos.append(actual)
            actual = None
            continue
        if actual is None or ":" not in linea:
            continue
        izq, valor = linea.split(":", 1)
        partes = izq.split(";")
        nombre = partes[0].upper()
        params = {}
        for p in partes[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.upper()] = v.strip('"')
        actual.setdefault(nombre, []).append((desescapar(valor.strip()), params))
    return eventos


def val(ev, clave, por_defecto=""):
    return ev[clave][0][0] if clave in ev else por_defecto


def zona(tzid, respaldo):
    if not tzid:
        return respaldo
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError):
        aviso(f"zona horaria desconocida en el calendario: {tzid!r}; se usa {respaldo}")
        return respaldo


def momento(valor, params, tz_cal):
    """Convierte un DTSTART/DTEND/EXDATE. Devuelve (datetime con zona, es_dia_completo)."""
    v = valor.strip()
    if params.get("VALUE") == "DATE" or (len(v) == 8 and "T" not in v):
        d = date(int(v[:4]), int(v[4:6]), int(v[6:8]))
        return datetime(d.year, d.month, d.day, tzinfo=tz_cal), True
    if v.endswith("Z"):
        base = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    else:
        base = datetime.strptime(v, "%Y%m%dT%H%M%S").replace(tzinfo=zona(params.get("TZID"), tz_cal))
    return base, False


def regla(valor):
    return dict(p.split("=", 1) for p in valor.split(";") if "=" in p)


def repeticiones(inicio, rrule, exdates, desde_tz):
    """Expande RRULE de forma limitada: DAILY/WEEKLY/MONTHLY/YEARLY con INTERVAL, COUNT, UNTIL y BYDAY semanal."""
    r = regla(rrule)
    freq = r.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        aviso(f"repetición no soportada (FREQ={freq or '?'}): solo se toma la primera fecha")
        return [inicio]
    no_soportado = {k for k in r if k.startswith("BY")} - ({"BYDAY"} if freq == "WEEKLY" else set())
    if no_soportado:
        aviso(f"repetición con {', '.join(sorted(no_soportado))}: se expande sin esa condición, conviene revisar las fechas")
    interval = max(1, int(r.get("INTERVAL", 1) or 1))
    count = int(r["COUNT"]) if r.get("COUNT", "").isdigit() else None
    hasta = None
    if r.get("UNTIL"):
        try:
            hasta = momento(r["UNTIL"], {}, desde_tz)[0]
        except ValueError:
            aviso(f"UNTIL con formato raro: {r['UNTIL']!r}")
    dias = [WEEKDAYS[d[-2:]] for d in r.get("BYDAY", "").split(",") if d[-2:] in WEEKDAYS] if freq == "WEEKLY" else []
    tope = datetime.now(timezone.utc) + MAX_AHEAD

    # COUNT cuenta las fechas que genera la regla (RFC 5545); EXDATE se descuenta después.
    brutas, actual, n = [], inicio, 0
    while len(brutas) < min(count or MAX_OCCURRENCES, MAX_OCCURRENCES) and actual <= tope:
        grupo = [actual]
        if dias:  # semana de 'actual': los días pedidos, respetando la hora de inicio
            lunes = actual - timedelta(days=actual.weekday())
            grupo = [lunes + timedelta(days=d) for d in sorted(dias)]
        for f in grupo:
            if f < inicio or (hasta and f > hasta) or f > tope or f in brutas:
                continue
            brutas.append(f)
            if count and len(brutas) >= count:
                break
        n += 1
        if freq == "DAILY":
            actual = inicio + timedelta(days=interval * n)
        elif freq == "WEEKLY":
            actual = inicio + timedelta(weeks=interval * n)
        else:
            meses = interval * n * (12 if freq == "YEARLY" else 1)
            y, m = divmod(inicio.month - 1 + meses, 12)
            nuevo_mes, nuevo_anio = m + 1, inicio.year + y
            dia = min(inicio.day, [31, 29 if nuevo_anio % 4 == 0 and (nuevo_anio % 100 or nuevo_anio % 400 == 0) else 28,
                                   31, 30, 31, 30, 31, 31, 30, 31, 30, 31][nuevo_mes - 1])
            actual = inicio.replace(year=nuevo_anio, month=nuevo_mes, day=dia)
        if n > MAX_OCCURRENCES * 4:
            break
    return [f for f in sorted(set(brutas)) if not excluida(f, exdates)][:MAX_OCCURRENCES]


def excluida(f, exdates):
    """EXDATE puede venir en la zona del evento o en UTC."""
    formas = {f.strftime("%Y%m%dT%H%M%S"), f.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S"),
              f.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), f.date().isoformat(), f.strftime("%Y%m%d")}
    return bool(formas & exdates)


# ---------- Datos sueltos de la descripción ----------
def limpiar(texto):
    return html.unescape(re.sub(r"<[^>]+>", " ", texto)).replace("\xa0", " ")


def campos(descripcion):
    """Lee las líneas 'Clave: valor' de la descripción."""
    out = {}
    for linea in limpiar(descripcion).split("\n"):
        if ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        clave = sin_acentos(clave).strip().lower().strip("-•* ")
        valor = valor.strip()
        if not valor or len(clave) > 30:
            continue
        if clave in ("expositor", "expositora", "presenta", "presentador", "presentadora", "speaker", "presenter"):
            out.setdefault("presenter", valor)
        elif clave in ("tipo", "type"):
            out.setdefault("type", TYPES.get(sin_acentos(valor).lower()))
        elif clave in ("grabacion", "recording", "video"):
            out.setdefault("recording", valor)
        elif clave in ("hora de referencia", "referencia", "tz_ref", "reference time"):
            v = valor.strip()
            out.setdefault("tz_ref", v.upper() if v.upper() in COUNTRY_TZ else COUNTRY_NAMES.get(sin_acentos(v).lower()))
        elif clave in ("enlace", "link", "reunion", "sala", "url"):
            out.setdefault("link", valor)
    return {k: v for k, v in out.items() if v}


def enlace_reunion(ev, extra):
    if extra.get("link", "").startswith("http"):
        return extra["link"]
    for clave in ("X-GOOGLE-CONFERENCE", "LOCATION"):
        v = val(ev, clave)
        if v.startswith("http"):
            return v.split()[0]
    for texto in (val(ev, "DESCRIPTION"), val(ev, "LOCATION")):
        for url in re.findall(r"https?://[^\s<>\"']+", limpiar(texto)):
            if any(h in url for h in MEETING_HOSTS):
                return url.rstrip(".,;)")
    return None


# ---------- Armado ----------
def eventos_del_calendario(texto):
    tz_cal = zona(next((v for v, _ in parsear_cabecera(texto)), None), timezone.utc)
    salida, overrides = [], set()
    vevents = parsear_vevents(texto)

    for ev in vevents:  # primero las excepciones de una serie: pisan esa fecha de la serie
        if "RECURRENCE-ID" in ev:
            v, p = ev["RECURRENCE-ID"][0]
            try:
                overrides.add((val(ev, "UID"), momento(v, p, tz_cal)[0]))
            except ValueError:
                pass

    for ev in vevents:
        uid = val(ev, "UID")
        titulo = val(ev, "SUMMARY").strip()
        if val(ev, "STATUS").upper() == "CANCELLED":
            continue
        if not titulo or "DTSTART" not in ev or not uid:
            aviso(f"evento sin título, sin fecha o sin identificador: se omite ({titulo or uid or '¿?'})")
            continue
        v, p = ev["DTSTART"][0]
        try:
            inicio, dia_completo = momento(v, p, tz_cal)
        except ValueError:
            aviso(f"fecha con formato raro en «{titulo}»: {v!r}; se omite")
            continue
        if dia_completo:
            aviso(f"«{titulo}» está como evento de todo el día: se omite (una reunión necesita hora de inicio)")
            continue

        duracion = 90
        if "DTEND" in ev:
            try:
                fin = momento(ev["DTEND"][0][0], ev["DTEND"][0][1], tz_cal)[0]
                duracion = max(15, round((fin - inicio).total_seconds() / 60))
            except ValueError:
                pass

        extra = campos(val(ev, "DESCRIPTION"))
        tz_ref = extra.get("tz_ref") or TZ_COUNTRY.get(str(p.get("TZID") or getattr(inicio.tzinfo, "key", "")), "AR")
        link = enlace_reunion(ev, extra)
        base = {
            "type": extra.get("type") or ("presentation" if extra.get("presenter") else "meeting"),
            "title": titulo,
            "presenter": extra.get("presenter"),
            "tz_ref": tz_ref,
            "duration_min": duracion,
            "link": link,
            "recording": extra.get("recording"),
            "draft": False,
            "uid": uid,
            "source": "calendar",
        }

        exdates = {x.strip() for v2, p2 in ev.get("EXDATE", []) for x in v2.split(",")}
        exdates |= {x.replace("-", "").replace(":", "") for x in list(exdates)}
        fechas = [inicio]
        if "RRULE" in ev and "RECURRENCE-ID" not in ev:
            fechas = repeticiones(inicio, val(ev, "RRULE"), exdates, tz_cal)
        for f in fechas:
            if "RECURRENCE-ID" not in ev and (uid, f) in overrides:
                continue  # esa fecha de la serie tiene su propio evento
            local = f.astimezone(ZoneInfo(COUNTRY_TZ[tz_ref]))
            salida.append(dict(base, id=f"{local.date().isoformat()}-{slug(titulo)[:48] or 'reunion'}",
                               start=f.astimezone(ZoneInfo(COUNTRY_TZ[tz_ref])).isoformat()))
    return salida


def parsear_cabecera(texto):
    return [(l.split(":", 1)[1].strip(), {}) for l in desdoblar(texto) if l.upper().startswith("X-WR-TIMEZONE:")]


CONSERVAR = ("recording", "draft", "presenter")


def fusionar(nuevos, previos):
    """Mezcla lo que viene del calendario con lo cargado a mano en data/events.json."""
    por_clave = {}
    for ev in previos:
        if ev.get("uid"):
            por_clave[(ev["uid"], (ev.get("start") or "")[:10])] = ev
    salida = []
    for ev in nuevos:
        viejo = por_clave.get((ev["uid"], ev["start"][:10]), {})
        for campo in CONSERVAR:
            if not ev.get(campo) and viejo.get(campo):
                ev[campo] = viejo[campo]
        if isinstance(viejo.get("title"), dict):   # traducciones cargadas a mano
            traducciones = dict(viejo["title"])
            if traducciones.get("es") != ev["title"]:
                traducciones["es"] = ev["title"]   # el calendario manda el título en español
                aviso(f"«{ev['title']}»: el título cambió en el calendario, conviene revisar las traducciones en data/events.json")
            ev["title"] = traducciones
        for campo, valor in viejo.items():         # cualquier otro campo agregado a mano
            ev.setdefault(campo, valor)
        salida.append(ev)
    manuales = [ev for ev in previos if not ev.get("uid")]
    salida.sort(key=lambda e: e["start"], reverse=True)
    return salida + manuales


def descargar(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": "gecal-sitio/1.0 (+https://gecal26.github.io)"})
    with urllib.request.urlopen(pedido, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser(description="Actualiza data/events.json desde el calendario público de GECAL.")
    ap.add_argument("--url", help="dirección pública en formato iCal (por defecto, calendar_ics_url de data/site.json)")
    ap.add_argument("--archivo", help="leer un .ics local en vez de descargarlo")
    ap.add_argument("--revisar", action="store_true", help="mostrar los cambios sin escribir data/events.json")
    ap.add_argument("--estricto", action="store_true", help="terminar con error si el calendario no se puede leer")
    args = ap.parse_args()

    site = json.loads(SITE.read_text("utf-8"))
    url = args.url or site.get("calendar_ics_url")
    if not args.archivo and not url:
        print("Sin calendario: falta 'calendar_ics_url' en data/site.json. No se toca data/events.json.")
        return 1 if args.estricto else 0

    try:
        texto = Path(args.archivo).read_text("utf-8") if args.archivo else descargar(url)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        motivo = getattr(e, "code", None)
        extra = ("  El calendario parece no estar público: en la cuenta de GECAL, Configuración del calendario →\n"
                 "  Permisos de acceso → «Hacer disponible para el público», y copiar la «Dirección pública en formato iCal».") if motivo in (403, 404) else ""
        print(f"No se pudo leer el calendario ({e}).\n{extra}\n  Se deja data/events.json como está.".rstrip())
        return 1 if args.estricto else 0
    if "BEGIN:VCALENDAR" not in texto:
        print("Lo que devolvió esa dirección no es un calendario .ics. Se deja data/events.json como está.")
        return 1 if args.estricto else 0

    datos = json.loads(EVENTS.read_text("utf-8"))
    previos = datos["events"]
    nuevos = eventos_del_calendario(texto)
    datos["events"] = fusionar(nuevos, previos)

    for a in avisos:
        print(f"  aviso: {a}")
    ahora = datetime.now(timezone.utc)
    proximas = [e for e in datos["events"] if e.get("start") and datetime.fromisoformat(e["start"]) >= ahora]
    print(f"Calendario leído: {len(nuevos)} reuniones ({len(proximas)} próximas) "
          f"+ {len(datos['events']) - len(nuevos)} cargadas a mano.")
    for e in proximas[-3:][::-1]:
        print(f"  · {e['start'][:16].replace('T', ' ')} ({e['tz_ref']}) {e['title']}")

    nuevo_texto = json.dumps(datos, ensure_ascii=False, indent=2) + "\n"
    if args.revisar:
        print("--revisar: no se escribió nada." if nuevo_texto == EVENTS.read_text("utf-8") else "--revisar: data/events.json CAMBIARÍA.")
        return 0
    if nuevo_texto != EVENTS.read_text("utf-8"):
        EVENTS.write_text(nuevo_texto, encoding="utf-8")
        print("data/events.json actualizado.")
    else:
        print("data/events.json ya estaba al día.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
