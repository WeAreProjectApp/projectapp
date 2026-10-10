### FLOW: `public-building-with-us-language`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-with-us`
- **Interaction:** Cambiar a English y leer el programa en inglés conservando la ruta pública localizada.
- **Outcomes:** `success`
- **Evidence:** frontend/components/BuildingWithUs/ProgramView.vue; frontend/pages/building-with-us/index.vue; GET /api/building-with-us/public/?lang=en; `frontend/e2e/public/building-with-us.spec.js`.
