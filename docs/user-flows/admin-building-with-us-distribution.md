### FLOW: `admin-building-with-us-distribution`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/building-with-us`
- **Interaction:** Navegar desde Comercial, copiar la URL inglesa, descargar el PDF y cambiar el idioma de la vista previa sin cambiar la URL del panel; reintentar un fallo del resumen.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/config/panelNav.js; frontend/components/BuildingWithUs/admin/DistributionCard.vue; frontend/pages/panel/building-with-us/index.vue; GET /api/building-with-us/admin/; `frontend/e2e/admin/admin-building-with-us.spec.js`.
