### FLOW: `proposal-gateway-guide`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** La portada con video y tarjetas ofrece una guía inicial y dos accesos inferiores derechos a Módulos adicionales y Programa de alianza. Los accesos abren las vistas públicas existentes en pestañas nuevas y conservan el idioma de la propuesta.
- **Steps:**
  1. Abrir la propuesta en su portada.
  2. Seguir u omitir la guía del video disponible, las tarjetas y los dos accesos.
  3. Abrir cada recurso sin abandonar la pestaña de la propuesta.
  4. Elegir una tarjeta; los accesos y la guía de portada desaparecen.
  5. Volver a la portada y reiniciar la guía con su botón de ayuda.
- **Branches:**
  - Sin video, el recorrido omite ese paso.
  - La guía no se abre automáticamente si ya fue vista; puede reiniciarse.
  - Las vistas ejecutiva, detallada, técnica y legal mantienen sus acciones propias.
- **E2E Spec:** `e2e/proposal/proposal-welcome-explainer.spec.js`
- **Components:** `ProposalViewGateway.vue`, `GatewayGuide.vue`, `PublicGuidedTour.vue`
