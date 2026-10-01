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
incompatibles se rechazan. Una respuesta pública exige publicación visible cuando
el documento está vinculado a entregas. El equipo puede adjuntar explícitamente
un PDF del proyecto sin vínculo de entrega; el cliente sólo elige documentos
visibles para él. Se reutilizan los índices y el almacenamiento
privado de P3; cada adjunto conserva bytes PDF, título y SHA-256 propios, aunque
luego cambie la fuente. La descarga exige autenticación y devuelve
`private, no-store`. No se publican ni modifican documentos fuente.

El equipo puede seleccionar el contrato aplicable al responder.
`issue_contract_reply` delega preparación, preview y citas al motor publicado de
P3. Sin selección explícita el alcance queda `indeterminate`; la ausencia de una
guía no prueba que el defecto esté fuera de alcance.
`issue_review_context.build_ticket_review_input` prepara la entrada del dominio:
origen congelado, conversación pública y referencias a adjuntos obtenidos en el
servidor, más `ticket_version` y `request_id`. No acepta una conversación enviada
por el cliente. Sin selección explícita, el contrato queda ausente.
Las respuestas vinculadas a otro contrato se excluyen de esa entrada; el historial
del ticket se conserva completo.
`contract_reply_target` proporciona identidad, dueño, versión, origen congelado
y conversación pública real. Publicar valida dueño, actor, destino, versiones y
hashes dentro de `_run`, bajo locks Project → ticket. P3 conserva el schema y
la captura/validación de fuentes; preparar/preview no llama IA ni publica.

Guardar el borrador requiere `contract_reply` con contexto, clasificaciones,
citas verificadas, versiones independientes de workspace/ticket y
`human_reviewed: true`. Editar JSON o texto final invalida la confirmación en la UI.
`inside_scope` se traduce a `within_scope`; decisiones mixtas son indeterminadas.
El campo existente `IssueResponse.review_evidence` conserva un envelope
`public`/`private` para auditoría, sin otra migración de esquema. El serializer
filtra el DTO por allowlist, también para JSON legado. El cliente no recibe
contextos, citas, fragments, prompts ni fuentes privadas. Sólo admin recibe
`review_context_id` y puede consultar/descargar ese contexto capturado.
Convertir una solicitud aprobada exige una etapa editable del contrato original;
el servicio compartido crea una guía pendiente sin aprobarla o publicarla.

`issue_client_transfer.assert_issue_client_transfer_safe(project, new_client)`
recibe el User de destino y consulta el dueño persistido, incluso si un formulario
ya cambió la instancia en memoria. Cualquier bug o solicitud, también archivados
o reportados por staff, bloquea cambiar de dueño con 409 y código
`issue_client_transfer_history`. El mismo dueño y los proyectos sin tickets se
permiten. El guard no modifica historia ni destinatarios. El puente en
`content.services.project_service.change_client_apply` bloquea la fila del proyecto
antes de comprobarlo y conserva ese lock hasta el save. P0 integra el orden
lock → financiero P2 → entregas P3 → tickets P1 → revocación P4 → save.
El formulario y recheck de ProjectAdmin corresponden a P2.

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
| Fuentes, preparación y preview de respuesta | No | Sí | `issue-reports/{kind}/{ticket_id}/reply/options/`, `contexts/`, `preview/` |
| Auditoría y copia de fuente de respuesta | No | Destino propio del contexto | `reply/contexts/{uuid}/`, `sources/{key}/` |

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

Dieciséis tools del conector `projects` llaman a los mismos servicios REST:

| Tools | Acción |
|---|---|
| `list_issue_reports`, `get_issue_report`, `get_issue_context_options` | Consulta por proyecto/tipo e historia |
| `create_bug_report`, `create_change_request` | Creación y captura del origen |
| `evaluate_issue_report`, `comment_issue_report` | Estado, respuestas, documentos y reapertura |
| `bulk_evaluate_issue_reports` | Hasta 500 entradas, éxito/error independiente |
| `archive_issue_report` | Confirmación, conserva historia |
| `convert_change_request` | Confirmación y versiones de ticket/entrega |
| `download_issue_attachment` | Artefacto privado de la credencial y proyecto indicado |
| `get_issue_reply_options`, `prepare_issue_reply` | Fuentes seleccionables y captura real del ticket |
| `get_issue_reply_context`, `preview_issue_reply` | Auditoría privada y preview sin escrituras |
| `download_issue_reply_source` | Fuente capturada como artefacto exclusivo de la credencial |

Las capturas usan uploads de imagen completos mediante `screenshot_asset_id`.
El asset temporal conserva el plazo del servicio de uploads para reintentos y
no se comparte entre credenciales. Los campos están clasificados en
`content/mcp/issue_contracts.py`; archivos privados y recibos internos no se editan
directamente.

## Bloques de integración

Base main `cce8e694`, dependencia publicada P3
`edfff19c2c56790398020a492e05df8c8a358872` absorbida mediante merge en la rama
propia. P0 reservó `0068_issue_reports`, dependiente de
`0067_explicit_delivery_authoring_context`; se conserva la dependencia
`content.0273_merge_document_provenance_and_proposal_owner`. La no-op propia
`0073_p1_delivery_issues_merge` combina `0071_delivery_followup` y `0068` sin
operaciones. P0 coordina hojas posteriores; esta rama no absorbe P2/0072.
Esta sesión no ejecuta migraciones
ni mergea su PR a main.

| Bloque compartido reservado | Dueño | Dependencia |
|---|---|---|
| `accounts/models.py`: versión BugReport/ChangeRequest e import del dominio | P1 | Publicaciones/modelos P3 |
| `accounts/serializers.py`, `views.py`: sólo bloques BugReport/ChangeRequest | P1 | Servicios dedicados de tickets |
| `accounts/urls.py`: include `issue_report_urls` | P1 | Vistas dedicadas |
| `content/services/project_service.py`: lock y guard de transferencia de tickets | P1 | Orden de guards/revocación coordinado por P0 |
| MCP: registros `ISSUE_TOOLS` / `build_issue_contracts` | P1 | Servicios dedicados y registro P3 |
| `content/fake_data.py`: clasificación derivada de los cuatro modelos Issue | P1 | Historia creada por operaciones de tickets |
| i18n: namespace `platformIssues` | P1 | Locales nuevos del dominio |
| Catálogos/shards bugs/changes y documentos derivados | P1 | UX y generador de registro |
| CI: job `frontend-issue-tests` | P1 | SQLite/settings_test y navegador real |
| Memoria: secciones de bugs/solicitudes | P1 | Comportamiento verificado |
| Provider de identidad/origen/conversación y wrappers de ticket | P1 | Motor publicado P3 `30fd7ab9` |
| Motor, schema, fuentes y citas contractuales | P3 | Integrar PR460 antes de PR464 |
| `0073_p1_delivery_issues_merge` | P1 | `0071` publicado + `0068`; operaciones vacías |

Cada sesión aplica sus bloques en su worktree/PR. Se conserva la navegación
existente. Cobros, hosting, ideas, accesos, enlaces seguros y correos de cierre
pertenecen a otros frentes.

## Verificación

Los tests focales cubren captura histórica, versiones, permisos, aislamiento,
reintentos, reapertura y conservación de aprobaciones. MCP comprueba contratos,
confirmaciones y artefactos aislados. El navegador usa APIs y JWT reales con
SQLite/media desechables en loopback 4212/4213: no lee `.env` ni envía correos
reales. La dependencia `edfff19c` fija el mailer de test antes de `django.setup`;
el fixture propio fuerza `MAILERS` en memoria para todos los aliases,
sin opciones SMTP, y comprueba el backend efectivo antes de DB/fixtures. Cuatro
regresiones prueban envíos al outbox memoria y rechazos sin outbox.
QA focal del adaptador: 17 casos REST (incluida CR), 12 casos MCP, 4 casos de
aislamiento de correo y 3 unitarias de UI pasaron en sus lotes correspondientes.
La auditoría de calidad no detectó errores y cerró sus observaciones; conserva
dos warnings baselineados de pruebas previas. Los dos flujos del dominio cubren
éxito, error, fallo y presentación. CI del head publicado se informa por separado.
Ejecutar sólo archivos del dominio y hasta veinte casos por lote.
`npm run e2e:issues` valida los recorridos nuevos. Los mapas se registran en
`docs/user-flows/platform-bug-reports.md` y `platform-change-requests.md`.
