### FLOW: `admin-consulting-preview`

- **Module:** commercial
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/consulting`
- **Interaction:** Consultar versión y previsualizar español o inglés; reintentar ante un fallo de carga.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** `frontend/pages/panel/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
