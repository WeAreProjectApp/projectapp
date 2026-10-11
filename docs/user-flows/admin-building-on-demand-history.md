### FLOW: `admin-building-on-demand-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/:locale/panel/cells`
- **Interaction:** Consultar el historial del programa y pulsar Ver más; si falla una página, pulsar Reintentar para recuperar las versiones restantes.
- **Outcomes:** `success`, `failure`
- **Result:** El historial muestra versión, autor, fecha, nota y origen de una restauración. Con 21 revisiones, Ver más añade la versión pendiente a las primeras veinte usando `offset=20`; los errores no borran lo ya cargado.
- **Evidence:** `frontend/pages/panel/cells/index.vue:90`; `frontend/components/BuildingOnDemand/admin/VersionHistory.vue:24`; `frontend/stores/building_on_demand.js:135`; GET `/api/building-on-demand/admin/program/versions/?limit=20&offset=20`; `frontend/e2e/admin/admin-building-on-demand.spec.js`.
- **Gap:** Contrato monta otro historial con el mismo componente y su propio endpoint. Su paginación y su estado vacío requieren evidencia específica y no se dan por cubiertos al probar el historial del programa.
