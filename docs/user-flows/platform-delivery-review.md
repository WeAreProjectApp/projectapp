### Platform: validar una entrega

Fuente: `DeliveryWorkspace.vue`, `DeliveryStage.vue`, `DeliveryReviewForm.vue` y `DeliveryReviewHistory.vue`.

| Acción | Resultado | Evidencia |
|---|---|---|
| Abrir Entregas desde el proyecto | Mostrar guía publicada con datos y pasos; ocultar borradores | `delivery-review.spec.js` |
| Aprobar solamente lo probado | Conservar conformidad parcial y dejar abiertos los demás casos | `delivery-review.spec.js` |
| Objetar sin motivo | Pedir el motivo sin guardar una decisión | `delivery-review.spec.js` |
| Corregir y republicar un caso pendiente | Mantener el caso aprobado y entregar otra versión del pendiente | `delivery-review.spec.js` |
| Aprobar todos los requerimientos | Cerrar la etapa; una etapa en borrador impide cerrar la fase | `delivery-review.spec.js` |
| Abrir el formulario en cinco anchos | Controles alcanzables sin desbordamiento horizontal | `delivery-authoring.spec.js` |

Los conflictos de versión, permisos por proyecto y evidencia inmutable se comprueban además en las pruebas de API. El navegador usa JWT reales y una base temporal; no simula aprobaciones.
