### FLOW: `platform-help-videos`

- **Module:** platform
- **Role:** client
- **Priority:** P2
- **Route:** `/:locale/platform/projects`
- **Interaction:** Abrir Ayuda desde el menú y elegir un tutorial disponible en un modal con subtítulos. Al completar un recorrido ofrece una invitación sin abrir el video automáticamente. La reproducción empieza sólo a petición; cerrar devuelve el foco a Ayuda. Permite reintentar un fallo de reproducción e identifica el contenido español también en la interfaz inglesa.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/platform/PlatformHelpVideoModal.vue; frontend/components/platform/PlatformVideoResourcesManager.vue.
- **Scope:** El catálogo filtra las capacidades efectivas; controles de acceso, concurrencia y MCP se prueban en backend. El modo cliente no tiene formulario de datos ni validación de entrada propia.
- **Validation:** Los diez casos de navegador de esta pieza verifican el acceso por controles visibles, las fuentes de video, la invitación después del recorrido, reproducción explícita, cierre, recuperación de reproducción, idioma y cinco anchos. La invitación se prueba con el host completo: el video permanece cerrado hasta elegir verlo y abre pausado. La recuperación del catálogo y las respuestas tardías se comprueban en pruebas de store/componente.
