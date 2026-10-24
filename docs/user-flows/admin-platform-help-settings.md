### FLOW: `admin-platform-help-settings`

- **Módulo:** admin
- **Prioridad:** P1
- **Rol:** admin
- **E2E:** `frontend/e2e/admin/admin-platform-help.spec.js`

Configuración global y por cliente de recorridos y videos, con control de versión e historial de vistos por usuario.

| Resultado | Interacción y evidencia |
|---|---|
| display | Entrar desde la navegación real y comprobar el contenido publicado o los datos de configuración. |
| success | Avanzar, saltar, repetir o guardar desde sus controles; comprobar el resultado visible y persistido. |
| error | Usar permisos o valores no admitidos; no se publica contenido ni se sobrescribe el estado vigente. |
| failure | Fallar una petición de carga o guardado; mostrar el error o conservar el acuse pendiente para reintento. |
