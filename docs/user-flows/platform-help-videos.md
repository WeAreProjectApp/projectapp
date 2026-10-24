### FLOW: `platform-help-videos`

- **Module:** platform
- **Role:** client
- **Priority:** P2
- **Route:** `/:locale/platform/projects`
- **Interaction:** Abrir Ayuda desde el menú, consultar y reproducir manualmente los tutoriales disponibles; elegir clip, cerrar o reintentar ante un fallo de reproducción. Español identificado también en interfaz inglesa.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/platform/PlatformHelpVideoModal.vue; frontend/components/platform/PlatformVideoResourcesManager.vue.
- **Scope:** El catálogo filtra las capacidades efectivas; controles de acceso, concurrencia y MCP se prueban en backend. El modo cliente no tiene formulario de datos ni validación de entrada propia.
