# Videos brag v2 — ProjectApp

Dos videos de 60 segundos, 1920×1080, 30 fps, voz colombiana, música y subtítulos.
`brag-plan.md`, `composition-brief.md`, `provenance.json` y los guiones son las
fuentes de autoría. `content/` conserva las respuestas públicas usadas como
referencia; la composición recrea las fichas de CatalogView/ModuleDetails y
ProgramView a escala legible. No muestra datos de clientes.

## Herramienta y respaldo

Brag: https://github.com/latent-spaces/brag, commit
`c893c5ed52aed84e3e2ee56787de869fccdae6b0`. Se leyó y aplicó
`skills/brag/SKILL.md` y sus referencias de inspección, plan, composición,
audio y entrega; extensión a 45 segundos y voz autorizadas por el operador.

Copia completa local: `~/tools/brag`. Respaldo con historial y refs completos:
`~/tools/brag-20260925.bundle`, verificado con `git bundle verify`.
No se instaló una skill global ni se agregó brag al runtime de Nuxt.
Para recuperar: `git clone ~/tools/brag-20260925.bundle ~/tools/brag-restored`.
Para replicar: clonar upstream y hacer checkout del commit indicado.
La licencia MIT se conserva en `BRAG-LICENSE.txt`; música y SFX tienen sus créditos
propios en `shared/`. Este respaldo es local, no una copia fuera del host.

## Reproducir

Requisitos: Node >=22, `npm ci` en `explainers/`, FFmpeg/ffprobe, Chrome,
un venv separado con `pip install -r requirements-voice.txt` (`edge-tts==7.2.8`).
Se necesita conexión al servicio de voz de Microsoft Edge durante la producción.
La reproducción del MP4 no usa ese servicio. Kokoro y espeak-ng sólo hacen falta
para volver a producir los guiones históricos con proveedor local.
Ejecutar desde `explainers/`. Poner el bin del venv en PATH para narración.
Si Chrome ya está instalado, `HYPERFRAMES_BROWSER_PATH` permite reutilizarlo.
En esta producción se usó Chrome Headless Shell de Playwright (build 1234).

```bash
npm run sync -- --video additional-modules --edition brag-v2
npm run narration -- --video additional-modules --edition brag-v2
npm run check -- --video additional-modules --edition brag-v2 --json
npm run poster -- --video additional-modules --edition brag-v2 --at 0.1
npm run render -- --video additional-modules --edition brag-v2 --with-narration --music-volume 0.22 --priority 5
npm run export -- --video additional-modules --edition brag-v2
```

Repetir con `--video financing` (identificador interno conservado; nombre visible:
Programa de Alianza). Un worker por render y dos threads de codificación final.
`--priority` fija el nivel nice (0–19; default 15). En el host de desarrollo
compartido se usó 5 para evitar timeouts de arranque del CLI por falta de CPU.
Los intermediarios quedan ignorados por Git.
`--skip-render` permite remezclar audio sin repetir el render visual. Si cambia
el guion, los tiempos o los subtítulos, regenerar narración y render visual.
La portada se captura en 0.1 s (tras inicializar el timeline) y coincide con el inicio legible del video, sin
añadir duración, desplazar audio ni hacer parpadear el titular al reproducir.

## Actualizar contenido

`npm run content -- --edition brag-v2` refresca exclusivamente los snapshots v2.
Luego revisar guion y composición a mano: los datos son referencia editorial,
no un generador automático de claims. La API de producción puede ir por detrás
de la base de integración; `provenance.json` registra esa diferencia en esta
entrega (exclusividad conceptual ya presente en a292b253, todavía no desplegada
al capturar la API). Nunca editar políticas comerciales para hacerlas coincidir
con el video. Las cifras del guion deben verificarse contra la política vigente
y revisarse cuando cambie; la revisión editorial del 27 de septiembre documenta
la referencia del paquete mensual.

Narración: `narrationConfig` en cada guion fija proveedor `edge`, voz
`es-CO-SalomeNeural`, locale `es-CO`, velocidad 1 y lead de 0.2 s.
Se comprueba que la voz esté disponible antes de generar; no hay sustitución
automática de acento. Clips cacheados por texto, proveedor, voz, idioma, locale y velocidad; si una frase no
cabe se detiene la producción. Un fingerprint del guion, schedule y configuración de voz impide
mezclar narración vieja. Los subtítulos se distribuyen por frase dentro de la
duración medida, con tres segmentos separados para pagos/reservas/IA. Los
archivos temporales se validan antes de entrar a la caché. Los desbordes de
todas las escenas se reportan juntos, sin exportar una mezcla incompleta.

## Integración y reversión

`useExplainerVideos.js` importa `additional-modules-brag-v2-es.mp4` y
`financing-brag-v2-es.mp4`, sus portadas y 60 segundos de duración.
No hay render EN: las superficies en inglés siguen ocultando la tarjeta.
Para volver a v1, restaurar imports de MP4/WebP sin `-brag-v2` y duraciones 70/72.
Los assets originales siguen versionados; no se necesita regenerarlos.

La verificación de esta entrega se registra en `verification.md`.

## Revisiones

- **2026-09-26 — Protección de propiedad intelectual.** El video del catálogo
  destaca el módulo nuevo: la escena 4 pasa a «Nuevo en el catálogo» con su
  ficha y la escena 2 muestra su tarjeta con la etiqueta Nuevo. Mismo nombre de
  asset, duración, música, clics y portada; sin cambios en el frontend. La voz de
  la escena 4 va en dos `voiceSegments` (0 y 3.6 s) para alinear los subtítulos.
  Para reproducirla sin re-sintetizar las escenas intactas, copiar antes el caché
  `tts/additional-modules/es/` de un worktree que ya lo tenga. El copy sale de la
  migración `content.0259`: el snapshot de `content/` no se refrescó porque la
  API de producción todavía no tiene el módulo (ver `provenance.json`).

## Revisión editorial 2026-09-27

- Primeras dos pantallas del catálogo: cuatro tarjetas compactas cada una, sin
  repetir capacidades entre ellas. La primera conserva «Y mucho más»; reservas
  aparece en la segunda. «Landing page e identidad visual» agrupa dos módulos
  existentes sólo para la composición; «Aplicación móvil» representa la PWA.
- Los tres eslóganes se integran en apertura, recorrido y cierre. El eslogan de
  treinta días no altera las condiciones del catálogo ni de las propuestas.
- Alianza incorpora una escena propia (24–35 s) para el paquete de 60 horas
  mensuales de la opción a cinco años: requerimientos aprobados, desde
  producción, renovación mensual sin acumulación y acuerdo vigente/al día.
  El alcance se contrastó con `financing_program_service.py`; no se cambió la política.
- Ambos videos duran 60 s, comparten voz colombiana a velocidad natural y omiten
  la marca en narración/subtítulos; el logo y las URL permanecen visibles.
- La agenda del HTML gobierna las demostraciones, clics y progreso. Alianza
  conserva sus escenas previas y suma la explicación del paquete; su voz se
  regenera completa para evitar mezclas de acento.

## Igualdad de tarjetas 2026-09-28

Las cuadrículas de las primeras dos pantallas del catálogo igualan todas sus
tarjetas a la altura de la más alta de su propio grupo, incluidas ambas filas.
Se conservan anchos, tipografía, padding y espaciado del diseño compacto.
La regla se limita a `data-video="additional-modules"`; Alianza y propuestas
conservan su composición. Un cambio de CSS exige regenerar portada y MP4;
si guion, agenda y voz siguen intactos, se reutiliza el audio vigente con su
metadata de fingerprint, sin volver a sintetizar la narración.
