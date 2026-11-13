### FLOW: `admin-monitoring-case-note`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, modal de caso.
- **Display:** notas con autor y fecha dentro del historial paginado.
- **Success:** agregar una nota la incorpora al historial compartido; cambiar páginas no borra el borrador.
- **Error:** nota vacía no se envía; validación rechazada conserva el texto y muestra el error.
- **Failure:** un fallo del servidor conserva la nota para reintentar.
- **API:** POST cases/:id/notes y GET cases/:id de `/api/monitoring/`.
- **Pruebas:** `e2e/admin/admin-monitoring-case-follow-up.spec.js`; ejecución y SHA se acreditan en CI.
