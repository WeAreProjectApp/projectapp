# Brief de composición — ProjectApp

Brag define guion y dirección; Hyperframes renderiza HTML + GSAP de forma determinista.
Fuentes: componentes AdditionalModules/CatalogView, ModuleDetails y
Financing/ProgramView; estilos theme.css; API pública; financing_program_service.py.
Se recrean únicamente las tarjetas/fichas necesarias a escala legible usando el copy
real. Las composiciones no simulan que los módulos estén instalados ni que se conceda
financiación automáticamente. Sin datos privados.

## Diseño
Ubuntu; esmeralda #002921, oscuro #001713, lima #F0FF3D, blanco #FFFFFF,
superficie #F1F5F9. Logo original de ProjectApp. Titulares 90–120 px,
beneficios 54–66 px, subtítulos 48 px. Márgenes amplios, foco único por escena.
Diseño estático primero, luego entradas; nada de fondos decorativos genéricos.

## Entregables
Por módulo: composición index.html + script.es.js; MP4 60 s, 1080p/30fps,
H.264 y AAC, faststart, ≤12 MiB; poster WebP de un frame estable incorporado
como frame cero sin desplazar el audio. Audio siempre obligatorio en v2.
Fuentes v1 intactas. Los recursos derivados y las dependencias se regeneran.

## Audio
Música: assets/music/happy-beats-business-moves-vol-11-by-ende-dot-app.mp3,
editada a 60 s con fade final. Edge es-CO-SalomeNeural por escenas, a velocidad natural. Clics CC0 de Kenney
sobre interacciones, sin impactos. Mezcla próxima a -16 LUFS; normalización
a -2.5 dBTP para conservar un pico final ≤-1.5 dBTP tras codificar en AAC.
Los WAV se invalidan al cambiar texto/proveedor/voz/locale/velocidad; desbordes detienen producción.

## Gate
Hyperframes lint/check; stills por escena/transición; control de desborde;
ffprobe y decodificación completa; comparación copy; pruebas del reproductor
real y flujos públicos/panel. No confundir E2E con API mockeada con revisión del MP4.

## Revisión 2026-09-26
La escena 4 del catálogo recrea la ficha de Protección de propiedad intelectual con
el copy de la migración `content.0259`, todavía sin publicar en la API al producir;
la escena 2 la muestra como tarjeta con la etiqueta Nuevo. Sin cambios de CSS: se
reutilizan las clases `pill lemon label`. El titular de la escena 4 va sin `em`,
porque sobre fondo lima el resaltado no se ve y su padding desalineaba la línea.
