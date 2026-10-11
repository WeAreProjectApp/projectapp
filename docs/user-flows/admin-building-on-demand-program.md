### FLOW: `admin-building-on-demand-program`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/cells` (`?tab=program` también abre Programa)
- **Interaction:** Abrir Comercial → Células, consultar la revisión vigente y el estado del conector; copiar la URL pública, descargar PDF y cambiar el idioma de la vista previa. Si falla el resumen, pulsar Reintentar.
- **Outcomes:** `display`, `success`, `failure`
- **Result:** Se muestran versión, autor, fecha y nota junto a los enlaces ES/EN y la vista previa. La administración corresponde exclusivamente al conector MCP `building-on-demand`; el panel consulta y distribuye el contenido.
- **Evidence:** `frontend/config/panelNav.js:57`; `frontend/pages/panel/cells/index.vue:78`; `frontend/components/BuildingOnDemand/admin/DistributionCard.vue:39`; `frontend/components/BuildingOnDemand/admin/McpHint.vue:16`; GET `/api/building-on-demand/admin/`; `frontend/e2e/admin/admin-building-on-demand.spec.js`.
- **Gap:** El rechazo del portapapeles, el fallo del PDF y el reintento de una vista previa fallida tienen controles propios; no se consideran cubiertos por el reintento del resumen. El acceso sin sesión corresponde al guard del panel.
