### FLOW: `public-consulting-share`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/consulting`
- **Interaction:** Abrir Compartir, copiar la URL actual y leer confirmación o error de portapapeles.
- **Outcomes:** `success`, `failure`
- **Evidence:** `frontend/pages/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
