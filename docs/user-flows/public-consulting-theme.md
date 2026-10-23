### FLOW: `public-consulting-theme`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/consulting`
- **Interaction:** Cambiar el tema y conservar la preferencia al recargar.
- **Outcomes:** `success`
- **Evidence:** `frontend/pages/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
