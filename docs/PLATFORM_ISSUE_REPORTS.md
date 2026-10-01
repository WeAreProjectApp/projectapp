# Bugs y solicitudes contextualizadas

Un bug general se reporta desde cualquier proyecto, aunque no tenga guías
publicadas. Si se selecciona una entrega, el ticket captura contrato, otrosí,
alcance, fase, etapa, requerimiento, publicación, ronda y versión originales. La
guía completa los pasos y el resultado esperado sin sobrescribir datos que ya
escribió el cliente. Las solicitudes de cambio conservan una guía publicada como
origen obligatorio.

«Resuelto por equipo» registra la decisión del equipo. El cliente indica «Sigue
fallando» mediante un comentario público no vacío: vuelve a Reportado y conserva
la historia. No se añade conformidad formal del cliente ni se alteran aprobaciones
de guías. Un comentario no convierte un defecto en ampliación.

## Historia y evidencia

Las respuestas son nuevas entradas de historia; `admin_response` conserva la
última respuesta pública por compatibilidad. Un cambio de estado sin texto no
borra esa respuesta. Las notas internas y sus adjuntos sólo son visibles para el
administrador. Los comentarios existentes añaden documentos opcionales.

Un documento debe pertenecer al proyecto o al cliente del proyecto y respetar el
contrato y el contexto del ticket. Las asociaciones a otros proyectos o contextos
incompatibles se rechazan. Una respuesta pública sólo adjunta documentos
publicados para ese cliente. Se reutilizan los índices y el almacenamiento
privado de P3; cada adjunto conserva bytes PDF, título y SHA-256 propios, aunque
luego cambie la fuente. La descarga exige autenticación y devuelve
`private, no-store`. No se publican ni modifican documentos fuente.

El equipo puede seleccionar el contrato aplicable al responder. El resultado
contractual sigue `indeterminate`: el adaptador de tickets al motor compartido
de revisión está pendiente de P3. No hay un motor paralelo ni citas inventadas.
Convertir una solicitud aprobada exige una etapa editable del contrato original;
el servicio compartido crea una guía pendiente sin aprobarla o publicarla.

## API y permisos

Se conservan las rutas, filtros y campos actuales de bugs y solicitudes. Los
adaptadores usan JWT en Platform y sesión con CSRF en administración; los stores
usan `usePlatformApi`.

| Acción | Cliente del proyecto | Administrador | Ruta bajo `/api/accounts/` |
|---|---|---|---|
| Listar, crear y leer | Contexto propio | Todos los proyectos | `projects/{id}/bug-reports/`, `change-requests/` |
| Evaluar o archivar | No | Sí | `evaluate/`, detalle `DELETE` |
| Comentar con documentos | Público | Público o interno | `comments/` |
| Sigue fallando | Bug resuelto, respuesta pública | Bug resuelto, respuesta pública | `bug-reports/{id}/reopen/` |
| Opciones de origen/evidencia | Publicadas, propias | Publicadas para respuesta pública | `projects/{id}/issue-reports/context-options/` |
| Descargar evidencia | Adjuntos públicos propios, ticket activo | Incluye internos y archivados | `issue-reports/attachments/{id}/` |
| Convertir solicitud | No | Aprobada, etapa editable | `change-requests/{id}/convert/` |

`source_publication_id` y `source_requirement_version` fijan el origen. Sin una
publicación explícita se captura la última ronda publicada; una versión
incompatible devuelve 409. Ninguno de esos campos se exige para un bug general.
Los tickets anteriores declaran `legacy_unknown`; no se les inventa una ronda.

`expected_version` detecta escrituras concurrentes: opcional en rutas legadas,
obligatorio en tools MCP de modificación. `request_id` es un UUID estable por
operación: un reintento devuelve el recibo previo; el mismo UUID con datos
distintos devuelve 409. La conversión distingue `issue_version` de la versión
del espacio de entregas. Los adjuntos son hasta diez IDs de documentos y requieren
texto cuando acompañan una respuesta.

## Administración MCP

Once tools del conector `projects` llaman a los mismos servicios REST:

| Tools | Acción |
|---|---|
| `list_issue_reports`, `get_issue_report`, `get_issue_context_options` | Consulta por proyecto/tipo e historia |
| `create_bug_report`, `create_change_request` | Creación y captura del origen |
| `evaluate_issue_report`, `comment_issue_report` | Estado, respuestas, documentos y reapertura |
| `bulk_evaluate_issue_reports` | Hasta 500 entradas, éxito/error independiente |
| `archive_issue_report` | Confirmación, conserva historia |
| `convert_change_request` | Confirmación y versiones de ticket/entrega |
| `download_issue_attachment` | Artefacto privado de la credencial y proyecto indicado |

Las capturas usan uploads de imagen completos mediante `screenshot_asset_id`.
El asset temporal conserva el plazo del servicio de uploads para reintentos y
no se comparte entre credenciales. Los campos están clasificados en
`content/mcp/issue_contracts.py`; archivos privados y recibos internos no se editan
directamente.

## Bloques de integración

Base main `cce8e694`, dependencia publicada P3 `abcffaf9`. P0 coordina el número
y dependencia definitivos de la migración después de P3 final. Esta sesión no
ejecuta migraciones ni mergea su PR.

| Bloque compartido reservado | Dueño | Dependencia |
|---|---|---|
| `accounts/models.py`: versión BugReport/ChangeRequest e import del dominio | P1 | Publicaciones/modelos P3 |
| `accounts/serializers.py`, `views.py`: sólo bloques BugReport/ChangeRequest | P1 | Servicios dedicados de tickets |
| `accounts/urls.py`: include `issue_report_urls` | P1 | Vistas dedicadas |
| MCP: registros `ISSUE_TOOLS` / `build_issue_contracts` | P1 | Servicios dedicados y registro P3 |
| i18n: namespace `platformIssues` | P1 | Locales nuevos del dominio |
| Catálogos/shards bugs/changes y documentos derivados | P1 | UX y generador de registro |
| CI: job `frontend-issue-tests` | P1 | SQLite/settings_test y navegador real |
| Memoria: secciones de bugs/solicitudes | P1 | Comportamiento verificado |
| Adaptador del destino ticket a revisión contractual | P3 | Contrato de integración final P3/P0 |

Cada sesión aplica sus bloques en su worktree/PR. Se conserva la navegación
existente. Cobros, hosting, ideas, accesos, enlaces seguros y correos de cierre
pertenecen a otros frentes.

## Verificación

Los tests focales cubren captura histórica, versiones, permisos, aislamiento,
reintentos, reapertura y conservación de aprobaciones. MCP comprueba contratos,
confirmaciones y artefactos aislados. El navegador usa APIs y JWT reales con
SQLite/media desechables en loopback 4212/4213: no lee `.env` ni envía correos
reales. Ejecutar sólo archivos del dominio y hasta veinte casos por lote.
`npm run e2e:issues` valida los recorridos nuevos. Los mapas se registran en
`docs/user-flows/platform-bug-reports.md` y `platform-change-requests.md`.
