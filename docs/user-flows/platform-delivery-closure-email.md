### Platform: enviar una constancia de etapa aprobada

Fuente: `DeliveryStage.vue`, `DeliveryClosureEmail.vue` y las acciones del store `platform-delivery.js`.

El administrador entra por Proyectos → Entregas y abre **Correo de conformidad** en una etapa cuyos requerimientos están aprobados. Puede escribir un mensaje, incluir un resumen PDF y seleccionar copias exactas de documentos públicos. Los adjuntos son opcionales. Preparar la vista previa conserva destinatario, asunto, cuerpo y archivos sin enviar.

Al entrar al portal en español o inglés (`/es-co/platform` o `/en-us/platform`),
la redirección conserva el idioma al abrir el listado de proyectos. La navegación
hacia Entregas o **Deliveries**, el modal y su estado de correo preparado mantienen
ese mismo idioma; abrir la vista previa no envía el mensaje.

| Interacción | Resultado que se comprueba | Clase |
| --- | --- | --- |
| Preparar y confirmar el correo revisado | Se registra un envío al cliente de ese proyecto; repetir la misma preparación conserva un solo intento. | `success` |
| Abrir una etapa parcial o usar una cuenta de cliente | La acción de correo de conformidad permanece inaccesible hasta que la etapa esté totalmente aprobada y actúe el administrador. | `error` |
| Intentar enviar cuando falla SMTP | El error queda visible en el historial; consultar o repetir la petición no envía automáticamente. | `failure` |
| Abrir el correo desde la navegación del proyecto | Se muestran el destinatario, la vista previa y su estado preparado sin envío en los cinco tamaños de pantalla; el recorrido inglés conserva su idioma. | `display` |

La acción sólo corresponde al administrador. Una etapa parcial, objetada o rechazada no habilita el correo. Las conversaciones y decisiones se conservan hasta el cierre, incluidas las rondas anteriores y el mensaje de la última revisión. La fecha de una conformidad externa y quien la registró se distinguen del cliente que la otorgó. Notas internas, prompts y fuentes administrativas privadas se excluyen.

La evidencia y sus descargas pertenecen al administrador y al canal que prepararon la copia. El historial común de correos conserva su autorización administrativa y los adjuntos permanecen en almacenamiento privado. Una pérdida de respuesta se muestra como resultado desconocido hasta consultar el estado conservado.

Cambiar el mensaje o los adjuntos después de preparar invalida la vista y exige
prepararla y confirmarla de nuevo; este bloqueo se verifica en las pruebas del componente.

`delivery-closure-email.spec.js` ejecuta estas interacciones contra Django y JWT reales, una base temporal y correo en memoria. El fallo se introduce únicamente en la frontera SMTP del servidor de pruebas.
