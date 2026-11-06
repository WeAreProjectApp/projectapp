### FLOW: `admin-communication-panel-resize`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/communications`
- **Description:** Admin resizes the adjacent thread navigation by mouse or keyboard from 240px to 400px, starting at 288px. The thread list reflows during drag; the communications preference persists the width and double-click restores the default. Compact navigation uses the drawer.
- **Selector:** `communications-navigation-resize-handle`
- **Outcomes:** display, success
- **Pasos:** abrir la vista desde el menú, arrastrar el separador en ambos sentidos y comprobar cómo cambia el contenido contiguo. Redimensionar con teclado, recargar y comprobar persistencia; el doble clic restaura el ancho inicial. Comprobar que en móvil el drawer conserva los accesos.
- **Error/failure:** n/a; el ajuste del ancho es local. Los fallos de carga pertenecen al flujo del listado.
