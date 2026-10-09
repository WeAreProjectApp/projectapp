### FLOW: `public-building-with-us-share`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-with-us`
- **Interaction:** Abrir el diálogo y copiar la URL actual; ante rechazo del portapapeles, conservar el enlace seleccionable y leer el error.
- **Outcomes:** `success`, `failure`
- **Evidence:** frontend/components/BuildingWithUs/ProgramView.vue; frontend/components/PublicDocumentShareButton.vue; `frontend/e2e/public/building-with-us.spec.js`.
