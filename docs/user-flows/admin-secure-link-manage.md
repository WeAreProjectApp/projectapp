### FLOW: `admin-secure-link-manage`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links`; `?link=<id>` abre el detalle.
- **Display:** pestañas con conteos de Listo para compartir, Enviado, Abierto, Vencido y Revocado, más Recibidos; detalle con historial y fecha de envío. Cancelar una eliminación conserva el registro.
- **Success:** marcar manualmente como enviado un enlace saliente activo sin enviar correo ni revelar contenido; consultar contenido sin consumir el enlace; editar datos o contenido explícitamente, eliminar con confirmación, revocar o reactivar. Reactivar vuelve a Listo y limpia la marca actual conservando el historial; revelar como destinatario produce Abierto.
- **Error:** campos inválidos al editar conservan el borrador y muestran el error junto al campo; un registro inexistente muestra error visible.
- **Failure:** errores de consulta ofrecen reintento; un fallo al guardar/eliminar/marcar enviado conserva los datos o la fila y muestra el error. Respuestas atrasadas no sustituyen el enlace abierto ni reponen secretos tras cerrar.
- **API:** `GET /api/secure-links/` (filtro `lifecycle_status` y conteos), `GET|PATCH|DELETE /api/secure-links/<id>/`, `POST .../content/`, `POST .../revoke/`, `POST .../reactivate/`, `POST .../mark-sent/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`; la persistencia y los permisos MCP se verifican en backend. Los tests unitarios cubren concurrencia de respuestas y limpieza al cerrar.
