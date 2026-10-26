#!/usr/bin/env python3
"""Comprueba que todo enlace y recurso interno de dist/ apunta a un archivo que existe.

    python scripts/check_links.py dist

Solo enlaces relativos (los externos no se consultan en CI para no volverlo frágil).
Sale con código 1 si hay alguno roto.
"""
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

root = Path(sys.argv[1] if len(sys.argv) > 1 else "dist").resolve()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ("href", "src"):
            if a.get(key):
                self.found.append(a[key])


broken, checked = [], 0
for page in sorted(root.rglob("*.html")):
    p = Links()
    p.feed(page.read_text(encoding="utf-8"))
    for ref in p.found:
        u = urlparse(ref)
        if u.scheme or u.netloc or ref.startswith(("#", "mailto:", "tel:")) or not u.path:
            continue
        target = (page.parent / unquote(u.path)).resolve()
        if target.is_dir():
            target = target / "index.html"
        checked += 1
        if not target.exists():
            broken.append(f"{page.relative_to(root)} -> {ref}")

print(f"{checked} enlaces internos comprobados, {len(broken)} rotos")
for b in broken:
    print("  ROTO:", b)
sys.exit(1 if broken else 0)
