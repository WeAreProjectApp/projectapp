### FLOW: `public-building-on-demand-theme`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Pulsar Cambiar tema en el control flotante y volver a cargar la presentación; ante una carga fallida, pulsar Reintentar para recuperar el programa con el tema guardado.
- **Outcomes:** `success`, `failure`
- **Result:** La página y sus controles alternan entre claro y oscuro y recuperan la preferencia al recargar. El aviso de carga y el programa recuperado conservan ese mismo tema.
- **Evidence:** `frontend/components/BuildingOnDemand/ProgramView.vue:254`; `frontend/composables/useBuildingOnDemandTheme.js:3`; `frontend/pages/building-on-demand/index.vue:126`; `projectapp-building-on-demand-theme`; `frontend/e2e/public/building-on-demand.spec.js`; `frontend/e2e/public/commercial-public-overlays.spec.js`.
- **Scope:** Este flujo verifica la conservación de la preferencia durante el fallo y la recuperación; el aviso y la recuperación de contenido también se registran en `public-building-on-demand-load`.
