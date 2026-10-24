### FLOW: `admin-platform-help-videos`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/:locale/panel/platform/help`
- **Interaction:** Administrar las tres piezas desde Ayuda: consultar recursos, sustituir MP4 y conservar la versión anterior ante errores; retirar o restaurar usando el ciclo compartido con MCP.
- **Outcomes:** `display`, `success`, `error`, `failure`
- **Evidence:** frontend/components/platform/PlatformHelpVideoModal.vue; frontend/components/platform/PlatformVideoResourcesManager.vue.
- **Scope:** El catálogo filtra las capacidades efectivas; controles de acceso, concurrencia y MCP se prueban en backend. El modo cliente no tiene formulario de datos ni validación de entrada propia.
