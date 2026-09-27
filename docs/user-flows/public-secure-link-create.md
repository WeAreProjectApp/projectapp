### FLOW: `public-secure-link-create`

- **Módulo / rol:** enlaces seguros / cliente sin sesión.
- **Ruta:** `/{locale}/secure-link`, compartida desde el panel con **Enlace para clientes**.
- **Success:** tipo predefinido o Personalizado (nombre y contenido), campos, nombre del remitente, vigencia (1–7 días) y captcha generan una URL de un solo uso para copiar o enviar por correo; sólo el equipo puede abrirla y el equipo recibe un aviso sin el enlace ni el contenido.
- **Error:** los campos obligatorios faltantes o un captcha fallido se muestran en el formulario sin crear el enlace.
- **Failure:** catálogo no disponible ofrece reintento con envío bloqueado; HTML del servidor se reemplaza por un aviso y se preservan los campos.
- **Display:** Crear otro enlace vuelve al formulario con credenciales vacías.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/public/create/`.
- **Cobertura:** `e2e/public/public-secure-links.spec.js`, `e2e/responsive/public.spec.js`.
