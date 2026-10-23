### FLOW: `admin-consulting-history`

- **Module:** commercial
- **Role:** admin
- **Priority:** P2
- **Route:** `/:locale/panel/consulting`
- **Interaction:** Consultar revisiones y cargar la página siguiente; reintentar sin perder las versiones mostradas.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** `frontend/pages/panel/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
