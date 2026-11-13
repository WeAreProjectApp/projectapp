### FLOW: `admin-platform-help-settings`

- **Módulo:** admin
- **Prioridad:** P1
- **Rol:** admin
- **E2E:** `frontend/e2e/admin/admin-platform-help.spec.js`

Administración de Ayuda, contenido e historial de vistos, con enlace a Feature flags para la disponibilidad global y por cliente.

| Resultado | Interacción y evidencia |
|---|---|
| display | Entrar desde la navegación real y comprobar el contenido publicado o los datos de configuración. |
| success | Abrir la gestión central o guardar contenido de ayuda desde sus controles; comprobar el resultado visible y persistido. |
| error | Usar permisos o valores no admitidos; no se publica contenido ni se sobrescribe el estado vigente. |
| failure | Fallar una petición de carga o guardado; mostrar el error o conservar el acuse pendiente para reintento. |


**PA-251/253/257/261 · delta de interfaz:** La lista de clientes consulta al escribir con debounce, descarta respuestas anteriores y conserva carga, errores, total y página de la consulta vigente. Limpiar vuelve a página 1 sin guardar configuración.
La autoría de pruebas de este delta se valida en CI sobre el SHA del PR; no acredita recorrido manual.
