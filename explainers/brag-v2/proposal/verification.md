# Verificación del video de bienvenida de propuestas

Fecha: 2026-09-27. Referencia editorial: PR #432,
`fe90443f0e162b1abd243790996e89cd3c514214`.

## Archivo entregable

- MP4 H.264, 1920 × 1080, 30 fps; audio AAC estéreo a 48 kHz.
- Duración real: **58,200 s**, dentro del máximo de 60 s.
- Tamaño: **1 992 447 bytes** (1,90 MiB); metadata `moov` antes de `mdat`
  para reproducción progresiva.
- MP4 SHA-256: `47e619bf1c986239274936f1712b337c599d3756f2010a280811186b416e2288`.
- Poster WebP SHA-256: `68be8a55dbd908c4a6232583ef9a2003b71c032d183dbea475fbbab16319a23d`.
- Decodificación completa con FFmpeg: cero errores.
- Audio final medido: **−16,08 LUFS**, pico verdadero **−2,56 dBTP**,
  rango de sonoridad **3,40 LU**. No se ha realizado escucha humana en esta sesión.

La voz colombiana `es-CO-SalomeNeural` conserva velocidad natural (1×).
Duraciones medidas por escena: 4,82 / 9,34 / 13,97 / 13,01 / 9,38 / 3,58 s.
La agenda reserva 5,5 / 10 / 14,5 / 13,6 / 10 / 4,6 s respectivamente, con 0,2 s
iniciales antes de cada voz. Música al 22 %, sin sonidos de clic y con cierre
suave de la mezcla. El guion y los subtítulos evitan lenguaje de interfaz y
nombres de clientes o precios concretos.

## Revisión visual y producción

- Composición, runtime, layout y contraste: cero errores y advertencias;
  58 comprobaciones de contraste aprobadas.
- Poster y fotogramas a 1, 8, 22, 36, 48 y 56 s revisados visualmente:
  títulos y subtítulos legibles, sin cortes ni solapamientos.
- Generación de voz, poster, render y export ejecutados con los comandos
  reproducibles del README de esta pieza.
- Pruebas de utilidades de narración: **16 aprobadas**.
- Compilación de producción Nuxt: aprobada, con backend local deshabilitado
  para evitar depender de datos reales durante la validación.

Los renders intermedios, pistas de voz, capturas y logs son artefactos ignorados
por Git. Se versionan la composición, el guion, los subtítulos, el poster y el
MP4 final. La migración `content.0268_proposal_explainer_video` está incluida;
`makemigrations --check --dry-run` no detecta cambios pendientes. No se aplicó
a una base real en esta sesión.

## Integración y pruebas focalizadas

- Backend: **22 casos aprobados** (13 de elegibilidad y rutas públicas, 4 del
  control general y 5 de creación, actualización y duplicación por MCP).
  Incluye el caso de actualizar JSON sin el campo, conservando una preferencia
  previamente apagada. Las bases de prueba son SQLite temporales.
- Componentes y estado: **42 casos aprobados** entre descriptor, controles,
  gateway y reproductor compartido. Tras corregir el idioma público se repitieron
  los 19 casos de gateway y reproductor.
- Catálogo de vistas: 11 casos aprobados; capacidades: 9 aprobados. Catálogo,
  contrato responsive, controles deshabilitados y diálogos nativos: comprobados.
- Idioma: el gateway entrega al reproductor los mensajes españoles ya disponibles
  en el componente, sin esperar otra carga ni cambiar el idioma del navegador.

- Navegador: **12 casos aprobados** (5 públicos y 7 del panel), incluidas
  reproducción real del MP4, pausa al entrar a las condiciones, alternativa
  al fallar el archivo, persistencia y reversión ante fallos de guardado.
  La prueba pública usa una ruta inglesa con una propuesta española para
  comprobar que el idioma del documento prevalece. Capturas compacta y de
  escritorio revisadas con los textos definitivos en español.
- Gate estricto final: backend 5 archivos / 33 pruebas, cero errores y avisos;
  unit y E2E 100/100, sin hallazgos. Los tres flujos nuevos quedan cubiertos,
  sin escenarios pendientes de ejecución. Se reubicaron las pruebas de
  serializador y servicio en sus capas y se retiró una aserción de constante
  que no protegía comportamiento.

La validación de navegador usa respuestas de API aisladas; la persistencia
real y los permisos se comprueban en los tests de backend. Esta evidencia no
representa un despliegue ni una validación con datos de clientes.
