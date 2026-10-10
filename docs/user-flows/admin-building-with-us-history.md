### FLOW: `admin-building-with-us-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/:locale/panel/building-with-us`
- **Interaction:** Consultar la versión vigente, autor y nota; pulsar Ver más para cargar offset=20 y reintentar un fallo del historial.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/BuildingWithUs/admin/VersionHistory.vue; frontend/stores/building_with_us.js; GET /api/building-with-us/admin/program/versions/?limit=20&offset=20; GET /api/building-with-us/admin/contract/versions/; `frontend/e2e/admin/admin-building-with-us.spec.js`.
