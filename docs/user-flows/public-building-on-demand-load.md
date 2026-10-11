### FLOW: `public-building-on-demand-load`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Abrir el enlace público con la API indisponible, leer «No pudimos cargar Building on Demand.» y pulsar Reintentar para recuperar la presentación.
- **Outcomes:** `failure`, `success`
- **Result:** El aviso se reemplaza por el programa vigente después de una respuesta válida; durante la carga se presenta un esqueleto.
- **Evidence:** `frontend/pages/building-on-demand/index.vue:25`; `frontend/pages/building-on-demand/index.vue:126`; GET `/api/building-on-demand/public/?lang=es`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** No hay formulario público ni validación de permisos. La validación de parámetros de la API corresponde a pruebas de backend.
