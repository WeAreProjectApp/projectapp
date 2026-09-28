### FLOW: `public-proposal-personalized-video`

- **Módulo:** proposal
- **Rol:** invitado mediante enlace público
- **Prioridad:** P2
- **Ruta:** `/:locale/proposal/:uuid`.
- **Interacción:** elegir Vista Ejecutiva o Propuesta Completa, navegar después de la bienvenida y reproducir el video de la propuesta. Sin archivo no hay panel ni entrada en el índice; técnico, contrato y PDF no incorporan este recurso.
- **Outcomes:** display (sección opcional y título localizado tras navegación), success (reproducción dentro de ambas vistas), failure (error de carga con Reintentar). Error de validación no aplica: no hay formulario; enlaces desconocidos/expirados pertenecen a sus flujos existentes.
- **Evidencia:** `pages/proposal/[uuid]/index.vue` y `components/BusinessProposal/PersonalizedVideo.vue`.
- **E2E Spec:** `e2e/public/proposal-personalized-video.spec.js`.
