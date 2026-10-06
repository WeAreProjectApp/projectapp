### FLOW: `admin-proposal-diagnostic-templates`

- **Módulo:** panel de propuestas
- **Rol:** administrador
- **Prioridad:** P2
- **Ruta:** `/panel/proposals/:id/edit` → Documentos
- **Descripción:** La pestaña Documentos está disponible en cualquier estado de la propuesta. Muestra una lista unificada de contratos activos según la modalidad, Propuesta comercial formal y Detalle técnico formal, además de Documentos adjuntos y su formulario de carga.
- **Pasos:**
  1. Abrir una propuesta, incluida una propuesta en borrador.
  2. Seleccionar Documentos en la navegación visible.
  3. Consultar los contratos y los PDFs formales de la lista.
  4. Consultar o cargar los documentos adjuntos.
- **Presentación:** Sin contrato generado aparece Generar contrato. Los documentos adjuntos existentes aparecen en su lista. La antigua sección Enviar documentos al cliente permanece ausente.
- **Disponibilidad:** Documentos también se mantiene disponible para propuestas vencidas y finalizadas. Los PDFs originales de estos estados y del borrador continúan accesibles desde General.
- **API:** `GET /api/proposals/:id/detail/`, rutas administrativas de documentos y de formalización de la propuesta.
- **Cobertura:** ✅ Cubierto
- **E2E:** `frontend/e2e/admin/admin-proposal-diagnostic-templates.spec.js`.
