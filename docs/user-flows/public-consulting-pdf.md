### FLOW: `public-consulting-pdf`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/consulting`
- **Interaction:** Descargar el PDF en el idioma actual o leer el error de descarga conservando la presentación.
- **Outcomes:** `success`, `failure`
- **Evidence:** `frontend/pages/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
