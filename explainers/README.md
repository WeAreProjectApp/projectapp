# Videos explicativos (brag + HyperFrames)

La edición activa es **brag v2**: dos piezas de 60 segundos en español latinoamericano, con
voz Kokoro, música rítmica cálida, subtítulos y recursos de marca. Abren las
vistas públicas de Módulos adicionales y Programa de Alianza, y el panel
reutiliza el mismo reproductor. Los interruptores globales y por enlace se mantienen.

Fuentes y guía de reproducción: [brag-v2/README.md](brag-v2/README.md).
Las fuentes y assets de la primera versión (70/72 s) permanecen intactos;
los comandos siguientes sin `--edition` siguen seleccionando **v1**.
Los assets activos tienen el sufijo `-brag-v2-es` para evitar sobrescribir v1.

## Requisitos

- Node 22+ y FFmpeg (`ffmpeg`/`ffprobe` en el PATH).
- `npm install` en este directorio (instala `hyperframes` y `gsap`, pineados).
- Chrome de render: `npm run browser:ensure` (lo descarga HyperFrames una sola vez).
- Narración opcional: Kokoro en un entorno Python aparte
  (`python3 -m venv ~/.venvs/kokoro && ~/.venvs/kokoro/bin/pip install kokoro-onnx soundfile`)
  y ejecutar los comandos de voz con `env PATH=$HOME/.venvs/kokoro/bin:$PATH`.

`npm run doctor` resume el estado de todo lo anterior.

## Estructura

```
shared/           brand.css (tokens de theme.css), layout.css, engine.js, music/bed.mp3
content/          contenido público congelado por idioma (generado, commiteado)
additional-modules/  index.html · script.es.js · timeline.js   (proyecto HyperFrames A)
financing/           index.html · script.es.js · timeline.js   (proyecto HyperFrames B)
scripts/          pipeline (fetch → sync → stage → lint/check/snapshot → render → poster → export)
```

Cada proyecto es autocontenido: `npm run sync` copia `shared/`, las fuentes del
frontend (Ubuntu + Noto Emoji) y `gsap.min.js` a `<video>/assets/`, y
`npm run stage` deja `content.js` + `script.js` en la raíz del proyecto. Esos
archivos están gitignoreados y se regeneran siempre.

## Regenerar un video (3 pasos + revisión)

```bash
npm run content                                    # baja catálogo y programa desde https://projectapp.co
npm run check -- --video financing --snapshots     # lint + auditoría en navegador (layout, colisiones, contraste AA)
npm run snapshot -- --video financing --at 3,25,45 # frames para revisar antes de renderizar
npm run render -- --video financing --lang es      # intermedio HyperFrames + mezcla ffmpeg (≤ 12 MB)
npm run poster -- --video financing --lang es      # portada WebP 1280x720 (frame a 4,5 s)
npm run export -- --video financing --lang es      # copia MP4 + poster a frontend/assets/…
```

`npm run preview -- --video financing` abre el editor/preview con recarga en vivo.
El render usa `nice -n 15` y un solo worker: este repo vive en un VPS de producción.

## Qué es dato y qué es autoría

- **Dato (API pública, congelado en `content/`)**: nombres y conteos de categorías,
  íconos y nombres de los 23 módulos, títulos del hero, condiciones (títulos e
  íconos de las cinco base), opciones (nombre, badge, años, ciclos, paquete),
  meses de financiación, nombre y horas del paquete.
- **Autoría (`<video>/script.<lang>.js`)**: eyebrows, títulos de escena,
  subtítulos en pantalla (`caption`), resúmenes de una línea de cada condición y
  el texto de la narración. Nunca se escriben montos en COP ni porcentajes de
  política: cambian desde el panel de financiación.
- Los tiempos de escena viven sólo en `index.html` (`data-start`/`data-duration`);
  `timeline.js` y la narración los leen de ahí.

## Audio

La composición es muda: la música y la narración se mezclan en `scripts/render.mjs`
con ffmpeg (ducking, `loudnorm`, fade final) sobre el intermedio casi sin pérdida.
Cambiar el audio nunca vuelve a renderizar el video.

- `shared/music/bed.mp3` es un pad sintético generado con
  `bash scripts/make-placeholder-bed.sh` (sin licencia externa). Reemplazalo por la
  pista definitiva y documentá su licencia en `shared/music/LICENSE.txt`.
- Narración: `npm run narration -- --video financing --lang es --voice em_alex`
  genera un WAV por escena (Kokoro, voces en español `em_alex`, `em_santa`,
  `ef_dora`) y los alinea con `audio/<video>-narration-es.wav`. Luego
  `npm run render -- --video financing --lang es --with-narration --skip-render`
  sólo re-mezcla.

## Agregar un idioma

1. `node scripts/fetch-content.mjs --lang en` → `content/<video>.en.js`.
2. Escribir `<video>/script.en.js` (misma forma que `script.es.js`).
3. Correr el pipeline con `--lang en` y registrar el descriptor `en` en
   `frontend/composables/useExplainerVideos.js`; la tarjeta aparece sola en `en-us`.

## Licencias

Ubuntu (Ubuntu Font Licence) y Noto Emoji (OFL) se copian desde
`frontend/assets/fonts/`. GSAP se vendoriza desde `node_modules` (licencia estándar
de GSAP para uso en render offline). HyperFrames es Apache 2.0.
