# Contribuir

Gracias por ayudar. Antes de abrir un pull request:

1. `python build.py && python scripts/check_links.py dist` debe pasar sin errores.
2. Si agregas texto, agrégalo en **los cuatro** `i18n/*.json` (el build lo exige). Si no dominas un idioma, deja tu mejor versión y márcalo en el PR para revisión.
3. Respeta el sistema de diseño: usa los tokens (`var(--…)`), no colores sueltos; texto blanco solo sobre `blue`, `teal` y `navy`; el degradado solo como filete o secuencia de puntos.
4. Nunca subas datos personales (correos, teléfonos, exports del formulario). El historial de git es público y permanente.
