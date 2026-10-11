### FLOW: `public-building-on-demand-guide`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Entrar desde el pie público en una primera visita, consultar el primer paso y avanzar en la guía; omitirla y volver a iniciarla con Repetir la guía.
- **Outcomes:** `display`, `success`
- **Result:** Nueve pasos explican producto, célula, plazo, nivel recomendado, bolsa, estimador, hosting, acciones y reinicio. La preferencia evita repetirla automáticamente en visitas posteriores.
- **Evidence:** `frontend/components/BuildingOnDemand/Onboarding.vue:12`; `frontend/components/BuildingOnDemand/ProgramView.vue:47`; `frontend/components/BuildingOnDemand/ProgramView.vue:253`; `frontend/components/PublicGuidedTour.vue`; `projectapp-building-on-demand-guide-seen`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** La guía opera sobre el contenido cargado y no solicita datos al servidor; no se inicia automáticamente en la vista previa del panel.
