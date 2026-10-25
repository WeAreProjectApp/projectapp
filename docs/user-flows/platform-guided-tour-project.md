### FLOW: `platform-guided-tour-project`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-guided-tour.spec.js`

Guía del primer proyecto accesible, una vez por usuario; Ayuda permite repetirla en cualquier proyecto. No comparte vistos entre cuentas.

| Resultado | Interacción y evidencia |
|---|---|
| display | Entrar desde la navegación real y comprobar el contenido publicado o los datos de configuración. |
| success | Avanzar, saltar, repetir o guardar desde sus controles; comprobar el resultado visible y persistido. |
| error | Usar permisos o valores no admitidos; no se publica contenido ni se sobrescribe el estado vigente. |
| failure | Fallar una petición de carga o guardado; mostrar el error o conservar el acuse pendiente para reintento. |
