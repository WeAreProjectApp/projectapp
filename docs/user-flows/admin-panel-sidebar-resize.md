### FLOW: `admin-panel-sidebar-resize`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel`
- **Description:** Admin resizes the expanded desktop Panel menu from 200px to 400px with mouse or keyboard. Content follows its width; the 240px default and chosen width persist independently of collapse. Long labels wrap, including Paquetes de requerimientos. Consultoría y asesoría follows Células behind a divider in Programas, has a conversation icon and opens /panel/consulting.
- **Selector:** `panel-sidebar-resize-handle`
- **Outcomes:** display, success
- **Pasos:** abrir la vista desde el menú, arrastrar el separador en ambos sentidos y comprobar cómo cambia el contenido contiguo. Redimensionar con teclado, recargar y comprobar persistencia; el doble clic restaura el ancho inicial. Comprobar que en móvil el drawer conserva los accesos.
- **Error/failure:** n/a; el ajuste del ancho es local. Los fallos de carga pertenecen al flujo del listado.
