#!/usr/bin/env python3
"""Comprueba los contrastes WCAG de static/css/tokens.css en tema claro y oscuro.

    python scripts/check_contrast.py

Texto: mínimo 4.5:1. Bordes de control, foco y elementos gráficos: mínimo 3:1.
Sale con código 1 si algún par falla. Ejecútalo tras cambiar design/tokens.json o WEB_DARK.
"""
import re
import sys
from pathlib import Path

css = (Path(__file__).resolve().parent.parent / "static/css/tokens.css").read_text(encoding="utf-8")


def block(selector):
    body = css[css.index(selector + "{") + len(selector) + 1:]
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", body[:body.index("}")]))


light = block(":root")
dark = {**light, **block(':root[data-theme="dark"]')}


def resolve(theme, name):
    v = theme[name].strip()
    while v.startswith("var("):
        v = theme[v[6:-1]].strip()
    return v


def lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


SURFACES = ("surface-100", "surface-200", "surface-300")
PAIRS = []  # (primer plano, fondo, mínimo, ¿omitir en claro?)
for bg in SURFACES:
    PAIRS += [("ink", bg, 4.5, False), ("ink-muted", bg, 4.5, False), ("border-control", bg, 3, False), ("focus-ring", bg, 3, False)]
    # El sistema documenta que action y accent no se usan como texto sobre surface-300 en claro.
    PAIRS += [("action", bg, 4.5, bg == "surface-300"), ("accent", bg, 4.5, bg == "surface-300")]
PAIRS += [
    ("on-action", "action", 4.5, False), ("on-action", "action-hover", 4.5, False),
    ("on-deep", "hero-bg", 4.5, False), ("hero-accent", "hero-bg", 4.5, False), ("hero-line", "hero-bg", 3, False),
    ("cta-ink", "cta-bg", 4.5, False), ("cta-ink", "cta-hover", 4.5, False), ("cta-bg", "hero-bg", 3, False),
]

failed = 0
for label, theme in (("claro", light), ("oscuro", dark)):
    worst = None
    for fg, bg, need, skip_light in PAIRS:
        if skip_light and label == "claro":
            continue
        r = ratio(resolve(theme, fg), resolve(theme, bg))
        worst = min(worst or r, r)
        if r < need:
            failed += 1
            print(f"  FALLA [{label}] {fg} sobre {bg}: {r:.2f}:1 (mínimo {need}:1)")
    print(f"tema {label}: peor par = {worst:.2f}:1")
print("OK: todos los pares cumplen" if not failed else f"{failed} pares no cumplen")
sys.exit(1 if failed else 0)
