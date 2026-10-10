### FLOW: `public-secure-link-create`

- **Módulo / rol:** enlaces seguros / cliente sin sesión.
- **Ruta:** `/{locale}/secure-link`, compartida desde el panel con **Enlace para clientes**.
- **Success:** empieza en Mensaje confidencial o permite elegir otra plantilla desde el dropdown; Personalizado muestra nombre y contenido. Campos, remitente, vigencia (1–7 días) y captcha generan una URL de un solo uso para copiar y enviar por el canal del cliente (la página no ofrece un atajo de correo); sólo el equipo puede abrirla y recibe un aviso sin enlace ni contenido.
- **Error:** los campos obligatorios faltantes o un captcha fallido se muestran en el formulario sin crear el enlace.
- **Failure:** catálogo no disponible ofrece reintento con envío bloqueado; HTML del servidor se reemplaza por un aviso y se preservan los campos.
- **Display:** campos esenciales visibles y opcionales bajo Más detalles. Crear otro enlace vuelve al formulario sin contenido del anterior.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/public/create/`.
- **Cobertura:** `e2e/public/public-secure-links.spec.js`, `e2e/responsive/public.spec.js`.
