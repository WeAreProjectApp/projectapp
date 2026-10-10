# Gestor Documental MCP 3.2.0

## Descubrimiento y validación

`tools/list` y `describe_capabilities` publican el mismo contrato autorizado:
nombres, títulos, descripciones, esquemas y anotaciones. Los adaptadores con
esquema explícito presentan argumentos planos y cerrados. El contrato interno
`accepted_arguments_schema` conserva los alias tipados `data`/`query` cuando
el adaptador los declara; esos alias no aparecen en el esquema publicado.

La validación central se activa en Documentos y Proyectos para esquemas
cerrados. Un argumento superior desconocido devuelve `unknown_field`; la falta
de uno obligatorio conserva `required` en `details.errors`, con campo y mensaje.
Los handlers y serializers siguen validando tipos y reglas del dominio.
Esta entrega no convierte todos los adaptadores genéricos en esquemas cerrados.

Las queries explícitas codifican booleanos como `true`/`false` y listas como
CSV, o parámetros repetidos con `x-query-encoding: repeat`. Un null nullable se
omite y uno no permitido se rechaza. El mismo transporte funciona en GET y
métodos con cuerpo; una `query` no declarada ya no se descarta silenciosamente.

Los errores mantienen `ok: false`, código, mensaje y detalles, tanto en
`structuredContent` como en el texto. Las listas `blockers` y los bloques
`planned`, `can_apply`, `impact_hash` y `plan_hash` conservan su estructura.
`cancel_action` devuelve `NOT_FOUND` ante un UUID inválido o una confirmación
pendiente inexistente para esa credencial.

## Espejos contractuales fijados por ID

`ContractTemplate.mirror_folder` fija la carpeta por ID, con `PROTECT`. El
resolver usa el campo persistido, luego una ubicación única derivada de los
espejos y, si no puede resolverla, informa `unpinned`. El nombre «Contratos»
deja de ser su identidad.

La carpeta y sus ancestros manuales pueden renombrarse, moverse y reordenarse.
La sincronización sigue comprobando el ID, el estado activo y la revisión del
espejo. La carpeta fijada y sus espejos permanecen sin cliente ni proyecto,
también dentro de la raíz de un proyecto migrado; las cascadas los omiten y los
reportan como `pinned`.

Archivar la carpeta fijada o un ancestro que contiene sus espejos devuelve
`CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED`, con ID/ruta de Contratos e IDs de los
espejos. Para archivar el ancestro hay que mover Contratos fuera primero.
Asignarle cliente o proyecto devuelve `CONTRACT_MIRROR_FOLDER_PINNED`.

`list_contract_mirrors` añade `folder_path` y `folder_movable` por espejo, y
`pinned_folder` con `pinned_folder_id`, `pin_source`, `folder_path`,
`folder_movable`, `archive_blocked` y `archive_block_reason`. Los documentos
espejo siguen siendo de solo lectura y no se mueven individualmente.
Detalle: [plantillas y pin contractual](../CONTRACT_TEMPLATE_MCP.md).

## Movimientos con políticas explícitas

`preview_move` previsualiza documentos o subárboles sin guardar. Devuelve filas
con `before`/`after` de ubicación, cliente, proyecto, visibilidad y audiencia
del portal; estados `changed`, `unchanged`, `pinned`, `frozen` o `blocked`,
totales, bloqueos, avisos, `can_apply` y `plan_hash`.

`client_policy` admite `inherit`, `keep` y `abort_on_conflict`: heredar la
propiedad del destino, conservarla con bloqueo ante incompatibilidad, o heredar
sólo sin conflictos. Un destino sin dueño no elimina el propietario existente.
`portal_policy` admite `abort`, `allow` y `hide_new_exposure`: bloquear una
nueva audiencia, permitirla u ocultar sólo los documentos que ganarían acceso.
También se evalúa la exposición latente de documentos archivados al restaurar.
Los defaults MCP son **`abort_on_conflict` y `abort`**.

Los argumentos efectivamente disponibles en este corte son:

| Escritura | Argumentos del planificador |
| --- | --- |
| `move_documents` | `client_policy`, `portal_policy`, `document_decisions`, `expected_plan_hash` |
| `update_folder` al cambiar `parent_id`/`parent` | `client_policy`, `portal_policy`, `expected_plan_hash` |
| `update_document` al cambiar `folder_id` | `client_policy`, `portal_policy` |

`document_decisions` permite `inherit` para un documento concreto o `move` con
otra `destination_folder_id`. `expected_plan_hash` compara el plan revisado con
el recalculado bajo candados y rechaza cambios con `STALE_MOVE_PLAN`.
`update_folder` aún no publica decisiones por documento; `update_document`
aún no publica decisiones ni hash de preview. No enviar esos argumentos como
si estuvieran implementados. La escritura de documentos tampoco permite que
metadata enviada junto al movimiento contradiga su decisión de dueño o portal.

Se conserva la atomicidad del lote y la protección de espejos, cuentas emitidas,
registros conservados y vínculos contractuales/de entrega. El Panel sin políticas
mantiene su ruta de herencia anterior.

## Migración de carpetas y deshacer

Documentos incorpora seis herramientas: `preview_folder_migration`,
`apply_folder_migration`, `get_folder_migration`,
`preview_folder_migration_undo`, `undo_folder_migration` y
`adopt_folder_as_project_root`. Con `preview_move`, el inventario pasa a
**73 herramientas**; Proyectos conserva **164**.

La migración requiere `source_folder_id`, `strategy` y un destino exclusivo:
`target.project_id` o `target.create_project` con `name`, `client_profile_id`,
`description` y `state_id` opcionales. Usa las mismas políticas y decisiones.

- `adopt_source` convierte una raíz manual activa y no conservada en la raíz
  gestionada. El proyecto existente debe carecer de raíz o tener sólo una
  plantilla descartable, sin documentos. Reutiliza Entregables/QA manuales y
  crea las categorías faltantes; colisiones con categorías automáticas bloquean.
- `move_contents` mueve hijos y documentos directos, incluidos los archivados,
  con filtros opcionales `include_folder_ids`/`include_document_ids`.
  `source_rename_to` resuelve el choque con una raíz nueva homónima; no se
  agregan sufijos. `archive_source_when_empty` sólo archiva si no queda ningún
  hijo ni documento, incluso archivado; lo pendiente conserva su motivo.

El preview no crea proyectos, carpetas, locks ni recibos. Publica árbol final,
filas, bloqueos, avisos, `plan_hash` y `plan_token` firmado, válido **30 minutos**
y ligado al actor y la credencial. `apply_folder_migration` recibe token,
`reason` y `request_id`; primero prepara una confirmación y sólo
`confirm_action` aplica. Replanifica bajo candados y ejecuta en una transacción.

Las postcondiciones exigen una sola raíz gestionada, ninguna raíz manual
homónima, Contratos activo/sin dueño con todos sus espejos, y ubicación,
propiedad y visibilidad iguales al plan. Un fallo revierte todo. El recibo
duradero registra antes/después, IDs creados/eliminados, lo movido, archivado y
pendiente. Repetir el mismo `request_id`, plan, actor y credencial devuelve el
resultado original; `get_folder_migration` lo consulta por `migration_id`.

Deshacer exige el `expected_impact_hash` del preview, motivo, `request_id` y
confirmación. Restaura exactamente ubicación, dueño, visibilidad y archivado,
incluidas las carpetas descartadas; sólo elimina las plantillas y el proyecto
creados si siguen sin uso. Bloquea cambios posteriores (`changed_since`),
contenido nuevo (`new_content_since`), proyecto en uso (`project_in_use`), una
operación ya revertida (`already_reverted`) y operaciones posteriores sobre
los mismos registros (`changed_since` con `reason: lifo`).

`adopt_folder_as_project_root` usa el mismo motor `adopt_source` para un
proyecto existente, con políticas, decisiones, motivo, request ID y plan
mostrado en la confirmación. Su recibo también permite deshacer.

## Códigos del recorrido

Las respuestas DRF usan lower snake_case; MCP normaliza el código principal a
mayúsculas, conservando `unknown_field` y `folder_cycle`. Los códigos de las
filas de `blockers` permanecen tal como los entrega el planificador.

| Códigos MCP | Motivo |
| --- | --- |
| `CONTRACT_MIRROR_FOLDER_PINNED`, `CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED` | Propiedad y archivo de Contratos protegidos |
| `OWNERSHIP_CONFLICT`, `OWNERSHIP_CONFLICT_KEEP`, `OWNERSHIP_FROZEN`, `PORTAL_EXPOSURE`, `OWNERSHIP_PLAN_BLOCKED` | Conflictos o exposición en movimientos |
| `STALE_MOVE_PLAN` | El movimiento cambió respecto del hash revisado |
| `PLAN_TOKEN_INVALID`, `REQUEST_ID_CONFLICT` | Token vencido/alterado o request ID de otro plan |
| `SOURCE_NAME_CONFLICT`, `TEMPLATE_NAME_CONFLICT`, `MIGRATION_BLOCKED`, `UNDO_BLOCKED` | Nombres, requisitos de migración o deshacer |
| `CHANGED_SINCE`, `NEW_CONTENT_SINCE`, `PROJECT_IN_USE`, `ALREADY_REVERTED` | Motivos de bloqueo de deshacer |
| `PROJECT_ROOT_NAME_CONFLICT` | La raíz manual requiere una decisión explícita al crear o renombrar |

Se reutilizan `CONFLICT` para planes bloqueados al preparar confirmaciones,
`STALE_VERSION` para cambios del plan firmado y `FORBIDDEN` para otra
credencial/actor. Un token de otra credencial no es un token vencido.

## Compatibilidad y despliegue

Los movimientos MCP ahora **abortan por defecto ante conflictos entre clientes**
y nueva exposición en el portal. Las automatizaciones que dependían de herencia
deben revisar el preview y elegir políticas. Los argumentos superiores
desconocidos de herramientas con esquema cerrado ahora devuelven `unknown_field`.

El deploy aplica [content.0286](../../backend/content/migrations/0286_contracttemplate_mirror_folder.py)
(pin y backfill) y [content.0287](../../backend/content/migrations/0287_document_ownership_operation.py)
(recibos de operaciones). No ejecutar migraciones ni reparaciones sobre una base
real desde un worktree.

Las credenciales con allow-list explícita deben añadir `preview_move` y las seis
herramientas de migración que necesiten, además de `confirm_action` y las lecturas
del flujo. Después del deploy, reconectar los conectores de **claude.ai** para
refrescar `tools/list` y cotejarlo con capacidades.

Validación y procedimiento de producción:
[parte 2 del runbook](../MCP_VALIDATION_RUNBOOK.md#migración-de-carpetas-por-mcp--parte-2-2026-10).
Esta nota documenta código de PR #504; no acredita su merge, deploy ni la
migración de los datos reales.

## Historia

**3.1.0 nunca tuvo changelog propio.** Esta nota reúne el framework, los espejos
por ID y la migración funcional incorporados desde esa versión. La numeración
debe coordinarse con PR #503: el PR que se integre segundo toma el siguiente
número y ajusta sus pins y notas antes de publicar.
