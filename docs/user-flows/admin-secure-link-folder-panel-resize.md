### FLOW: `admin-secure-link-folder-panel-resize`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/secure-links`
- **Description:** Admin resizes the adjacent secure-links folder navigation by mouse or keyboard from 240px to 480px, starting at 256px. The list reflows during drag; projectapp-secure-links-folder-width persists independently of Documents, and double-click restores the default. Below panel-landscape the drawer replaces the sidebar.
- **Selector:** `secure-folders-resize-handle`
- **Outcomes:** display, success
- **Pasos:** abrir la vista desde el menú, arrastrar el separador en ambos sentidos y comprobar cómo cambia el contenido contiguo. Redimensionar con teclado, recargar y comprobar persistencia; el doble clic restaura el ancho inicial. Comprobar que en móvil el drawer conserva los accesos.
- **Error/failure:** n/a; el ajuste del ancho es local. Los fallos de carga pertenecen al flujo del listado.
