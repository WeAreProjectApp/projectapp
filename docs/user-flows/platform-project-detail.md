### platform-project-detail — Detalle de proyecto

- **Rol:** administrador o cliente autorizado.
- **Ruta:** `/platform/projects/:id`.
- **Interacción:** abrir un espacio por ID. Un administrador puede volver a su ficha comercial del Panel en otra pestaña.
- **Error:** 403 o 404 muestra una explicación sin datos ni navegación interna del proyecto; un error recuperable ofrece reintentar. Una sesión sin autenticación se dirige al inicio de sesión.
- **Validación:** automatizada exclusivamente en CI; acceso real por roles en Chrome coordinado con dev-qa.

Actualización 2026-11-12: El acceso directo ajeno termina la carga con 403, permite regresar al listado propio y abrir un proyecto autorizado, en ambos sentidos entre clientes. Mensajes 403/404 y recuperación conservan idioma es-co/en-us (PA-252). La cobertura nueva se ejecuta en CI; la aceptación manual requiere un corte propio.
