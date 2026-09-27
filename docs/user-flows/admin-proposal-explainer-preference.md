### FLOW: `admin-proposal-explainer-preference`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/:locale/panel/proposals/:id/edit` → `General`
- **Interacción:** Consultar la disponibilidad y cambiar la preferencia individual. El estado explica si falta el control general, idioma español, contrato, detalle técnico o propuesta activa. Un fallo de guardado restaura el valor anterior y muestra un error.
- **Outcomes:** `display`, `success`, `failure`
- **Evidencia:** `ProposalGeneralTab.vue`, `ProposalExplainerToggle.vue`, `pages/panel/proposals/[id]/edit.vue`.
