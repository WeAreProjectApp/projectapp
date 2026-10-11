### FLOW: `admin-building-on-demand-contract`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/cells?tab=contract`
- **Interaction:** Abrir Contrato desde Células para consultar la revisión, el contenido y su copia en ProjectApp › Contratos; leer los estados Sincronizado, Desactualizado, Sin inicializar o todavía no disponible, descargar PDF y reintentar un fallo de carga.
- **Outcomes:** `display`, `success`, `failure`
- **Result:** La copia muestra el estado y los metadatos de sincronización y permite abrir el documento del Gestor Documental cuando existe. El contrato y su copia se administran desde MCP; el panel no edita ni sincroniza. `contract: null` con respuesta 404 muestra que el contrato todavía no está disponible, mientras un fallo del servidor presenta Reintentar.
- **Evidence:** `frontend/pages/panel/cells/index.vue:124`; `frontend/components/BuildingOnDemand/admin/ContractPanel.vue:42`; `frontend/stores/building_on_demand.js:48`; GET `/api/building-on-demand/admin/contract/`; GET `/api/building-on-demand/admin/contract/pdf/`; `frontend/e2e/admin/admin-building-on-demand.spec.js`.
- **Scope:** Los estados del espejo son resultados de consulta, no errores de entrada. Su historial y el fallo de descarga de PDF requieren evidencia adicional a la lectura del contrato.
