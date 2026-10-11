### FLOW: `public-building-on-demand-language`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/es-co/building-on-demand` → `/en-us/building-on-demand`
- **Interaction:** Pulsar English en el selector de idioma y leer la presentación en inglés.
- **Outcomes:** `success`
- **Result:** La ruta pasa al idioma seleccionado y la API entrega el programa localizado, conservando los mismos niveles, plazos y bolsas.
- **Evidence:** `frontend/pages/building-on-demand/index.vue:114`; `frontend/components/BuildingOnDemand/ProgramView.vue:117`; GET `/api/building-on-demand/public/?lang=en`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** Los idiomas son opciones cerradas. La carga fallida de un idioma utiliza el mismo aviso y reintento que `public-building-on-demand-load`.
