### FLOW: `public-secure-link-reveal`

- **Módulo / rol:** enlaces seguros / destinatario sin sesión.
- **Ruta:** `/{locale}/secure-link/view#<token>` (el token viaja en el fragmento).
- **Display:** tipo, remitente, vencimiento y advertencia de un solo uso; cargar la página no gasta el enlace.
- **Success:** **Ver contenido** revela los campos una vez, con mostrar/ocultar y copiar.
- **Failure:** enlaces usados, vencidos, revocados o inválidos muestran su estado sin contenido; los creados por clientes piden iniciar sesión del equipo.
- **API:** `POST /api/secure-links/public/status/`, `POST /api/secure-links/public/reveal/`.
- **Cobertura:** `e2e/public/public-secure-links.spec.js`, `e2e/responsive/public.spec.js`.
