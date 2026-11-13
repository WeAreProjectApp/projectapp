### FLOW: `admin-program-contract-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/documents/:id/edit`
- **Interaction:** Abrir el documento vinculado desde Contrato en Building with Us o Células, editar la fuente y guardar con motivo. Volver al módulo y consultar la misma versión guardada.
- **Outcomes:** `success`, `error`, `failure`
- **Evidence:** frontend/pages/panel/documents/[id]/edit.vue; frontend/composables/useProgramContractRefresh.js; PATCH /api/documents/:id/update/; frontend/e2e/admin/admin-module-contract-document-editor.spec.js.

El guardado exige la versión leída. Motivo ausente impide guardar. Ante conflicto o fallo del servicio se conserva la fuente local; los metadatos contractuales permanecen protegidos. Los contratos de propuestas siguen en sólo lectura. Los casos parametrizados cubren ambos módulos sin atribuir aprobación o firma al documento.
