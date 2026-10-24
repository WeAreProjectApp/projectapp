# Verificación de los tutoriales de plataforma

Verificación audiovisual: 2026-10-24. Los tres archivos exportados son H.264
1920 × 1080, 30 fps, con audio AAC estéreo a 48 kHz. Sus portadas WebP y las
entradas del manifiesto acompañan a los MP4 bajo `frontend/assets/`.

| Pieza | Duración | Bytes | Capturas / fotogramas finales | SHA-256 del MP4 |
|---|---:|---:|---:|---|
| platform-overview | 90 s | 2659866 | 941 / 2700 | `cabab603026e3ab097d9760e9bc66ace92865b23c0effc8f61ba6fb46614e9d6` |
| platform-chatbot | 72 s | 2277945 | 936 / 2160 | `921745b95216c8db5030cb16f6a68a762be60d1dba147bf5898b2f180dfaaefe` |
| platform-voice-reporting | 72 s | 2289429 | 936 / 2160 | `104c05297cb3bdec7c94f9fe16d89e87ad8c93ac10201c3000773ec67d38861a` |

## Fuentes y narración

Las tres narraciones conservan la voz colombiana `es-CO-SalomeNeural` (Edge,
locale `es-CO`), verificada en sus metadatos. La mezcla incluye música con
reducción durante la voz. Los guiones no pronuncian ProjectApp; la marca está
reservada al gráfico. Los subtítulos están integrados en el video y sus cues
medidos no se solapan ni exceden la duración de la pieza.

El general muestra el uso principal de la plataforma sin IA. Appi se contrastó
con `493194dc1`, `1d60ef685` y la integración publicada `920a47b45`. El reporte
por voz se contrastó con `6d0a79424`, `65b9f9ecc` y `ffa55890d`; las correcciones
internas posteriores conservan los pasos visibles. La escena de aplicación
explica que usar el texto llena el formulario y el envío se confirma después.

## Controles de producción

- `ffprobe`: formato, dimensiones, velocidad, audio y duración de cada MP4
  exportado; huellas calculadas sobre los archivos que recibe el frontend.
- Hyperframes: Appi y voz pasan lint, ejecución y layout sin errores ni
  advertencias; contraste 60/60 en cada pieza. El general se validó antes de
  su captura y se revisó visualmente en su archivo final.
- Revisión de portadas y cuadros extraídos de los MP4 finales a los 35 s
  (general), 29 s (Appi) y 41 s (voz): títulos, contexto, rótulos y subtítulos
  visibles, sin recortes. Se revisaron además cuadros de contexto/fuentes
  de Appi durante la captura.
- Captura secuencial de un navegador; codificación con dos threads. La caché
  conserva la huella de HTML, estilos, animación y guion preparados y escribe
  las imágenes de forma atómica para retomar interrupciones.

El procedimiento de actualización y la responsabilidad del equipo ProjectApp
están en [README.md](README.md). Los resultados de navegador y permisos de la
aplicación se documentan con sus pruebas y el CI del PR; esta evidencia cubre
los archivos audiovisuales exportados.
