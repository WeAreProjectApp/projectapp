### FLOW: `admin-secure-link-create`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links` → **Nuevo enlace**.
- **Success:** elegir tipo, título, campos, vigencia e idioma crea el enlace y muestra una única vez la URL con copiar enlace y copiar mensaje sugerido.
- **Error:** si falta un campo obligatorio (por ejemplo, la contraseña) el formulario muestra el error del servidor en ese campo y no crea nada.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/create/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`.
