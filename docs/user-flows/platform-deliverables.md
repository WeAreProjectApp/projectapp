### Platform: consultar y descargar recursos

Fuente: `frontend/pages/platform/projects/[id]/deliverables/index.vue`,
`platform-deliverables.js` y la API de archivos privados de recursos.

El administrador prepara materiales con historial de versiones. La biblioteca
mantiene diseños, documentos, credenciales, APK y otros recursos; también
presenta contratos, otrosíes y anexos legales en sus grupos. Elegir una categoría
no convierte el archivo en evidencia de firma o conformidad de una entrega.

| Interacción | Resultado | Clase |
|---|---|---|
| Abrir la biblioteca del proyecto | Muestra los recursos disponibles, incluidos los tres grupos contractuales. | `display` |
| Abrir el detalle y descargar el archivo actual | Obtiene los bytes originales y el nombre de archivo declarado por el servidor mediante una descarga autenticada. | `success` |
| Descargar una versión anterior | Obtiene esa versión conservada, sin sustituirla por el archivo actual. | `success` |
| Pulsar otra vez mientras la descarga está pendiente | Los controles permanecen deshabilitados y no se genera otra solicitud. | `success` |
| Descargar con una identidad sin acceso al proyecto | Muestra la explicación recibida sin cerrar el detalle ni crear una descarga. | `error` |
| Perder la conexión al descargar | Muestra el fallo, conserva el detalle y permite intentarlo de nuevo. | `failure` |

El paquete documental confirmado al aprobar una propuesta sigue separado de los
adjuntos editables. Sus copias privadas no establecen por sí mismas una firma o
una aprobación de entrega.

La vista del proyecto se abre en `/platform/projects/:id/deliverables`; la
biblioteca conjunta conserva su ruta `/platform/deliverables`.

Evidencia: `delivery-private-files.spec.js` usa el backend y JWT reales para la
biblioteca y las descargas. El rechazo conserva una respuesta real de permisos;
el fallo de conexión sólo interrumpe el transporte HTTP. Mientras el spec tenga
el marcador `draft-unvalidated`, todavía no acredita una ejecución en vivo.
