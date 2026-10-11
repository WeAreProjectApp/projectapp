### FLOW: `public-building-on-demand-terms`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Seleccionar Mensual, 3 meses, 6 meses o 9 meses en el selector de plazo y comparar las tarjetas actualizadas.
- **Outcomes:** `success`
- **Result:** Cambian el precio mensual, descuento, total y ahorro a partir de los cálculos entregados por la API. En 9 meses los precios mensuales son 1.530.000, 3.360.000 y 7.200.000 COP, más IVA; la nota aclara que la bolsa se renueva cada mes y no se acumula.
- **Evidence:** `frontend/components/BuildingOnDemand/TermSelector.vue:20`; `frontend/components/BuildingOnDemand/ProgramView.vue:195`; `frontend/components/BuildingOnDemand/TierCard.vue:82`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** El selector usa opciones cerradas y actualiza la vista localmente: no envía datos ni tiene un fallo de escritura.
