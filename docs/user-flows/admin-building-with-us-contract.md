### FLOW: `admin-building-with-us-contract`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/building-with-us`
- **Interaction:** Abrir Contrato, consultar la versión y el documento sincronizado; previsualizar y descargar PDF, abrir el documento exacto en el Gestor, editar con motivo y volver para consultar la nueva versión. Conservar el borrador ante conflicto o fallo de guardado; consultar estados desactualizado o sin inicializar y reintentar fallos de lectura.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/BuildingWithUs/admin/ContractPanel.vue; frontend/pages/panel/building-with-us/index.vue; GET /api/building-with-us/admin/contract/; GET /api/building-with-us/admin/contract/pdf/; `frontend/e2e/admin/admin-building-with-us.spec.js`.

La edición compartida y sus errores se registran en `admin-program-contract-edit`.
