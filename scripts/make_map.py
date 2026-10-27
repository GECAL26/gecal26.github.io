#!/usr/bin/env python3
"""TopoJSON de world-atlas (Natural Earth, dominio público) -> data/map.json con rutas SVG simplificadas.

    npm pack world-atlas && tar xzf world-atlas-*.tgz
    python scripts/make_map.py package/countries-50m.json

Mapa principal: ventana sobre Latinoamérica, proyección equirrectangular con paralelo de referencia a 12° S.
Francia va en un recuadro aparte (su parte europea), fuera de escala; las partes de ultramar de Francia
(Guayana, Antillas) se dibujan como contexto gris, nunca como "Francia" resaltada.
Los territorios en disputa se dibujan tal como vienen en Natural Earth, sin etiquetas.
Solo se tocan los países de ISO; el resto es un único trazo de contexto.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ISO = {"032": "AR", "068": "BO", "076": "BR", "152": "CL", "170": "CO", "188": "CR", "218": "EC", "250": "FR",
       "484": "MX", "600": "PY", "604": "PE"}
# Punto de la etiqueta (lon, lat) de cada país; se comprueba que cae dentro del país.
LABEL = {"AR": (-65.0, -36.0), "BO": (-64.6, -16.8), "BR": (-53.0, -11.0), "CL": (-71.5, -35.5), "CO": (-73.0, 3.5),
         "CR": (-84.2, 10.0), "EC": (-78.5, -1.4), "MX": (-102.0, 23.5), "PY": (-58.4, -23.2), "PE": (-75.0, -9.2)}

LON_MIN, LON_MAX, LAT_N, LAT_S = -118.0, -32.0, 33.0, -57.0
S = 6.0                                    # unidades SVG por grado
K = math.cos(math.radians(-12))
W, H = round((LON_MAX - LON_MIN) * K * S, 1), round((LAT_N - LAT_S) * S, 1)
FR_BOX = (-6.0, 41.0, 10.0, 52.0)          # Francia europea (con Córcega): lon_min, lat_min, lon_max, lat_max
FR_K, FR_S = math.cos(math.radians(46.3)), 11.0
FR_LON0, FR_LAT0 = -5.2, 51.2


def main_xy(lon, lat):
    return (lon - LON_MIN) * K * S, (LAT_N - lat) * S


def inset_xy(lon, lat):
    return (lon - FR_LON0) * FR_K * FR_S, (FR_LAT0 - lat) * FR_S


def clip(pts, xmin, ymin, xmax, ymax):
    """Sutherland-Hodgman contra un rectángulo."""
    def step(pts, inside, inter):
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if inside(p):
                if not inside(q):
                    out.append(inter(q, p))
                out.append(p)
            elif inside(q):
                out.append(inter(q, p))
        return out
    ix = lambda x: lambda q, p: (x, q[1] + (p[1] - q[1]) * (x - q[0]) / (p[0] - q[0]))
    iy = lambda y: lambda q, p: (q[0] + (p[0] - q[0]) * (y - q[1]) / (p[1] - q[1]), y)
    for inside, inter in ((lambda p: p[0] >= xmin, ix(xmin)), (lambda p: p[0] <= xmax, ix(xmax)),
                          (lambda p: p[1] >= ymin, iy(ymin)), (lambda p: p[1] <= ymax, iy(ymax))):
        pts = step(pts, inside, inter)
        if not pts:
            return []
    return pts


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            x, y = pts[i]
            d = abs(dy * (x - x1) - dx * (y - y1)) / norm if norm else math.hypot(x - x1, y - y1)
            if d > best:
                best, idx = d, i
        if best > eps:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2


def rings_to_path(polys, project, box, eps, min_area):
    parts = []
    for poly in polys:
        for r in poly:
            pts = r[:-1] if r[0] == r[-1] else r
            if max(q[0] for q in pts) - min(q[0] for q in pts) > 180:
                continue  # cruza el antimeridiano (Fiyi, Rusia, Antártida): al recortarse dejaría un filo horizontal
            if box:
                pts = clip(pts, *box)
            if len(pts) < 3:
                continue
            pts = rdp([project(*p) for p in pts], eps)
            pts = [(round(x, 1), round(y, 1)) for x, y in pts]
            pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
            if len(pts) >= 3 and abs(area(pts)) >= min_area:
                parts.append("M" + " ".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
    return "".join(parts)


def point_in(pt, polys):
    inside = False
    for poly in polys:
        for r in poly:
            for i in range(len(r)):
                (x1, y1), (x2, y2) = r[i - 1], r[i]
                if (y1 > pt[1]) != (y2 > pt[1]) and pt[0] < (x2 - x1) * (pt[1] - y1) / (y2 - y1) + x1:
                    inside = not inside
    return inside


topo = json.loads(Path(sys.argv[1]).read_text())
sx, sy = topo["transform"]["scale"]
tx, ty = topo["transform"]["translate"]
arcs = []
for arc in topo["arcs"]:
    x = y = 0
    pts = []
    for dx, dy in arc:
        x, y = x + dx, y + dy
        pts.append((x * sx + tx, y * sy + ty))
    arcs.append(pts)


def ring(idx):
    pts = []
    for i in idx:
        a = arcs[i] if i >= 0 else arcs[~i][::-1]
        pts.extend(a if not pts else a[1:])
    return pts


def polygons(g):
    polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
    return [[ring(r) for r in poly] for poly in polys]


window = (LON_MIN - 1, LAT_S - 1, LON_MAX + 1, LAT_N + 1)
context_polys, country_polys, fr_inset = [], {}, []
for g in topo["objects"]["countries"]["geometries"]:
    code = ISO.get(g.get("id"))
    polys = polygons(g)
    if code == "FR":
        for poly in polys:
            lon = sum(p[0] for p in poly[0]) / len(poly[0])
            lat = sum(p[1] for p in poly[0]) / len(poly[0])
            (fr_inset if FR_BOX[0] <= lon <= FR_BOX[2] and FR_BOX[1] <= lat <= FR_BOX[3] else context_polys).append(poly)
    elif code:
        country_polys[code] = polys
    else:
        context_polys += polys

for code, pt in LABEL.items():
    assert point_in(pt, country_polys[code]), f"la etiqueta de {code} cae fuera del país"

out = {
    "w": W, "h": H,
    "context": rings_to_path(context_polys, main_xy, window, 0.45, 0.8),
    "countries": {c: rings_to_path(p, main_xy, window, 0.4, 0.5) for c, p in sorted(country_polys.items())},
    "labels": {c: [round(v, 1) for v in main_xy(*pt)] for c, pt in LABEL.items()},
}
fw = round((FR_BOX[2] - FR_LON0) * FR_K * FR_S + 6)
fh = round((FR_LAT0 - FR_BOX[1]) * FR_S + 6)
out["inset"] = {"w": fw, "h": fh, "d": rings_to_path(fr_inset, lambda lo, la: (inset_xy(lo, la)[0] + 3, inset_xy(lo, la)[1] + 3), None, 0.35, 0.3),
                "label": [round(inset_xy(2.4, 46.6)[0] + 3, 1), round(inset_xy(2.4, 46.6)[1] + 3, 1)]}
dest = ROOT / "data/map.json"
dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print(f"data/map.json: {dest.stat().st_size / 1024:.0f} KB · viewBox {W}x{H} · recuadro {fw}x{fh} · "
      f"contexto {len(out['context']) / 1024:.0f} KB · países {len(out['countries'])}")
