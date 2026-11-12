### FLOW: `platform-help-videos`

- **Module:** platform
- **Role:** client
- **Priority:** P2
- **Route:** `/:locale/platform/projects`
- **Interaction:** Abrir Ayuda desde el menú y elegir un tutorial disponible en un modal con subtítulos. Al completar un recorrido ofrece una invitación sin abrir el video automáticamente. La reproducción empieza sólo a petición; cerrar devuelve el foco a Ayuda y permite volver a consultarlo. Revalida la disponibilidad al recuperar foco, conserva los recorridos si sólo se desactiva el video y ofrece los clips autorizados por separado. Permite reintentar un fallo de reproducción e identifica el contenido español también en la interfaz inglesa.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** frontend/components/platform/PlatformHelpVideoModal.vue; frontend/components/platform/PlatformVideoResourcesManager.vue.
- **Scope:** El catálogo filtra las capacidades efectivas; controles de acceso, concurrencia y MCP se prueban en backend. El modo cliente no tiene formulario de datos ni validación de entrada propia. La sesión de navegador reproduce el contrato real de cuenta: `user_id`, sin un alias `id`.
- **Validation:** La suite de navegador cubre el acceso por controles visibles, las fuentes de video, la invitación después del recorrido, reproducción explícita, cierre y reapertura, recuperación de reproducción, idioma y cinco anchos. Incluye apagado y reactivación efectivos, retirada del último recurso, conservación de recorridos y clips independientes. La invitación se prueba con el host completo: el video permanece cerrado hasta elegir verlo y abre pausado. La recuperación del catálogo, el cambio de cliente y las respuestas tardías se comprueban en pruebas de store/componente. La ejecución automatizada de PA-220 corresponde exclusivamente a CI; audio, subtítulos y correspondencia editorial se revisan en Chrome con DevQA y QA frontend.
