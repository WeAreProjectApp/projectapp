### FLOW: `admin-platform-help-videos`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/:locale/panel/platform/help`
- **Interaction:** Llegar desde el menú del panel a Ayuda y previsualizar las piezas general, Appi y voz en español. Sustituir un MP4, rechazar archivos incompatibles y conservar la versión anterior ante un error del servidor; retirar o restaurar usando el ciclo compartido con MCP.
- **Outcomes:** `display`, `success`, `error`, `failure`
- **Evidence:** frontend/pages/panel/platform/help.vue; frontend/components/platform/PlatformVideoResourcesManager.vue; frontend/components/resources/VideoResourceManager.vue.
- **Scope:** Se llega desde la navegación del panel y se comprueba el contenido de las tres piezas. La sustitución, la validación local de MP4 y el rechazo del servidor se ejercitan en la interfaz; los permisos, la concurrencia y el ciclo completo de carga, retirada y restauración por MCP se prueban en backend. Los interruptores compartidos pertenecen al flujo de administración de Ayuda.
