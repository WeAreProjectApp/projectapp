### FLOW: `admin-proposal-download-pdf`

- **Módulo:** panel de propuestas
- **Rol:** administrador
- **Prioridad:** P2
- **Ruta:** `/panel/proposals/:id/edit`
- **Éxito:** desde General, descarga Propuesta comercial o Detalle técnico de una propuesta vencida; recibe el archivo por `/api/proposals/:id/pdf/`.
- **Error:** la autorización y el detalle técnico ausente se verifican en backend; esta corrección conserva los enlaces de descarga nativos del panel.
- **Fallo:** sin nuevo estado de error en panel; sigue la respuesta HTTP del enlace nativo.
- **Presentación:** sin nueva vista; los anexos formales de Documentos conservan contenido y rutas.
- **E2E:** `frontend/e2e/admin/admin-proposal-pdf.spec.js`.
