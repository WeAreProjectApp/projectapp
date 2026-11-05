# Accesos autorizados

Panel y plataforma conservan contraseña y añaden código por correo y Google. Ningún login registra usuarios. El estado `User.is_active` es la autoridad de habilitación; el panel también exige `is_staff`. Clientes comerciales/proyectos no conceden acceso por existir. Accesos permite registrar un cliente sin proyecto ni habilitación, y habilitarlo después. Los controles anteriores reutilizan la misma autoridad. Las APIs existentes de administradores de plataforma conservan sus permisos sobre clientes; el módulo Accesos exige sesión staff. El equipo administra clientes; sólo superusuarios administran equipo, con protección contra autobloqueo y último superusuario.

## Código y Google

`GET /api/auth/config/` prepara CSRF y navegador y publica el ID de cliente Google (público). `POST /api/auth/{panel|platform}/{email-request|email-verify|google-challenge|google-verify}/` exige CSRF. Solicitar código o preparar Google exige el captcha vigente; verificar usa el desafío ligado al navegador. La respuesta pública de solicitud es genérica.

Código: seis dígitos generados con secrets, diez minutos, cinco intentos, una utilización, sustitución global entre superficies. Se conserva HMAC con clave del servidor; el worker Huey sólo recibe el identificador y genera el código en memoria. No hay código en argumentos persistidos. Cada desafío liga identidad, versión de acceso, navegador y superficie. Emisión: 60 segundos entre envíos, cinco por correo/15 minutos, 30 por IP/15 minutos. Los buckets DB compartidos se bloquean en orden estable. La limpieza diaria retira desafíos y buckets antiguos; no retira auditoría.

Google Identity Services verifica firma/audiencia/emisor/expiración, email_verified y nonce de cinco minutos consumido mediante escritura condicional. Admite Gmail y Workspace con hd. Vincula sub sólo con correo local habilitado y único. No descarga avatares ni pide acceso a Gmail. El primer acceso por código/Google verifica correo, completa onboarding, invalida contraseña temporal y conserva el requisito de perfil. Contraseñas definitivas permanecen. Recuperación permite establecer una contraseña opcional.

Referencia: [validación oficial de Google ID tokens](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), incluida la autoridad del correo de Gmail/Workspace y el identificador estable sub.

La versión de acceso invalida sesiones y JWT/refresh anteriores cuando cambia identidad, contraseña, habilitación o permisos; desvincular Google también revoca. Sesiones/tokens anteriores a esta versión se consideran versión cero. Deshabilitar y reactivar no recupera las sesiones previas.

## Administración y MCP

`/panel/access`: clientes/equipo, búsqueda, dropdowns combinables, vistas guardadas, orden, paginación y actividad. API con sesión/CSRF: `/api/accounts/access/` GET/POST y `/api/accounts/access/{user_id}/` GET/PATCH. Crear recibe nombre/correo/empresa; el PATCH sólo acepta enabled y unlink_google. La actividad está paginada por cuenta y conserva fecha, acción, método, superficie, IP y navegador sin credenciales.

MCP projects incorpora list_accesses, get_access, create_client_access y change_access (sensible). Usa el actor y la confirmación del conector, los servicios del panel y esquemas cerrados. El catálogo no expone desafíos, huellas ni identificadores privados Google.

## Correo y despliegue

El gateway aplica por canal una excepción obligatoria para login_code, client_invitation, admin_invitation, verification_code_* y magic_link. Entrega sólo al destinatario primario, sin copias. El snapshot se genera desde una constancia neutra antes de SMTP. El escritor adicional del historial también neutraliza cuerpo/metadatos. Historial, adjuntos y reenvío rechazan canales protegidos aunque el registro sea histórico. No se elimina evidencia histórica ni se retiran copias de buzones previos. password_changed conserva copias porque no contiene credenciales.

Aplicar la migración aditiva accounts.0091 por el deploy, nunca desde un worktree. Configurar GOOGLE_OAUTH_CLIENT_ID propio de ProjectApp y sus orígenes HTTPS autorizados en Google; no reutilizar configuración de GM ni los proyectos base. No requiere client secret para el flujo GIS de ID token. Sin configuración Google queda deshabilitado y siguen disponibles código/contraseña. Mantener captcha de producción.

Configurar ACCESS_TRUSTED_PROXY_IPS con las IP exactas de nginx/proxies de entrada; por defecto no se confía en X-Forwarded-For. Se toma sólo la última IP añadida por el proxy confiable. No registrar cuerpos de solicitudes de /api/auth/ en observabilidad o proxies. Reiniciar aplicación y Huey tras desplegar. Verificar en staging ingreso por los tres métodos y revocación antes de activar en producción.
