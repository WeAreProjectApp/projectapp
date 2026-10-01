### Platform: preparar y publicar etapas

Fuente: `DeliveryAuthoringForm.vue`, `DeliveryWorkspace.vue` y `accounts.services.delivery_workflow`.

El administrador vincula el contrato original, sus otrosíes y el alcance; crea fases de ejecución independientes de los cobros y organiza sus etapas y requerimientos. Guarda borradores antes de publicar. Una etapa sin requerimientos, con guía incompleta o con contrato aplicable sin firmar no se puede publicar. Las ampliaciones de una etapa aprobada requieren otra etapa.

`delivery-authoring.spec.js` cubre la preparación y publicación desde el formulario. La API comprueba también permisos, versiones y protección de aprobaciones.
