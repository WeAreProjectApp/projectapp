# Verificación — videos brag v2

## Producción

- Brag clonado con historial completo y bundle verificado (commit en provenance.json).
- Revisión de imágenes: ocho muestras del catálogo y seis de Alianza; marca,
  márgenes, jerarquía, contenido y contraste revisados.
- Hyperframes check: cero errores de runtime/layout/contraste en ambos proyectos.
- Narración ef_dora a 1.1, segmentos medidos; ninguna frase excede su ventana.
- Renderer: un worker por video, nice 5 en el host compartido (default 15);
  codificación final limitada a dos threads.
- Ambos MP4: 45.000 s, H.264 1920×1080 a 30 fps, AAC estéreo a 48 kHz,
  faststart; decodificación completa sin errores.
- Reproducción real en Chromium: carga, avance, salto al segundo 43.5 y final
  natural aprobados en ambos archivos exportados (349/352 frames decodificados).
- Portada y primer movimiento revisados: el titular permanece visible al empezar.

| Video | Tamaño | Sonoridad integrada | Pico real tras AAC |
|---|---:|---:|---:|
| Módulos adicionales | 2.03 MiB | -16.85 LUFS | -2.07 dBTP |
| Programa de Alianza | 1.78 MiB | -16.72 LUFS | -1.98 dBTP |

Presupuesto: 12 MiB por pieza. La normalización deja margen para los picos que
introduce AAC; música atenuada durante la voz y fade final sin cortar palabras.

## Integración

- Node: ocho pruebas de cache, desborde y subtítulos aprobadas.
- Jest: nueve pruebas de descriptores/player aprobadas.
- Jest: veinte pruebas de Mapa de vistas aprobadas.
- Catálogo y contrato responsive: 115 vistas, estructura válida, sin rutas nuevas.
- Flow-map freshness: actualizado. Se regeneró USER_FLOW_MAP desde sus shards.
- Auditoría focal: los siete flows de video/visibilidad/enlaces están cubiertos (success,
  display y failure según corresponda); sin formularios, error de validación no aplica.
- El inventario global reporta un junk-only previo en platform-hosting-subscription;
  queda fuera de este cambio. La auditoría estática no demuestra decodificación del MP4.
- Build de producción Nuxt completo: aprobado (cliente, SSR, 24 rutas y Nitro).
- La primera ejecución E2E local encontró timeouts durante la hidratación de
  páginas previas a los módulos. Se precalentó el servidor y se usó una
  configuración temporal con traza desactivada y espera de assertions de 45 s;
  los casos pendientes se ejecutaron sobre el build de producción. El timeout
  de cada test sigue en 60 s; el CI conserva su configuración versionada.
- E2E: 19 casos aprobados (10 públicos y 9 del panel), en tandas focalizadas.
  Incluyen reproducción, fallback, inglés sin video, visibilidad global y por
  enlace, preview y recuperación de un guardado fallido. El último caso público
  se repitió por un elemento del footer desmontado durante la carga y pasó.
- Resultado del CI de la entrega: consultar el PR #415; usa los tests y el build
  para Django de la configuración versionada, sin los ajustes locales.

## Revisión 2026-09-26 — Protección de propiedad intelectual (catálogo)

- Cambio: la escena 4 pasa a «Nuevo en el catálogo» con la ficha del módulo 25 y
  una fila por capa; la escena 2 muestra su tarjeta con la etiqueta Nuevo. El
  Programa de Alianza no se re-renderizó.
- Narración ef_dora a 1.1 con lead 0.2: las escenas intactas salieron del caché
  con las mismas duraciones; la escena 4 va en dos frases, 3.03 s de 3.10 s y
  5.27 s de 5.90 s disponibles. Sólo cambian sus tres cues en `captions.es.json`.
- Hyperframes check: lint, runtime y layout sin errores ni advertencias;
  contraste 44/44. Stills revisados a 7.5, 25.5, 28, 29 y 30.5 s: tarjeta Nuevo,
  ficha legible, subtítulos en una línea y titular alineado.
- MP4 exportado: 45.000 s, H.264 High 1920×1080 a 30 fps, AAC LC estéreo a
  48 kHz, `moov` antes de `mdat` (faststart); decodificación completa sin errores.
  La portada WebP salió idéntica a la anterior, porque la escena 1 no cambió.
- Reproducción real en Chromium: carga, avance, salto a la escena 4 (28 s) y
  final natural desde 43.5 s aprobados (209 frames decodificados).
- Node: ocho pruebas de narración aprobadas. Sin cambios de frontend: mismo
  nombre de asset y misma duración, así que Jest, E2E y el Mapa de vistas no se
  tocan; el CI del PR los corre sobre el asset nuevo.

| Video | Tamaño | Sonoridad integrada | Pico real tras AAC |
|---|---:|---:|---:|
| Módulos adicionales (revisión 2026-09-26) | 2.09 MiB | -16.6 LUFS | -2.1 dBTP |
