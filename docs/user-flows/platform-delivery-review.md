### Platform: validar una entrega

Fuente: `DeliveryWorkspace.vue`, `DeliveryStage.vue`, `DeliveryReviewForm.vue` y `DeliveryReviewHistory.vue`.

| Acción | Resultado | Evidencia |
|---|---|---|
| Abrir Entregas desde el proyecto | Mostrar guía publicada con datos y pasos; ocultar borradores | `delivery-review.spec.js` |
| Aprobar solamente lo probado | Conservar conformidad parcial y dejar abiertos los demás casos | `delivery-review.spec.js` |
| Objetar o rechazar sin motivo | Pedir el motivo sin guardar una decisión | `delivery-review.spec.js` |
| Rechazar con un motivo | Conservar la decisión y el motivo al volver a abrir la entrega | `delivery-review.spec.js` |
| Responder públicamente a una objeción | Conservar la respuesta sin conceder conformidad | `delivery-review.spec.js` |
| Corregir y republicar un caso pendiente | Mantener el caso aprobado y entregar otra versión del pendiente | `delivery-review.spec.js` |
| Enviar una revisión sobre una versión que cambió en otra sesión | Mostrar el conflicto sin perder el motivo pendiente | `delivery-review.spec.js` |
| Enviar una respuesta después de otra respuesta del equipo | Mostrar el conflicto sin guardar ni perder el texto pendiente | `delivery-review.spec.js` |
| Aprobar todos los requerimientos | Cerrar la etapa; una etapa en borrador impide cerrar la fase | `delivery-review.spec.js` |
| Abrir el formulario en cinco anchos | Controles alcanzables sin desbordamiento horizontal | `delivery-authoring.spec.js` |

El flujo registra resultados `success`, `error`, `failure` y `display`. Los conflictos de versión se ejercitan en el navegador con dos sesiones; los permisos por proyecto y la evidencia inmutable también se comprueban en las pruebas de API. El harness usa JWT reales y una base temporal. La ejecución de cada spec se acredita con el artefacto de su revisión de código; un spec marcado `draft-unvalidated` todavía no acredita cobertura en vivo.
