# Enlaces seguros de un solo uso

Módulo para compartir información sensible (contraseñas, llaves API, accesos a
servidor o base de datos, `.env`, datos bancarios, códigos 2FA y comunicados
confidenciales) sin pegarla en correos ni WhatsApp. El contenido queda
**guardado y cifrado** en ProjectApp; el enlace sólo se consume, vence, se
revoca o se reactiva.

## Uso

| Quién | Dónde | Qué hace |
|---|---|---|
| Equipo | `/panel/secure-links` → **Nuevo enlace** | Elige tipo, título interno, campos, vigencia (1/3/7/30 días, 7 por defecto) e idioma; copia la URL o el mensaje sugerido. |
| Asistente | MCP `communications` → `create_secure_link` | La skill `client-response` crea el enlace **con contenido** y pone la URL en los borradores. Si el secreto no está en la conversación, se lo pide al operador. |
| Cliente | `https://projectapp.co/es-co/secure-link` (botón **Enlace para clientes** del panel) | Crea un enlace de hasta 7 días para enviárselo al equipo. **Sólo el equipo** (sesión del panel) puede abrirlo; el equipo recibe un correo sin enlace ni contenido. |

- **Abrir:** el destinatario ve tipo, remitente y vencimiento; el contenido sale
  sólo al pulsar **Ver contenido**. Recargar después muestra "ya fue utilizado".
- **Reactivar:** desde el detalle del enlace, con nueva vigencia. Por defecto se
  reactiva el **mismo** enlace; si otra persona pudo abrirlo, marca "generar un
  enlace nuevo" y el anterior deja de funcionar.
- **Ver en el panel:** muestra el contenido sin gastar el enlace y queda en el
  historial (quién y cuándo).
- **Recibidos:** pestaña con lo que envían los clientes y el conteo de enlaces
  sin abrir. El correo de aviso enlaza a `/panel/secure-links?link=<id>`.

## Seguridad

- **Cifrado:** carga útil JSON cifrada con Fernet (`PROJECT_ACCESS_CIPHER_KEY`,
  la misma llave de accesos de proyectos; no hay variable nueva). Un fallo de
  descifrado responde error explícito, nunca contenido vacío.
- **Token:** `secrets.token_urlsafe(32)` en el fragmento de la URL
  (`/{locale}/secure-link/view#<token>`). No llega a nginx, Silk, Referer ni a
  las vistas previas de WhatsApp/correo. La API recibe el token en el cuerpo de
  un POST; se guarda su SHA-256 para buscarlo y una copia cifrada para que el
  equipo pueda volver a copiar el enlace.
- **Un solo uso:** `reveal` bloquea la fila (`select_for_update`), revisa estado
  y marca `consumed_at` en la misma transacción. Los intentos rechazados quedan
  como `reveal_blocked` con el motivo.
- **Estado derivado:** revocado → usado → vencido → activo, calculado desde las
  fechas; no hay tarea programada de expiración.
- **Sin analítica:** `/secure-link` está en `PRIVATE_SEGMENTS`
  (`plugins/analytics.client.js`), sin navbar ni botón de WhatsApp, fuera del
  prerender y con `noindex` y `referrer=no-referrer`. Silk omite
  `/api/secure-links`.
- **Página pública:** reCAPTCHA (`verify_captcha`, fail-closed), honeypot,
  10 creaciones por hora por IP y 30 consultas por minuto por IP, topes de
  tamaño por campo y de 20 000 caracteres por enlace.
- **Respuestas con contenido:** `Cache-Control: no-store`; el frontend lo guarda
  sólo en estado efímero del componente y lo pinta como texto.
- **Correo:** clave `secure_link_received_team` en
  `outbound_email_inventory`, clasificación interna; nunca incluye el enlace ni
  el contenido.

## Contrato técnico

- App Django `secure_links`: `SecureLink`, `SecureLinkEvent` (append-only),
  `catalog.py` (8 tipos; tarjetas de pago excluidas a propósito),
  `services.py` (única capa de escritura para panel, página pública y MCP).
- API panel (sesión + CSRF, staff): `GET /api/secure-links/`,
  `POST create/`, `GET|PATCH|DELETE <id>/`, `POST <id>/content|link|reactivate|revoke/`.
- API pública: `GET public/types/`, `POST public/create|status|reveal/`.
- MCP: ver `docs/MCP_VALIDATION_RUNBOOK.md` → "Comunicaciones: enlaces seguros".
- Datos de desarrollo: `python manage.py create_fake_secure_links` (bloqueado en
  producción).

## Despliegue

El deploy aplica `secure_links.0001_initial` y `content.0259` (sólo la
descripción del conector Comunicaciones). Las herramientas MCP aparecen en el
conector Comunicaciones sin reemitir credenciales, salvo credenciales con
`allowed_tools` restringido.

## Fuera de alcance (posibles mejoras)

Compartir directo desde el modal de accesos del proyecto, solicitudes
personalizadas por cliente, varias aperturas por enlace, aviso por WhatsApp y
purga automática.
