# Avisos del ciclo de revisión de entregas

Este documento describe el código de la entrega del 2026-10-07. La integración,
las migraciones y el despliegue se verifican por separado. Los ensayos usan
usuarios, archivos y correos ficticios en una base aislada.

## Cuándo se avisa

| Acción registrada | Aviso interno | Correo |
| --- | --- | --- |
| Publicar una etapa o una nueva ronda | Cliente del proyecto | Cliente del proyecto |
| Objetar, rechazar o comentar una revisión | Equipo administrativo | Destinatarios internos configurados |
| Responder públicamente desde el equipo | Cliente del proyecto | Cliente del proyecto |
| Escribir públicamente como cliente | Equipo administrativo | Destinatarios internos configurados |
| Aprobar sin observaciones o registrar conformidad histórica | Recibo existente en el portal | Sin correo automático |
| Escribir una nota interna | Conversación interna | Sin correo automático |

El aviso incluye proyecto, etapa cuando corresponde, resultados y observaciones,
y un enlace al portal. No lleva inventarios de código, contraseñas ni archivos
privados como adjuntos. Las plantillas del inventario universal permiten apagar
cada canal; no reescriben el contenido de un evento ya registrado.

## Persistencia y transporte

Una operación pública registra su evento, sus destinatarios y la copia exacta
del mensaje dentro de la misma transacción que el cambio. El identificador
estable de la operación evita crear un segundo aviso al repetir la petición.
El envío se encola después del commit y un despachador periódico recupera
intentos pendientes si la cola estaba indisponible.

El trabajador registra el intento antes de contactar al transporte. Usa
`EmailDeliveryGateway`, el mailer configurado y un timeout SMTP máximo de
20 segundos; conserva un timeout menor ya configurado. El historial del gateway
queda enlazado al intento cuando está disponible. Los logs sólo incluyen
identificadores, estado y códigos de diagnóstico.

| Estado | Interpretación y acción |
| --- | --- |
| `pending` | Registrado; aún no reclamado por un trabajador. El despachador puede recogerlo. |
| `sending` | Reclamado. No se ofrece otro envío mientras el resultado está pendiente. |
| `sent` | El transporte aceptó el envío. No acredita lectura ni entrega a la bandeja del destinatario. |
| `failed` | Fallo confirmado. Se permite un reintento explícito después de revisar la copia exacta. |
| `unknown` | El transporte o el trabajador no pudo confirmar el resultado. No se reenvía automáticamente. |
| `cancelled` | El destino, la credencial o el canal dejó de ser válido. No se envía esa copia. |

Un intento reclamado hace más de 15 minutos pasa a resultado desconocido. No
se interpreta como un fallo seguro. Antes del transporte se comprueban cliente,
correo del cliente, estado del proyecto y vigencia de la credencial que originó
el intento. Los eventos conservados después de retirar un proyecto son de sólo
consulta y no se despachan.

## Consulta y reintento

La sección **Historial de avisos** de Entregas es administrativa. Lista páginas
de 20 eventos con sus intentos y códigos. Cambiar de proyecto descarta los
resultados y la vista previa anteriores, incluso si una respuesta HTTP llega
con retraso.

Las rutas se encuentran bajo `/api/accounts/projects/:id/delivery/notices/`:
consulta de lista y detalle; `/:event_id/retry-preview/` obtiene el aviso y su
huella; `/:event_id/retry/` exige versión, huella e identificador estable del
reintento. Si cambia el evento o su destino, se exige una nueva revisión.
Repetir la misma petición conserva el recibo del mismo actor y credencial.

El Gestor de la plataforma (`projects`) expone estas cuatro herramientas:

- `list_delivery_notification_events`
- `get_delivery_notification_event`
- `preview_delivery_notification_retry`
- `retry_delivery_notification_event`

El reintento conversacional es una acción sensible: muestra contenido y
destinatarios, solicita confirmación y comprueba la versión del evento. No se
acepta un reintento de estados `sending` o `unknown`.

## Comprobación operativa después del despliegue

Con un proyecto y un buzón de prueba propios, comprobar publicación, observación
y respuesta del equipo; consultar el evento y su intento en el portal o MCP.
Verificar que el enlace abre la etapa correcta y que los resultados desconocidos
no ofrecen reenvío. Si el canal está apagado, el intento debe quedar cancelado.
Los tests locales sustituyen el transporte por `locmem`; no verifican SMTP real.

La guía de autoría se encuentra en
[platform-delivery-authoring](../.agents/skills/platform-delivery-authoring/SKILL.md).
Su ejecución crea borradores revisables por defecto. Publicar, firmar y aprobar
son acciones separadas de la generación de las instrucciones.
