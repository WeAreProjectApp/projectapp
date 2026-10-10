### FLOW: `admin-building-with-us-contract`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/building-with-us`
- **Interaction:** Abrir Contrato, consultar Markdown y el espejo sincronizado en ProjectApp/Contratos; leer la advertencia desactualizada o sin inicializar, descargar PDF y reintentar un fallo del contrato.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/BuildingWithUs/admin/ContractPanel.vue; frontend/pages/panel/building-with-us/index.vue; GET /api/building-with-us/admin/contract/; GET /api/building-with-us/admin/contract/pdf/; `frontend/e2e/admin/admin-building-with-us.spec.js`.
