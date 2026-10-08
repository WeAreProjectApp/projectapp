### Platform: preparar y publicar etapas

Fuente: `DeliveryAuthoringForm.vue`, `DeliveryWorkspace.vue`,
`accounts.services.delivery_workflow` y `accounts.services.delivery_contract_sources`.

Cada contrato u otrosí elige exactamente una fuente: documento del proyecto,
PDF de propuesta o archivo del paquete de aprobación confirmado para el mismo
proyecto y cliente, incluidos archivos personalizados. Una selección nueva del
paquete se registra privada y sin firma; la selección no acredita aprobación
contractual ni habilita publicación.

| Interacción | Resultado | Clase |
|---|---|---|
| Elegir una fuente confirmada y guardar el borrador | Conserva el archivo seleccionado y la fuente nueva queda privada. | `success` |
| Guardar sin fuente única o con una fuente ajena/no confirmada | El formulario o la API rechaza la operación sin crear la referencia. | `error` |
| Descargar la fuente conservada | Entrega el formato original exacto si no hay PDF; la copia firmada prevalece tras acreditar firma. | `display` |
| Usar una fuente ausente, corrupta o congelada | La operación falla sin sustituir el contenido contractual ni su firma. | `failure` |

El administrador vincula el contrato original, sus otrosíes y el alcance; crea fases de ejecución independientes de los cobros y organiza sus etapas y requerimientos. Guarda borradores antes de publicar. Una etapa sin requerimientos, con guía incompleta o con contrato aplicable sin firmar no se puede publicar. Si una guía basada en fuentes nombra un rol del producto, debe explicar acceso y datos, acciones permitidas y bloqueadas, y los pasos y resultados para verificar ambos casos. El rechazo conserva el borrador; se completa la guía y sólo entonces se publica para el cliente. Las ampliaciones de una etapa aprobada requieren otra etapa.

Los specs de autoría y fuente verifican estas interacciones; la ejecución viva
y sus límites se consultan en los artefactos de QA ligados al SHA combinado.
La API comprueba también permisos, versiones y protección de aprobaciones.
