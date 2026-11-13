### FLOW: `admin-building-on-demand-contract`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/cells?tab=contract`
- **Interaction:** Abrir Contrato, consultar la versión y el documento sincronizado; previsualizar y descargar PDF, abrir el documento exacto en el Gestor, editar con motivo y volver para consultar la nueva versión. Conservar el borrador ante conflicto o fallo de guardado; consultar estados no disponible, desactualizado o sin inicializar y reintentar fallos de lectura.
- **Outcomes:** `display`, `success`, `failure`
- **Result:** La copia muestra el estado y los metadatos de sincronización y permite abrir el documento del Gestor Documental cuando existe. El contrato y su copia se administran desde MCP; el panel no edita ni sincroniza. `contract: null` con respuesta 404 muestra que el contrato todavía no está disponible, mientras un fallo del servidor presenta Reintentar.
- **Evidence:** `frontend/pages/panel/cells/index.vue:124`; `frontend/components/BuildingOnDemand/admin/ContractPanel.vue:42`; `frontend/stores/building_on_demand.js:48`; GET `/api/building-on-demand/admin/contract/`; GET `/api/building-on-demand/admin/contract/pdf/`; `frontend/e2e/admin/admin-building-on-demand.spec.js`.
- **Scope:** Los estados del espejo son resultados de consulta, no errores de entrada. Su historial y el fallo de descarga de PDF requieren evidencia adicional a la lectura del contrato.

La edición compartida y sus errores se registran en `admin-program-contract-edit`.
