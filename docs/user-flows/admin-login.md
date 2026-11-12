### FLOW: `admin-login`

- **Módulo:** auth · **Rol:** admin · **Prioridad:** P1
- **Rutas:** `/panel/login` → `/admin/login/` → destino interno de `next`.
- **Recorrido:** elegir «Entrar con contraseña», completar credenciales y
  reCAPTCHA v2; enviar para crear la sesión y volver a la página solicitada.
- **Success:** CAPTCHA aceptado y credenciales de staff válidas crean la sesión.
- **Error:** token ausente, inválido o expirado bloquea el intento; se requiere
  una verificación nueva tras credenciales incorrectas.
- **Failure:** reCAPTCHA no disponible o script bloqueado deja el acceso cerrado
  con mensaje y Reintentar. Las sesiones previamente abiertas siguen vigentes.
- **Display:** «Entrar con contraseña» enlaza a `/admin/login/?next=%2Fpanel%2F`.
- **E2E:** `e2e/auth/auth-admin-login.spec.js` mantiene el hand-off;
  `e2e/captcha/panel-login-captcha.spec.js` recorre el formulario Django real,
  con base temporal y simulación únicamente del proveedor externo.
- **Ejecución:** `npx playwright test --config playwright.captcha.config.js panel-login-captcha.spec.js`.
- La abstención histórica para credenciales/sesión queda reemplazada por estos
  recorridos. POST sin JavaScript, CSRF y permisos se cubren además en backend.
