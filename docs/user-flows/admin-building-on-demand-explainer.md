### FLOW: `admin-building-on-demand-explainer`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Route:** `/:locale/panel/cells`
- **Interaction:** Entrar a Células desde el panel, consultar la tarjeta compacta y reproducir el video; pausar al perder foco y ofrecer un enlace al archivo si falla.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/pages/panel/cells/index.vue; frontend/components/ExplainerVideoCard.vue.
- **Scope:** Sin formulario de datos; los permisos y parámetros HTTP se validan en backend.
