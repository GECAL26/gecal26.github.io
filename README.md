# GECAL · sitio web

Sitio de **GECAL** (Grupo de Estudio de la Calidad del Aire en Latinoamérica), en español, inglés, francés y portugués, con tema claro, oscuro o del sistema.
Es estático, gratuito de mantener (GitHub Pages + Actions) y sigue el sistema de diseño de GECAL.

## Páginas

| Página | Contenido |
|---|---|
| Inicio | Qué es GECAL, próxima reunión con la hora en cada país, últimas novedades, cifras de la red, países |
| Comunidad | Directorio filtrable (solo perfiles autorizados), países y herramientas más usadas |
| Actividades | Próximas reuniones y archivo, y cómo suscribirse al calendario del grupo |
| Novedades | Congresos, becas, cursos, seminarios y convocatorias de otras instituciones, con su fecha límite, más la lista de difusión por correo. Feed RSS en `/<idioma>/feed.xml` |
| Únete | Grupo de WhatsApp, formulario de registro, lista de correo y qué se publica y qué no |
| Acerca de | Antecedentes, objetivo y misión del grupo, quiénes lo integran (cifras y países calculados de los datos) y cómo funciona. Enlazada desde Inicio y el pie, no desde el menú |

## Cómo funciona

```
Calendario de GECAL (.ics público) ──importar_calendario.py──▶ data/events.json
                                                                     │
                            data/*.json  +  i18n/*.json  +  templates/  ──build.py──▶  dist/{es,en,fr,pt}/…
```

```bash
pip install -r requirements.txt
python build.py                       # genera dist/
python -m http.server -d dist 8000    # ver en http://localhost:8000
INCLUDE_DRAFTS=1 python build.py      # incluye eventos con "draft": true
python scripts/check_links.py dist    # enlaces internos rotos
```

Los CSS y JS se enlazan con `?v=<hash del contenido>`: GitHub Pages cachea 10 minutos y no permite fijar cabeceras, y sin versión un navegador podía mezclar HTML nuevo con CSS viejo (el mapa salía negro). El SVG del mapa lleva además colores de respaldo propios.
Los enlaces son relativos: el sitio funciona igual en `gecal26.github.io`, en una subruta o en un dominio propio.
`SITE_URL` fija la URL absoluta para `canonical`, `hreflang` y `sitemap.xml` (el workflow la toma de GitHub).

## Tareas habituales

**Agregar o cambiar una reunión.** Se carga en el **calendario de GECAL** (cuenta `gecal.latinoamerica@gmail.com`) y el sitio la toma de ahí:
el workflow lee todos los días la dirección pública en formato iCal (`calendar_ics_url` en `data/site.json`) y reescribe `data/events.json`.
Lo que el calendario no sabe se escribe en la **descripción** del evento, una línea por dato:

```
Expositor: Pablo Lichtig (CNEA, Argentina)
Tipo: presentación            # presentación | reunión | club de lectura
Hora de referencia: CO        # país de la hora que se anuncia; por defecto, la zona del calendario
Grabación: https://youtu.be/… # cuando exista
```

El enlace de la reunión sale de Google Meet, de la ubicación o de la descripción. Los eventos de todo el día y los cancelados se omiten.
Las reuniones que se repiten se expanden hasta 15 meses (`FREQ` diaria, semanal, mensual o anual, con `INTERVAL`, `COUNT`, `UNTIL` y excepciones).

```bash
python scripts/importar_calendario.py --revisar     # ver qué cambiaría
python scripts/importar_calendario.py               # actualizar data/events.json y commitear
```

Para que esto funcione, el calendario tiene que ser público: en Google Calendar de esa cuenta, Configuración del calendario →
Permisos de acceso → **Hacer disponible para el público**; la dirección pública en formato iCal está en "Integrar calendario".
Si el calendario no se puede leer, el workflow avisa y publica lo último que haya en `data/events.json`.

También se puede editar `data/events.json` a mano: las entradas **sin** `uid` (las reuniones viejas, sin hora) no se tocan nunca, y de las
que vienen del calendario se conservan `recording`, `draft` y los títulos traducidos `{es,en,fr,pt}`. El instante se da con su desfase
(`2026-10-28T11:30:00-05:00`) y `tz_ref` con el país de la hora de referencia. Las horas por país se calculan con la base de zonas IANA,
con el horario de verano de esa fecha. El workflow se ejecuta cada día y mueve solo las reuniones pasadas a "Anteriores".

**Cargar una novedad.** `data/news.json`: congresos, becas, cursos, seminarios y convocatorias **de otras instituciones** (las reuniones
del propio grupo van en el calendario). Hay dos ejemplos con `"draft": true`; reemplazarlos y poner `false`. Campos: `id`, `type`
(`congress`, `grant`, `course`, `seminar`, `call`, `other`), `title`, `org`, `place` o `virtual: true`, `when`, `summary`, `link`,
`published` y, si corresponde, `deadline`. `title`, `summary`, `place` y `when` aceptan texto o `{es,en,fr,pt}`.
La tarjeta muestra sola los días que faltan (en ámbar cuando quedan 15 o menos) y la novedad pasa a "Ya pasaron" después del `deadline`,
del `until` o a los 120 días de publicada. El build falla si falta un campo o una fecha está mal escrita.

**Mandar el boletín.** `scripts/boletin.py` arma el correo con lo que ya está publicado: las novedades vigentes y las próximas reuniones.

```bash
python scripts/boletin.py --dias 30                   # texto por pantalla
python scripts/boletin.py --html /tmp/boletin.html    # además, versión con formato
```

La versión con formato se abre en el navegador, se selecciona todo, se copia y se pega en un correo nuevo a la lista: Gmail conserva el
formato. El script no manda nada.

**Lista de difusión.** Es un grupo de Google. Para crearlo: <https://groups.google.com> → *Crear grupo* (por ejemplo `gecal-novedades`),
con la cuenta de GECAL; en la configuración, *Quién puede publicar* solo administradores y *Quién puede unirse* cualquiera que lo pida.
Después, en `data/site.json`, `news_group_url` (la página del grupo) y `news_group_email` (su dirección). Mientras estén en `null`, el
bloque de suscripción no se muestra. Con una dirección `@googlegroups.com`, el botón "Suscribirme por correo" escribe a
`<grupo>+subscribe@googlegroups.com`, que funciona sin cuenta de Google. Las direcciones de la lista no se guardan en este repositorio.

**Actualizar el directorio.** Los datos personales NO se guardan en este repo.

1. Exporta la hoja del formulario a CSV **fuera de esta carpeta** y agrega una columna `Publicar` con `Sí` solo para quien lo autorizó
   (opcional: `Idioma de la presentación` con `es`, `en`, `fr` o `pt`).
2. `python scripts/import_members.py /ruta/al/export.csv` (con `--photos` y `pip install -r requirements-import.txt` para descargar fotos). Con `--merge` se agregan solo las personas del CSV sin tocar a las demás ni `data/network.json`.
3. Revisa los avisos que imprime (LinkedIn o ORCID con formato inválido, áreas desconocidas) y el `git diff` de `data/`.
4. `data/members.json` queda **solo** con perfiles autorizados y sin correo ni teléfono. `data/network.json` guarda únicamente conteos.

**Textos de interfaz.** `i18n/<idioma>.json`. El build falla si algún idioma tiene claves de más o de menos que `es.json`.
Las traducciones al inglés, francés y portugués necesitan revisión de hablantes nativos.
Las presentaciones de cada persona se muestran en su idioma original; no se traducen.

**Enlaces del grupo.** `data/site.json`: WhatsApp, URL del formulario de registro (`form_url`; mientras sea `null` el paso no se muestra) y correo de contacto.
También el calendario (`calendar_id` para el botón de Google, `calendar_ics_url` para leerlo y para suscribirse desde otra aplicación con `webcal://`)
y la lista de difusión (`news_group_url`, `news_group_email`). También las listas de CHIMERE que se muestran en "Acerca de" (`chimere_users_url`, `chimsur_news_url`; sitios externos en inglés, la tarjeta se oculta si faltan).

**Nombre y sigla.** El nombre completo no se traduce (sistema de diseño). Se imprime con la macro `brand_name()` (iniciales G·E·C·A·L resaltadas) en la portada, en "Acerca de" y junto al logo en la cabecera a partir de 1100 px; la glosa traducida (`brand.gloss`) solo aparece en "Acerca de". Inicio incluye datos estructurados `Organization` (JSON-LD) con `alternateName: GECAL`.

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
