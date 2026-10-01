### Platform: responder sobre una etapa

Fuente: reporte contextual en `DeliveryWorkspace.vue` e historial en `DeliveryStage.vue`.

Administrador y cliente escriben un mensaje, seleccionan los requerimientos tratados y pueden asociar documentos existentes. El mensaje es obligatorio; los adjuntos son opcionales. El cliente sólo puede responder en contenido publicado que pertenece a su proyecto.

`delivery-review.spec.js` comprueba que una respuesta sin adjuntos persiste al volver. Las respuestas no otorgan conformidad ni sustituyen la decisión explícita del cliente.
