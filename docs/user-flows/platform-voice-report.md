### Platform: preparar un reporte con una nota de voz

Entrada: iniciar sesión como cliente, abrir su proyecto y Bugs, Cambios o una
etapa de Seguimiento contractual. El botón sólo existe con activación efectiva
y proveedores configurados. Cambios exige un requerimiento publicado.

| Resultado | Interacción | Evidencia esperada |
|---|---|---|
| success | Grabar, detener, escuchar, transcribir, corregir y preparar. | Texto estructurado editable según la plantilla del escenario. |
| success | Revisar y usar la propuesta. | Se llena el formulario; todavía no existe un reporte enviado ni una decisión de conformidad. |
| success | Recuperar o descartar una preparación propia. | Sólo borradores vigentes del mismo contexto; descartar elimina su contenido. |
| error | Denegar acceso al micrófono y pulsar Grabar. | Mensaje visible y alternativa de escribir manualmente. |
| failure | Fallar el procesamiento de la grabación. | Mensaje visible, sin envío del reporte y con posibilidad de reintentar. |
| display | Navegar a Bugs y abrir Reportar. | Marcador con usadas/disponibles del cupo compartido y próxima liberación; agotado impide otra grabación. |

El máximo es 60 segundos con parada automática; 30 segundos es recomendación.
Transcribir un reporte consume una unidad; transcribir y enviar una pregunta de
chatbot comparten una sola unidad. Un resultado ya obtenido sigue contando aunque
se descarte. Los fallos sin resultado útil liberan la reserva. Ninguna lectura
consume cupo. El formulario tradicional sigue disponible.

Código: `frontend/components/platform/VoiceReportInput.vue`,
`frontend/components/platform/PlatformAIQuotaMeter.vue`,
`backend/accounts/services/platform_ai_jobs.py`, `platform_ai_quota.py`.
Bugs, cambios y observaciones comparten este control; las pruebas de navegador
usan un micrófono simulado y API simulada, sin enviar audio a proveedores reales.
