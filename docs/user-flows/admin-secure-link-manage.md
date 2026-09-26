### FLOW: `admin-secure-link-manage`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links`; `?link=<id>` abre el detalle (destino del correo de aviso).
- **Display:** pestañas por estado con conteos y **Recibidos** con los enlaces sin abrir que envían los clientes.
- **Success:** el detalle muestra historial, **Ver contenido** descifra sin gastar el enlace, **Revocar** lo desactiva y **Reactivar** lo vuelve a habilitar (opcionalmente con un enlace nuevo).
- **API:** `GET /api/secure-links/`, `GET /api/secure-links/<id>/`, `POST .../content/`, `POST .../revoke/`, `POST .../reactivate/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`.
