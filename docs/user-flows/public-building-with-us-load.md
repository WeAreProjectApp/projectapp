### FLOW: `public-building-with-us-load`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/building-with-us`
- **Interaction:** Abrir un enlace público con la API indisponible, leer el error y reintentar hasta recuperar el programa.
- **Outcomes:** `failure`, `success`
- **Evidence:** frontend/pages/building-with-us/index.vue; GET /api/building-with-us/public/; `frontend/e2e/public/building-with-us.spec.js`.
