### FLOW: `public-building-with-us-pdf`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-with-us`
- **Interaction:** Descargar el PDF localizado; si falla la solicitud, leer el aviso sin perder el programa.
- **Outcomes:** `success`, `failure`
- **Evidence:** frontend/components/BuildingWithUs/ProgramView.vue; GET /api/building-with-us/public/pdf/?lang=es; `frontend/e2e/public/building-with-us.spec.js`.
