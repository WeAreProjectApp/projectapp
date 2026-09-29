### FLOW: `admin-secure-link-create`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links` → **Nuevo enlace**.
- **Success:** escribir título y mensaje en la plantilla inicial Mensaje confidencial o elegir otro tipo desde el dropdown; Personalizado muestra nombre y contenido. Generar crea la URL automáticamente y ofrece copiar enlace o mensaje. Compartir es manual, sin borradores ni envío automático.
- **Error:** si falta un campo obligatorio (por ejemplo, la contraseña) el formulario valida antes de enviar y muestra los errores del servidor junto a sus campos y no crea nada.
- **Failure:** catálogo no disponible bloquea el envío y permite reintentar; errores HTML/servidor se convierten en avisos breves, conservando el contenido para reintentar.
- **Display:** campos esenciales visibles; opcionales bajo Más detalles y cliente/proyecto/idioma/vigencia bajo Configuración. Al cancelar y volver a Nuevo enlace, empieza otra vez en Mensaje confidencial sin contenido anterior; las contraseñas se ocultan al elegir Credenciales.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/create/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`.
