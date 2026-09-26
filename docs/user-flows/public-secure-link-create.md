### FLOW: `public-secure-link-create`

- **Módulo / rol:** enlaces seguros / cliente sin sesión.
- **Ruta:** `/{locale}/secure-link`, compartida desde el panel con **Enlace para clientes**.
- **Success:** tipo, campos, nombre, vigencia (1–7 días) y captcha generan una URL de un solo uso para copiar o enviar por correo; sólo el equipo puede abrirla y el equipo recibe un aviso sin el enlace ni el contenido.
- **Error:** los campos obligatorios faltantes o un captcha fallido se muestran en el formulario sin crear el enlace.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/public/create/`.
- **Cobertura:** `e2e/public/public-secure-links.spec.js`, `e2e/responsive/public.spec.js`.
