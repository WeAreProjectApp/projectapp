# Enlaces seguros de un solo uso

Módulo para compartir información sensible (contraseñas, llaves API, accesos a
servidor o base de datos, `.env`, datos bancarios, códigos 2FA y comunicados
confidenciales) sin pegarla en correos ni WhatsApp. El contenido queda
**guardado y cifrado** en ProjectApp; el enlace sólo se consume, vence, se
revoca o se reactiva.

## Uso

| Quién | Dónde | Qué hace |
|---|---|---|
| Equipo | `/panel/secure-links` → **Nuevo enlace** | Escribe título y contenido; el formulario empieza en Mensaje confidencial. Genera la URL, la copia y después puede marcarla como enviada. |
| Asistente | MCP `communications` → `create_secure_link` | La skill `client-response` crea el enlace **con contenido** y pone la URL en los borradores. Si el secreto no está en la conversación, se lo pide al operador. |
| Cliente | `https://projectapp.co/es-co/secure-link` (botón **Enlace para clientes** del panel) | Crea un enlace de hasta 7 días para enviárselo al equipo. **Sólo el equipo** (sesión del panel) puede abrirlo; el equipo recibe un correo sin enlace ni contenido. |

- **Abrir:** el destinatario ve tipo, remitente y vencimiento; el contenido sale
  sólo al pulsar **Ver contenido**. Recargar después muestra "ya fue utilizado".
- **Reactivar:** desde el detalle del enlace, con nueva vigencia. Por defecto se
  reactiva el **mismo** enlace; si otra persona pudo abrirlo, marca "generar un
  enlace nuevo" y el anterior deja de funcionar.
- **Editar:** título y asociaciones se pueden cambiar sin descifrar el secreto; **Editar contenido** carga sus campos de forma explícita. Guardar no cambia la URL, vigencia ni estado del enlace.
- **Eliminar:** borra permanentemente el enlace, contenido cifrado e historial; requiere confirmar en el panel o MCP. Revocar permite conservarlos.
- **Ver en el panel:** muestra el contenido sin gastar el enlace y queda en el
  historial (quién y cuándo).
- **Recibidos:** pestaña con lo que envían los clientes y el conteo de enlaces
  sin abrir. El correo de aviso enlaza a `/panel/secure-links?link=<id>`.

## Estados del enlace

| Estado | Cuándo aparece |
|---|---|
| Listo para compartir | El enlace ya existe y todavía no se marcó como enviado. |
| Enviado | El equipo pulsó **Marcar como enviado** después de compartirlo. Es una anotación manual; no envía correo ni confirma entrega. |
| Abierto | El destinatario pulsó **Ver contenido** y consumió el enlace. Visitar la página o consultar el contenido desde el panel no lo consume. |
| Vencido | Terminó la vigencia sin consumirse. |
| Revocado | El equipo desactivó el enlace. |

No hay borradores. Reactivar devuelve el enlace a Listo para compartir y limpia
la marca de envío actual; los eventos anteriores permanecen en el historial.
La marca de envío sólo está disponible para enlaces salientes activos. En
Recibidos, el estado inicial se presenta como **Disponible para abrir**.

## Formulario y errores

El tipo se elige con el mismo dropdown del formulario de parámetros de contrato
de servicio. **Personalizado** muestra debajo el campo para darle un nombre.
Los campos esenciales están visibles; **Más detalles** despliega los opcionales.
**Configuración** agrupa cliente, proyecto, idioma y vigencia del panel
(1/3/7/30 días, 7 por defecto). Cliente y proyecto siguen siendo opcionales.
La página pública conserva nombre del remitente y CAPTCHA cuando está habilitado.

La URL del enlace seguro se genera automáticamente. En la plantilla Credenciales,
**Dirección del sistema** es una URL opcional del sitio al que pertenece la
cuenta; **Usuario de la cuenta** y **Contraseña que quieres compartir** son los
datos confidenciales de esa cuenta, no el destinatario ni una contraseña extra
para abrir el enlace. Para compartir texto sin contraseña, usa Mensaje confidencial.

**Personalizado** pide `fields.custom_name` (nombre, hasta 200 caracteres) y
`fields.content` (texto libre, hasta 15 000). Ambos se cifran; las listas, MCP y
el estado público previo a revelar sólo muestran «Personalizado». El nombre no
se agrega a un catálogo global. API y MCP mantienen los endpoints y argumentos
existentes.

Los formularios validan antes de enviar, muestran errores junto al campo y
conservan el contenido mientras se reintenta. Si el catálogo falla, ofrecen
reintento y bloquean el envío. Las respuestas HTML del servidor o del proxy se
reemplazan por un mensaje breve; nunca se extrae texto de un traceback para
mostrarlo. Un fallo de configuración de cifrado devuelve JSON 503 con código
`secure_links_unavailable`, sin guardar enlace ni evento parcial.
El cliente HTTP no registra errores Axios de enlaces seguros: pueden contener
el secreto enviado o el token de apertura dentro del cuerpo de la petición.

Las credenciales nuevas empiezan vacías; cerrar el modal borra su contenido y
reabrir restablece el ocultamiento. Los campos de contraseña usan
`autocomplete="new-password"` y el formulario `autocomplete="off"`. Los gestores
externos pueden ignorar estas indicaciones: su comportamiento requiere prueba
con credenciales ficticias guardadas en el navegador afectado.

## Seguridad

- **Cifrado:** carga útil JSON cifrada con Fernet, con la misma clave de accesos
  y notas de proyectos. `PROJECT_ACCESS_CIPHER_KEY` conserva prioridad; si falta,
  se lee `PRIVATE_MEDIA_ROOT/runtime-secrets/project-access.key`.
  `PROJECT_ACCESS_CIPHER_KEY_FILE` permite indicar otra ruta privada. Un fallo de
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
  fechas; no hay tarea programada de expiración. El campo `status` conserva
  `active/consumed/expired/revoked`. `lifecycle_status` añade
  `ready/sent/opened/expired/revoked`, con `sent_at` y `sent_by` como metadatos.
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

- App Django `secure_links`: `SecureLink`, `SecureLinkEvent` (eventos inmutables mientras existe el enlace),
  `catalog.py` (8 tipos predefinidos y Personalizado; tarjetas de pago excluidas a propósito),
  `services.py` (única capa de escritura para panel, página pública y MCP).
- API panel (sesión + CSRF, staff): `GET /api/secure-links/`,
  `POST create/`, `GET|PATCH|DELETE <id>/`, `POST <id>/content|link|reactivate|revoke|mark-sent/`.
  El listado admite `lifecycle_status` y devuelve `lifecycle_counts` además
  de los filtros y conteos anteriores.
- API pública: `GET public/types/`, `POST public/create|status|reveal/`.
- MCP: ver `docs/MCP_VALIDATION_RUNBOOK.md` → "Comunicaciones: enlaces seguros".
- Datos de desarrollo: `python manage.py create_fake_secure_links` (bloqueado en
  producción).

## Despliegue

El deploy aplica las migraciones pendientes, incluida `secure_links.0003`
para fecha/actor de envío y el evento `marked_sent`. Las herramientas MCP aparecen en el
conector Comunicaciones sin reemitir credenciales, salvo credenciales con
`allowed_tools` restringido.

`manage.py check --deploy` valida la clave del entorno o archivo privado mediante
`projectapp.E002`, sin imprimirla. La clave también protege los accesos y notas
de proyectos: recuperar la existente si hay datos cifrados. Crear una nueva sólo
tras comprobar que no hay datos dependientes. No se genera ni se rota desde la app.

El archivo privado debe ser regular, sin symlinks ni hardlinks, propiedad del
usuario del servicio o root y sin permisos de grupo/otros (recomendado: 0600;
directorio: 0700). Mantenerlo fuera de Git y de media pública. Respaldar la
misma clave en almacenamiento privado fuera del checkout antes de usarla; una
nueva generación del código debe conservar ese archivo. Reiniciar los procesos
tras instalar/restaurar una clave: el cifrador está cacheado, mientras el check
de deploy siempre relee la configuración. Una clave de entorno inválida no se
sustituye silenciosamente por la del archivo.

Antes de generar una clave inicial comprobar, con lecturas de producción, que
no hay claves/cargas de `SecureLink`, contraseñas antiguas de `Project`,
contraseñas de `ProjectAdminAccess`, notas de `ProjectAccessNote` ni secretos
en `EntityRevision.secrets`. Si existen, restaurar su clave original.

## Fuera de alcance (posibles mejoras)

Compartir directo desde el modal de accesos del proyecto, solicitudes
personalizadas por cliente, varias aperturas por enlace, aviso por WhatsApp y
purga automática.


## Diagnóstico verificado en producción (2026-10-06)

En `vps-projectapp-prod`, con ProjectApp `57bb3677`, la configuración activa y
su fuente canónica carecían de `PROJECT_ACCESS_CIPHER_KEY`. La consulta de
las cinco columnas cifradas y `EntityRevision.secrets` devolvió cero datos
dependientes. La fuente canónica está versionada en el toolkit y su huella está
sellada por Integrity; añadir ahí la clave obligaría a versionar un secreto y a
renovar la autoridad root. El archivo privado permite conservar esa fuente.
La corrección requiere integrarse y desplegarse; el diagnóstico y las pruebas
aisladas no acreditan por sí solos la recuperación del sitio.

## Diagnóstico previo de creación en producción (2026-09-27)

Se reprodujo en tests la excepción no controlada ante una clave de cifrado
faltante o inválida y se agregó su manejo. Esto no confirma la causa del
incidente reportado en projectapp.co: la consulta de registros quedó pendiente
de la verificación adicional de Tailscale SSH. Antes de declarar resuelto el
incidente, correlacionar el traceback del POST `/api/secure-links/create/` con
la versión desplegada, comprobar migraciones y validar la configuración sin
imprimir la clave. No reemplazar una clave existente: protege datos anteriores.
Después del despliegue, verificar una creación con contenido ficticio.

## CRUD y consulta desde MCP (2026-09-28)

`update_secure_link` recibe `link_id` y los cambios de título, cliente, proyecto,
tipo o contenido. Omitir conserva; `fields` reemplaza el contenido completo y
cambiar tipo exige `fields`. Cliente/proyecto admiten `null`; si queda un
proyecto, su cliente se deduce igual que al crear. `delete_secure_link` exige
confirmación y borra definitivamente el registro y sus eventos.

`reveal_secure_link_content` es una lectura administrativa **sin consumir** el
enlace, incluso usado, vencido o revocado. Requiere seleccionar la herramienta
en el alcance personalizado de una credencial de Comunicaciones (MCPs →
Credenciales → Editar alcance). El acceso general no la incluye. Solicitarla
crea una confirmación de diez minutos; `confirm_action` entrega el contenido
sólo una vez. Si la respuesta se pierde o se repite, hay que pedir y confirmar
otra lectura. La auditoría `mcp_viewed` registra actor y credencial; ni el intent
ni los logs guardan el secreto o el resultado en claro. Una vez entregado, el
contenido queda bajo el manejo del cliente MCP que lo solicitó.

Confirmar relee permisos y bloquea el enlace mientras comprueba su versión y
ejecuta la acción. Un registro modificado/eliminado o una confirmación vencida,
cancelada o perteneciente a otra credencial no revela contenido. Los argumentos
inválidos se rechazan antes de persistir la confirmación. Las respuestas MCP
son `no-store`; listas y detalle ordinario continúan sin contenido ni URL.

El panel muestra errores de consulta con reintento, conserva el borrador si
falla un guardado y bloquea cierre/envíos repetidos durante esa operación.
Cerrar o abandonar borra contenido y URLs temporales; respuestas atrasadas no
reponen secretos. El listado usa la última petición y corrige la página tras
eliminar su última fila. La migración `secure_links.0002_mcp_viewed_event` sólo
agrega el tipo de evento; no cambia claves ni datos anteriores.
