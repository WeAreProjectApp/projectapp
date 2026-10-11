# Plantillas HTML de Linktree — Nivel 2

Especificación 1.0, implementada sobre la personalización básica del Linktree.

## Uso desde el panel

1. Abre **Linktrees → Editar → Apariencia → Plantilla HTML**. Guarda primero los datos del perfil.
2. Selecciona un ZIP, una carpeta o agrega archivos individuales. Son obligatorios `template.html` y `manifest.json`; `template.css` y `assets/` son opcionales.
3. **Subir y validar** crea una versión candidata. La publicación actual se conserva durante la validación.
4. Revisa errores/avisos, la vista previa aislada y las capturas a **320, 375 y 430 px**. Los errores impiden publicar.
5. En **Imágenes de la plantilla**, cambia o restablece las claves que el manifest declara editables; cada cambio se valida como una nueva versión.
6. **Publicar** activa el diseño en la misma URL pública. El historial conserva todas las publicaciones. Para recuperar una anterior, selecciónala y usa **Restaurar esta plantilla y validar**; luego publica.
7. **Restablecer tema básico** recupera los colores, logo y tipografía del editor. Conserva el historial.

La publicación es una instantánea de datos e imágenes: después de cambiar el perfil hay que **Validar con datos actuales → Publicar**. Así, un cambio de texto o imagen no elude las comprobaciones de accesibilidad de una versión aprobada. El panel lo indica junto a los controles.

La biblioteca se comparte **por cliente**, entre sus proyectos. El Linktree debe estar vinculado a un proyecto para compartir. Desactivar la compartición impide nuevas aplicaciones; las tarjetas que ya tienen una versión conservan esa publicación. Un proyecto de otro cliente nunca recibe esa plantilla en su biblioteca. El módulo mantiene el acceso de administración del panel (sesión + CSRF).

## Contrato para autores

- Mustache escapado: `name`, `role`, `bio`, `company`, `badge`, `footer_tagline`, `photo_url`, `logo_url`, `profile_url`, `initials`. Secciones normales/invertidas; sin HTML crudo, parciales, lambdas ni cambio de delimitadores.
- `primary_link`, `links` y `links.social`/`web`/`whatsapp`/`email`/`phone`/`file`. Cada enlace expone `label`, `url`, `icon`, `kind`, `index` (desde cero), `first`, `last`. Cuando se usa `primary_link`, `links` contiene los restantes; en otro caso incluye todos los enlaces activos con destino. Los botones de vCard/instalación se expresan mediante acciones.
- Enlaces: `<a data-link href="{{url}}">{{label}}</a>`. No se permiten destinos fijos. Las URLs del perfil se comprueban antes de renderizar.
- Acciones: `save-contact`, `install-pwa`, `share`, `whatsapp`, `email`, `copy`. `data-value` configura qué copiar. Un runtime exclusivo de la plataforma conecta las acciones y oculta las que no están disponibles.
- `data-icon` inserta un SVG Lucide local que hereda `currentColor`. Catálogo vendorizado 1.47.0 con licencia ISC; no se descarga JavaScript externo.
- Biblioteca de imágenes por Linktree (`LinktreeAsset`): cada tarjeta tiene sus propias imágenes con clave, subidas desde `POST /api/linktrees/admin/<id>/assets/` o con `upload_linktree_asset` (MCP). La plantilla las usa con `<img data-asset="clave">`/`asset(clave)` o pegando la URL devuelta (`src="/api/linktrees/admin/<id>/assets/<clave>/"`, `url(...)`); al subir el paquete la URL se normaliza a la clave y el manifest registra `library_assets` (campo administrado por el servidor, no se declara). Una clave no puede repetirse entre el paquete y la biblioteca. Cada versión conserva su propia copia de las imágenes: reemplazar o eliminar una imagen de la biblioteca no altera lo publicado; una plantilla que use una clave eliminada no vuelve a validarse (`missing_library_asset`). Una plantilla compartida con otro Linktree exige que ese Linktree tenga las mismas claves en su biblioteca.
- Decorativas del paquete: `<img data-asset="clave">` y CSS `asset(clave)`. `alt: ""` produce imagen decorativa con `aria-hidden`. El servidor conserva alfa, limita los lados a 2000 px y entrega variantes de hasta 1x/2x/3x sin ampliar el original. El `srcset` usa la densidad real de cada variante y omite tamaños duplicados; los SVG se sirven una sola vez. Esta corrección también se aplica al leer versiones antiguas, sin modificar sus instantáneas. Los SVG eliminan scripting, eventos, contenido extranjero y referencias externas.
- Fuentes de Google Fonts exclusivamente desde `fonts` (por ejemplo `Oswald:wght@600;700`). La plataforma genera el enlace CSS2; un fallo al cargar las fuentes bloquea la validación para no aprobar con métricas de otra tipografía.
- Slots `photo`/`logo`: presencia obligatoria si se declara, dimensiones mínimas, formatos y proporción aplicada mediante `aspect-ratio`/`object-fit`. El logo admite SVG sanitizado desde el panel.
- Límites: 4 MB de paquete descomprimido, 12 decorativas, 800 KB por decorativa, 200 KB por archivo de texto. ZIP sin cifrado, symlinks, rutas exteriores ni nombres duplicados.

El HTML/CSS prohibido **bloquea la carga** e informa archivo/línea. Resuelve la discrepancia de la especificación a favor de su tabla de errores bloqueantes; no se publica una plantilla mutilada silenciosamente. La sanitización de SVG sí conserva el dibujo permitido y muestra un aviso.

## Validación y seguridad

`html5lib` normaliza el árbol HTML; el dialecto Mustache escapa todos los valores y no evalúa código; `tinycss2` inspecciona tokens CSS, incluyendo escapes. Las reglas de CSS no permiten importaciones, fuentes externas, URLs externas, propiedades ejecutables ni animaciones de propiedades distintas de transform/opacity. Los paquetes originales y las capturas nunca se sirven desde MEDIA_URL.

Huey procesa una validación a la vez. La parte de navegador corre en un worker aislado (`backend/linktree_sandbox/worker.py`) que no importa Django, no lee el `.env` y no tiene red: recibe en un solo pedido el documento, la CSP, las imágenes ya normalizadas del almacenamiento privado y las fuentes de Google que el lado Django descargó con la lista blanca de siempre. Chromium usa un origen sintético sin sesión, sirve sólo lo que trae el pedido y aborta todo lo demás, así que no puede consultar APIs internas ni URLs elegidas por la plantilla. La respuesta del worker se valida estrictamente antes de guardar nada. Un fallo del motor, del transporte o del contrato deja la versión inválida (`validator_unavailable`); una candidata que lleva diez minutos pendiente puede reintentarse. Detalle en [Validador aislado](#validador-aislado-transporte-y-contrato).

El navegador mide objetivos táctiles, overflow a 320 px, overlays fijos (incluidos `body`, `::before` y `::after`, con cajas de layout reales y muestreo de fotogramas), cantidad y propiedades de animaciones, cambios por segundo, texto/botones animados continuamente y preferencia de movimiento reducido. Para contraste se muestrean fondos reales (incluidas texturas y degradados) detrás de las cajas de texto, con umbral 4.5:1 o 3:1 en encabezados ≥24 px. Texto con mezcla/filtros o colores no RGB que no pueda certificarse produce error, nunca un aprobado inventado. Se limitan el DOM y el alto de página a 2000 elementos y 12000 px. El render de Mustache también limita iteraciones y tamaño antes de construir el DOM para rechazar bucles anidados expansivos.

La página publicada tiene CSP por respuesta con nonce exclusivo para el runtime de la plataforma, sin eventos inline, bases, formularios ni objetos. Las vistas previas tienen CSP `sandbox`, `script-src 'none'` y un iframe sin permisos. Las imágenes privadas de esas vistas llevan una firma de una hora limitada a su versión. Las capturas requieren sesión de administrador.

Los clics se agregan por versión/enlace/día sin IPs ni identificadores de visitante. Sólo se aceptan claves de enlaces publicados y se limita la tasa por origen. El envío comienza antes de navegar y usa `keepalive`; un fallo analítico no impide abrir el destino.

## Validador aislado: transporte y contrato

**Settings** (`backend/projectapp/settings.py`; también en `backend/.env.example`). Sin definirlos, el comportamiento es el de siempre:

| Setting | Default | Efecto |
|---|---|---|
| `LINKTREE_BROWSER_VALIDATION` | `True` | Interruptor de emergencia. `False` deja cada candidata `invalid` con `validator_disabled`, sin lanzar Chromium, sin conectarse al socket y sin bajar fuentes. |
| `LINKTREE_VALIDATOR_TRANSPORT` | `inprocess` | `inprocess` llama al worker dentro del proceso de Huey (DEV, tests y producción mientras no existan las units). `unix-socket` habla con la unit del toolkit. Cualquier otro valor deja la validación en `validator_unavailable`. |
| `LINKTREE_VALIDATOR_SOCKET` | `/run/projectapp-linktree-validator.sock` | Socket de la unit. |
| `LINKTREE_VALIDATOR_TIMEOUT` | `180` | Segundos de plazo total por intercambio con el socket. Dos pasadas más la descarga de fuentes quedan debajo de los 10 minutos de `expire_pending`. |
| `LINKTREE_CHROMIUM_EXECUTABLE` | vacío | Binario de Chromium; vacío usa el de Playwright. En la unit es la variable de entorno homónima, opcional. |

**Lanzamiento.** Chromium arranca con `HOME` temporal, `PATH` y `LANG` (nada más del entorno del proceso) y `--js-flags=--jitless`; `chromium_sandbox` sigue en `False`. Esto ayuda poco mientras el navegador comparta uid con el worker: un renderer comprometido puede leer `/proc/<pid>/environ` del proceso padre, y con `inprocess` el driver Node de Playwright sigue heredando el entorno de Huey. Se hace porque cuesta poco; la barrera real es `unix-socket` con la unit de otro uid, sin `/home`, sin `/run/user` y sin red.

**Comando del worker:** `<venv>/bin/python -E -s <repo>/backend/linktree_sandbox/worker.py`. Lee un JSON por stdin hasta EOF y escribe uno por stdout (`Accept=yes`, `StandardInput=socket`, `StandardOutput=socket`: un proceso nuevo por validación). No necesita variables de entorno: Playwright ubica el navegador con `PLAYWRIGHT_BROWSERS_PATH` si la unit la define, y `LINKTREE_CHROMIUM_EXECUTABLE` es opcional. La unit monta en sólo lectura el venv, `backend/linktree_sandbox/` y el directorio de navegadores de Playwright.

**Pedido** (un objeto JSON en UTF-8, sin claves extra; los binarios en base64):

```json
{"v": 1, "document": "<!doctype html>…", "csp": "default-src 'none'; …", "widths": [320, 375, 430],
 "resources": {"/api/linktrees/templates/<id>/assets/<clave>/<densidad>/": {"mime": "image/webp", "b64": "…"}},
 "fonts": {"<url del CSS o de https://fonts.gstatic.com/s/…>": {"mime": "font/woff2", "b64": "…"}},
 "google_css": "<url exacta de https://fonts.googleapis.com/css2?… o vacío>",
 "motion_declared": false, "pwa_enabled": false}
```

**Respuesta:** `{"v": 1, "issues": [...], "page_bytes": 0, "fonts_requested": ["…"], "screenshots": {"320": "<png en base64>"}}`, o `{"v": 1, "error": "<código>"}` con `invalid_json`, `invalid_request`, `request_too_large`, `browser_failed` o `response_too_large`.

- `page_bytes` del worker es el documento más cada fuente servida una vez; Django le suma el tamaño 3x de cada imagen y agrega `page_weight`, la misma cuenta de siempre.
- **Fuentes.** Django baja el CSS exacto del manifest con un User-Agent de Chrome y elige los archivos cuyo `unicode-range` cubre los caracteres del documento (tinycss2). Misma lista blanca que tenía el navegador: sin redirecciones, 5 s, status 200, 2 MiB por archivo, 40 archivos contando el CSS, 16 MiB en total. `fonts_requested` informa qué pidió Chromium: si pidió alguna que no se envió, la validación se repite **una sola vez** con exactamente lo pedido. Así el resultado es el mismo que cuando el navegador bajaba las fuentes, sin pagar una segunda pasada en el caso normal.
- **Capturas.** La que se guarda se recorta al ancho de la pantalla y a 12 000 px de alto; el contraste se sigue midiendo sobre la página completa. Una página que se desborda a lo ancho, que ya falla `overflow` a 320 px, queda recortada en la imagen.

**Validación de la respuesta** (`content/services/linktree_templates/contract.py`): esquema cerrado; `severity` en {`error`, `warning`}; `code` en `KNOWN_CODES`; hasta 150 issues con mensajes de hasta 300 caracteres; `page_bytes` exacto; claves de captura dentro de {"320", "375", "430"}, firma PNG, ancho del IHDR igual a la clave, alto hasta 12 000 px y hasta 20 MiB, leídas sólo por cabecera con Pillow y su límite de bomba de descompresión. Cualquier desvío deja la versión en `validator_unavailable`, nunca `valid`.

**Límites** (constantes de `worker.py`, fijadas por `test_linktree_validator_request.py`):

| Límite | Valor | De dónde sale |
|---|---|---|
| Documento | 8 MiB | HTML renderizado de hasta 2 Mi caracteres × hasta 3 bytes, más marcadores |
| Recursos | 384, 6 MiB cada uno, 48 MiB en total | 12 decorativas + 2 slots + biblioteca, a 3 densidades; un slot SVG de 5 MiB se repite por densidad. La biblioteca no tiene tope de cantidad: 384 es un tope nuevo |
| Fuentes | 40 contando el CSS, 2 MiB cada una, 16 MiB en total | los topes de siempre; lo real ronda 40 × 150 KB |
| Pedido | 96 MiB | 8 + ⌈4/3 × (48 + 16)⌉ + margen |
| Captura | 20 MiB | 430 × 12 000 px RGBA incomprimible ≈ 19,7 MiB |
| Respuesta | 81 MiB | ⌈4/3 × 3 × 20⌉ + 1 |

**Etapa 2 (pendiente, toolkit):** el navegador dentro del venv publicado, un perfil AppArmor con `userns` sólo para esa ruta y `chromium_sandbox=True` en la unit del validador.

## Despliegue y operación

1. Instalar `backend/requirements.txt` en el entorno del backend.
2. Instalar Chromium **con el usuario del servicio Huey**: `python -m playwright install --with-deps chromium`. El binario y su caché deben quedar accesibles para ese usuario. Repetir tras actualizar Playwright. El script `scripts/deploy.sh` instala y prueba Chromium antes de migrar; debe ejecutarse con el usuario del servicio. El CI instala el navegador en cada shard con pruebas visuales.
3. Aplicar las migraciones aditivas `0253_linktree_html_templates` y `0254_linktree_assets` mediante el procedimiento de deploy. Nunca se ejecuta `migrate` desde un worktree conectado a producción.
4. Reiniciar Huey y el servidor mediante el despliegue normal. Mantener `PRIVATE_MEDIA_ROOT` en backups junto con la base de datos.
5. Ejecutar `python scripts/check-template-deploy.py --url https://projectapp.co`. La ruta administrativa de plantillas debe devolver 401 JSON sin sesión; una portada HTML con 200 indica que la ruta no está operativa. El script de deploy incluye esta comprobación y termina con error si falla.
6. El worker de validación necesita memoria para Chromium. Medido en DEV el 2026-10-11 (Chromium 1243, una plantilla sintética con tres imágenes a tres densidades, pedido de 12,5 MB, tres corridas): pico de ~410 MiB PSS sumando todo el árbol de procesos (Python, driver Node y Chromium, 9 procesos), ~660 MiB sumando RSS (cuenta varias veces la memoria compartida) y ~170 MiB el proceso más grande; 13-16 s por validación con la máquina cargada. El límite histórico de 350 MB queda corto; en producción es una inferencia hasta medirlo allí. Con `inprocess` ese pico cae dentro del worker Huey; con `unix-socket` lo acota el `MemoryMax` de la unit del validador. Las consultas públicas no arrancan Chromium.

No se cambian recursos del servidor ni se despliega desde esta sesión. Los datos de demostración generan candidatas que exigen validación real antes de publicar, sin aprobaciones simuladas.

## Nivel 3 — autoría por MCP

El conector **Gestor de Contenido** (`content`, Panel → MCPs) expone el mismo ciclo del panel para que un asistente diseñe plantillas a medida:

1. `get_linktree_template_contract` con `linktree_id` devuelve el contrato de autoría y las variables reales de la tarjeta: nombre, rol, bio, iniciales, si hay foto y logo, cada enlace con etiqueta, URL, icono y tipo, botones sin destino, acciones disponibles (WhatsApp sólo si hay teléfono, correo sólo si hay email), contacto, la biblioteca de imágenes y los colores y fuente del tema básico. `icon_query` busca nombres Lucide válidos.
2. `upload_linktree_asset` sube cada imagen del diseño (fondo, textura, sello) a la biblioteca del Linktree bajo una clave y devuelve su URL y el marcado (`<img data-asset="clave">`, `asset(clave)`); `list_linktree_assets` y `delete_linktree_asset` (con confirmación) la administran.
3. `upload_linktree_template` recibe `files` (template.html, manifest.json, template.css y `assets/*` como texto, base64 o `asset_id` de un upload) y crea una candidata que Huey valida en Chromium. Los errores llegan con archivo, línea y código.
4. `get_linktree_template_version` informa `pending/valid/invalid`, el reporte completo y `profile_current`; `preview_linktree_template` devuelve el HTML renderizado y las capturas a 320/375/430 px como artefactos descargables.
5. `override_linktree_template_asset` reemplaza o restablece imágenes editables; `validate_linktree_template` recorta una candidata nueva con los datos actuales o restaura una versión previa.
6. `publish_linktree_template` exige `status=valid` y perfil vigente, y se ejecuta sólo tras `confirm_action`. `reset_linktree_template` vuelve al tema básico; `share_linktree_template` comparte con el cliente; `get_linktree_template_clicks` lee los clics agregados.

Las mismas guardas del panel aplican por conversación: una validación en curso por tarjeta, biblioteca filtrada por dueño/cliente y ninguna publicación sin validación. Detalle operativo en [MCP_VALIDATION_RUNBOOK.md](MCP_VALIDATION_RUNBOOK.md).
