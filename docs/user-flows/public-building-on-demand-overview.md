### FLOW: `public-building-on-demand-overview`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Desde el inicio público, usar el enlace Building on Demand del pie y consultar la célula Scrum compartida, sus roles y los tres niveles.
- **Outcomes:** `display`
- **Result:** Starter, Business y Enterprise presentan bolsas mensuales de 96, 192 y 288 horas; Business figura como recomendado. Las tarjetas muestran precio mensual, roles y servidor, sin tarifa por hora ni costos internos.
- **Evidence:** `frontend/components/layouts/FooterDesktop.vue:236`; `frontend/components/layouts/FooterMobile.vue:130`; `frontend/components/BuildingOnDemand/ProgramView.vue:155`; `frontend/components/BuildingOnDemand/TierCard.vue:34`; GET `/api/building-on-demand/public/?lang=es`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** La navegación y los datos visibles son el comportamiento de consulta. Los fallos de la carga pertenecen a `public-building-on-demand-load`.
