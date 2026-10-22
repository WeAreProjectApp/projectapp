### FLOW: `public-building-on-demand-explainer`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Llegar por la navegación pública, consultar y reproducir el video español bajo el encabezado; ofrecer enlace si falla y omitir la tarjeta sin recurso del idioma o con visibilidad apagada.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/BuildingOnDemand/ProgramView.vue; frontend/components/ExplainerVideoCard.vue.
- **Scope:** Sin formulario de datos; los permisos y parámetros HTTP se validan en backend.
