### FLOW: `public-building-on-demand-estimator`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Desde el pie público, consultar las tareas y la explicación del estimador vacío; añadir o quitar unidades, describir el pedido y leer el rango, el encaje por nivel y el enlace para pedir una estimación formal por WhatsApp.
- **Outcomes:** `display`, `success`
- **Result:** Sin selección aparecen tareas, cantidades en cero y la aclaración de que la estimación formal se aprueba antes de empezar. Al seleccionar tareas, el rango es el total del pedido, comparado con cada bolsa mensual. Una tarea que requiere diseño, arquitectura o levantamiento de requerimientos puede elevar la sugerencia a Business aunque quepa en Starter; DevOps continuo requiere Enterprise. El enlace incluye tareas, cantidades, descripción, rango y nivel sugerido.
- **Evidence:** `frontend/components/BuildingOnDemand/BagEstimator.vue:53`; `frontend/components/BuildingOnDemand/BagEstimator.vue:142`; `frontend/utils/buildingOnDemand.js:66`; `frontend/utils/buildingOnDemand.js:117`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** La compatibilidad de roles es información de la estimación, no un error de permiso. Las cantidades están limitadas a cero–diez y la descripción a mil caracteres; no existe un envío validable ni una llamada de cálculo que pueda fallar.
