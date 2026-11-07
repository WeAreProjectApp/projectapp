### FLOW: `platform-guided-tour-project`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-guided-tour.spec.js`

Guía del primer proyecto accesible, una vez por usuario; Ayuda permite repetirla en cualquier proyecto. No comparte vistos entre cuentas. Los controles explicados quedan visibles al cerrar el cajón global y el recorte sigue su geometría al cambiar entre móvil, tableta y escritorio.

| Resultado | Interacción y evidencia |
|---|---|
| display | Entrar por Documentos, navegar a Proyectos, al proyecto propio y a Bugs; repetir desde Ayuda. En móvil el cajón global se cierra antes de explicar Resumen. Conservar el mismo paso al redimensionar entre las cinco medidas; comprobar hueco SVG y tarjeta junto al control, sin borrar el acuse terminal al recargar. |
| success | Avanzar, saltar, repetir o guardar desde sus controles; comprobar el resultado visible y persistido. |
| error | Usar permisos o valores no admitidos; no se publica contenido ni se sobrescribe el estado vigente. |
| failure | Fallar una petición de carga o guardado; mostrar el error o conservar el acuse pendiente para reintento. |
