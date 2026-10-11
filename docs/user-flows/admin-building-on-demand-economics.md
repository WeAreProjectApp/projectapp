### FLOW: `admin-building-on-demand-economics`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/cells?tab=economics`
- **Interaction:** Desde Comercial → Células, abrir Economía para consultar la referencia y los cálculos internos; ante un fallo de carga, pulsar Reintentar.
- **Outcomes:** `display`, `failure`
- **Result:** La referencia indica costo por hora de 55.000 COP e IVA del 19 %. El hosting mensual con IVA es 46.291, 116.501 y 200.991 COP; en Mensual las horas de equilibrio son 31,9, 74,2 y 170,9, equivalentes al 33 %, 39 % y 59 % de cada bolsa. Los cálculos los entrega el backend y no se publican en la presentación ni en el PDF público.
- **Evidence:** `frontend/pages/panel/cells/index.vue:121`; `frontend/components/BuildingOnDemand/admin/EconomicsTable.vue:89`; GET `/api/building-on-demand/admin/economics/`; `frontend/e2e/admin/admin-building-on-demand.spec.js`.
- **Scope:** Es una consulta de datos internos sin campos editables. El acceso de una persona sin permisos se comprueba en el guard y en los endpoints del panel, no mediante un formulario de este módulo.
