### FLOW: `public-consulting-load`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/consulting`
- **Interaction:** Leer el aviso de fallo de carga y reintentar para recuperar la presentación.
- **Outcomes:** `failure`, `success`
- **Evidence:** `frontend/pages/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
