# GECAL · sitio web

Sitio de **GECAL** (Grupo de Estudio de la Calidad del Aire en Latinoamérica), en español, inglés, francés y portugués, con tema claro, oscuro o del sistema.
Es estático, gratuito de mantener (GitHub Pages + Actions) y sigue el sistema de diseño de GECAL.

## Páginas

| Página | Contenido |
|---|---|
| Inicio | Qué es GECAL, próxima reunión con la hora en cada país, cifras de la red, países |
| Comunidad | Directorio filtrable (solo perfiles autorizados), países y herramientas más usadas |
| Actividades | Próximas reuniones y archivo |
| Únete | Grupo de WhatsApp, formulario de registro y qué se publica y qué no |

## Cómo funciona

```
data/*.json  +  i18n/*.json  +  templates/  ──build.py──▶  dist/{es,en,fr,pt}/…
```

```bash
pip install -r requirements.txt
python build.py                       # genera dist/
python -m http.server -d dist 8000    # ver en http://localhost:8000
INCLUDE_DRAFTS=1 python build.py      # incluye eventos con "draft": true
python scripts/check_links.py dist    # enlaces internos rotos
```

Los enlaces son relativos: el sitio funciona igual en `gecal26.github.io`, en una subruta o en un dominio propio.
`SITE_URL` fija la URL absoluta para `canonical`, `hreflang` y `sitemap.xml` (el workflow la toma de GitHub).

## Tareas habituales

**Agregar o cambiar una reunión.** Edita `data/events.json` (hay un ejemplo con `"draft": true`; quítalo o ponlo en `false`).
Se da el instante con su desfase (`2026-10-28T11:30:00-05:00`) y `tz_ref` con el país de la hora de referencia.
Las horas por país se calculan con la base de zonas IANA, con el horario de verano de esa fecha. El workflow se ejecuta cada día
y mueve solo las reuniones pasadas a "Anteriores".

**Actualizar el directorio.** Los datos personales NO se guardan en este repo.

1. Exporta la hoja del formulario a CSV **fuera de esta carpeta** y agrega una columna `Publicar` con `Sí` solo para quien lo autorizó
   (opcional: `Idioma de la presentación` con `es`, `en`, `fr` o `pt`).
2. `python scripts/import_members.py /ruta/al/export.csv` (con `--photos` y `pip install -r requirements-import.txt` para descargar fotos).
3. Revisa los avisos que imprime (LinkedIn o ORCID con formato inválido, áreas desconocidas) y el `git diff` de `data/`.
4. `data/members.json` queda **solo** con perfiles autorizados y sin correo ni teléfono. `data/network.json` guarda únicamente conteos.

**Textos de interfaz.** `i18n/<idioma>.json`. El build falla si algún idioma tiene claves de más o de menos que `es.json`.
Las traducciones al inglés, francés y portugués necesitan revisión de hablantes nativos.
Las presentaciones de cada persona se muestran en su idioma original; no se traducen.

**Enlaces del grupo.** `data/site.json`: WhatsApp, URL del formulario de registro (`form_url`; mientras sea `null` el paso no se muestra) y correo de contacto.

**Colores y tipografía.** `design/tokens.json` viene del sistema de diseño de GECAL. Tras cambiarlo: `python scripts/tokens_to_css.py`.
El **tema oscuro de la web se aparta del sistema a propósito**: en vez del navy de marca como fondo (saturación 90 %, muy intenso en pantalla) usa un azul pizarra desaturado, definido en `WEB_DARK` dentro de `scripts/tokens_to_css.py`. Los colores de marca y el tema claro no cambian.
Tras tocar cualquier color, `python scripts/check_contrast.py` verifica los contrastes WCAG en ambos temas.

**Mapa de países.** `data/map.json` (rutas SVG simplificadas) se genera una sola vez con `scripts/make_map.py` a partir de Natural Earth:
`npm pack world-atlas && tar xzf world-atlas-*.tgz && python scripts/make_map.py package/countries-50m.json`.
Los países resaltados y los números salen de `data/network.json`; no hace falta regenerar el mapa al cambiar los conteos. Francia va en un recuadro (su parte europea) y sus territorios de ultramar se dibujan en gris. Los territorios en disputa se dibujan como vienen en Natural Earth, sin etiquetas.

## Publicación

Settings → Pages → *Source*: **GitHub Actions**. Para que la web salga en `https://gecal26.github.io/` el repositorio debe llamarse `gecal26.github.io`.

## Licencias

Código MIT (`LICENSE`). Contenido CC BY 4.0. Logo y marca GECAL con uso reservado. Fuentes bajo OFL. Datos personales sin licencia abierta.
Detalle en `LICENSE-CONTENT`.
