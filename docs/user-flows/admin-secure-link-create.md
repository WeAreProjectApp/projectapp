### FLOW: `admin-secure-link-create`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links` → **Nuevo enlace**.
- **Success:** elegir tipo predefinido o Personalizado (nombre y contenido), título, campos, vigencia e idioma, sin exigir cliente ni proyecto, crea el enlace y muestra una única vez la URL con copiar enlace y copiar mensaje sugerido.
- **Error:** si falta un campo obligatorio (por ejemplo, la contraseña) el formulario valida antes de enviar y muestra los errores del servidor junto a sus campos y no crea nada.
- **Failure:** catálogo no disponible bloquea el envío y permite reintentar; errores HTML/servidor se convierten en avisos breves, conservando el contenido para reintentar.
- **Display:** al cancelar y volver a Nuevo enlace, las credenciales aparecen vacías y la contraseña vuelve a estar oculta.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/create/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`.
