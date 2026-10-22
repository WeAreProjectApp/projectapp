### FLOW: `admin-building-on-demand-explainer-visibility`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/:locale/panel/cells`
- **Interaction:** Mostrar u ocultar el video público de Scrum; confirmar el guardado o restaurar el estado previo si falla.
- **Outcomes:** `success`, `failure`
- **Evidence:** frontend/components/ExplainerVisibilityToggle.vue; frontend/stores/explainer_videos.js.
- **Scope:** Sin formulario de datos; los permisos y parámetros HTTP se validan en backend.
