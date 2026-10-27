#!/usr/bin/env python3
"""design/tokens.json -> static/css/tokens.css y static/css/fonts.css.

El sistema de diseño de GECAL es la fuente de verdad: no se editan a mano
los CSS generados. Para actualizar los tokens, reemplazar design/tokens.json
y volver a ejecutar este script.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tokens = json.loads((ROOT / "design/tokens.json").read_text(encoding="utf-8"))

# Variables propias de la web (no están en el sistema): piezas que dependen del tema.
# hero-*: bloque expresivo (portada y bandas). cta-*: botón primario sobre ese bloque.
EXTRAS = {
    "hero-bg": ("var(--navy)", "#16223a"),
    "hero-accent": ("var(--cyan)", "#74c3ea"),
    "hero-line": ("#7f98c4", "#8497ba"),
    "cta-bg": ("var(--cyan)", "var(--action)"),
    "cta-ink": ("var(--on-bright)", "var(--on-action)"),
    "cta-hover": ("#5cc6f4", "var(--action-hover)"),
}

# DESVIACIÓN DELIBERADA del sistema, solo para el tema oscuro de la web.
# El oscuro del sistema usa el navy de marca (#042050, saturación HSL 90 %) como fondo; en pantalla resulta
# muy intenso y el cian de acción (#12afeb) suma brillo. Aquí se usa un azul pizarra desaturado (~45 %) y un
# cian más suave. Los colores de marca (navy, blue, teal, cyan, green, lime, orange) y el tema claro no cambian.
# Los contrastes se verifican con scripts/check_contrast.py.
WEB_DARK = {
    "surface-100": "#0d1524", "surface-200": "#141f33", "surface-300": "#1d2b45",
    "ink": "#e6ecf5", "ink-muted": "#a9b8d0", "line": "#2a3a56", "border-control": "#8497ba",
    "action": "#5db9e8", "action-hover": "#8accf0", "on-action": "#0d1524", "focus-ring": "#5db9e8",
    "accent": "#58c5bd",
}

light, dark = {}, {}
for t in tokens["color"]["tokens"]:
    v = t["value"]
    if isinstance(v, dict):
        light[t["name"]], dark[t["name"]] = v["light"], v["dark"]
    else:
        light[t["name"]] = v
for name, (l, d) in EXTRAS.items():
    light[name], dark[name] = l, d
for name, value in WEB_DARK.items():
    assert name in dark, f"WEB_DARK: token desconocido {name}"
    dark[name] = value

# Alias "{blue}" -> var(--blue)
def resolve(v):
    return f"var(--{v[1:-1]})" if v.startswith("{") else v

static = {}
for fam in ("spacing", "radius"):
    for t in tokens[fam]["tokens"]:
        static[t["name"]] = t["value"]
for k, v in tokens["type"]["families"].items():
    static[f"font-{k}"] = v

def block(selector, props):
    body = "".join(f"  --{k}:{resolve(v)};\n" for k, v in props.items())
    return f"{selector}{{\n{body}}}\n"

shadow_l = {t["name"]: t["value"]["light"] for t in tokens["shadow"]["tokens"]}
shadow_d = {t["name"]: t["value"]["dark"] for t in tokens["shadow"]["tokens"]}

out = "/* Generado por scripts/tokens_to_css.py desde design/tokens.json. No editar a mano. */\n"
out += block(":root", {**static, **light, **shadow_l}).replace(":root{", ":root{\n  color-scheme:light dark;", 1)
out += "@media (prefers-color-scheme: dark){\n"
out += block(':root:not([data-theme="light"])', {**dark, **shadow_d}).replace("\n", "\n  ").rstrip(" ")
out += "}\n"
out += block(':root[data-theme="dark"]', {**dark, **shadow_d})
out += ':root[data-theme="light"]{color-scheme:light}\n:root[data-theme="dark"]{color-scheme:dark}\n'
(ROOT / "static/css/tokens.css").write_text(out, encoding="utf-8")

# Fuentes autoalojadas (OFL). Rangos unicode: los mismos de Google Fonts para latin / latin-ext.
LATIN = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
LATIN_EXT = "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"
FACES = [
    ("Montserrat", "montserrat", (500, 600, 700, 800)),
    ("Source Sans 3", "source-sans-3", (400, 600, 700)),
    ("IBM Plex Mono", "ibm-plex-mono", (400,)),
]
fonts = "/* Generado por scripts/tokens_to_css.py. Fuentes bajo SIL OFL 1.1 (ver static/fonts/LICENSE-*). */\n"
for family, slug, weights in FACES:
    for w in weights:
        for subset, rng in (("latin-ext", LATIN_EXT), ("latin", LATIN)):
            fonts += (
                f'@font-face{{font-family:"{family}";font-style:normal;font-weight:{w};font-display:swap;'
                f'src:url("../fonts/{slug}-{subset}-{w}-normal.woff2") format("woff2");unicode-range:{rng}}}\n'
            )
(ROOT / "static/css/fonts.css").write_text(fonts, encoding="utf-8")
print("tokens.css y fonts.css generados")
