### FLOW: `public-building-on-demand-pdf`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/building-on-demand`
- **Interaction:** Pulsar Descargar PDF en el control flotante de la presentación y consultar el aviso cuando la solicitud no logra descargar el archivo.
- **Outcomes:** `success`, `failure`
- **Result:** Se descarga `building-on-demand-es.pdf` o `building-on-demand-en.pdf` según el idioma. Si falla la descarga, aparece «No pudimos descargar el PDF. Vuelve a intentarlo.» sin ocultar el programa. El documento público no incluye la economía interna ni el contrato.
- **Evidence:** `frontend/components/BuildingOnDemand/ProgramView.vue:75`; `frontend/components/BuildingOnDemand/ProgramView.vue:251`; GET `/api/building-on-demand/public/pdf/?lang=es`; `frontend/e2e/public/building-on-demand.spec.js`.
- **Scope:** Los datos privados del PDF se comprueban en backend; el navegador verifica el archivo entregado o el aviso de la solicitud fallida.
