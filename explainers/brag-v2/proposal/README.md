# Tu propuesta, paso a paso

Video genérico para la entrada pública de propuestas, sobre las cuatro opciones.
[Ver el MP4 final](../../../frontend/assets/videos/explainers/proposal-brag-v2-es.mp4) ·
[Portada](../../../frontend/assets/images/explainers/proposal-brag-v2-es.webp).
Duración: **58,2 segundos**, 1920 × 1080, 30 fps. Español colombiano con voz
`es-CO-SalomeNeural` a velocidad natural, música de fondo y subtítulos integrados.
La narración no nombra la empresa ni habla de vistas o tarjetas. Las imágenes
son una composición editorial genérica, sin datos de clientes ni cifras comerciales.

## Fuentes y decisiones editoriales

- Resumen: `ProposalViewGateway.vue` y el filtro ejecutivo de
  `pages/proposal/[uuid]/index.vue`: problema, solución, tiempo e inversión.
- Propuesta completa: secciones de contexto, estrategia, diseño, funcionalidades,
  metodología, etapas, cronograma e inversión. No se promete una sección que
  exista exclusivamente en el PDF.
- Detalle técnico: `technicalProposalPanels.js`: componentes, integraciones,
  seguridad, calidad y preparación para el crecimiento.
- Legal: opción pública `Contrato y condiciones`, que presenta un borrador
  contractual. El video no presenta ese borrador como un contrato ya firmado.
- Referencia de voz/producción: PR #432, commit
  `fe90443f0e162b1abd243790996e89cd3c514214`. Se incorporaron sus utilidades de voz,
  fingerprint y niveles de mezcla sin sustituir los otros dos videos comerciales.
- Diseño: Ubuntu, esmeralda, lima y logo del proyecto; ilustraciones SVG propias.
  Música reutilizada con la licencia conservada en `../shared/music/LICENSE.txt`.
  Esta pieza no simula clics ni usa efectos de interacción.

## Reproducir

Desde `explainers/`, con Node >=22, `npm ci`, FFmpeg y Chrome. Instalar
`requirements-voice.txt` en un venv separado y añadir su directorio `bin` a PATH.
La generación de voz consulta Microsoft Edge; la reproducción del MP4 es local.
`HYPERFRAMES_BROWSER_PATH` permite señalar un Chrome ya instalado.

```bash
npm run narration -- --video proposal --edition brag-v2
npm run check -- --video proposal --edition brag-v2 --json
npm run poster -- --video proposal --edition brag-v2 --at 0.1
npm run render -- --video proposal --edition brag-v2 --with-narration --music-volume 0.22 --priority 5
npm run export -- --video proposal --edition brag-v2
```

El guion vive en `script.es.js`; la agenda en `index.html`. Cambiar texto o tiempos
requiere regenerar voz, subtítulos y render. No se usa `npm run content` para
esta pieza: su contenido es genérico y no consulta propuestas reales.
Un worker de render y dos threads de codificación. El poster se captura antes
que la voz y coincide con el primer fotograma. La mezcla deja margen de pico
antes de AAC y mantiene la voz hasta el cierre.

## Visibilidad y reversión

El panel general está en Propuestas → Configuraciones, con previsualización.
La preferencia individual está en Editar propuesta → General; duplicar conserva
esa preferencia. Ambos interruptores nacen activos para propuestas existentes
y nuevas (`content.0268_proposal_explainer_video`, aplicada por deploy).

El video aparece solo con ambos controles activos, español, propuesta activa,
detalle técnico habilitado y Contrato y condiciones visible. Apagar el control
general lo retira al volver a abrir la propuesta sin perder preferencias
individuales; no requiere regenerar frontend. El MP4 se carga al pulsar reproducir.
Elegir una opción pausa el audio antes de la transición; desmontar el reproductor
también lo pausa. Los enlaces directos a un modo conservan su destino.

El admin recibe la preferencia individual almacenada; la API pública devuelve
la visibilidad efectiva en `show_explainer_video`, igual en UUID, slug, enlaces
compartidos y preview. El campo es metadato, ajeno al contenido y a los PDF.

## Verificación

La evidencia y límites de la entrega se registran en `verification.md`.
