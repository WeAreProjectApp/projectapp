### Platform: crear guías con fuentes conservadas

Fuente: `DeliveryPromptWorkbench.vue`, `DeliveryPromptSources.vue` y
`accounts.services.delivery_authoring`.

El administrador elige un contrato, los otrosíes aplicables y anexos o referencias
explícitos. Puede empezar sin una etapa previa. Cada fuente conserva su identidad,
versión conocida, fecha, hash, copia y fragmentos citables; la selección de un anexo
no demuestra su incorporación jurídica. Las fuentes faltantes, ilegibles o
parciales y las incertidumbres aparecen antes de usar el prompt.

El JSON con contexto y citas se valida contra las capturas del servidor. La
previsualización no escribe; la aplicación prepara borradores y conserva guías
aprobadas. Cambiar la selección invalida el prompt y cambiar el JSON exige otra
previsualización. El JSON manual anterior se identifica como sin trazabilidad.
Las correcciones muestran y conservan las citas originales y exigen revisar su
aplicabilidad al texto final. El historial permite reabrir preparaciones y
descargar las copias exactas.

`delivery-guide-prompt.spec.js` cubre aplicar un borrador con cita verificada,
contrato obligatorio, rechazo de una cita inventada y consulta de un anexo faltante
después de navegar desde el proyecto.
También cubre la corrección trazada, descarga comprobada por huella, consulta
del historial y operación en los cinco tamaños de pantalla.
