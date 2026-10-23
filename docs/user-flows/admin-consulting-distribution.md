### FLOW: `admin-consulting-distribution`

- **Module:** commercial
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/consulting`
- **Interaction:** Desde Comercial, consultar enlaces ES/EN, copiar, abrir como cliente y descargar PDF. Informar errores de portapapeles y descarga.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** `frontend/pages/panel/consulting/index.vue`; `frontend/components/Consulting/`; `frontend/stores/consulting.js`; `/api/consulting/`.
- **Validación de entrada:** no se recibe información del cliente; los idiomas y la paginación inválidos se prueban en backend.
