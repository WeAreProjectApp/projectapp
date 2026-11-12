### FLOW: `admin-outbound-email-history-retry`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/emails?tab=history`
- **Description:** Admin expands a failed recipient in universal Email History and confirms a retry naming its original address and subject. The retry accepts no replacement destination; exact snapshots or valid accounting origin facts create a linked attempt in History. Missing facts, reversed payments, invalid addresses and insufficient permissions explain why no retry is available. Failed retried sends remain recorded and show failure feedback.
- **Selector:** `email-history-retry-<id>`
- **Outcomes:** display, success, error, failure
- **Pasos:** abrir Emails desde Comunicaciones, elegir Historial y desplegar el envío. Revisar el destinatario fallido y confirmar Reintentar envío. Consultar el nuevo intento vinculado; si falla, conservar su resultado en el historial. Un registro incompleto o sin permiso explica el bloqueo antes de enviar.
