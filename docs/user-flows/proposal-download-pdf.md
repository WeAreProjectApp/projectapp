### FLOW: `proposal-download-pdf`

- **Módulo:** propuesta pública
- **Rol:** visitante
- **Prioridad:** P2
- **Ruta:** `/proposal/:uuid`
- **Éxito:** abre la vista comercial o técnica, pulsa Descargar PDF y recibe el archivo.
- **Error:** una propuesta vencida conserva su lectura, pero explica por qué sus PDFs no se pueden descargar; un 410 posterior a la carga muestra el mismo aviso.
- **Fallo:** un error de servidor o de red informa del fallo y permite reintentar.
- **Presentación:** el aviso pertenece al bloqueo anterior, no constituye otro flujo.
- **E2E:** `frontend/e2e/proposal/proposal-pdf.spec.js`.
- **Límite:** E2E intercepta HTTP; la generación de PDFs reales y los permisos se prueban en backend.
