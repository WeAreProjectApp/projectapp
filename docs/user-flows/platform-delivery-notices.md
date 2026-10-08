### Platform: consultar y reintentar avisos de entrega

Fuente: `DeliveryWorkspace.vue`, `DeliveryNoticeHistory.vue` y
`accounts.services.delivery_notifications`.

Sólo el administrador ve el historial al entrar por Proyecto → Entregas. Cada
registro conserva asunto, destinatarios y estado del aviso derivado de una
publicación, una respuesta pública o una revisión con observaciones. No crea
conformidades ni sustituye la revisión del cliente.

| Interacción | Resultado | Clase |
|---|---|---|
| Llegar a Entregas desde la navegación del proyecto y consultar el historial | Muestra datos reales del aviso y permite paginar más de veinte registros. El cliente no recibe esta superficie. | `display` |
| Abrir «Revisar reintento» en un aviso fallido | Muestra destinatarios, asunto y cuerpo exactos retenidos; la previsualización no envía. | `display` |
| Confirmar el reintento después de revisar la copia | Envía versión, huella de la copia e identificador idempotente; refresca el estado conservado. | `success` |
| Reintentar tras cambio de versión, destinatario, proyecto o estado | La API rechaza la acción y la interfaz conserva y muestra el error. | `error` |
| Consultar un envío fallido, en curso o de resultado desconocido | Un fallo confirmado puede revisarse; los estados en curso o desconocidos requieren revisión humana y no ofrecen reintento automático. | `failure` |

Los fallos de carga, previsualización y confirmación se muestran en el aviso de
error. La generación de avisos, el worker de correo y las operaciones MCP son
contratos backend; no constituyen flujos E2E de navegador.

La ejecución viva y sus límites se consultan en los artefactos de QA ligados al
SHA combinado; los borradores de specs no acreditan cobertura por sí solos.
