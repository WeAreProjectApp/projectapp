# Ayuda audiovisual de plataforma

Tres composiciones Brag/Hyperframes con paleta, tipografía, música y movimiento
de las referencias comerciales. Son demostraciones esquemáticas con datos
ficticios, no capturas de clientes ni promesas de funciones desplegadas.

## Historia y duración

- `platform-overview`: seis escenas de 15 s (90 s). Bienvenida; proyecto; entregas; solicitudes/bugs; documentos/avisos; volver a Ayuda. No incluye IA.
- `platform-chatbot`: seis escenas de 12 s (72 s). Apertura; contexto; respuesta y fuentes; guía de uso; reconsulta; límites. No incluye dictado.
- `platform-voice-reporting`: seis escenas de 12 s (72 s). Abrir formulario; grabar; corregir transcripción; revisar propuesta; envío manual; alternativas.

La escena inicial es legible desde el primer frame y sirve como portada.
Los subtítulos siguen la duración medida de cada segmento. Voz colombiana
`es-CO-SalomeNeural`, sin sustitución automática de acento; el nombre de marca
se reserva para el gráfico. Música licenciada de `shared/music/`.

## Fuentes y actualización

Base editorial: `origin/main` 33f1759c6 y contratos coordinados de las sesiones
de Ayuda, Voz y Appi del 24 de octubre de 2026. El clip de Appi se contrasta
con la interfaz publicada en `493194dc1`, y el de voz con `6d0a79424`.
Aceptar la propuesta de voz llena el formulario: no envía el reporte.
Antes de cerrar la entrega se verifica la interfaz integrada; los guiones no describen cuotas
ni modelos que cambian desde configuración. Las opciones dependen de permisos.

Responsable: equipo ProjectApp. Al cambiar un flujo, revisar su pieza, retirar
el recurso si quedó desactualizado y regenerar únicamente esa composición.
Conservar guion, HTML, subtítulos, procedencia y evidencia de validación.
Los reemplazos cargados deben llevar subtítulos visibles en el propio MP4.

## Regenerar

Desde `explainers/`, instalar dependencias con `npm ci` en el worktree propio.
Instalar también las dependencias de `frontend/` para el driver Playwright.
Usar FFmpeg, Chrome y un venv de voz con la versión de `requirements-voice.txt`.
La validación usa Hyperframes. La exportación de tutoriales captura su mismo
HTML/GSAP en Chromium a 30 fps, reutiliza fotogramas consecutivos sin movimiento
y mezcla voz/música con FFmpeg. La caché se liga a la huella de las fuentes;
tras una interrupción se retoma sin repetir los fotogramas válidos.
Para cada identificador anterior, ejecutar `npm run narration`, `npm run check`,
`npm run poster`, `npm run render -- --with-narration` y `npm run export`, con
`--video <identificador> --edition brag-v2`. Narración necesita el bin del
venv en PATH; el MP4 final funciona sin proveedor externo.

Un render a la vez, un worker y dos threads de codificación final. Los recursos
finales se publican bajo `frontend/assets/{videos,images}/explainers/`; intermedios,
audio y caché no se versionan. La verificación final vive en `verification.md`.
