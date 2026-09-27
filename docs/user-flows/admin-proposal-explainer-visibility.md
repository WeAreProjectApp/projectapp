### FLOW: `admin-proposal-explainer-visibility`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/:locale/panel/proposals` → `Configuraciones`
- **Interacción:** Previsualizar el video y activar o desactivar su visibilidad general. El guardado exitoso confirma el cambio; ante un fallo, el interruptor vuelve al valor anterior y se informa el error. Se conservan las preferencias individuales.
- **Outcomes:** `display`, `success`, `failure`
- **Evidencia:** `pages/panel/proposals/index.vue`, `ExplainerVisibilityToggle.vue`, `stores/explainer_videos.js`.
