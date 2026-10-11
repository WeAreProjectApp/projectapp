### FLOW: `public-building-on-demand-faq`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Expandir una pregunta frecuente sobre la bolsa de horas y volver a contraerla.
- **Outcomes:** `success`
- **Result:** El control cambia su estado expandido y revela la respuesta correspondiente; las horas sin usar vencen al finalizar el mes y no se acumulan.
- **Evidence:** `frontend/components/BuildingOnDemand/ProgramView.vue:54`; `frontend/components/BuildingOnDemand/ProgramView.vue:227`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** El acordeón usa respuestas ya cargadas: no hay validación de entrada ni solicitud al servidor al expandirlo.
