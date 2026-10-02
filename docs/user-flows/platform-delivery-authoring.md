### Platform: preparar y publicar etapas

Fuente: `DeliveryAuthoringForm.vue`, `DeliveryWorkspace.vue` y `accounts.services.delivery_workflow`.

El administrador vincula el contrato original, sus otrosíes y el alcance; crea fases de ejecución independientes de los cobros y organiza sus etapas y requerimientos. Guarda borradores antes de publicar. Una etapa sin requerimientos, con guía incompleta o con contrato aplicable sin firmar no se puede publicar. Si una guía basada en fuentes nombra un rol del producto, debe explicar acceso y datos, acciones permitidas y bloqueadas, y los pasos y resultados para verificar ambos casos. El rechazo conserva el borrador; se completa la guía y sólo entonces se publica para el cliente. Las ampliaciones de una etapa aprobada requieren otra etapa.

`delivery-authoring.spec.js` cubre la preparación y publicación desde el formulario. La API comprueba también permisos, versiones y protección de aprobaciones.
