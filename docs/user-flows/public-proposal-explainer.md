### FLOW: `public-proposal-explainer`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Ruta:** `/:locale/proposal/:uuid`
- **Interacción:** Reproducir el video de bienvenida sobre las cuatro opciones. La selección de una opción detiene el audio y abre su contenido. Si falla el archivo, el enlace de respaldo permite abrirlo aparte. Se oculta sin ambos controles, español, propuesta activa, detalle técnico activo o Contrato y condiciones.
- **Outcomes:** `display`, `success`, `failure`
- **Evidencia:** `ProposalViewGateway.vue`, `ExplainerVideoCard.vue`, `proposal_explainer_video_visible()`.
