### FLOW: `public-consulting-guide`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/consulting`
- **Interaction:** Leer la guía de primera visita, avanzar, omitir y reiniciarla.
- **Outcomes:** `display`, `success`
- **Evidence:** `frontend/pages/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
