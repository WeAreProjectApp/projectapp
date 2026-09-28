### FLOW: `admin-secure-link-manage`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links`; `?link=<id>` abre el detalle.
- **Display:** pestañas con conteos, Recibidos y detalle con historial; cancelar una eliminación conserva el registro.
- **Success:** consultar contenido sin consumir el enlace; editar título/asociaciones sin descifrar, editar contenido explícitamente, confirmar eliminación permanente, revocar o reactivar (opcionalmente con URL nueva).
- **Error:** campos inválidos al editar conservan el borrador y muestran el error junto al campo; un registro inexistente muestra error visible.
- **Failure:** errores de consulta ofrecen reintento; un fallo al guardar/eliminar conserva el borrador o la fila. Respuestas atrasadas no sustituyen el enlace abierto ni reponen secretos tras cerrar.
- **API:** `GET /api/secure-links/`, `GET|PATCH|DELETE /api/secure-links/<id>/`, `POST .../content/`, `POST .../revoke/`, `POST .../reactivate/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`; la persistencia y los permisos MCP se verifican en backend. Los tests unitarios cubren concurrencia de respuestas y limpieza al cerrar.
