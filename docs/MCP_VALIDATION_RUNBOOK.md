# Guion de validación y mantenimiento de MCP

Las plantillas contractuales independientes se administran desde Propuestas
(2.2.0) y se consultan en Documentos (4.0.0) como espejos de solo lectura.
Ver [contrato de herramientas y primer uso](CONTRACT_TEMPLATE_MCP.md): validar
lectura de las tres variantes, preview sin escritura, campos obligatorios,
rechazo por etag, confirmación, coherencia, historial/restauración y reversión
del lote si falla un PDF o una nota. Comprobar `list_contract_mirrors`: el pin
por ID permite renombrar y mover la carpeta y sus ancestros, mientras bloquea
su archivado y la asignación de cliente/proyecto a la carpeta fijada. Los
contratos ya guardados o firmados conservan sus bytes.

## Tickets de proyecto: bugs y solicitudes contextualizadas

`projects` incorpora once acciones mediante los mismos servicios REST. Inventario,
permisos, versiones, reintentos y dependencia de revisión contractual:
[Bugs y solicitudes](PLATFORM_ISSUE_REPORTS.md). Validar bug general sin guía,
origen con ronda publicada, respuesta pública o interna con PDF opcional,
descarga aislada y reapertura «sigue fallando». Archivar y convertir exigen
confirmación. Convertir sólo crea una guía pendiente en una etapa editable del
contrato aplicable; las aprobaciones existentes permanecen intactas y el alcance
sigue indeterminado hasta el adaptador compartido de P3.

Las carpetas del conector de Documentos declaran `folder_kind`, proyecto y
estado. `create_folder` hereda la asociación de su padre y `rename_folder`
rechaza raíces automáticas de proyecto; estas protecciones se validan junto
con los contratos de modelo antes de publicar cambios del gestor.

Última revisión integral: 2026-09-04.
Última revisión focal de esquemas: 2026-10-10; contrato objetivo de PR 2:
Documentos **4.0.0 / 73 tools** y Proyectos **3.0.0 / 171 tools**. Notas de
versión y migración de callers:
[Documentos 4.0.0](changelog/2026-10-10-documents-mcp-4.0.0.md) y
[Proyectos 3.0.0](changelog/2026-10-10-projects-mcp-3.0.0.md).
Comprobar las versiones publicadas antes de operar; esta revisión documental
no acredita despliegue ni CI del conjunto.

Este documento es el procedimiento repetible para validar la plataforma MCP de
ProjectApp: transporte moderno y compatible, credenciales con alcance,
confirmación de operaciones sensibles, uploads temporales y paridad operativa
con las áreas del Panel. La fuente ejecutable del inventario está en
`backend/content/mcp/connectors.py` (`CONNECTORS` y `TOOLS_BY_SLUG`); los
adaptadores de paridad viven en
`backend/content/mcp/operation_catalogs.py` y la clasificación de campos en
`backend/content/mcp/contracts.py`.
Versiones, compatibilidad, fuentes, uploads e instrucciones se declaran en
`ConnectorSpec`. Ver el [changelog de esta entrega](changelog/2026-10-09-mcp-connectors-schema-registry.md)
y la [medición antes/después](audits/2026-10-09-mcp-schema-parity.md).

## Esquemas explícitos — documents 4.0.0 y projects 3.0.0 (2026-10-10)

PR 2 cambia el contrato de entrada, sin añadir herramientas ni modificar datos.
Los ejemplos operativos de este guion usan la forma nueva. Las revisiones
fechadas de PR #504 conservan sus versiones como referencia histórica; no
confundirlas con los pins requeridos para este barrido.
El [inventario inicial](audits/2026-10-10-documents-projects-schema-inventory.md)
registra el punto de partida, no el contrato final.

### Comprobaciones del contrato

1. **Versiones y descubrimiento.** Exigir Documentos **4.0.0 / 73 tools** y
   Proyectos **3.0.0 / 171 tools** en registry, initialize/discovery y
   capacidades. Comparar `tools/list` con `describe_capabilities`, con
   credenciales completas y limitadas: mismos schemas, descripciones y
   anotaciones para las herramientas autorizadas. Los pins de
   [discovery de Documentos](../backend/content/tests/views/test_documents_mcp_301.py),
   [capacidades documentales](../backend/content/tests/views/test_document_organization_api.py)
   y [contratos/conteos](../backend/content/tests/views/test_mcp_contracts.py)
   deben corresponder a las versiones nuevas.
2. **Explicitud y deriva.** Cada herramienta convertida publica una raíz
   object cerrada, sin combinador superior ni propiedades `data`/`query`.
   Cada argumento superior tiene tipo y descripción; `required` es subconjunto
   de `properties`; los objetos anidados están cerrados o son mapas tipados.
   Auditar los 36 bridges de Documentos y los 48 de Proyectos contra las
   lecturas de vistas/serializers/servicios. Los backlogs de explicitud, alias
   y deriva deben quedar vacíos, con techo cero. Las exclusiones
   `describe_capabilities`, `confirm_action`, `cancel_action` y el historial
   `*_history` llevan el motivo `owned by PR #503`; no se usan para esconder
   otra herramienta pendiente. El historial excluido conserva su contrato.
3. **Desconocidos antes de efectos.** Vía `handle_message`, completar primero
   los obligatorios y añadir una clave superior desconocida. Exigir
   `unknown_field` con esa clave en `details.errors[*].field`, cero llamadas a
   handler, preparación, impacto, predicado de confirmación o ETag, y cero
   escrituras SQL. Repetir con `data` y `query` en herramientas convertidas de
   ambos conectores. El guard de frontera debe demostrar también que un alias
   de Propuestas sigue funcionando; Propuestas/Comercial y los demás
   conectores conservan su compatibilidad.
4. **Dieciséis raíces nativas de Documentos.** La sonda dedicada cubre las
   once de documentos/notas/estados: `add_document_note`,
   `close_document_state`, `delete_document`, `delete_document_notes`,
   `finish_document_note`, `list_deleted_document_notes`,
   `list_document_states`, `list_documents`, `read_document`,
   `restore_document_note` y `set_document_state`; y las cinco de hilos:
   `get_document_thread`, `list_document_threads`, `create_document_thread`,
   `update_document_thread`, `dissolve_document_thread`. Además se auditan los
   schemas nativos de alta/edición, migración, propiedad y uploads compartidos.
   No alcanza con que un listado ignore el argumento: debe rechazarlo antes
   de ejecutar o escribir.
5. **Errores de `message`.** Omitir `message` de `add_delivery_message` con los
   demás requeridos presentes: `VALIDATION_ERROR`, fila con `field: message`
   y `code: required`, sin handler. Probar también ErrorDetail escalar, lista
   y objeto anidado de un serializer: conservar `message`/`message.subject`
   en lugar de `non_field_errors`. El texto principal del envelope y los
   bloques `blockers`, `planned`, `can_apply`, `impact_hash` y `plan_hash`
   permanecen intactos; texto y `structuredContent` deben coincidir.
6. **Entregas planas e imports.** Crear/editar cada una de las seis entidades
   con sus campos planos y confirmar cuando afecta contenido público.
   Verificar que preparación, instantánea y revalidación usan esos mismos
   campos, incluida la selección de fuente. `preview_delivery_import` y
   `apply_delivery_import` conservan `payload`, con los contratos existentes
   v1/v2 seleccionados por `payload.schema_version`: v1 manual, v2 con contexto
   y citas. El combinador está dentro de `payload`, no en la raíz. Rechazar
   envelopes y mantener las validaciones de propiedad, citas, versiones e
   inmutabilidad del servicio. El preview no guarda; aplicar usa confirmación,
   transacción e idempotencia.
7. **Recursos planos y slice nativo de Proyectos.** Comprobar metadata de
   recursos, `title`/`category` de adjuntos, `name`/`order` de carpetas,
   `title`/`folder_id` de PDFs del cliente y `entities` del modelo de datos,
   todos planos donde se declaran. Los uploads siguen usando UUIDs propios y
   sus límites; no rutas de storage. `upload_project_resource_attachment`
   rechaza `description`, que su serializer ignoraba; la descripción del
   recurso permanece. El archivo nativo de Proyectos contiene **22 casos**:
   cinco verifican las familias resources/issues/billing/hosting/create;
   nueve comprueban escrituras, uploads, carpetas y modelo de datos planos;
   ocho rechazan `data` antes de callbacks/escrituras. Tickets conserva su
   objeto tipado `payload`.
8. **Inputs exclusivos del Panel y borrado.** El guard de deriva consume
   `PANEL_ONLY_FIELDS` de
   [projects_bridge.py](../backend/content/mcp/schemas/projects_bridge.py),
   con motivo por campo. Las listas legacy de `change_project_client`
   (`hosting_ids`, `income_ids`, `communication_thread_ids`) se rechazan en MCP:
   usar `mode` y `expected_impact_hash` con el plan del servidor. Los campos
   de cliente/estado que `update_project` siempre rechaza siguen fuera.
   `preview_project_delete` y `delete_project` sólo admiten `project_id` y
   `if_match` opcional; `force`, `delete_keys`, `confirmation` e `impact_token`
   producen `unknown_field`, sin intención ni borrado. Con proyecto vacío y
   llamada válida, preview y confirmación siguen evaluando las mismas
   dependencias. `if_match` es concurrencia optimista, no control de purga.
9. **Paridad completa.** Cada `preview_*` debe tener pareja de ejecución en el
   arnés o figurar en la lista explícita de excepciones con motivo. La sonda
   no reemplaza los escenarios de éxito/error que prueban el comportamiento
   observable de esa pareja.

### Cobertura y lotes de verificación

Desde `backend/` del worktree, usar
`../.venv/bin/pytest <archivo> -v --no-cov -k '<selección>'`. No exportar
`DJANGO_SETTINGS_MODULE`/`DJANGO_ENV`, leer `.env`, instalar dependencias ni
ejecutar migraciones sobre una base real. Máximo veinte casos por comando y
tres comandos por ciclo. Las selecciones siguientes son recetas de
verificación; esta revisión documental no acredita nuevas corridas.

| Frente | Archivo y selección por lote |
| --- | --- |
| Política/backlogs/exclusiones/paridad/frontera | [test_mcp_schema_explicitness.py](../backend/content/tests/views/test_mcp_schema_explicitness.py): `-k 'not policy_reports_a_mutated_contract_at_its_pointer and not every_closed_tool_rejects_unknown_arguments_before_execution'`; ciclo separado del lote de mutaciones `-k policy_reports_a_mutated_contract_at_its_pointer` (13 casos). |
| Sonda global de desconocidos | Mismo archivo: `-k every_closed_tool_rejects_unknown_arguments_before_execution` (un caso recorre las raíces cerradas por `handle_message`, con callbacks interceptados y cero escrituras). |
| Bridge de Documentos | [test_mcp_documents_bridge_schemas.py](../backend/content/tests/views/test_mcp_documents_bridge_schemas.py): `-k batch1` y `-k batch2` (18 contratos cada uno), luego `-k 'not test_document_bridge_contract_matches_its_view'` para cobertura y transporte plano. |
| Bridge de Proyectos | [test_mcp_projects_bridge_schemas.py](../backend/content/tests/views/test_mcp_projects_bridge_schemas.py): separar `-k 'project_delete or legacy_panel'` del resto con `-k 'not project_delete and not legacy_panel'`; comprobar filtros, ideas, actualización, impacto y exclusiones. |
| Nativas de Documentos y errores | [test_mcp_documents_native_schemas.py](../backend/content/tests/views/test_mcp_documents_native_schemas.py): `-k formerly_open_root` (16 casos), luego `-k 'not formerly_open_root'` para política, uploads y nombre de campo `message`. |
| Nativas de entregas | [test_mcp_delivery_native_schemas.py](../backend/content/tests/views/test_mcp_delivery_native_schemas.py): separar `-k 'native_delivery_catalog or import_tools'` de `-k 'not native_delivery_catalog and not import_tools'`; CRUD plano, envelopes rechazados y revalidación de fuentes públicas. |
| Slice nativo de Proyectos, 22 casos | [test_mcp_projects_native_schemas.py](../backend/content/tests/views/test_mcp_projects_native_schemas.py): `-k native_policy` (5), luego `-k 'not native_policy'` (17); no ejecutar los 22 juntos. |
| Inventario de vistas | [test_mcp_view_inventory.py](../backend/content/tests/views/test_mcp_view_inventory.py): AST, serializers, opacidad, assets y evidencia de parejas, sin ejecutar la vista para inventariarla. |
| Discovery y eliminación | [test_mcp_discovery_parity.py](../backend/content/tests/views/test_mcp_discovery_parity.py), los pins del punto 1 y [test_mcp_project_deletion.py](../backend/content/tests/views/test_mcp_project_deletion.py): seleccionar los casos de Documentos/Proyectos; no agrupar si supera veinte. |

Para cada lote guardar comando, SHA, selección, número de casos y resultado;
registrar las exclusiones reales. El cierre requiere revisión del registro y
pins, no sólo que existan estos archivos. Las
[guías de Documentos](changelog/2026-10-10-documents-mcp-4.0.0.md#migración-de-llamadas-mcp)
y [Proyectos](changelog/2026-10-10-projects-mcp-3.0.0.md#migración-de-llamadas-mcp)
muestran ejemplos antes/después. Reconectar ambos conectores tras el deploy
para retirar schemas cacheados; los allow-lists, tokens y permisos permanecen.

## Migración de carpetas por MCP — parte 1 (2026-10)

Revisión focal del 2026-10-09 sobre los commits `74ca0073` (framework),
`484997f6` (espejos), `870bacf2` (cambio de cliente), `e676c1c1` (hosting),
`388b1fae` y `7d5526b5` (UI/E2E), y `ba83a834` (contratos y conteos).
Ejecutar las comprobaciones mutantes en datos aislados de test/staging, con
Wompi y correo simulados. Son criterios de validación, no resultados de un
despliegue ni asignación de una versión nueva.

1. **Framework — descubrimiento.** Comparar `tools/list` con
   `describe_capabilities` en `documents` y `projects`, con credencial completa
   y restringida: mismos nombres, títulos, descripciones, input/output schemas
   y anotaciones. Los adaptadores con `payload_schema` o `query_schema`
   explícito publican campos planos y `additionalProperties: false`, sin
   envelopes `data`/`query`.
2. **Framework — argumentos planos.** En las herramientas convertidas de
   `documents`/`projects`, los campos del cuerpo y filtros van directamente en
   `arguments`; ya no se aceptan alias internos `data`/`query`. Probar ambas
   envolturas como campos desconocidos antes de cualquier callback o escritura.
   Los demás conectores conservan sus alias. Descubrimiento, confirmación y
   `*_history`, compartidos con PR #503, se verifican aparte del barrido.
3. **Framework — query encoding.** Verificar booleanos como `true`/`false`,
   listas CSV por defecto en queries explícitas o repetidas con
   `x-query-encoding: repeat`. Un null permitido se omite; uno no nullable se
   rechaza. Comprobar el mismo encoding en GET y métodos con body: una query
   declarada llega a la vista mediante su campo plano; un filtro no declarado
   en POST se rechaza en lugar de descartarse. `query` como envelope tampoco
   se acepta en las herramientas convertidas.
4. **Framework — validación central.** En schemas cerrados, probar un campo
   desconocido y uno required ausente: `details.errors` conserva `field`,
   `code` (`unknown_field` o `required`) y `message`. La validación central
   cubre el nivel superior, usa `accepted_arguments_schema` si existe y, por
   defecto, se activa en `documents`/`projects`; una tool puede optar mediante
   `strict_arguments`. Un schema abierto queda fuera de este control y los
   serializers/handlers conservan la validación de tipos y reglas de negocio.
   Comprobar que `blockers`, `planned`, `impact_hash` y `can_apply` mantienen
   su estructura al normalizar un error. Si el serializer tiene un campo
   llamado `message`, `details.errors[*].field` debe conservar `message` o su
   ruta anidada, nunca sustituirlo por `non_field_errors`.
5. **Framework — cancelación.** `cancel_action` con UUID malformado o sin
   intent pendiente de la misma credencial responde `NOT_FOUND`, sin excepción
   interna ni modificación de otra confirmación.
6. **Espejos — pin y flags.** `list_contract_mirrors` devuelve los tres espejos
   y `pinned_folder`, con `pinned_folder_id`, `pin_source`, `folder_path`,
   `folder_movable`, `archive_blocked` y `archive_block_reason`. En una réplica
   correctamente inicializada, comprobar pin persistido (`field`), carpeta
   activa/movible y los tres `synchronized: true`. Los flags y la ruta de cada
   espejo deben coincidir con las operaciones disponibles.
7. **Espejos — reorganización.** Renombrar y mover Contratos y luego un
   ancestro manual. Releer el listado: cambian las rutas, permanece el ID del
   pin y los tres espejos siguen `synchronized: true`. Una actualización
   contractual válida sigue sincronizando Markdown, PDF y notas en esa carpeta.
8. **Espejos — archivado y dueño.** Archivar Contratos o un ancestro que aún
   contiene espejos devuelve `CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED`; el Panel
   responde 409 `contract_mirror_folder_archive_blocked`, con ID/ruta de la
   carpeta fijada y IDs de espejos. Cambiar cliente o proyecto de la carpeta
   fijada devuelve 409 `contract_mirror_folder_pinned` (MCP:
   `CONTRACT_MIRROR_FOLDER_PINNED`). Ningún rechazo altera asociaciones ni
   archivado. El cambio de cliente de un ancestro omite la rama fijada y la
   informa como pinned; el borrado forzado exige moverla fuera primero.
9. **Cambio de cliente — preview y bloqueo.**
   `preview_project_client_change` con `project_id` y `client_profile_id`
   devuelve `can_apply`, `blockers`, `blocker_counts`, `planned.move`,
   `planned.detach`, `financial_history` e `impact_hash` independiente del modo.
   Comparar con el evaluador compartido y las tres guardas. Un proyecto con
   historia, incluida una suscripción cancelada, no crea un intent al llamar
   `change_project_client` con el hash vigente: devuelve
   `PROJECT_CLIENT_CHANGE_BLOCKED` y `details.blockers[].resolution:
   create_new_project`. Si el bloqueo aparece antes de `confirm_action`, el
   rechazo añade `details.guard_code` y conserva dueño e historia.
10. **Cambio de cliente — impacto obsoleto.** Con preview inicialmente
    permitido, cambiar el conjunto vinculado y enviar el hash anterior como
    `expected_impact_hash`: `STALE_VERSION` al preparar la acción, sin escritura.
    Confirmar también una intención cuyo impacto cambió: debe rechazarse y
    requerir nueva revisión. El endpoint del Panel revalida bajo lock y usa
    409 `records_changed`; mantiene las listas de IDs legacy.
11. **Hosting — cancelación confirmada.** Encadenar
    `preview_hosting_subscription_change` (`subscription_id`, `action: cancel`,
    `effective_date` opcional) → `change_hosting_subscription` con motivo y
    `expected_impact_hash` → `confirm_action` → `get_project_hosting` con el
    `project_id`. Antes de confirmar no hay cambios. Después, suscripción
    `cancelled`, próxima fecha null y los cobros abiertos futuros del preview
    en `subscription.payments` como `voided`, archivados y con historia. En la
    réplica del caso PRUEBA, conservar el pago recibido 4 y anular el pendiente
    futuro 5; no usar esos IDs para mutar producción durante esta validación.
12. **Hosting — fecha y transiciones.** Probar `pause` desde `active`/`pending`
    a `suspended`, con evento de pausa manual; `resume` sólo desde esa pausa y
    `cancel` como terminal. Sólo se anulan cobros abiertos activos con
    `due_date > effective_date`; los ya causados se conservan cobrables. Al
    reanudar, restaurar los anulados por esa pausa todavía futuros; si no quedan,
    iniciar un ciclo desde la fecha de reanudación. Validar fecha futura,
    suspensión por fallos, retención, archivado, proyecto sin facturación y
    pago en proceso con transacción Wompi como bloqueos.
13. **Hosting — entradas de pago.** Los endpoints de link, widget, tarjeta
    nueva y tarjeta guardada rechazan pagos archivados o `voided`. Una aprobación
    tardía sobre un cobro anulado registra `paid`, desarchiva el cobro y conserva
    `settled_after_void`, su evento y aviso al administrador, sin reactivar ni
    generar otro ciclo. Simular al proveedor; no intentar un cobro real.
14. **Hosting — automatismos y rechecks.** El pago manual conserva cancelación
    o pausa; `_generate_next_payment` omite archivados y no genera para esas
    suscripciones. La tarjeta guardada se revalida bajo lock antes de Wompi y
    `_onboard_due_phases` relee sus estados bajo lock. PATCH `status` de la
    suscripción devuelve 400 `subscription_lifecycle_required`. Registrar el
    trade-off: los locks siguen durante la llamada externa y su polling;
    **claim-then-call** es seguimiento pendiente.
15. **UI y E2E.** En Cambiar cliente, un preview bloqueado muestra los motivos
    y la orientación de crear un proyecto nuevo, oculta los modos y deshabilita
    Confirmar sin enviar POST. El permitido exige modo y envía el hash revisado.
    Verificar «Anulado» en pagos/historial y «Anulado»/«Voided» en los locales
    de billing. El flow `admin-project-change-client` registra display, success
    y error con APIs simuladas.
16. **Contratos y conteos.** El inventario vigente, completado por la parte 2,
    contiene **73** tools de Documentos y **171** de Proyectos.
    `ContractTemplate.mirror_folder` queda excluido de
    escritura en propuestas y observable en Documentos; los flags de archivo de
    Payment son read-only. Sólo `projects` clasifica `HostingSubscription.status`
    y `next_billing_date` como modificables mediante la acción de ciclo de vida:
    rechazar esos campos directos en su payload; `accounting-billing` conserva
    su lectura.

Referencias: [Carpeta Contratos fijada por ID](CONTRACT_TEMPLATE_MCP.md#carpeta-contratos-fijada-por-id-2026-10-09),
[Evaluación compartida y vista previa](ISSUE_CLIENT_TRANSFER_INTEGRATION.md#evaluación-compartida-y-vista-previa-2026-10-09)
y [Ciclo de vida de la suscripción](PLATFORM_PROJECT_BILLING.md#ciclo-de-vida-de-la-suscripción).

Cobertura focal existente, para seleccionar lotes de hasta 20 tests y un máximo
de tres comandos por ciclo, desde `backend/` con
`../.venv/bin/pytest <archivo> -v --no-cov`:

| Frente | Archivos |
| --- | --- |
| Framework | `content/tests/views/test_mcp_discovery_parity.py`, `test_mcp_query_encoding.py`, `test_mcp_parity_harness.py`; `content/tests/services/test_mcp_error_contract.py` |
| Pin y espejo | `content/tests/services/test_contract_mirror_pin.py`; `content/tests/views/test_contract_template_mirrors.py` |
| Cambio de cliente | `content/tests/services/test_project_client_transfer_blockers.py`; `content/tests/views/test_mcp_project_client_change.py`, `test_panel_projects_change_client.py` |
| Hosting y dinero | `accounts/tests/billing/test_hosting_subscription_lifecycle.py`, `test_payment_lifecycle_guards.py`; `content/tests/views/test_mcp_hosting_subscription.py` |
| Contratos/pins | `content/tests/views/test_mcp_contracts.py` |
| Frontend | `frontend/test/components/ProjectChangeClientModal.test.js`; `frontend/e2e/admin/admin-project-change-client.spec.js` |

La tabla enumera cobertura existente; no acredita una nueva ejecución ni el
comportamiento de locks MySQL a partir de SQLite.

### Nota post-deploy

Las credenciales con allow-list explícita deben añadir las tools nuevas que
necesiten: en esta parte, `preview_hosting_subscription_change` y
`change_hosting_subscription`. Verificar también el acceso a `confirm_action`
y las lecturas del recorrido. El alcance de la credencial limita tanto
descubrimiento como ejecución. Después del deploy, reconectar los conectores
de claude.ai para refrescar `tools/list` y comprobar sus schemas y permisos.

## Migración de carpetas por MCP — parte 2 (2026-10)

Revisión documental del 2026-10-10 sobre los commits `9446a196` (políticas),
`7f7927d5` (pin de preview), `55a31237` (migración y deshacer), `3886f01e`
(contrato de recibos/conteo), `5e0ddd25` (raíces sin duplicados), `c40f3822`
(sincronización, exposición latente y adopción estricta) y `92beb803`
(audiencia al deshacer y cambio de cliente de carpeta), junto con `3bd28f84`
(guardas de concurrencia de facturación) y los de la parte 1.
Versiones de ese corte de PR #504: **documents 3.2.0** y
**projects 2.2.0**; PR 2 requiere los pins 4.0.0/3.0.0 de la sección de
esquemas explícitos. Validar con datos aislados, proveedor de pagos y correo
simulados. La lista siguiente describe criterios, no acredita su ejecución
en producción ni el merge/deploy de PR #504.

1. **Descubrimiento y permisos.** Comparar `tools/list` y
   `describe_capabilities` con credenciales completas y restringidas: versiones,
   nombres y contratos iguales; inventario completo 73/164. Una allow-list
   antigua no incorpora tools nuevas automáticamente. Comprobar
   `preview_move` y las seis herramientas de migración sólo en Documentos.
2. **Preview de movimiento y políticas.** Llamar `preview_move` con
   `document_ids` o `folder_ids`, `destination_folder_id`, `client_policy`,
   `portal_policy` y decisiones opcionales. Verificar ausencia de escrituras,
   filas `before`/`after`, audiencia real/latente, estados, bloqueos, totales y
   `plan_hash`. Probar `inherit`, `keep`, `abort_on_conflict` y `abort`, `allow`,
   `hide_new_exposure`; un destino sin dueño conserva la propiedad anterior.
   Con `abort`, un documento archivado marcado visible que ganaría audiencia
   al restaurarse bloquea con `portal_exposure_latent` y `can_apply: false`;
   `hide_new_exposure` oculta tanto la exposición actual como la latente.
   MCP usa `abort_on_conflict`/`abort` por defecto. `move_documents` admite
   ambas políticas, `document_decisions` y `expected_plan_hash`; `update_folder`
   admite políticas y hash al cambiar padre; `update_document` admite sólo las
   políticas al cambiar carpeta. No suponer decisiones en `update_folder` ni
   decisiones/hash en `update_document`: esa ampliación no está en este corte.
   Comparar el resultado con el preview; un hash obsoleto donde está soportado
   devuelve `STALE_MOVE_PLAN`, sin cambios parciales.
3. **Las dos estrategias de migración.** Probar
   `preview_folder_migration` con destino exclusivo `project_id` o
   `create_project`. `adopt_source` exige raíz manual activa, sin retención ni
   `managed_client`; admite proyecto sin raíz o plantilla descartable sin
   documentos, reutiliza Entregables/QA manuales y bloquea categorías automáticas
   homónimas. `move_contents` admite filtros de hijos/documentos directos y
   requiere `source_rename_to` si la fuente raíz choca con el nombre destino.
   No hay sufijos silenciosos. Probar contenido archivado: también impide
   `archive_source_when_empty` mientras permanezca en la fuente. El preview
   no crea carpetas, proyectos, mutexes ni recibos.
4. **Token y vigencia.** Capturar `plan_hash` y `plan_token`; el token firmado
   dura 30 minutos y está ligado al actor/credencial. Expiración y alteración
   producen `PLAN_TOKEN_INVALID`; otra credencial/actor, `FORBIDDEN`. Cambiar
   el alcance después del preview o de preparar `apply_folder_migration`
   produce `STALE_VERSION`. Ninguno de esos casos crea la migración. Un plan
   bloqueado devuelve `CONFLICT` con `details.blockers` antes de confirmar.
5. **Confirmación y postcondiciones.** Aplicar con token, motivo y `request_id`,
   revisar el impacto y ejecutar `confirm_action`. Comprobar una sola raíz
   gestionada, ninguna manual homónima, la carpeta fijada activa/sin dueño con
   todos los espejos y la ubicación/propiedad/visibilidad de cada fila igual al
   plan. Verificar por separado que los espejos siguen sincronizados. Una falla
   inyectada de escritura o postcondición debe revertir el árbol y el proyecto.
   La raíz adoptada sigue el nombre, cliente y estado activo al guardar después
   el proyecto, con padre null. `_synchronize_root` sólo tolera la colisión de
   nombre con una raíz manual: conserva el nombre de la raíz gestionada y
   registra el choque. Inyectar cualquier otro fallo de sincronización en un
   guardado posterior: debe propagarse y revertir tanto el proyecto como su
   árbol, sin guardar un proyecto cuya raíz quedó desincronizada.
6. **Recibo e idempotencia.** `get_folder_migration(migration_id)` debe devolver
   el mismo reporte de aplicación: origen/destino, cambios antes/después, IDs
   creados/eliminados, archivados, pendientes y motivo. Comprobar la audiencia
   original en `before.portal_audience` de los documentos de `moved`; el recibo
   conserva también la de los documentos sin cambios, visible en `restore`
   del preview de deshacer. El mismo `request_id`, plan, actor y credencial
   devuelve el resultado original; otro plan con ese
   ID devuelve `REQUEST_ID_CONFLICT`. Guardar el ID del recibo para deshacer.
7. **Deshacer y sus bloqueos.** Usar `preview_folder_migration_undo`, pasar su
   `impact_hash` como `expected_impact_hash` a `undo_folder_migration` con
   motivo/request ID y confirmar. Comparar con la instantánea original de
   propiedad, ubicación, visibilidad y archivo; sólo se elimina el proyecto
   creado si sigue sin uso. Probar `changed_since`, `new_content_since`,
   `project_in_use`, `already_reverted` y `changed_since` con `reason: lifo`
   ante una operación posterior que toca las mismas filas. Los cambios de
   contenido Markdown o `updated_at` por sí solos no son cambios de propiedad.
   Un documento que adquirió un vínculo congelado debe impedir restaurar
   su propiedad; un impacto obsoleto o una falla de escritura no deja cambios.
   Cambiar el dueño del proyecto original después de migrar: si la restauración
   daría acceso a otro cliente, el preview y el rechazo incluyen
   `undo_audience_changed` en `blockers`, con documento y audiencias antes/después.
   Recalcular bajo candados al aplicar; si el impacto cambió desde el preview,
   devolver `STALE_VERSION` sin restauración parcial. Con audiencia original
   intacta, deshacer debe recuperar el acceso de ese cliente. Para recibos
   antiguos sin audiencia registrada, bloquear si se abriría acceso; permitir
   sólo la restauración sin audiencia en el portal.
8. **Adopción directa.** `adopt_folder_as_project_root` con `folder_id`,
   `project_id`, políticas/decisiones, motivo y `request_id` debe mostrar un
   plan `adopt_source` en la confirmación. Revalidar, confirmar, releer el
   recibo y deshacer por el mismo motor; no crea una raíz paralela.
9. **Alta de proyecto con raíz.** En Proyectos, llamar `create_project` con
   `name`, `client_profile_id` y `root_folder_id`, y sólo `description`/`state_id`
   como opciones de proyecto. Comprobar el esquema cerrado: `client_policy`,
   `portal_policy` y `document_decisions` se rechazan como `unknown_field`.
   Toda adopción usa `abort_on_conflict` y `abort`, sin decisiones. Un plan
   bloqueado devuelve `CONFLICT`, `details.blockers` y la pista en
   `details.hint` a `preview_folder_migration`/`apply_folder_migration` de
   Documentos, sin crear proyecto ni intención. Una confirmación pendiente
   preparada con políticas permisivas o decisiones anteriores devuelve
   `STALE_VERSION`. En un plan permitido no se crea antes de confirmar;
   el resultado incluye `document_root.folder_id`, `adopted: true` y
   `migration_id`. El alta sin colisión es inmediata y devuelve
   `adopted: false`/`migration_id: null`. Una raíz homónima adoptable sin ID
   explícito también exige confirmación y conserva una sola raíz.
10. **Regla de nombre al crear y renombrar.** Probar en Panel, Platform y MCP
    raíces manuales homónimas con espacios/mayúsculas y archivadas. Las altas
    adoptan sólo una candidata segura o devuelven `PROJECT_ROOT_NAME_CONFLICT`
    con IDs/rutas/motivos. La adopción automática rechaza cualquier documento
    marcado visible, activo o archivado, aunque hoy no tenga audiencia.
    La 66 con espejos requiere revisión por las tools de Documentos. Un
    renombre en colisión se rechaza sin adopción implícita. Raíces gestionadas
    de otro proyecto o cliente no bloquean proyectos homónimos; un save posterior
    no debe crear otra raíz ni renombrar sobre una manual en conflicto.
11. **Cliente de carpeta y políticas de portal.** Llamar
    `preview_folder_client_change` con `folder_id` y `client_profile_id`:
    `portal_changes` identifica los documentos que ganarían audiencia con
    `document_id`, `before_audience` y `after_audience`, sin escrituras.
    En `change_folder_client` con `mode: propagate`, omitir `portal_policy`
    por MCP equivale a `abort`, con argumentos planos; `data` se rechaza:
    nueva audiencia devuelve `PORTAL_EXPOSURE` con bloqueos y conserva el árbol.
    Probar `allow` (audiencia aprobada) y `hide_new_exposure` (nuevo dueño,
    `is_client_visible: false` sólo en los documentos que ganarían acceso).
    `folder_only` conserva dueño y visibilidad de los documentos. Una petición
    del Panel sin política conserva la cascada legacy; una política inválida
    se rechaza antes de escribir.
12. **Facturación y carreras.** Interponer pausa o cancelación entre la lectura
    de acceso y el PATCH de ajustes de suscripción: la relectura bajo candados
    y la escritura limitada a campos solicitados/derivados deben conservar
    el estado y la próxima fecha decididos por el ciclo de vida. Un PATCH vacío
    no escribe ni actualiza la fecha de modificación.
    En `card-pay`, simular cambios durante la tokenización o la espera del
    token de aceptación. Antes de crear la transacción Wompi, releer bajo
    candados proyecto → suscripción → hosting → pago y exigir pago sin archivar
    en `pending`/`overdue`/`failed`, suscripción activa/pendiente sin archivar
    ni contexto de retención y ligada al proyecto, y que `project_allows_billing`
    permita facturar.
    Si deja de ser elegible, responder HTTP 400 sin enviar el cobro al proveedor
    ni escribir historia de pago. Reanudar y cobrar con tarjeta nueva o guardada
    deben usar `project_allows_billing`; incluir un proyecto sin estado
    clasificado con `state_review_required: true` como caso bloqueado.
    Simular Wompi y correo. La relectura comprobada en SQLite no certifica
    la exclusión concurrente de los locks de MySQL REPEATABLE READ.

Referencias de comportamiento, para elegir lotes de hasta 20 tests y no ampliar
el barrido por la carga del host:

| Frente | Cobertura existente |
| --- | --- |
| Plan y movimientos | [Planificador](../backend/content/tests/services/test_ownership_planner.py), [paridad REST/MCP](../backend/content/tests/views/test_ownership_parity.py), [guardas](../backend/content/tests/services/test_ownership_move_guards.py) |
| Migración y tokens | [Motor de migración](../backend/content/tests/services/test_folder_migration.py), [guardas de migración](../backend/content/tests/services/test_folder_migration_guards.py), [recorrido MCP](../backend/content/tests/views/test_mcp_folder_migration.py) |
| Deshacer | [Bloqueos y restauración](../backend/content/tests/services/test_folder_migration_undo.py), [audiencia original y recibos antiguos](../backend/content/tests/services/test_folder_migration_undo_audience.py) |
| Cliente de carpeta | [Exposición y políticas REST/MCP](../backend/content/tests/views/test_folder_client_change_exposure.py) |
| Raíz y alta | [Regla compartida](../backend/content/tests/services/test_project_root_adoption.py), [alta por MCP](../backend/content/tests/views/test_mcp_create_project_root.py), [sincronización y rollback](../backend/content/tests/services/test_project_document_folder_service.py) |
| Facturación y carreras | [PATCH, tarjeta y revisión de estado](../backend/accounts/tests/billing/test_billing_race_guards.py) |
| Versión y discovery | [Pin de Documentos](../backend/content/tests/views/test_documents_mcp_301.py), [capacidades](../backend/content/tests/views/test_document_organization_api.py), [paridad de conectores](../backend/content/tests/views/test_mcp_discovery_parity.py) |

El deploy aplica `content.0286_contracttemplate_mirror_folder`,
`content.0287_document_ownership_operation` y
`accounts.0082_hosting_payment_voided_status`. Para Documentos, las allow-lists
explícitas deben incorporar `preview_move`, `preview_folder_migration`,
`apply_folder_migration`, `get_folder_migration`,
`preview_folder_migration_undo`, `undo_folder_migration` y
`adopt_folder_as_project_root` según el alcance necesario. Para Proyectos,
añadir las dos tools de hosting indicadas en la parte 1. Permitir confirmaciones
y lecturas del recorrido y reconectar claude.ai. El orden de integración con
PR #503 puede exigir el número siguiente y nuevos pins; comprobar las versiones
realmente publicadas antes de la operación.

### Runbook post-despliegue del caso real

**Ejecutar sólo después del merge y del deploy**, desde los conectores de
producción con el alcance autorizado. Este procedimiento no se ejecuta desde
el worktree. Los IDs siguientes provienen de la lectura del 2026-10-09 y deben
revalidarse: carpeta manual ProjectApp 66, estimaciones 69, Contratos 121,
documentos de otro cliente 235/241, cliente destino perfil 29 y proyecto
histórico PRUEBA 7 con suscripción 3 y pagos 4/5. Cancelar la 3 no habilita
el cambio de cliente del proyecto histórico: la historia financiera se conserva.
La migración de la 66 se realiza por el conector **Documentos**, mediante
`preview_folder_migration`/`apply_folder_migration`. No usar `create_project`
de Proyectos para este caso: las decisiones de 235/241 y la política del portal
de 69 requieren las herramientas de Documentos.

Guardar evidencia de cada paso en el registro privado de la operación:
argumentos revisados, request ID, respuestas, hashes, IDs de confirmación y
recibos. No guardar secretos de credencial ni tokens firmados en Git.
**El paso 5 debe completarse antes del 2026-12-01 a las 06:00 UTC**, fecha del
débito automático del pago 5 ($4.800). Si el deploy se demora, el plan alterno
de retirar la tarjeta guardada requiere una decisión operativa separada; no
declarar cancelación por haber llegado al plazo.

1. **Credenciales y reconexión.** En el Panel, ampliar las allow-lists de
   Documentos y Proyectos con las tools anteriores, confirmaciones y lecturas.
   Reconectar ambos conectores en claude.ai. Consultar `tools/list` y
   `describe_capabilities` y comparar versiones, schemas y alcance. Revalidar
   que el deploy aplicó las migraciones citadas. **Evidencia:** SHA desplegado,
   migraciones aplicadas, IDs/etiquetas de credenciales sin secreto y respuestas
   nuevas de discovery/capacidades (73/164 con alcance completo).
2. **Espejos antes de migrar.** Llamar `list_contract_mirrors` sin argumentos.
   Exigir `pinned_folder.pinned_folder_id: 121`, `folder_movable: true`, carpeta
   activa/sin dueño y los tres `synchronized: true` (documentos 104/239/205).
   `pinned_folder_id` es un campo de salida, no un filtro de la herramienta.
   **Evidencia:** listado completo con IDs, pin, ruta, versiones y flags antes
   del cambio. Si no coincide, resolver el pin/sincronización antes del paso 3.
3. **Plan de la carpeta 66.** En el conector Documentos, llamar
   `preview_folder_migration` con
   `source_folder_id: 66` y
   `target: {create_project: {name: "ProjectApp", client_profile_id: 29}}`.
   Elegir `strategy: adopt_source` para conservar la 66 como raíz, o
   `strategy: move_contents` con `source_rename_to: "ProjectApp anterior"`
   y `archive_source_when_empty: true` para crear raíz y archivar la fuente
   realmente vacía. `target.create_project` es el destino del plan de Documentos,
   no la herramienta `create_project` de Proyectos. Revalidar que el nombre
   elegido está libre. En ambos caminos, como argumentos del preview,
   enviar `client_policy: abort_on_conflict`, `document_decisions` para **235 y
   241** y una `portal_policy` explícita para las estimaciones visibles de **69**.
   Para cada documento, decidir `action: inherit` si se autoriza adoptar el
   dueño del destino, o `action: move` con una `destination_folder_id` ya
   verificada que conserve el destino adecuado; no inventar ese ID. Para 69,
   elegir `hide_new_exposure` si no se autoriza abrir acceso al cliente 29,
   `allow` sólo si se autoriza esa audiencia, o `abort` para detenerla.
   Incluir la exposición latente de estimaciones archivadas al restaurarse.
   Exigir `can_apply: true`, cero bloqueos y filas revisadas de esos IDs; Contratos
   debe aparecer pinned y sin dueño. **Evidencia:** argumentos finales, políticas
   y decisiones aprobadas, filas 235/241 y de 69, pin 121, árbol final, avisos y
   `plan_hash`; guardar el token de 30 minutos únicamente en el registro privado.
   Si vence o cambia el árbol, repetir este paso antes de aplicar.
4. **Aplicación, recibo y tres comprobaciones.** Llamar
   `apply_folder_migration` en Documentos con el token vigente, motivo y
   `request_id` único; revisar el impacto, ejecutar `confirm_action` con su
   `confirmation_id` y
   consultar `get_folder_migration` con el `migration_id` recibido. Comprobar:
   **(a)** `list_folders` con `{name: "ProjectApp", parent_id: null}` devuelve
   una sola raíz y su ID coincide con `root_folder_id` del recibo;
   **(b)** `get_project_folder_readiness` sin argumentos devuelve `status: ready`
   y la raíz del nuevo proyecto está gestionada; **(c)** `list_contract_mirrors`
   conserva pin 121 y los tres espejos sincronizados, activos y sin dueño.
   Releer las filas de 69 para comprobar la visibilidad aprobada y la carpeta
   de estimaciones activa; conservar sus IDs. Con `move_contents`, verificar
   además fuente 66 renombrada/archivada o el motivo de pendientes del reporte.
   **Evidencia:** impacto confirmado, request/confirmation/migration IDs,
   reporte completo y respuestas de las tres comprobaciones, más visibilidad
   posterior de 69. No declarar la migración completa si alguna difiere del plan.
5. **Detener el débito de PRUEBA antes del plazo.** Llamar
   `preview_hosting_subscription_change` con
   `{subscription_id: 3, action: "cancel"}` y revisar `can_apply`, bloqueos,
   `voided_payments` y `kept_history`. Exigir que el pago 5 se anule y el pago
   recibido 4 se conserve. Llamar `change_hosting_subscription` con la misma
   acción/fecha efectiva, motivo y `expected_impact_hash` del preview; revisar
   y ejecutar `confirm_action`. Consultar `get_project_hosting` con
   `{project_id: 7}`: suscripción 3 `cancelled`, próxima fecha null, pago 5
   `voided` con `is_archived: true`/`archived_at`, y pago 4 pagado con su historia.
   **Evidencia:** timestamp UTC anterior al **2026-12-01 06:00 UTC**, preview y
   hash, impacto/confirmación, evento de cancelación e historial de pago,
   y lectura final del hosting de 7. Si hay bloqueo o el 5 no figura en el
   preview, detener la aplicación y revisar el estado actual; no intentar un
   cobro real para verificarlo.

## Intereses y contratos de propuestas (2026-09-29)

En `proposals` y `commercial`, los intereses en módulos y su fecha son sólo de
lectura: proceden de la elección pública del cliente, sin alterar alcance ni
inversión. El snapshot del precio anterior queda excluido por ser respaldo
interno de la migración. La formalización usa el mismo control de vigencia del
contrato de servicio que el panel y rechaza adjuntos obsoletos; las descargas y
preparaciones respetan la modalidad de cierre. Validar clasificación de campos,
consulta de propuesta y errores de generación/preparación antes de publicar.
El anexo comercial usa la misma exclusión de «¿Por qué esta inversión?» que
Documentos, conservando importes y pagos. La versión documental 6 exige revisar
las preparaciones previas sin reemplazar sus adjuntos; no cambia el esquema MCP.

## Videos y conectores comerciales (2026-09-28)

Programa de Alianza (`partnership-program`) y Módulos adicionales (`additional-modules`) tienen conectores independientes; `proposals` incorpora videos general/personalizado. Todos permiten transferir un MP4 real, completar la carga y asignar/sustituir con `asset_id` y revisión. Guía y nombres exactos: [Recursos de video comerciales](COMMERCIAL_VIDEO_RESOURCES.md).

Validar consulta → begin_upload → PUT firmado (o bloques) → complete_upload → set_*_video, luego repetir para reemplazar. Verificar rechazo de archivo corrupto, credencial ajena, carga incompleta, revisión vieja y límite de 250 MiB. Confirmar reproducción pública y conservación del anterior ante fallos. Los otros archivos mantienen su límite de 25 MiB y vencimiento de 15 minutos; videos vencen en una hora.

## Plataforma operativa común

Revisión focal LinkedIn (2026-10-01): refresh conserva credenciales ante
429/5xx y respuestas ambiguas; sólo un rechazo explícito admitido las borra.
El contrato MCP mantiene metadata de `LinkedInToken` en sólo lectura y excluye
ambos secretos cifrados. Validar los dos contratos de `linkedin-personal` en
`test_mcp_contracts.py`, junto con crear, leer, editar, publicar/error y estado
de conexión de `test_mcp_linkedin.py`; simular el proveedor, sin llamadas reales.
La retención y recuperación de tokens se comprueban en las pruebas del servicio.

- El endpoint canónico acepta `Authorization: Bearer <credencial>` en
  `/api/mcp/<slug>/`. La URL histórica `/api/mcp/<slug>/<token>/` permanece
  disponible para no romper conectores instalados.
- El contrato stateless MCP `2026-07-28` usa `server/discover`, metadata por
  request, `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` para `tools/call`,
  `resultType` y hints de caché privada. Los handshakes 2025 y 2024 siguen
  admitidos por compatibilidad.
- Cada credencial tiene etiqueta, alcance de herramientas, vencimiento y
  revocación propios. El secreto sólo se muestra al crear o rotar; la base
  conserva únicamente SHA-256 y un prefijo enmascarado.
- Cada conector ejecuta como un principal técnico no interactivo
  `mcp_<slug>`, con contraseña inutilizable. No toma prestada la identidad del
  primer superusuario humano.
- `tools/list` y `describe_capabilities` comparten `registry.public_tool` y el
  alcance de credencial. Identidad y versión proceden del mismo registro en
  `initialize`, `server/discover` y metadata moderna; ambos handshakes entregan
  las instrucciones propias del conector.
- Las herramientas nativas de propuestas actualizadas publican argumentos planos. Los sobres
  `data`/`query` y aliases históricos admitidos siguen funcionando en ejecución;
  el uso de sobres se registra como `deprecated_envelope`. Su forma privada
  `accepted_arguments_schema` nunca se publica. Los adaptadores genéricos
  pendientes permanecen en el backlog. El puente Panel compartido aún publica
  `data` en algunos payloads explícitos (por ejemplo, `update_proposal_settings`
  y `review_proposal_approval`); su proyección plana depende del trabajo paralelo.
- La confirmación depende de cada herramienta y de sus instrucciones. Las que
  la requieren devuelven `confirmation_id`, impacto y vencimiento;
  `confirm_action` ejecuta los mismos argumentos y `cancel_action` descarta el
  intent. `update_expected_income` sólo previsualiza si el cambio afecta dinero,
  IVA, reparto, contabilidad, cliente o proyecto. Las herramientas existentes
  de los cinco conectores de compatibilidad conservan ejecución directa.
- Los módulos con archivos exponen `begin_upload`, PUT firmado o
  `upload_asset_chunk`, `complete_upload` y `abort_upload`. Tamaño, MIME y
  SHA-256 se verifican antes de que un `asset_id` pueda consumirse; descargas y
  exports se entregan como artefactos firmados temporales.
- La auditoría conserva las 200 entradas más recientes por conector con
  request ID, credencial, herramienta, riesgo, resultado/error, duración e IDs
  de objetos afectados. No persiste cuerpos completos ni secretos.

## Invariantes

- Todos los conectores comparten control de Origin, throttle por conector,
  principal técnico, registro de actividad y los dos transportes de credencial.
- Un conector nuevo nace inactivo y sin token. Activarlo y emitir la URL es una
  decisión explícita del superusuario en `/panel/mcps`.
- Los handlers MCP reutilizan serializers y servicios del panel. Una regla que
  impide una acción en la interfaz también la impide por conversación.
- La política de `schema_policy.py` exige objetos cerrados, argumentos tipados y
  descritos, sin combinadores de raíz; los objetos libres necesitan motivo
  documentado. `schema_backlog.py` mantiene excepciones que sólo pueden reducirse
  para adaptadores genéricos, descripciones pendientes y esquemas diferidos.
  Los objetos de propuestas con campos definidos rechazan claves desconocidas
  también en listas y objetos anidados.
- Los esquemas publicados son el contrato; esta rama no añade un validador
  central de argumentos. Los desconocidos o faltantes se rechazan en cada
  handler/serializer; las tools de ingresos esperados usan `unknown_field` para
  claves desconocidas. `accepted_arguments_schema` es privado y conserva las
  formas aceptadas en ejecución. La rama `feat/09102026-mcp-folder-migration`
  incorpora validación central opt-in en `protocol.py` para Documentos,
  Proyectos o tools con `strict_arguments`, usando ese esquema privado cuando
  existe; no se atribuye ese validador a esta entrega.
- Un cambio del contrato público requiere incrementar la versión en
  `ConnectorSpec`, escribir un changelog y ejecutar
  `mcp_schema_report --write-fingerprints`. Las huellas se versionan en
  `backend/content/mcp/connector_contracts.json` y las pruebas detectan deriva.
  La versión se almacena aparte del SHA-256 del contrato.
- En propuestas, `_meta.optional_metadata.email_intro` del template/artifact se
  persiste como `BusinessProposal.email_intro`. Debe ser texto plano específico
  del cliente y conectar problema, solución y resultado. `send_proposal`,
  `resend_proposal` y el envío múltiple rechazan el mensaje vacío antes de
  snapshots o transiciones; `resend_proposal` acepta un `email_intro` opcional
  para editarlo y enviarlo en la misma operación.
- Las carpetas con `system_key` pertenecen al archivado automático. El MCP puede
  listarlas para orientar al operador, pero no crearlas debajo, renombrarlas ni
  usarlas como destino de un documento markdown.
- Ninguna descripción puede prometer un dato que el handler descarte o una
  acción que el servidor no realiza.
- `DocumentState.description` es una lectura clasificada del contrato MCP. Para
  estados de proyecto, la descripción administrable no sustituye el
  `operational_effect` ni la ayuda de consecuencias derivada por el sistema.
- `UserProfile.document_navigation_mode` es una preferencia de presentación del
  panel y permanece clasificada como perfil/plataforma: no altera ni se expone
  en las herramientas MCP de clientes o Documentos.
- `UserProfile.address` es una lectura de facturación del conector de clientes,
  junto con NIT/cédula y código. `search_clients`, `list_clients` y `get_client`
  usan los serializers del panel y devuelven la proyección `billing_customer`
  que completa una nueva cuenta. Las tools actuales de escritura de clientes
  conservan sus campos declarados de contacto; la identificación y dirección
  se editan en la ficha del panel, también accesible desde la cuenta nueva.
- Todo `Project` pertenece a los catálogos de Documentos y Comunicaciones; no
  existe un opt-out por módulo. `DocumentFolder.managed_project` identifica su
  única raíz documental canónica. El MCP puede seguir referenciando proyectos
  existentes, pero no adopta carpetas históricas ni provisiona raíces por esa
  vía.
- `ProjectAdminAccess`, `ProjectAccessNote` y los campos legacy
  `Project.admin_url/admin_username/admin_password_encrypted` quedan excluidos
  con motivo explícito. Ninguna tool MCP lista, revela, crea o modifica
  URLs, credenciales o notas del detalle seguro; las operaciones MCP de proyecto
  conservan únicamente identidad, ciclo y metadatos no operativos.
- `DocumentFolder.managed_client` es el equivalente para clientes y se comporta
  igual desde el MCP: read-only, sin adopción ni provisión por esa vía. Con él
  `folder_kind` tiene **tres** valores (`project` / `client` / `manual`), que es
  lo que declara la descripción de `list_folders`. Dos asimetrías respecto de
  proyectos, deliberadas: la raíz de cliente **no** se crea sola con el cliente
  (se adopta), y **sí** se puede renombrar —el nombre lo pone el operador, no un
  módulo externo—, así que `rename_folder` la acepta.
- **Archivado de clientes.** `UserProfile.archived_at` (antes `deactivated_at`)
  es el eje de ciclo de vida del cliente, con el mismo vocabulario que el bucket
  no activo de proyectos. `list_clients` devuelve **sólo activos** salvo que se
  pida `archived=true`: devolverlos mezclados es como el conector termina
  proponiendo trabajo sobre un cliente que se archivó a propósito. `archived_at`
  es read-only y `archived_by` está excluido como auditoría interna, junto a
  `created_by` — archivar **no** es una operación del MCP, porque suspende los
  proyectos del cliente y cancela su facturación futura, y eso exige la vista
  previa del panel. El archivado de un hilo de comunicaciones sólo cambia su
  visibilidad y sí está expuesto mediante una acción de dominio específica.
  Única excepción: la fusión de clientes duplicados del motor de integridad
  (`apply_integrity_fixes`, regla CL1-CL3) archiva el cliente que se fusiona
  como último paso, después de comprobar que ya no le queda ningún proyecto,
  así que no hay nada que suspender ni facturación que cancelar.
- **Integridad de datos.** El motor nunca borra registros para resolver un
  duplicado, nunca escribe filas conservadas (`retention_context`), raíces
  gestionadas fuera de una fusión, carpetas de sistema ni documentos generados,
  y nunca reescribe historial, logs ni evidencia. Toda corrección queda en
  `DataIntegrityOperation` con valores antes/después y se deshace exacta
  mientras nadie haya cambiado esos datos (`docs/DATA_INTEGRITY.md`).
- `update_message` edita sólo un borrador saliente activo;
  `delete_draft` aplica la misma condición; `mark_message_sent` registra un
  hecho externo y no contacta proveedores. El envío real pertenece a las
  herramientas separadas `send_email`/`resend_email`, clasificadas como
  sensibles y ejecutables únicamente después de vista previa y confirmación.
  Sus payloads de destino usan `recipient_emails` (Para) y `cc_emails` (copia
  visible): admiten hasta 10 direcciones únicas entre ambas listas. El campo
  legado singular `recipient_email`/`recipient` sigue aceptándose para clientes
  MCP anteriores, pero no permite expresar varios destinatarios.
- `CommunicationThread.managed_project` / `managed_client` identifican la
  **comunicación madre** de un proyecto o un cliente, en paralelo con
  `DocumentFolder.managed_project` / `managed_client`. Son read-only para el MCP:
  la madre de proyecto se provisiona sola al crearse el proyecto, la de cliente
  sólo por adopción revisada, y ninguna se marca desde una herramienta.
  `thread_kind` toma tres valores (`project` / `client` / `manual`).
- El **archivado** de hilos (`is_archived`/`archived_at`) es un eje de visibilidad
  ortogonal a `status` (`open`/`closed`): cerrar bloquea la escritura, archivar
  saca de la vista. Esos campos son read-only: el MCP sólo puede cambiarlos con
  `archive_thread`/`unarchive_thread`, que reutilizan el servicio del panel; una
  comunicación madre no se puede archivar. `list_threads` expone
  `scope=active|archived|all` y conserva `active` como valor por defecto.
- Los hilos entre documentos (`DocumentThread` / `DocumentThreadItem`) sí forman
  parte del conector `documents`. Tres reglas los gobiernan y ninguna se puede
  relajar desde una herramienta:
  - **La edición de miembros es incremental.** El PATCH del panel reemplaza la
    lista completa y disuelve el hilo cuando queda un solo miembro; un conector
    que reconstruyera esa lista destruiría la historia al olvidar una entrada.
    Por eso `update_document_thread` expone `link` / `unlink_document_ids`, se
    rechaza antes de bajar de dos documentos, y disolver es una herramienta
    aparte.
  - **Enlazar acepta sólo documentos markdown activos**, la misma regla del
    resto del conector. Leer y desenlazar aceptan cualquier miembro, porque un
    hilo armado desde el panel puede contener una cuenta de cobro o un
    documento archivado.
  - **Las cuentas de cobro emitidas siguen excluidas del contrato documental
    MCP.** Su `generated_file`, hash/procedencia y datos contables son artefactos
    comerciales de sólo lectura en el panel; `list_documents`/`read_document`
    continúan operando únicamente Markdown y no prometen vista previa, descarga
    ni reemplazo del PDF. Esta exclusión no impide leer una cuenta que ya sea
    miembro de un hilo creado desde el panel.
  - **`position` es derivada** de la cronología: el conector envía fechas y el
    servidor mantiene el orden estable. Es la única exclusión del contrato.
  - **La fila del listado es una sola.** `list_document_threads` y el índice de
    hilos del panel (`GET /api/document-threads/`) comparten
    `DocumentThreadListSerializer` sobre `thread_list_queryset`, igual que ya
    compartían la consulta. Al tocar esa fila hay que verificar ambas
    superficies: las fechas se serializan con `isoformat()` (`+00:00`), no con
    los campos de fecha de DRF, que emitirían `Z` y romperían al conector.
  `dissolve_document_thread` es irreversible —se pierde `linked_by`/`linked_at`—
  y por eso devuelve el hilo completo previo más `released_document_ids`, con lo
  que se puede recrear con `create_document_thread`.
- Nunca copiar tokens reales en tickets, fixtures, logs, commits o este guion.

## Inventario vigente

| Slug | Versión | Herramientas | Alcance |
|---|---|---:|---|
| `operations` | 2.1.0 | 4 | Dashboard, indicadores, alertas y conteos globales de sólo lectura |
| `partnership-program` | 2.1.1 | 26 | Condiciones, formalización y recursos del Programa de Alianza |
| `building-with-us` | 1.0.0 | 16 | Presentación pública bilingüe y contrato privado versionados, preview, confirmación, restauración, PDF e inicialización del espejo; creado inactivo, sin uploads ni videos |
| `additional-modules` | 2.1.1 | 25 | Catálogo bilingüe, configuración y recursos de módulos adicionales |
| `commercial` | 2.1.1 | 201 | Clientes, propuestas, diagnósticos, módulos adicionales, horas, Programa de Alianza (financiación), visibilidad de videos explicativos, archivos, instantáneas de contratos y correos comerciales |
| `proposals` | 2.2.1 | 108 | Propuestas, secciones, contratos, instantáneas, formalización, archivos y enlaces |
| `projects` | 3.0.0 | 171 | Proyectos, asignaciones, estados, transiciones, documentos asociados, historial, integridad de datos y ciclo de vida de hosting |
| `documents` | 4.0.0 | 73 | Documentos Markdown editables, carpetas, migración/adopción con deshacer, movimientos con políticas, estados, tags, observaciones, hilos, correo, imports y exports |
| `communications` | 2.1.1 | 50 | Hilos, carpetas, mensajes, compositor, previews, envío/reenvío, adjuntos, historial, templates, entregabilidad y enlaces seguros de un solo uso |
| `content` | 2.1.1 | 60 | Blog, portafolio, QR, Linktrees, LinkedIn y activos relacionados |
| `tasks` | 2.1.0 | 20 | Tareas, archivo, comentarios, alertas, orden y controles comunes |
| `accounting-ledger` | 2.3.0 | 64 | Ingresos esperados con ETag, abonos individuales y colectivos sin cuenta previa, corrección y reversa del abono, liquidación con ajustes, gastos, bolsillo, recurrentes, Ads, categorías, previsión de cobro, liquidaciones y exports |
| `accounting-billing` | 2.1.1 | 46 | Cuentas de cobro, hosting, ciclos, ajustes, destinatarios y correo contable |
| `accounting-cards` | 2.1.1 | 39 | Tarjetas, snapshots, detalle completo con get_statement, extractos, transacciones, alias, imports y recordatorios |
| `blog` | 1.1.0 | 10 | Conector de compatibilidad: plantilla, CRUD y calendario editorial |
| `clients` | 1.1.0 | 9 | Conector de compatibilidad: búsqueda, detalle y CRUD de clientes |
| `accounting` | 1.3.0 | 80 | Conector de compatibilidad (Gestor Contable): catálogo monolítico, ingresos esperados, creación, corrección y reversa de abonos y controles comunes |
| `diagnostics` | 1.1.0 | 16 | Conector de compatibilidad: diagnósticos y secciones |
| `linkedin-personal` | 1.1.0 | 10 | Conector de compatibilidad: LinkedIn personal |

Los 19 conteos proceden de `CONNECTORS` / `TOOLS_BY_SLUG` y de
`mcp_schema_report` local con `projectapp.settings_test` el 2026-10-10, sin
consultar datos reales: 1028 herramientas sumadas entre catálogos, incluidas las
compartidas. Los cinco conectores de compatibilidad sumaron tres controles cada
uno; `accounting` y `accounting-ledger` sumaron cinco herramientas de ingresos
esperados, y `accounting-cards` incorporó `get_statement`. Los dos conectores
contables incorporan además `update_income_abono` y `delete_income_abono`.
El barrido de PR 2 conserva esos conteos y fija como objetivo **4.0.0** y
**3.0.0**, respectivamente. Los pins de discovery/capacidades deben verificar
esas versiones además de la paridad de esquemas; ver el
[cierre de esquemas explícitos](#esquemas-explícitos--documents-400-y-projects-300-2026-10-10).

Los conectores canónicos nuevos nacen inactivos. Los cinco slugs marcados como
compatibilidad no se eliminan ni cambian de URL; permiten una transición gradual
hacia los conectores agrupados por área.

## Preparación segura

### Building with Us — presentación (PA-174, B1)

La migración `0286_building_with_us_program` crea el conector `building-with-us`
inactivo, sin credenciales, y la presentación inicial en español e inglés. Su
versión MCP es `1.0.0`. No comparte herramientas con `commercial`; sus dieciséis
herramientas incluyen los tres controles comunes, las seis de presentación y
las siete contractuales de B2. El overview devuelve metadatos independientes
de programa y contrato, incluido el estado del espejo documental.

El Panel sólo admite GET en `/api/building-with-us/admin/` y
`/api/building-with-us/admin/program/versions/`. Todo cambio de presentación
pasa por MCP con `if_match`, `change_note` y `confirm_action`. Las revisiones
son inmutables: restaurar crea una nueva. La validación exige todos los campos
de cada sección suministrada en ambos idiomas, ids y meses alineados, listas
acotadas y ausencia de porcentajes, símbolos monetarios y códigos de moneda.

Validar con una credencial temporal del entorno de pruebas:

1. Leer `get_building_with_us_program`: comprobar `content.es`, `content.en`,
   el orden de `sections`, metadatos de versión y `etag`.
2. Llamar `preview_building_with_us_program_update` con `sections.hero.es` y
   `sections.hero.en` completos. Revisar el diff y comprobar que la versión
   pública sigue igual. Las secciones omitidas se conservan.
3. Enviar esas secciones a `update_building_with_us_program` con el `if_match`
   leído y un `change_note` significativo; revisar el impacto y confirmar con
   `confirm_action`. Sin motivo no debe existir intención pendiente.
4. Comprobar `/api/building-with-us/public/?lang=es` y `?lang=en`: nueva versión,
   contenido localizado, `cta.whatsapp_url`, rutas canónicas y enlace PDF, sin
   datos de video ni cifras económicas. Tras el commit debe solicitarse la
   reconstrucción con motivo `building-with-us`. En producción se verifica la
   solicitud y el consumo por el regenerator del toolkit, seguido del HTML de
   ambas rutas; la aplicación no ejecuta el build dentro del worker.
5. Listar `list_building_with_us_program_versions`, incluyendo contenido si se
   desea: comprobar autor, fecha, motivo y orden descendente. Revisar también
   la paginación de sólo metadatos del Panel.
6. Enviar `restore_building_with_us_program_version` con `version_id`, el etag
   actual y `change_note`; confirmar. Verificar una nueva versión con referencia
   a la restaurada y una nueva solicitud de reconstrucción.
7. Preparar otra actualización, publicar un cambio independiente y confirmar
   la preparación anterior. Debe devolver `STALE_VERSION` sin escribir otra
   revisión. Los etags se comprueban otra vez con el singleton bloqueado.
8. Ejecutar `render_building_with_us_program_pdf` con `lang: es` o `en`; abrir
   el `download_url` firmado y comprobar que contiene la presentación vigente.
   El catálogo carece de herramientas de upload y video.

Pruebas focales desde `backend/`, usando el Python autorizado de la sesión (sin
exportar settings para pytest y sin ejecutar migrate):

```bash
PY=/home/dev_env/webapps/.wt/projectapp_staging/partner-split-auto-values/.venv/bin/python
$PY -m pytest content/tests/services/test_building_with_us_program_service.py --no-cov -q
$PY -m pytest content/tests/views/test_building_with_us_public.py --no-cov -q -k panel_rejects
$PY -m pytest content/tests/views/test_building_with_us_public.py --no-cov -q -k 'not panel_rejects'
$PY -m pytest content/tests/views/test_building_with_us_mcp.py --no-cov -q
```

`test_mcp_contracts.py` y la selección de rebuild exceden veinte casos. Los
siguientes grupos cubren sus selecciones completas sin exceder ese límite
(MCP: 19, 19, 12 y 20; rebuild: 18 y 15). Revalidar los conteos con
`--collect-only -q` si se agregan casos; correr hasta tres comandos por ciclo:

```bash
$PY -m pytest content/tests/views/test_mcp_contracts.py --no-cov -q -k model_fields_are_classified
$PY -m pytest content/tests/views/test_mcp_contracts.py --no-cov -q -k tool_metadata_is_actionable
$PY -m pytest content/tests/views/test_mcp_contracts.py --no-cov -q -k canonical_sensitive_tools
$PY -m pytest content/tests/views/test_mcp_contracts.py --no-cov -q -k 'not model_fields_are_classified and not tool_metadata_is_actionable and not canonical_sensitive_tools'
$PY -m pytest content/tests/services/test_frontend_build.py --no-cov -q -k '(Rebuild or rebuild) and (TestRebuildNeeded or TestRunFrontendRebuild)'
$PY -m pytest content/tests/services/test_frontend_build.py --no-cov -q -k '(Rebuild or rebuild) and not (TestRebuildNeeded or TestRunFrontendRebuild)'
```

Completar con las regresiones acotadas:

```bash
$PY -m pytest content/tests/management/test_fake_data_contract.py --no-cov -q -k classifies
$PY -m pytest content/tests/views/test_financing.py --no-cov -q -k sitemap
DJANGO_SETTINGS_MODULE=projectapp.settings_test $PY manage.py makemigrations --check --dry-run
```

Desde la raíz, ejecutar el gate con `--include-file` para los tres archivos
nuevos y los dos archivos de regresión editados (rutas completas desde
`backend/`). El scanner no admite como filtros `conftest.py` ni archivos de
fixtures sin tests; su integración se verifica con las pruebas que los usan.
Usar `--junk-severity=error` y `--report-path /tmp/building-with-us-test-quality.json`.

### Building with Us — contrato y espejo (PA-175, B2)

La migración `0287_building_with_us_contract` incorpora el contrato privado v1:
21 cláusulas completas, Condiciones particulares y anexos de alcance e hitos.
Los importes y porcentajes de referencia sólo viven en ese contrato. No se
aplica el bloqueo de cifras de la presentación pública. No se admiten tokens
`{placeholder}`: los espacios se escriben literalmente `XXX-XXX-XXX`.

El Panel sólo lee `/api/building-with-us/admin/contract/`, `contract/versions/`
y `contract/pdf/`. El PDF usa el renderizador Markdown del Gestor, sus portadas
y estilo, y marca de agua; `?inline=1` permite previsualizarlo. Si hay un espejo
sincronizado se entrega su copia guardada; si falta o quedó desactualizado, el
Panel genera la versión vigente sin escribir. La descarga desde el documento
del Gestor rechaza un PDF cuya revisión ya no es la actual.

Validar con una credencial temporal del conector `building-with-us`:

1. Leer `get_building_with_us_contract`: verificar Markdown, versión, autor,
   `change_note`, `etag` y `mirror.status`. Inicialmente es `not_initialized`.
   `update_building_with_us_contract` debe rechazar aplicar antes de inicializar
   el espejo con `MIRROR_NOT_INITIALIZED`.
2. Elegir una carpeta manual **Contratos** del espacio interno ProjectApp,
   activa y sin cliente, proyecto ni `system_key`. Preparar
   `initialize_building_with_us_contract_mirror` con `folder_id` y confirmar
   mediante `confirm_action`. El preview no crea documentos. La confirmación
   comprueba hashes del contrato, espejo y carpeta, guarda un documento interno
   de sólo lectura con PDF y dos notas privadas: versión inicial e inventario de
   las catorce decisiones pendientes. Repetir debe producir `noop` sin nuevas
   notas. Un espejo desactualizado se repara explícitamente con `resync`.
3. Previsualizar `preview_building_with_us_contract_update` con exactamente
   `markdown` o `patches`; revisar `diff`, `placeholders: []` y `document_to_sync`.
   Los patches admiten las mismas operaciones y selección literal que las
   plantillas de propuestas. Enviar `update_building_with_us_contract` con
   `if_match` y `change_note` y confirmar. Revisar nueva versión, PDF guardado,
   fecha del documento y nota privada. Un fallo en cualquiera revierte todo.
4. Desde `documents`, llamar `read_document` con el id del espejo: devuelve el
   Markdown vivo del contrato BWU, `contract_variant: building_with_us`, versión,
   fecha de sincronización, `is_contract_mirror: true` y
   `edit_blockers: ["contract_mirror"]`. Editar, mover o archivar el documento
   está bloqueado; la carpeta que lo contiene tampoco se renombra ni archiva.
   `list_contract_mirrors` conserva exclusivamente combined/product/service.
   Documentos sigue en **66 herramientas**, versión **3.1.0**.
5. Consultar `list_building_with_us_contract_versions`, opcionalmente con
   `include_content: true`. Restaurar mediante
   `restore_building_with_us_contract_version` con `version_id`, `if_match` y
   `change_note`, seguido de `confirm_action`: crea una revisión nueva y
   sincroniza el espejo. `restored_from_version` es el número de versión de
   origen; `restored_from_version_id` identifica su fila. Programa expone ambas
   referencias también.
6. Preparar un cambio; alterar la versión o el espejo/documento; confirmar la
   preparación anterior. Debe devolver `STALE_VERSION` sin revisión adicional.
   Para inicialización, repetir cambiando la carpeta después del preview:
   también debe rechazarse. Los escritores vuelven a comprobar etags bajo
   bloqueo en orden contrato → espejo → documento.
7. Llamar `render_building_with_us_contract_pdf` con `{}` y abrir su URL temporal
   firmada: `contrato-building-with-us-v<version>.pdf`, `application/pdf`.
   El adaptador libera los archivos de la respuesta interna sin emitir
   `request_finished`: el request MCP mantiene abierta su transacción hasta
   conservar el artefacto y registrar la llamada. Se verifica también el PDF
   de B1 y el cierre de un `FileResponse` real.

La alternativa operativa es `initialize_building_with_us_contract_mirror`:
sin `--apply` imprime el estado en JSON; con `--apply` exige `--folder-id` y
admite `--actor-id` de un staff activo, o toma el primer superusuario activo.
**Nunca ejecutar su aplicación desde un worktree de sesión**; corresponde al
despliegue autorizado. Los tests lo ejecutan sólo en SQLite aislado.

Desde `backend/`, con el mismo `PY` autorizado, ejecutar por separado y en
ciclos de hasta tres comandos (todos estos archivos tienen como máximo veinte
casos):

```bash
$PY -m pytest content/tests/services/test_building_with_us_contract_service.py --no-cov -q
$PY -m pytest content/tests/views/test_building_with_us_contract_mirror.py --no-cov -q
$PY -m pytest content/tests/views/test_building_with_us_contract_mcp.py --no-cov -q
$PY -m pytest content/tests/management/test_building_with_us_mirror_command.py --no-cov -q
$PY -m pytest content/tests/views/test_contract_mirror_document.py --no-cov -q
$PY -m pytest content/tests/views/test_contract_template_mirrors.py content/tests/management/test_contract_template_mirrors.py --no-cov -q
$PY -m pytest content/tests/views/test_contract_template_mcp.py --no-cov -q
$PY -m pytest content/tests/views/test_document_organization_api.py --no-cov -q -k mirror
$PY -m pytest content/tests/management/test_fake_data_contract.py --no-cov -q -k classifies
$PY -m pytest content/tests/management/test_fake_data_contract.py --no-cov -q -k fake_reset_clears_retained_document_ownership
DJANGO_SETTINGS_MODULE=projectapp.settings_test $PY manage.py makemigrations --check --dry-run
```

Completar los lotes B1 y los cuatro grupos de `test_mcp_contracts.py` indicados
arriba. Desde la raíz, ejecutar `scripts/test_quality_gate.py` con
`--junk-severity=error` y `--include-file` por cada uno de los cuatro tests B2
y los tres tests B1 editados. Fixtures y `conftest.py` se verifican mediante los
tests que los consumen; no son filtros admitidos por el scanner.

### Preparación general

1. Ejecutar en una base de test o staging. Producción sólo admite consultas
   read-only hasta que el operador autorice una mutación concreta.
2. Crear una credencial temporal, preferentemente Bearer y limitada a las
   herramientas del caso. Verificar que se le asignó el principal técnico del
   conector y que el secreto no reaparece al recargar.
3. Activar el conector bajo prueba. No reutilizar credenciales reales en
   capturas, comandos compartidos ni fixtures.
4. En contrato moderno, empezar con `server/discover`; en compatibilidad,
   inicializar con `initialize`. Consultar `tools/list` y comparar nombres,
   riesgos, schemas y alcance con el inventario esperado.
5. Para una acción sensible, validar primero el preview, luego confirmar una
   sola vez y repetir `confirm_action` para comprobar respuesta replay-safe.
6. Al terminar, desactivar el conector y revocar la credencial temporal.

Desde `backend/` del worktree, medir primero el registro local con settings de
test. No carga la `.env` enlazada ni consulta datos reales:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py mcp_schema_report
```

El comando consulta `initialize`, `server/discover`, `tools/list` y
`describe_capabilities` sin ejecutar herramientas de negocio. Sin `--slug`
revisa los 18; se puede repetir `--slug` para un caso focal. `--format json`
permite guardar un resultado procesable. Tras un cambio de contrato y su
incremento de versión, regenerar el lock en modo local:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py mcp_schema_report --write-fingerprints
```

Para consultar el servidor desplegado como cliente limpio, usar `--remote` con
la URL base del host. Cargar previamente tokens Bearer en variables de entorno
`MCP_TOKEN_<SLUG>`: slug en mayúsculas y guiones reemplazados por `_`
(por ejemplo, `MCP_TOKEN_ACCOUNTING_LEDGER` y `MCP_TOKEN_LINKEDIN_PERSONAL`).
Sin `--slug` hacen falta las 18 variables; no escribir sus valores en este guion
ni imprimirlos. `--token-env-template` permite otra convención con `{SLUG}`.

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py mcp_schema_report --remote 'https://<host>'
```

La consulta usa `/api/mcp/<slug>/`, Bearer y cabeceras sin caché, sin redirecciones.
El modo remoto no calcula huellas ni tamaños de backlog local y no admite
`--write-fingerprints` ni `--print-backlog`. Compara las vías del servidor entre
sí: también hay que contrastar versiones y conteos con el inventario local,
pues un servidor antiguo puede ser internamente consistente.

Petición base compatible para una llamada manual (sustituir los marcadores
localmente y no guardarlos en el historial del shell):

```bash
curl -sS -X POST 'https://<host>/api/mcp/<slug>/<token>/' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://claude.ai' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Descubrimiento stateless `2026-07-28` por Bearer:

```bash
curl -sS -X POST 'https://<host>/api/mcp/<slug>/' \
  -H 'Authorization: Bearer <credencial>' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: server/discover' \
  --data '{"jsonrpc":"2.0","id":"discover-1","method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"manual-validation","version":"1.0.0"}}}}'
```

Para invocar una herramienta:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": {}
  }
}
```

Una llamada de negocio válida responde HTTP 200. Un rechazo de negocio también
usa HTTP 200, con `result.isError=true`, `structuredContent.error.code` y texto
accionable. Un envelope moderno inválido responde HTTP 400; token, slug inválido
o inactividad responden 404 para no revelar conectores.

Una operación que requiere confirmación usa dos llamadas: la primera devuelve
un `confirmation_id` sin ejecutar y la segunda llama `confirm_action` con ese
ID. Consultar `requires_confirmation` y la descripción: `update_expected_income`
aplica su condición de cambio sensible y puede ejecutar directamente un cambio
descriptivo. El intent vence a los diez minutos, queda ligado a conector y
credencial, conserva la huella exacta de argumentos y no vuelve a ejecutarse
ante un replay.

## Verificación post-deploy y caché de clientes

1. Repetir el informe `--remote` sin `--slug`, con las 18 credenciales cargadas
   por entorno. Es una consulta de descubrimiento como cliente limpio; no
   modifica registros ni ejecuta operaciones contables. Para contrastar los
   conteos completos, usar credenciales con acceso al catálogo completo.
2. Exigir código 0 y contrastar las versiones con «Inventario vigente».
   `tools/list` y `describe_capabilities` deben coincidir en nombres, esquemas,
   descripción, título y anotaciones; las instrucciones de ambos handshakes
   también. El informe local y la prueba de huellas comprueban el lock del repo;
   el informe remoto no calcula ese SHA-256.
3. Abrir una conversación nueva en claude.ai. El descubrimiento moderno anuncia
   `ttlMs: 300000` (cinco minutos) y caché privada; las apps de escritorio o móvil
   pueden conservar definiciones propias además de ese hint.
4. Si la consulta limpia ya muestra las herramientas vigentes pero el agente
   conserva definiciones antiguas, quitar y volver a agregar el conector en
   **claude.ai Settings → Connectors**, con la misma URL. Si se necesita otra
   credencial, crear una en `/panel/mcps`; no rotar `Default`, porque invalidaría
   las conexiones que aún la utilizan. Revisar además activación y revocación.
5. Reiniciar las sesiones de Claude Code y Codex que tenían el catálogo anterior.
   El prefijo **Input constraint** lo añade el cliente al reescribir `anyOf` o
   `oneOf` de raíz a texto en la descripción; si sólo aparece en un catálogo
   almacenado por el cliente, no demuestra deriva del servidor.

La incidencia reportada de «Gestor de Contenido» con HTTP 405 desde claude.ai el
2026-10-09 se registra en la [auditoría](audits/2026-10-09-mcp-schema-parity.md).
Su posible relación con activación o token rotado necesita diagnóstico aparte;
la paridad local no confirma conectividad del cliente ni esa hipótesis.

## Caso crítico: editar un documento en borrador

1. Invocar `list_documents` y luego `read_document` con el ID elegido.
2. Exigir `editable=true`, guardar `etag` y leer `edit_blockers`. Un documento
   archivado o un artefacto generado no se fuerza: responde `NOT_EDITABLE`.
   El contrato vigente (`is_contract_mirror=true`, blocker `contract_mirror`)
   tampoco: `read_document` devuelve el borrador completo en vivo, y
   `update_document`, `append_document` y `delete_document` responden
   `NOT_EDITABLE`. El contrato sólo cambia por migración de su plantilla.
3. Editar con el nombre canónico `markdown` y el ETag leído:

```json
{
  "document_id": 40,
  "markdown": "# Borrador actualizado\n\nContenido revisado.",
  "if_match": "<etag-de-read_document>"
}
```

4. Volver a leer y comprobar `markdown`, `content_markdown`, `content_json` y
   un ETag nuevo. `content_markdown` se acepta como alias de compatibilidad,
   pero no puede enviarse con un valor distinto a `markdown`.
5. Repetir la edición con el ETag anterior: debe fallar con `STALE_VERSION` sin
   sobrescribir el cambio vigente.

Esta operación es una escritura reversible y no requiere confirmación. Borrar,
disolver o reemplazar evidencia sí conserva el flujo preview + confirm.

## Barrido de paridad por área

Ejecutar `mcp_schema_report` sin `--slug` para abarcar los 18 conectores,
incluidos los cinco de compatibilidad; después repetir con `--remote` tras el
deploy. Debe terminar con código 0, sin diferencias de nombres, campos públicos,
identidad, versiones o instrucciones. La paridad no significa que los backlogs
de contratos explícitos y descripciones estén vacíos.

Para cada conector, ejecutar `describe_capabilities` con una credencial
sin alcance y con otra limitada. La primera debe coincidir con `tools/list`; la
segunda sólo muestra herramientas autorizadas más `describe_capabilities`,
`confirm_action` y `cancel_action`.

| Área | Lectura mínima | Mutación mínima | Acción sensible a previsualizar |
|---|---|---|---|
| Operaciones | dashboard global | no aplica | no aplica |
| Comercial | cliente/propuesta/diagnóstico | actualizar una entidad reversible | envío o eliminación disponible en el catálogo |
| Proyectos | detalle e historial | actualizar datos o transición reversible | eliminación disponible en el catálogo |
| Documentos | leer Markdown y ETag | actualizar borrador con `if_match` | eliminar/disolver |
| Comunicaciones | hilo, cuerpo y adjuntos | actualizar borrador/default/template | enviar, reenviar o eliminar |
| Contenido | abrir blog/portafolio/QR/Linktree | editar borrador o metadata | publicar/eliminar |
| Tareas | detalle, comentarios y alertas | crear/editar/reordenar | eliminar |
| Libro contable | dashboard, previsión de cobro y movimientos | crear/editar movimiento o semáforo | liquidar/eliminar/export sensible cuando aplique |
| Cobros | cuenta, hosting y ciclos | actualizar configuración o registro | emitir/reintentar/eliminar |
| Tarjetas | extracto y transacciones | resolver alias o editar snapshot | finalizar/reabrir/eliminar |

La eliminación forzada de Proyectos es exclusiva del Panel con sesión de
superusuario: exige `DELETE`, una selección explícita `delete_keys` (vacía
significa conservar todos los registros relacionados) y una vista previa vigente
obtenida con esa misma selección. Los adaptadores MCP
conservan la eliminación confirmada de proyectos vacíos; enviar `force` por
`query` o `data` no habilita el borrado de dependencias.

La propiedad `retention_context` de los registros y el modelo
`ProjectRetentionContext` son internos del panel y están excluidos expresamente
del contrato de escritura MCP. El cliente conserva los datos no elegidos sin
un proyecto operativo y puede consultarlos desde su ficha. No se permite
editar una conversación conservada mediante las acciones habituales del panel
ni mediante MCP. Un callback de un pago ya iniciado conserva el resultado
real y su historial, pero no renueva hosting ni crea nuevos avisos o cargos.

### Proyectos: auditoría de datos conservados (2026-10-07)

1. Invocar `list_project_retention_contexts` sin argumentos. Cada resultado es un
   proyecto eliminado con su cliente (`profile_id` y `user_id`), quién lo eliminó
   y, por categoría, `at_deletion` (índice capturado al eliminar), `remaining`
   (filas que siguen conservadas, con sus `ids`) y `unlisted` (conservadas pero
   fuera del índice). `tracked: false` indica categorías sin vínculo directo al
   proyecto: siguen a su registro padre y no tienen conteo propio.
2. Repetir con `client_profile_id` plano de un cliente con datos conservados y
   comprobar que sólo aparecen sus contextos; `proposals` lista las propuestas
   cuyo entregable o fase comercial quedó conservado.
3. Con `integrity: true` plano, `integrity` debe venir vacío; una fila conservada
   que volvió a tener proyecto aparece como `retained_with_project`.
4. `get_proposal_approval` de una propuesta con entregable conservado responde
   sin error, con `linked_project.retained = true` y
   `project_reassignment_required = true`; `review_proposal_approval` (salvo
   `action=defer`) responde `RETAINED_PROJECT` antes de crear una confirmación.
5. Un `PermissionDenied` de un servicio llamado por una herramienta nativa
   responde `FORBIDDEN`; un fallo inesperado responde `INTERNAL_ERROR` y el log
   técnico guarda sólo el tipo de excepción y los frames `archivo:línea:función`,
   nunca su mensaje.

### Proyectos: traslado auditado de datos conservados

1. `list_project_unlinked_records` de un proyecto vigente del mismo cliente marca
   cada registro conservado con `retained` (contexto y proyecto eliminado) y
   `duplicates`, y suma los hilos de comunicación conservados en `threads`.
2. `assign_project_unlinked_records` con esos ids (y `thread_ids`, `reason`)
   exige la confirmación habitual. Al confirmar, la respuesta trae `adoptions`
   (una operación por proyecto eliminado); los registros quedan en el proyecto,
   editables, y desaparecen de «Datos sin proyecto» del cliente. Los ingresos
   viajan con sus hijos líquidos y sus cuentas.
3. `preview_retained_operation_undo` de esa operación no muestra bloqueos;
   `undo_retained_operation` (con `expected_impact_hash`, `reason` y `request_id`)
   pide confirmación y devuelve los registros a solo consulta. Si alguno se editó
   después del traslado, la vista previa informa `changed_since` y no se deshace.
4. `preview_retained_container_cleanup` lista hilos y carpetas conservados con sus
   `holders`; `delete_empty_retained_containers` (misma selección) sólo elimina
   contenedores vacíos, hijos antes que padres, y nunca un contenedor con datos.
5. `preview_proposal_project_reassignment` de una propuesta con entregable
   conservado no informa `no_source_project`: `source_project.retained = true` y
   la vista previa lista fases y entregables con sus ids. Si el destino tiene
   hosting activo y la fase ya alcanzó su fecha, aparece `pending_hosting_start`
   hasta enviar `hosting_start_date` futura o `accept_hosting_start`.
   `reassign_proposal_project` mueve esos ids y deja una operación
   `proposal_reassignment` en la auditoría.
6. Escribir directamente un dato conservado (`move_documents`, `update_thread`,
   `update_income`) sigue respondiendo que sólo admite consulta, y el mensaje
   indica usar «Asignar registros sin proyecto».

Los adaptadores resuelven la misma ruta DRF del Panel mediante
`APIRequestFactory`, autentican el principal técnico y dejan que la vista,
serializer y servicio existentes decidan permisos, validación y transacción.
No se implementa un segundo CRUD con escrituras ORM paralelas.

### Proyectos: integridad de datos (2026-10-09)

1. `describe_integrity_rules` devuelve `catalog_version` y cada regla con
   dominio, gravedad, `fix_kinds` y `fixable_kinds` (las correcciones que el
   motor sabe aplicar).
2. `list_integrity_findings` con `query.scope_kind=client` y
   `query.scope_query` de un nombre ambiguo devuelve `scope_candidates` y ningún
   hallazgo; con un `scope_id` devuelve hallazgos con `fingerprint`, `inputs`,
   `suggestion` y, si aplica, `tool`. Repetir la búsqueda devuelve los mismos
   fingerprints, también en `scope_kind=all`.
3. `preview_integrity_fixes` con un hallazgo que exige una decisión y sin
   `params` informa `input_required`; con los `params` correctos no tiene
   bloqueos y devuelve `impact_hash`. No escribe nada.
4. `apply_integrity_fixes` con un `expected_impact_hash` viejo responde
   `STALE_VERSION`; con un lote bloqueado, `CONFLICT` con los bloqueos; con el
   hash vigente pide confirmación y no escribe hasta `confirm_action`. Repetir la
   confirmación devuelve el mismo resultado sin aplicar dos veces.
5. Tras confirmar, el hallazgo desaparece de `list_integrity_findings` y
   `list_integrity_operations` muestra la operación con `source=mcp:projects` y
   el actor técnico del conector.
6. Editar a mano uno de los registros corregidos y pedir
   `preview_integrity_operation_undo`: informa `changed_since`. Sin esa edición,
   `undo_integrity_operation` (con `expected_impact_hash`, `reason` y
   `request_id`) pide confirmación, restaura los valores anteriores y una
   segunda vista previa informa `already_reverted`.
7. Un hallazgo `report_only` o `existing_tool` nunca se aplica por el motor: la
   vista previa lo bloquea y, en el segundo caso, nombra la herramienta que lo
   corrige con su propia vista previa.

### Libro contable: previsión manual de cobro

1. Invocar `get_receivables` sin argumentos. Debe listar únicamente ingresos
   esperados abiertos de la contabilidad de empresa, sin limitarse al año del
   dashboard, y devolver `summary.by_confidence` para verde (`high`), naranja
   (`medium`), rojo (`low`) y seleccionados sin clasificar.
2. Elegir un resultado abierto e invocar `update_income` con
   `collection_confidence: "high"`. Verificar que la respuesta conserva el
   valor anterior de `is_receivable_candidate` —no lo activa—, que sólo el nivel
   aparece como cambio en el historial y que se genera el aviso habitual.
3. Invocar `update_income` de forma explícita con
   `is_receivable_candidate: true` y volver a consultar `get_receivables`:
   `summary.high_total` debe sumar el `total_amount` original del registro, no
   sólo su saldo restante. Luego se puede retirar de la selección con
   `is_receivable_candidate: false`; el color se conserva como contexto
   histórico.
4. Casos negativos: intentar seleccionar un ingreso personal, líquido,
   perdido o completamente pagado debe fallar sin modificarlo. Al liquidar por
   completo un candidato, debe salir automáticamente de la selección activa.

### Libro contable: ingresos esperados

Disponible en `accounting` 1.3.0 (el «Gestor Contable» de claude.ai) y
`accounting-ledger` 2.3.0. Ambos publican `list_expected_incomes`,
`get_expected_income`, `update_expected_income`, `create_expected_income` y
`duplicate_expected_income`. Crear y duplicar siempre requieren vista previa
y `confirm_action`; actualizar sólo la requiere si cambia dinero, IVA, reparto,
contabilidad, cliente o proyecto. Un cambio descriptivo aislado se aplica
directamente. Los argumentos están en la raíz; no usar `amount`, `kind` ni
claves internas de confirmación en estas cinco herramientas.

Reproducir el caso #172 en test/staging con las fixtures de
`test_mcp_expected_income_flow.py`: cliente G&M #54, proyecto #8, ingreso esperado
de empresa por 760000, reparto 380000/380000, origen sin clasificar, IVA sin
registrar y cobro en noviembre de 2026, sin pagos, deducciones ni cuenta emitida.
Los IDs ilustran esa fixture; no ejecutar este guion sobre un registro real sin
autorizar su cambio.

1. `list_expected_incomes` con `{"client_id": 54, "q": "G&M", "origin": ["none"]}`
   debe encontrar #172 sin inferir el origen a partir del concepto. Comprobar
   importes, fecha de cobro, paginación y bloqueos.
2. `get_expected_income` con `{"income_id": 172}` devuelve ingreso, pagos,
   deducciones, cuenta, `editability` y `etag`. Guardar la huella de 64 caracteres
   para `if_match`; incluye pagos/deducciones/cuentas aunque `updated_at` del
   ingreso no haya cambiado.
3. Invocar `update_expected_income` con el siguiente payload y el ETag leído:

```json
{
  "income_id": 172,
  "if_match": "<etag-de-get_expected_income>",
  "concept": "G&M (Hosting: Semestral) – Semestre 1",
  "total_amount": "4200000",
  "gustavo_amount": "2100000",
  "carlos_amount": "2100000",
  "company_amount": "0",
  "period_date": "2026-11-01",
  "period_start": "2026-10-01",
  "period_end": "2027-03-31",
  "period_cadence": "semiannual",
  "origin": "hosting",
  "notes": "Propuesta Fase IA 2027 §11 (doc #84). Reajuste por renovación: % aumento SMMLV + 8%."
}
```

4. Exigir `confirmation_required=true`; revisar antes/después, reparto, IVA,
   avisos y efectos secundarios en `impact`. El ingreso sigue por 760000 y aún
   no hay cambio contable. Llamar `confirm_action` con su `confirmation_id` y
   verificar por `get_expected_income` y Panel: total 4200000, ventana de
   octubre a marzo, cobro en noviembre, cliente/proyecto conservados, historial
   y aviso contable habitual. Repetir la confirmación no duplica la escritura.
5. Invocar `duplicate_expected_income` con
   `{"income_id": 172, "overrides": {"concept": "G&M (Hosting: Semestral) – Semestre 2", "total_amount": "4200000", "collection_confidence": "medium"}}`.
   Revisar la nueva ventana 2027-04-01 a 2027-09-30 y cobro 2027-05-01:
   `period_rule.rule=kept_payment_offset`. Confirmar y leer el nuevo ID.
   Es otro esperado; no copia pagos, deducciones ni cuenta de cobro.
6. Comprobar también `create_expected_income` con concepto, origen, `vat_rate`
   explícito (`null` conserva IVA sin registrar), total o base y fecha de cobro:
   no crea fila antes de confirmar. Un cambio sólo de notas debe ser directo;
   un cambio idéntico no escribe historial ni envía aviso.

Sin reparto explícito se usa `split_half` del Panel. Al cambiar el total se
recalcula un reparto automático; uno personalizado se conserva con aviso. La
empresa recibe el residual y una contabilidad personal pertenece al 100 % a su
dueño. Base, IVA y total deben coincidir exactamente.

| Caso negativo | Resultado que comprobar |
| --- | --- |
| Cambiar finanzas, cliente o proyecto con pagos, deducciones, liquidación completa o cuenta emitida/pagada | `INCOME_LOCKED`, con campos y bloqueos; los datos conservados bloquean además toda edición. |
| `if_match` viejo, o pago/cuenta/cambio después de la vista previa | `STALE_VERSION`; releer y preparar otra vista previa, sin sobrescribir. |
| Reparto explícito que no suma el total | `VALIDATION_ERROR`, `details.reason=split_mismatch`. |
| Base/IVA incompatibles con tasa y total | `VALIDATION_ERROR`, `details.reason=vat_mismatch`, con cálculo esperado. |
| Clave desconocida en raíz o `overrides`, como `amount` | `unknown_field`, con ruta del campo; no crear intent ni escribir. |
| Leer/editar/duplicar un líquido, perdido u otro kind con estas tools | `NOT_EXPECTED_INCOME`; usar la herramienta del dominio correspondiente. |

**Mes de cobro propio en hosting.** `period_start` / `period_end` delimitan el
servicio y `period_date` ordena cobros, filtros y avisos. Una fecha explícita
prevalece sobre la ventana. Al crear sin ella toma el inicio; al editar sin ella
sigue un inicio movido sólo si ya coincidían en el registro guardado. Una fecha
independiente y la de un hosting histórico sobreviven al completar o cambiar su
ventana. Duplicar conserva el desfase de cobro. Comprobar en el formulario
«Mes de cobro esperado» y su opción de día exacto; al editarlo deja de seguir
automáticamente el inicio. Inicio, fin y periodicidad se auditan en
`TRACKED_FIELDS`, además de la fecha de cobro.

### Libro contable: confirmación de pago al liquidar (2026-10-09)

1. Elegir un ingreso esperado con cliente y cuenta de cobro emitida e invocar
   `get_income_payment_confirmation` con su `record_id`. Debe responder
   `can_send: true` y como `recipient` el correo de la cuenta emitida; sin
   cliente, sin cuenta o con un correo provisional responde `can_send: false`
   y el motivo en `blocked_reason`.
2. En `accounting-ledger`, invocar `settle_income` con
   `send_payment_confirmation: true`. La vista previa debe incluir
   `impact.payment_confirmation` con destinatario, número de cuenta, asunto,
   texto del correo y `pending_after`; nada se escribe ni se envía todavía.
3. Confirmar con `confirm_action`. El resultado informa
   `payment_confirmation.status = "scheduled"`: el correo sale después del
   commit y queda en el historial de correos con la clave
   `income_payment_received_client` y los targets del ingreso, el pago y la
   cuenta. Un fallo de envío deja una fila `failed` reintentable desde el
   Historial contable.
4. En el conector de compatibilidad `accounting`, el mismo flag responde
   `ToolError` antes de registrar nada: ese conector no tiene vista previa y un
   correo al cliente nunca sale sin una. Sin el flag (valor por defecto),
   `settle_income` se comporta como antes en ambos conectores.

### Comercial: visibilidad de los videos explicativos

1. Invocar `get_explainer_video_settings`: sin configuración previa devuelve
   `show_additional_modules_video` y `show_financing_video` en `true`.
2. Invocar `update_explainer_video_settings` con
   `{"show_additional_modules_video": false}`. La respuesta refleja el cambio,
   `GET /api/additional-modules/public/` pasa a `show_explainer_video: false`
   y el panel agenda el rebuild de la página pre-generada; repetir el mismo
   valor no agenda otro rebuild.
3. Crear un enlace con `create_additional_module_share` incluyendo
   `show_explainer_video: false` y luego invocar
   `update_additional_module_share` con su `share_uuid` y
   `{"show_explainer_video": true}`: la respuesta de administración refleja el
   valor, y el payload público del enlace sólo lo muestra si el interruptor del
   catálogo también está encendido. Idioma y selección siguen inmutables.
4. Casos negativos: `update_additional_module_share` sin el campo responde 400
   y no modifica el enlace; un valor no booleano en
   `update_explainer_video_settings` responde 400.

## Comunicaciones: guion por herramienta

Usar dos clientes, un proyecto de cada cliente, un documento markdown de cada
cliente y un superusuario. Conservar los IDs que devuelve cada paso.

`list_threads` y el endpoint del panel comparten
`communication_query_service.py`. Los argumentos escalares del conector se
normalizan como una selección de un valor y conservan su contrato; el REST puede
enviar valores repetidos o separados por coma para la selección múltiple del
panel. En ambos caminos, canal, dirección, estado del mensaje y fechas deben
coincidir en un mismo mensaje, no en mensajes distintos del mismo hilo. El
argumento `q` busca por título del hilo, cliente, nombre de proyecto, asunto o
contenido del mensaje en ambos caminos.

`CommunicationPanelPreference` queda excluido deliberadamente del conector:
sus campos personalizan la interfaz de una cuenta y no forman parte del registro
conversacional que MCP consulta o modifica.

### 1. `list_threads`

Lectura exitosa:

```json
{
  "client_id": 10,
  "project_id": 20,
  "status": "open",
  "channel": "email",
  "direction": "outgoing",
  "message_status": "draft",
  "reply_status": "unanswered",
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "q": "Portal Boreal",
  "order": "recent",
  "scope": "active",
  "page": 1,
  "page_size": 20
}
```

Verificar `results`, `count`, `page` y `num_pages`; cada fila debe incluir
cliente/proyecto, actividad, conteos y preview vigente. `reply_status` acepta
`answered` o `unanswered` y evalúa mensajes salientes enviados no anulados
mediante su relación explícita de respuesta. Repetir por separado con
`client_id`, con `project_id` y con `q` igual a una parte del nombre del proyecto
para probar los cortes estructurados y la búsqueda legible.

Errores: filtros, `order` o `scope` fuera de catálogo, fecha no ISO, página cero
e IDs no enteros deben producir `isError=true`. Una página
posterior al final puede normalizarse a la última página, como `Paginator`.

### 2. `get_thread`

```json
{"thread_id": 30}
```

Verificar mensajes cronológicos completos, estados, `reply_to`, documentos y
correcciones de fecha. Un ID inexistente, vacío, cero o no entero debe fallar sin
crear ni modificar registros.

### 3. `create_thread`

```json
{"client_id": 10, "project_id": 20, "title": "Aprobación de entrega"}
```

Verificar que nace `open`, vacío y atribuido al actor MCP. Casos de error:
cliente omitido/inexistente, título vacío, perfil no cliente y proyecto de otro
cliente. Ningún rechazo puede dejar un hilo parcial.

### 4. `update_thread`

```json
{"thread_id": 30, "title": "Aprobación final", "project_id": null}
```

Verificar que corrige sólo los campos enviados, conserva cliente e historial y
permite asociar o desasociar un proyecto del mismo cliente. Deben fallar: hilo
cerrado, proyecto ajeno, título vacío, ausencia de campos editables y cualquier
campo no declarado. Ningún rechazo puede producir una actualización parcial.

### 5–6. `close_thread` / `reopen_thread`

```json
{"thread_id": 30}
```

`close_thread` debe registrar estado, fecha y actor. Mientras el hilo está
cerrado, crear mensajes, editar su cabecera o confirmar un borrador enviado debe
fallar. `reopen_thread` revierte esa condición sin tocar archivo ni historial.
Cerrar uno ya cerrado o reabrir uno abierto debe ser un error explícito.

### 7–8. `archive_thread` / `unarchive_thread`

```json
{"thread_id": 30}
```

Archivar retira el hilo del `scope=active`, lo incorpora a `archived` y lo
mantiene en `all`; restaurar hace el movimiento inverso sin alterar `status`.
Una comunicación madre de proyecto o cliente no se puede archivar. Repetir la
misma transición debe fallar sin modificar fechas ni actor.

### 9. `create_message`

Saliente de correo con referencia documental:

```json
{
  "thread_id": 30,
  "channel": "email",
  "direction": "outgoing",
  "subject": "Acta de entrega",
  "content": "Adjunto el acta para aprobación.",
  "occurred_at": "2026-09-02T15:00:00Z",
  "document_ids": [40]
}
```

Debe quedar como `draft`: crear no equivale a enviar. Un mensaje entrante de
WhatsApp queda `received`, sin asunto. `reply_to_id` sólo acepta un mensaje
previo del mismo hilo y dirección opuesta. Deben fallar: hilo cerrado, email sin
asunto, WhatsApp con asunto, contenido vacío, documento de otro cliente,
documento inexistente, respuesta de otro hilo o de igual dirección. Cada fallo
debe dejar iguales los conteos de mensajes y referencias.

### 10. `update_message`

```json
{
  "message_id": 50,
  "subject": "Acta de entrega corregida",
  "content": "Texto corregido.",
  "document_ids": [40],
  "reply_to_id": null
}
```

Verificar que se conserva ID, hilo, canal y dirección, se reemplazan —no se
acumulan— documentos y queda una revisión append-only con el diff suministrado.
Sólo un borrador saliente activo es editable. Mensajes enviados, recibidos,
fallidos o anulados, documentos ajenos y respuestas de otro hilo deben fallar
sin cambiar el registro.

### 11. `delete_draft`

```json
{"message_id": 50}
```

Verificar eliminación física del borrador y retorno de `deleted`, `id` y
`thread_id`. Sólo aplica a borradores salientes activos; la evidencia enviada,
recibida, fallida o anulada debe preservarse y producir `isError=true`.

### 12. `mark_message_sent`

```json
{"message_id": 50, "occurred_at": "2026-09-02T15:05:00Z"}
```

Verificar transición `draft → sent`, fecha efectiva y actor. Repetir sin
`occurred_at` para conservar la fecha registrada. Deben fallar un mensaje
entrante, uno ya enviado, uno anulado, un hilo cerrado, un ID inexistente y una
fecha no ISO. Confirmar que no se creó `EmailLog` ni se invocó ningún proveedor:
la herramienta sólo registra el envío realizado por fuera.

### 13. `void_message`

```json
{"message_id": 51, "reason": "Registro duplicado"}
```

Verificar que el mensaje histórico permanece visible con fecha, motivo y actor
de anulación. Sólo se anulan mensajes enviados, recibidos o fallidos; un
borrador, una segunda anulación o un motivo vacío deben rechazarse.

### 14. `correct_message_date`

```json
{
  "message_id": 51,
  "occurred_at": "2026-09-01T18:30:00Z",
  "reason": "Corrección contra evidencia externa"
}
```

Verificar la nueva fecha y una corrección append-only con valor anterior, valor
nuevo, motivo y actor. Sólo aplica a mensajes históricos no anulados; borradores,
fecha idéntica, formato inválido o motivo vacío deben fallar sin crear auditoría.

## Comunicaciones: enlaces seguros de un solo uso

Las herramientas de `communications` reutilizan los servicios del panel.
Crear y actualizar reciben secretos, los cifran y no persisten sus argumentos
en intents. Sólo la consulta explícita devuelve contenido tras permiso y
confirmación; listas y detalle siguen siendo metadatos. La URL sólo se devuelve
al crear. Los logs extraen exclusivamente IDs enteros permitidos de este módulo.

| Herramienta | Riesgo | Verificación |
|---|---|---|
| `list_secure_link_types` | read | tipos, incluido Personalizado, y campos obligatorios |
| `create_secure_link` | write | contenido obligatorio y URL sólo al crear |
| `list_secure_links` / `get_secure_link` | read | estado e historial; nunca URL ni contenido |
| `mark_secure_link_sent` | write | marca manual de envío, fecha y actor; no envía correo ni consume/revela el enlace; repetición idempotente |
| `update_secure_link` | write | ID y cambios; fields reemplaza; omitir conserva; editar no reactiva |
| `delete_secure_link` | sensitive | preview y confirmación; desaparecen enlace y eventos |
| `reveal_secure_link_content` | sensitive | habilitación explícita en allowed_tools; preview sin secreto; entrega efímera al confirmar |
| `revoke_secure_link` | write | el enlace queda desactivado |
| `reactivate_secure_link` | sensitive | confirmación; mismo enlace y nueva vigencia; resultado sin URL |

En MCPs → Credenciales → alcance personalizado, seleccionar explícitamente
`reveal_secure_link_content`. Una credencial con alcance general no la descubre
ni ejecuta. Verificar también describe_capabilities, llamada directa y
confirm_action después de retirar el permiso.

Para lectura/eliminación/reactivación: comprobar confirmación ajena, vencida,
cancelada o registro cambiado; no debe ejecutar. Repetir una lectura confirmada
devuelve sólo comprobante, nunca el contenido ni otra auditoría de lectura.
No inspeccionar secretos reales: usar valores ficticios y comprobar ausencia
en McpActionIntent (arguments/impact/result), McpRequestLog y mensajes de error.
Las respuestas deben incluir Cache-Control: no-store.

Los metadatos agregan `lifecycle_status` (`ready/sent/opened/expired/revoked`),
`sent_at` y `sent_by`. `list_secure_links` permite filtrar por `lifecycle_status`;
`status` conserva sus valores anteriores. Marcar un recibido, vencido, abierto
o revocado debe responder `invalid_send_state` sin eventos ni cambios. Reactivar
limpia la marca de envío actual y conserva su historial.

Comprobar tipo inexistente, campo obligatorio vacío, campo desconocido, título
vacío/largo, proyecto de otro cliente, secreto inválido en una solicitud de
confirmación y vigencia fuera de 1/3/7/30. Un error no debe guardar parcialmente.

## Documentos: eliminación recuperable de observaciones

Usar un documento markdown con dos observaciones, una pendiente enlazada a un
episodio **Solucionar bug** con `origin=note` y otra resuelta o descartada. Las
herramientas reutilizan el mismo servicio transaccional que el panel.

### 1. `delete_document_notes`

```json
{"document_id": 40, "note_ids": [70, 71]}
```

Verificar que una sola llamada elimina lógicamente toda la selección, devuelve
`deleted_note_ids` y no deja resultados parciales. Las observaciones salen de
`read_document`, de la lista activa y de los conteos. Si la selección contenía
la última pendiente de un episodio originado por observaciones, ese episodio se
cierra como `removed`; un estado manual nunca se cierra por esta regla.

Deben fallar sin modificar nada: selección vacía, IDs repetidos, observación de
otro documento, ID inexistente y observación ya eliminada. Se puede eliminar
una observación pendiente, resuelta o descartada; una copia enviada antes por
correo o mensaje permanece fuera del sistema.

### 2. `list_deleted_document_notes`

```json
{"document_id": 40}
```

Verificar que sólo devuelve la papelera recuperable con contenido, estado,
`deleted_at` y actor. La lectura normal del documento debe seguir ocultando esas
filas. El historial técnico de eliminación es distinto: registra actor y fecha,
pero no crea una copia del título o contenido.

### 3. `restore_document_note`

```json
{"document_id": 40, "note_id": 70}
```

Verificar que la observación vuelve al alcance activo. Si era pendiente y su
eliminación había cerrado el episodio enlazado, la restauración reabre o
reutiliza **Solucionar bug** y vuelve a enlazarla. Una incompatibilidad de
estados o un estado retirado debe revertir toda la operación y conservar la
observación en la papelera. Restaurar una fila activa o de otro documento debe
fallar de forma explícita.

## Documentos: hilos entre documentos

Usar tres documentos markdown activos en carpetas distintas —el punto del hilo
es que la historia cruza carpetas, clientes y proyectos— y un cuarto que ya
pertenezca a otro hilo. Las herramientas reutilizan `document_thread_service`,
el mismo servicio transaccional que el modal del panel.

### 1. `create_document_thread`

```json
{"title": "Etapa 2 · Conteo Diario",
 "items": [{"document_id": 138, "occurred_on": "2026-08-16"},
           {"document_id": 146, "occurred_on": "2026-08-24"}]}
```

Verificar que el hilo nace con los documentos ordenados **por fecha**, no por el
orden en que se enviaron, y que `occurred_on` omitido cae en `issue_date` o en
el día Bogotá de `created_at`. Sin `title`, el nombre es el del primer documento.

Deben fallar sin crear nada: un solo documento, un documento repetido, uno que
ya pertenece a otro hilo (el mensaje nombra el hilo dueño), una cuenta de cobro,
un documento archivado y una fecha que no sea `YYYY-MM-DD`.

### 2. `get_document_thread` y `list_document_threads`

```json
{"document_id": 146}
```

Verificar que un documento suelto responde `thread: null` —no un error— y que
`thread_id` abre el mismo hilo. En el listado, comprobar `document_count`,
`first_occurred_on`, `last_occurred_on`, `latest_item` y que `search` encuentra
el hilo tanto por su nombre como por el título de cualquiera de sus documentos.

### 3. `update_document_thread`

```json
{"thread_id": 4, "link": [{"document_id": 162, "occurred_on": "2026-08-27"}]}
```

**La verificación que importa**: los miembros no mencionados siguen ahí. Un
`link` agrega o re-fecha; `unlink_document_ids` retira sin borrar el documento.
La operación que dejaría el hilo con menos de dos documentos debe rechazarse y
el hilo quedar intacto — ésa es la diferencia con el PATCH del panel, que ahí sí
disuelve. Renombrar y mover miembros en la misma llamada es atómico: si el
nombre falla, la membresía tampoco cambia.

### 4. `dissolve_document_thread`

```json
{"thread_id": 4}
```

Verificar que los documentos sobreviven y quedan disponibles para otro hilo, que
la respuesta trae el hilo completo previo y `released_document_ids`, y que un
documento antes enlazado ya se puede eliminar (el `PROTECT` lo bloqueaba).

## Revalidación de conectores existentes

| Conector | Lectura que debe comprobarse | Escritura/acción que debe comprobarse | Error representativo |
|---|---|---|---|
| Blog | `get_blog_post` devuelve JSON bilingüe, fuentes, SEO, portada y LinkedIn | crear/editar conserva esos campos | post inexistente o payload incompleto |
| Documents | resumen/detalle y filtros muestran cliente, proyecto, estados, tags y sólo observaciones activas | crear/editar mantiene asociaciones; eliminar/restaurar observaciones reconcilia estados y papelera en una transacción | proyecto ajeno, archivado, selección de observaciones mezclada o restauración incompatible |
| Clients | métricas incluyen documentos, ingresos, hostings y comunicaciones | CRUD usa `proposal_client_service` | un hilo impide tratar/eliminar el cliente como huérfano |
| Communications | hilo completo incluye ciclo de vida, mensajes, documentos, correcciones y revisiones; listado separa activos/archivados | cabecera y ciclo del hilo más crear/editar/eliminar borrador, confirmar envío, anular y corregir fecha convergen en `communication_service` sin enviar por el canal | transición repetida, comunicación madre, mensaje no editable, proyecto/documento ajeno o respuesta de otro hilo |
| Tasks | detalle, comentarios y alertas reflejan el modelo actual | CRUD, archivo, orden y duplicación | comentario/alerta de otra tarea |
| Accounting | detalle incluye pagos, deducciones, cuenta de cobro, período de hosting y ciclo de vida de recurrentes | `settle_income`/`bulk_settle_incomes` crean pagos (`settle_income` con `send_payment_confirmation` avisa al cliente tras `confirm_action`); las seis tools de recurrentes preparan duplicado, cambian estado, archivan/restauran, silencian avisos y aplican lote por el mismo servicio del panel | no esperado, repetido, excedido, ID perdido o intento de activar/silenciar un recurrente archivado |
| Diagnostics | detalle expone slug, expiración y cliente | update permite esos campos y usa el serializer actual | slug duplicado o cliente inválido |
| Proposals | detalle/template exponen metadata comercial completa, incluido `email_intro` | importación persiste el mensaje personalizado; reenvío permite editarlo; `update_proposal` con `technicalDocument` exige que cada ítem funcional quede referenciado en algún `linked_item_ids` | JSON incompleto, mensaje vacío al enviar/reenviar, transición inválida o detalle técnico sin trazar (`technical_item_coverage_incomplete`) |
| LinkedIn | estado de token/post y errores de publicación | borrador, programación, edición, borrado y publicación de texto | token ausente/expirado o post no publicable |

## Verificación automatizada

Desde `backend/` del worktree, con el virtualenv disponible y
`projectapp.settings_test` (fijado por `pytest.ini`), nunca con la suite completa.
Ejecutar **con migraciones**, sin `--nomigrations`: las migraciones de datos
siembran las filas de `McpConnector`; las fixtures deben recuperarlas con
`get_or_create`, no recrearlas a ciegas. Cada comando respeta el máximo de 20
tests; iniciar otro ciclo después de tres comandos.

Para el registro y las 18 huellas, un ciclo de tres lotes:

```bash
../.venv/bin/pytest content/tests/services/test_mcp_connector_registry.py -v --no-cov -k 'explicit_semver'
../.venv/bin/pytest content/tests/services/test_mcp_connector_registry.py -v --no-cov -k 'fingerprint_matches_versioned_lock'
../.venv/bin/pytest content/tests/services/test_mcp_connector_registry.py -v --no-cov -k 'not explicit_semver and not fingerprint_matches_versioned_lock'
```

`test_mcp_registry_parity.py` recorre los 18 por HTTP: catálogo completo,
credencial limitada, versiones de handshakes/metadata y correspondencia entre
instrucciones y confirmación. Ejecutar las primeras tres selecciones en un ciclo
y las últimas dos en el siguiente (16, 8, 16, 16 y 16 casos):

En la última selección, `[content]` identifica el parámetro del conector;
`content` sin corchetes coincide también con la carpeta y selecciona todo el archivo.

```bash
../.venv/bin/pytest content/tests/views/test_mcp_registry_parity.py -v --no-cov -k 'accounting'
../.venv/bin/pytest content/tests/views/test_mcp_registry_parity.py -v --no-cov -k 'documents or proposals'
../.venv/bin/pytest content/tests/views/test_mcp_registry_parity.py -v --no-cov -k 'blog or clients or diagnostics or linkedin'
../.venv/bin/pytest content/tests/views/test_mcp_registry_parity.py -v --no-cov -k 'operations or partnership or additional or projects'
../.venv/bin/pytest content/tests/views/test_mcp_registry_parity.py -v --no-cov -k 'commercial or communications or [content] or tasks'
```

Agregar las regresiones focales según el contrato afectado, siempre en
selecciones de hasta 20 casos; no ejecutar enteros los archivos parametrizados
que superan ese límite:

- `content/tests/services/test_mcp_schema_policy.py`: objetos cerrados, tipos,
  descripciones, metadatos privados y backlogs sin crecimiento ni excepciones
  obsoletas; filtrar por prueba y, cuando corresponda, por slug.
- `content/tests/views/test_mcp_deprecated_envelopes.py`: sobres y aliases
  existentes, argumentos publicados planos y rechazo de claves anidadas.
- `content/tests/management/test_mcp_schema_report.py`: informe local, modo remoto
  simulado sin secretos y rechazo de huellas cambiadas sin incremento de versión.
- `content/tests/services/test_accounting_expected_income_service.py`,
  `content/tests/views/test_mcp_expected_income_flow.py` y
  `content/tests/views/test_mcp_expected_income_guards.py`: reparto, IVA, ETag,
  preview/confirmación, duplicación, bloqueos y campos desconocidos.
- `content/tests/views/test_income_period_fields.py`,
  `content/tests/views/test_income_duplicate_draft.py` y
  `content/tests/views/test_settlement_hosting_period.py`: fecha de cobro
  independiente, desfase en duplicados y auditoría de ventanas de hosting.

Los siguientes comandos conservan la regresión de plataforma operativa:

```bash
/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_operational_platform.py -q \
  -k 'default_token or panel_ or bearer_ or rotating_ or revoked_ or tools_list_exposes or sensitive_call'

/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_operational_platform.py -q \
  -k 'confirm_action or confirmation_cannot or signed_upload or temporary_output or operations_connector or tool_audit or modern_ or scoped_discovery'

/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_contracts.py -q -k 'all_registered or every_panel'
```

En el ciclo siguiente, ejecutar el resto de `test_mcp_contracts.py` en lotes,
`test_mcp_protocol.py`, las regresiones focales de Documentos, Comunicaciones,
Tareas y Contabilidad y los servicios afectados. No agrupar archivos si la
selección supera 20 casos.

Para cambios en observaciones de Documentos, agregar el archivo focal sin
superar 20 tests por ejecución:

```bash
/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_documents.py::TestDocumentsMcpToolList \
  content/tests/views/test_mcp_documents.py::TestDocumentsMcpWorkflow -q
```

Luego ejecutar una regresión mínima de los handlers compartidos modificados y:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py check
DJANGO_SETTINGS_MODULE=projectapp.settings_test ../.venv/bin/python manage.py makemigrations --check --dry-run
python3 scripts/test_quality_gate.py --repo-root . \
  --report-path test-results/test-quality-audit-report.json
```

No ejecutar `manage.py migrate` desde un worktree: su `.env` enlazado apunta a
producción. La migración `content.0240_mcp_operational_platform` se valida con
el grafo y se aplica únicamente durante deploy. Crea credenciales, intents,
uploads y trazas ampliadas; copia cada token histórico a la credencial
`Default`, preserva la URL actual y siembra los conectores canónicos inactivos.
Su reverse es deliberadamente no destructivo.

Para la UI, ejecutar el unit test del store y el único spec E2E del flujo:

```bash
npm --prefix frontend test -- test/stores/mcps.test.js
E2E_PORT=3001 E2E_WORKERS=1 npm --prefix frontend run e2e -- \
  e2e/admin/admin-mcps.spec.js
```

## Contrato anti-deriva

Todo cambio futuro de modelo/serializer/servicio en un módulo expuesto debe, en
la misma entrega:

1. Revisar `MCP_MODEL_CONTRACTS` y clasificar cada campo agregado o cambiado.
2. Comparar handlers con la vista, serializer y servicio vigentes del panel.
3. Actualizar descripción, schema, filtros y payload real de cada tool afectada.
4. Agregar una prueba observable de éxito y otra de error cuando cambie una
   regla; actualizar este guion si cambia la operación manual.
5. Ejecutar los archivos MCP anteriores y la regresión compartida mínima.
6. Si cambia el contrato público, incrementar `ConnectorSpec.version`, escribir
   su changelog, ejecutar `mcp_schema_report --write-fingerprints` y revisar el
   diff de `connector_contracts.json`; después ejecutar el informe sin flags de
   escritura y la prueba de huellas.

`test_mcp_contracts.py` falla ante campos sin clasificar, nombres duplicados,
descripciones demasiado vagas o schemas que dejan de ser objetos. Esa falla es
una solicitud de revisión: nunca se resuelve ocultando el campo sin explicar por
qué queda fuera del MCP.

`test_mcp_connector_registry.py` comprueba identidad, límites contables y el
lock versionado. `test_mcp_registry_parity.py` comprueba por HTTP ambos
descubrimientos y sus instrucciones. `test_mcp_schema_policy.py` conserva la
política estricta y sus tres backlogs; `test_mcp_deprecated_envelopes.py`
comprueba compatibilidad y rechazo anidado; `test_mcp_schema_report.py`
comprueba informe local/remoto y el incremento obligatorio de versión. Las
pruebas del servicio y de flujo/guardas de ingresos esperados sostienen las
reglas contables; la paridad de esquemas por sí sola no demuestra esas reglas.

## Criterio de cierre

- Los 18 conectores de `CONNECTORS` aparecen en el inventario: 13 canónicos y
  5 de compatibilidad. `mcp_schema_report` termina con código 0; lista y
  capacidades coinciden, y versiones e instrucciones proceden del registro.
  Las huellas y los backlogs siguen verificados por sus pruebas.
- Comunicaciones expone 50 herramientas, incluidos preview, envío confirmado, enlaces seguros,
  adjuntos, templates y entregabilidad; sus rechazos dejan la base consistente.
- Los MCP existentes devuelven y aceptan los campos descritos en su contrato;
  Documentos 4.0.0 expone 73 herramientas y conserva edición Markdown con ETag,
  papelera, observaciones, hilos, uploads y artefactos; añade migración/adopción
  confirmada, recibo y deshacer con las postcondiciones de la parte 2.
- Proyectos 3.0.0 expone 171 herramientas; el cambio de cliente previsualiza las
  mismas guardas que ejecuta y el ciclo de hosting exige impacto vigente y
  confirmación, conservando los pagos y su historia.
- Los contratos convertidos de Documentos/Proyectos son planos, cerrados,
  tipados y descritos; no publican ni aceptan `data`/`query`. Los backlogs de
  explicitud, alias y deriva quedan vacíos, con techo cero, salvo las exclusiones
  documentadas de PR #503. La sonda de desconocidos prueba cero callbacks y
  cero escrituras; la paridad de previews tiene pareja o motivo explícito.
- Las operaciones que requieren confirmación usan intent ligado a credencial,
  confirman una sola vez y dejan evidencia. Las instrucciones describen también
  ejecución directa de compatibilidad y cambios descriptivos de ingresos
  esperados; toda credencial respeta alcance, expiración y revocación.
- No se alteraron tokens, prefijos, estados activos ni `last_used_at` de
  conectores existentes durante la migración; los nuevos quedan inactivos.
- Tests focales, regresión, Django check, migraciones sin drift y quality gate
  quedan verdes y anotados; el flujo `/panel/mcps` cubre inventario, riesgo,
  creación, edición, rotación, revocación, error y gate de superusuario.

## Ejecución de referencia — 2026-08-26

| Verificación | Resultado |
|---|---|
| Communications MCP | 15/15 tests verdes |
| Contrato de nueve conectores | 19/19 tests verdes |
| Paridad de módulos existentes | 17/17 tests verdes |
| Regresión compartida Propuestas/Contable + catálogos | 31/31 tests verdes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate de los tres archivos MCP nuevos | 91/100, 0 errores, 0 warnings |

El gate global local puntuó 97/100, pero no pudo ejecutar sus dos puentes AST de
frontend porque este worktree backend-only no instala `frontend/node_modules`
(`@babel/parser` ausente). No fue un hallazgo de los cambios MCP; el workflow de
CI, que instala las dependencias frontend, conserva la validación global final.

## Ejecución focal — 2026-08-31

| Verificación | Resultado |
|---|---|
| Edición MCP de borradores | 19/19 tests verdes |
| Servicio y auditoría de revisiones | 14/14 tests verdes |
| Regresión `tools/list` / creación / envío | 3/3 tests verdes |
| Contratos MCP | 20/20 tests verdes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate focal | 0 errores; warnings históricos no bloqueantes |

## Ejecución focal — 2026-09-02

| Verificación | Resultado |
|---|---|
| Acciones administrativas MCP | 20/20 tests verdes |
| Edición MCP de borradores | 19/19 tests verdes |
| Catálogo, creación, consulta y envío confirmado | 19/19 tests verdes |
| Contratos de campos y metadata (dos lotes) | 23/23 tests verdes |
| Paridad transversal de conectores | 17/17 tests verdes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate focal | 93/100, 0 errores, 0 junk; 1 warning de infraestructura (`ruff` ausente) |

El cambio es backend/MCP y no altera modelos, relaciones, reglas de fake data ni
un flujo humano del frontend; por eso no requiere refresh de datos ni cambios en
USER_FLOW_MAP/E2E. El CI, que instala su toolchain de lint, conserva la última
validación del warning local.

## Ejecución focal — 2026-09-02 (plataforma operativa)

| Verificación | Resultado |
|---|---|
| Fundamento de credenciales, confirmación, uploads, actor y auditoría | 25 casos verdes |
| Protocolo MCP moderno + compatibilidad heredada | 14/14 tests verdes |
| Resolución de rutas y métodos de adaptadores | 12/12 tests verdes |
| Edición documental y validación de contenido binario | 3 regresiones nuevas verdes |
| Store de administración MCP | 8/8 tests verdes |
| Flujo `/panel/mcps` | 10/10 E2E verdes en servidor local aislado |
| Build Nuxt | aprobado; warnings preexistentes no bloqueantes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate del lote QA | 0 errores; `ruff` ausente como warning ambiental conocido |

El mapa global quedó en 304 flows cubiertos, 34 parciales, 0 faltantes y 33
exentos; `admin-mcps` cubre `display`, `success`, `error` y `failure`. El único
`junk-only`, `platform-hosting-subscription`, es un draft preexistente ajeno a
esta entrega y requiere validación live antes de retirar su marcador. El
Arquitecto, el Verificador y el Auditor aprobaron el corpus MCP; el Auditor no
dejó candidatos `DELETE`, `MERGE` ni `REWRITE`.

La migración conserva tokens, prefijos, activación y `last_used_at` de los
conectores existentes. Los conectores canónicos nuevos nacen inactivos. La
rotación de las credenciales compartidas entregadas al inicio se realiza sólo
después de merge, migración y verificación del corte; nunca dentro de esta
corrida de desarrollo.

## Ejecución focal — 2026-09-05 (detalle seguro de proyectos)

| Verificación | Resultado |
|---|---|
| Contrato de campos del conector Proyectos | 1/1 verde |
| Modelos `ProjectAdminAccess` / `ProjectAccessNote` | todos los campos excluidos con motivo explícito |
| URLs y campos legacy de acceso en `Project` | excluidos del contrato MCP con motivo explícito |
| Rotación o uso de credenciales MCP | no ejecutado; fuera del alcance de la entrega |

La superficie humana nueva usa APIs staff/JWT dedicadas y no añade tools MCP.

## Ejecución focal — 2026-09-14 (videos explicativos y Programa de Alianza)

| Verificación | Resultado |
|---|---|
| Contrato de campos del conector Comercial (`ExplainerVideoSettings`, `show_explainer_video` del enlace) | verde |
| Adaptadores `get/update_explainer_video_settings` y `update_additional_module_share` resuelven a vistas con el método declarado | verde |
| Descripciones de `get_financing_program` / `render_financing_program_pdf` | nombran el Programa de Alianza; comparten las ocho condiciones, incluida la exclusividad conceptual de Project App. sólo a cinco años. Los nombres de las tools no cambian |
| Invocación en vivo contra producción | no ejecutada; fuera del alcance de la entrega |

El conector Comercial pasa de 132 a 135 herramientas. La descripción del
conector sembrada en BD por la migración 0240 se conserva sin migración de
datos.

## Revisión de formalización — 2026-09-19

`ProposalFormalization` y `ProposalFormalizationFile` clasifican todos sus
campos como excluidos del MCP: son preparaciones privadas de 24 horas,
revisadas y enviadas por el administrador que las creó desde Documentos.
El conector Comercial conserva sus herramientas actuales; no expone el HTML,
destinatarios, rutas privadas ni el envío de estas preparaciones. La regresión
focal verifica los contratos de campos de `proposals` y `commercial` y sus
adaptadores, sin invocar conectores contra producción.

## Agregados de proyectos anidados — 2026-09-22

`get_client` y `retrieve-proposal-client` reutilizan `ProjectListSerializer`
con instancias sin las anotaciones privadas de los listados de Plataforma.
Los getters conservan sus fallbacks: propuesta de la primera fase (o vínculo
legacy por entregable), bugs abiertos, cambios pendientes, inversión total y
próximo pago del hosting activo. La ausencia de propuesta o suscripción sigue
siendo `null`; los conteos vacíos permanecen en cero.

La optimización no añade campos de modelo, herramientas ni cambios de schema
MCP; las clasificaciones de `content/mcp/contracts.py` permanecen vigentes.
La regresión focal lee un proyecto real anidado por ambos consumidores y
comprueba valores concretos, además de los contratos y las operaciones MCP de
crear, actualizar y consultar un cliente inexistente. Se ejecuta sólo con
`projectapp.settings_test`, sin conectores ni datos del servicio en producción.

### Linktrees — marca personalizada (2026-09-21)

`create_linktree` y `update_linktree` aceptan `background_color`, `accent_color`,
`text_color`, `muted_color`, `button_text_color` (hexadecimal de seis dígitos) y
`font_family` (nombre de Google Fonts, sin URL ni CSS). Los serializers compartidos
validan los datos del panel y MCP. `upload_linktree_logo` usa `asset_id` para un
JPG/PNG/WebP real de hasta 5 MB; `remove_linktree_logo` lo elimina. El logo es
independiente del avatar. Comprobar lectura pública tras actualizar y rechazo de
color/CSS inválidos o archivo falso; no modificar tarjetas reales al validar.

### Linktrees asociados a proyectos

`create_linktree`/`update_linktree` aceptan `data.project` (ID de Project) o null.
Verificar lectura de la relación, desvinculación y rechazo de IDs inexistentes.
Las mismas reglas corren en el serializer del panel. `ProjectBrandAsset` queda
excluido explícitamente del conector: documentos privados disponibles sólo en
el panel, sin URLs públicas ni descargas vía MCP. Prueba focal:
`content/tests/views/test_mcp_linktree_branding.py::test_mcp_links_and_unlinks_project`.

### Linktrees — plantillas HTML Nivel 2 (2026-09-23)

Las plantillas HTML se administran desde el panel con sesión y CSRF. Ninguna
actualización genérica de Linktree (`update_linktree`) puede cargar, validar ni
activar HTML: `Linktree.active_template_version` es de sólo lectura y cambia
únicamente con las herramientas de Nivel 3 descritas a continuación.

El contrato de branding existente sigue disponible. La página pública sólo
anuncia `template_url` cuando la versión pertenece al perfil, fue publicada y
tiene validación válida. Al cambiar datos de una tarjeta con plantilla hay que
validar una nueva instantánea y publicarla (panel o MCP).

Comprobaciones focalizadas: contrato de clasificación de campos en
`content/tests/views/test_mcp_contracts.py` y aislamiento/publicación en
`content/tests/views/test_linktree_template_views.py`. Operación y despliegue:
[Plantillas HTML de Linktree](LINKTREE_HTML_TEMPLATES.md).

### Linktrees — plantillas HTML Nivel 3 por MCP (2026-09-23)

El conector `content` expone en `backend/content/mcp/linktree_template_tools.py`
el ciclo completo de una plantilla, reutilizando el lector de paquetes, la
creación de instantáneas, la validación en Chromium (Huey) y la guarda de
publicación del panel. Una conversación nunca salta la validación ni activa una
instantánea sin `status=valid` y perfil vigente.

| Herramienta | Riesgo | Qué hace |
| --- | --- | --- |
| `get_linktree_template_contract` | read | Contrato de autoría (archivos, manifest, variables Mustache, enlaces, acciones, iconos, reglas HTML/CSS, ejemplo). Con `linktree_id` devuelve las variables reales de la tarjeta: nombre, rol, bio, iniciales, foto/logo disponibles, enlaces con etiqueta/URL/icono/tipo, botones sin destino, acciones disponibles, contacto, colores y fuente. `icon_query` busca nombres Lucide. |
| `list_linktree_templates` | read | Biblioteca (propias + compartidas por cliente) y versiones con estado, errores, capturas y versión activa. |
| `get_linktree_template` | read | Fuente del paquete (manifest, html, css, avisos, metadatos de imágenes) para iterar un diseño. |
| `get_linktree_template_version` | read | Estado `pending/valid/invalid`, reporte completo, overrides, `profile_current` y `next_step`. |
| `upload_linktree_template` | write | `files[]` con `path` y `content` (texto; manifest.json admite objeto), `base64` o `asset_id`. Crea la plantilla y una candidata `pending`. |
| `validate_linktree_template` | write | Nueva candidata con datos actuales desde `template_id` o restaurando `version_id`. |
| `preview_linktree_template` | read | Documento HTML de vista previa (firmado por una hora) y capturas 320/375/430 como artefactos temporales descargables. |
| `override_linktree_template_asset` | write | Reemplaza (`asset_id`/`base64`) o restablece (`reset`) una imagen de `editable_assets`; crea candidata nueva. |
| `publish_linktree_template` | sensitive | Publica una versión válida; responde con `confirmation_id` y se ejecuta con `confirm_action`. |
| `reset_linktree_template` | write | Vuelve al tema básico conservando el historial. |
| `share_linktree_template` | write | Comparte una plantilla propia con el cliente del proyecto vinculado. |
| `get_linktree_template_clicks` | read | Clics agregados por enlace y día de una versión publicada (sin IPs ni visitantes). |
| `list_linktree_assets` | read | Biblioteca de imágenes propia del Linktree: clave, alt, URL, dimensiones y marcado de uso. |
| `upload_linktree_asset` | write | Sube o reemplaza una imagen por clave (`base64` + `filename` o `asset_id`) y devuelve la URL para usarla en el HTML/CSS. |
| `delete_linktree_asset` | sensitive | Elimina una imagen de la biblioteca tras `confirm_action`; las versiones publicadas conservan su copia. |

Biblioteca de imágenes (`content.LinktreeAsset`): las plantillas pueden pegar la URL
devuelta (`src="…"`, `url(…)`) o usar `data-asset="clave"`/`asset(clave)`; al subir
el paquete la URL se normaliza a la clave y `manifest.library_assets` (administrado
por el servidor) registra las claves usadas. Cada candidata copia la imagen vigente
de la biblioteca; una clave faltante bloquea la candidata con
`missing_library_asset` y una clave repetida entre paquete y biblioteca se rechaza
con `library_key_clash`. Los archivos se conservan mientras alguna versión los
referencie. El tema básico (colores y fuente del editor) sigue existiendo para las
tarjetas sin plantilla publicada; el contrato lo indica como no aplicable al HTML.

Reglas verificadas: una sola validación en curso por tarjeta (código
`validation_pending`); paquetes rechazados informan archivo, línea y código sin
dejar plantilla ni versión; `template_id` ajeno responde `NOT_FOUND`;
`confirm_action` sobre una versión `invalid` responde `not_validated`; los
`asset_id` consumidos quedan marcados como usados. Contratos: `LinktreeTemplate`
y `LinktreeTemplateVersion` pasan a lectura (más `is_shared` escribible) y
`assets`/`profile_digest` siguen excluidos con motivo.

Prueba focal: `content/tests/views/test_mcp_linktree_templates.py` (17 casos,
Chromium sustituido por `queue_validation` neutralizado),
`content/tests/views/test_mcp_linktree_assets.py`,
`content/tests/services/test_linktree_asset_library.py`,
`content/tests/views/test_linktree_asset_views.py` más
`test_mcp_contracts.py`, `test_mcp_linktree_branding.py` y
`test_mcp_parity_refresh.py`. En producción la validación real corre en Huey; el
worker debe tener Chromium instalado (ver guía de plantillas).


### Documentos de propuestas — copia Markdown

`ProposalDocument`, su `content_markdown` y su indicador `is_archived` quedan
excluidos del CRUD genérico MCP. Los contratos activos y las instantáneas se
consultan por sus operaciones de propuestas; el archivo y la restauración son
responsabilidad del servicio compartido, sin escrituras directas sobre la
evidencia retenida. Revisar el contrato de campos al añadir campos a este modelo.

### Modalidad de cierre e instantáneas — 2026-10-06

`BusinessProposal.contract_modality` se clasifica como lectura/escritura en el
conector de propuestas. Se escribe sólo mediante la operación
`update_proposal_contract_modality`, que comparte el servicio transaccional del
panel:
- permite cambiar `single`/`split` en cualquier estado;
- fuera de negociación exige nota y vista previa, seguida de `confirm_action`
  o `cancel_action`; el intento pertenece al actor y rechaza datos obsoletos;
- acepta `proposal_id`, `contract_modality`, `change_note` y los tres parámetros
  opcionales de servicio: plazo inicial, preaviso de renovación y de terminación;
  exige valores enviados o ya guardados, sin tomar preselecciones globales;
- conserva literalmente el Markdown y PDF personalizado al moverlo entre
  contrato único y producto; genera las variantes de plantilla vigentes;
- guarda una instantánea permanente antes de cambiar y registra autor, fecha,
  modalidades y nota; los documentos anteriores se archivan sin eliminarse;
- la respuesta informa variantes activas, fuente `default`/`custom` y la
  correspondencia con documentos históricos o firmados, sin envío automático.

`list_proposal_contract_snapshots` pagina el historial de esta propuesta;
`read_proposal_contract_snapshot` devuelve la evidencia anterior y su Markdown.
`restore_proposal_contract_snapshot` exige nota y confirmación, recupera la
instantánea revisada y conserva primero una instantánea del estado actual.
Los tres modelos internos de instantáneas/archivos/intentos quedan excluidos
del CRUD genérico para preservar su inmutabilidad y confirmaciones propias.

`update_proposal_contract` acepta `variant` (`combined`, `product`, `service`).
Las operaciones de render reenvían `variant` como parámetro de consulta: en
cierre separado exigen `product` o `service` (`variant_required`) y rechazan la
variante de la otra modalidad (`inactive_variant`).

Slice focal:
- `test_mcp_contracts.py -k "proposals or commercial or operations"`;
- `test_mcp_proposal_contract_modality.py`;
- `test_proposal_contract_modality_views.py`;
- `test_proposal_contract_change_intents.py`;
- `test_proposal_contract_snapshots.py`.

La aceptación real de la propuesta 118 requiere desplegar la migración 0281 e
indicar los tres plazos del servicio. Procedimiento completo:
[Modalidad contractual en cualquier estado](proposal-contract-modality.md).

### Carpetas de Comunicaciones

Validar `list_folders`, `create_folder`, `update_folder`, `delete_folder` con un perfil de cliente y proyecto opcional. Rechazar ciclos, cambio de contexto y eliminación con hilos archivados. `create_thread`/`update_thread` reciben `folder_id`; null retira la ubicación, una comunicación madre lo rechaza. `list_threads` admite `folder=<id>|none`; con `q`, busca todas las carpetas del contexto. Una actualización exclusivamente organizativa funciona con hilo cerrado. Los contratos incluyen `CommunicationFolder` y `CommunicationThread.folder`; los servicios son los mismos del panel.


### Regresión de enlaces seguros: personalizado y disponibilidad

`list_secure_link_types` incluye `custom` con `custom_name` y `content`
obligatorios. `create_secure_link` acepta esos campos sin cliente ni proyecto;
los listados y `get_secure_link` conservan sólo metadatos, nunca el nombre
personalizado ni contenido cifrado. Un nombre vacío falla sin crear registros.
Si el cifrado no está disponible, el mismo servicio usado por el panel retorna
un error amigable al conector, sin registrar secretos. No cambian campos de
modelos ni su clasificación en `content/mcp/contracts.py`.

## Video de bienvenida de propuestas

`BusinessProposal.show_explainer_video` es booleano editable en creación y
actualización, también por JSON/MCP. La duplicación conserva la preferencia.
`ExplainerVideoSettings.show_proposal_video` es el control general editable por
las herramientas genéricas del modelo. Ambos nacen activos. La respuesta admin
conserva la preferencia; la pública calcula la visibilidad efectiva con ambos
controles, idioma español y las cuatro opciones disponibles. Verificar PATCH
válido, rechazo de valor no booleano y conservación de la preferencia al apagar
el control general; no ejecutar envíos ni migraciones reales.


## Documentos 3.0.0 — organización y respuestas compactas

Contrato y cambios incompatibles: [changelog](changelog/2026-09-28-documents-mcp-3.md).
Validar en entorno de pruebas, con documentos descartables:

1. `describe_capabilities` con `tools: ["update_folder", "move_documents"]` y
   `summary: true`; repetir sin summary y comprobar el esquema concreto.
2. Mover carpeta con `parent_id` plano; probar alias de campo `parent`, campo
   desconocido, ciclo, raíz administrada y destino protegido. Un rechazo no
   renombra nada.
3. Crear dos carpetas del mismo nombre/padre (también si la primera está
   archivada): la segunda responde error con IDs coincidentes. El mutex vuelve
   a validar al guardar; no se intenta sanear duplicados históricos.
4. Mover el contrato espejo sólo con `folder_id`; un payload con título o texto
   se rechaza completo. Consultar contrato/PDF y verificar la misma fuente viva.
5. Ejecutar cada escritura con un documento grande: sin `include_content` sólo
   metadatos; con `true`, una clave `markdown`. Leerlo después por su ID.
6. `move_documents` con un ID inexistente o protegido: resultados por ID y cero
   cambios. Repetir con dos IDs válidos y comprobar ambos destinos.
7. Verificar filtros por padre/nombre, conteos archivados y autoría en carpetas.
8. Renombrar/mover la carpeta configurada para estimates; el resolver por ID debe
   seguir guardando allí. Configuración ausente falla sin crear carpetas.

Regresiones focales: `test_document_folder_organization.py`,
`test_document_folder_races.py`, `test_document_organization_api.py`,
`test_document_moves.py` y `test_create_estimate_document.py`, más respuestas y
permisos MCP. Ejecutar desde worktree y en lotes de hasta 20 tests.


## Documentos 3.0.1 — errores, paridad y origen

1. En datos de test, crear una carpeta y probar campo desconocido y ciclo.
   Comprobar `error.code`, `error.message`, `details.errors` y su presencia en
   `content[0].text`, igual a `structuredContent`.
2. Mover un ID válido junto a uno inexistente. Debe responder un resultado por ID
   (`aborted`/`failed`) con códigos y mensajes, sin guardar movimientos.
3. Comparar el mapa nombre→inputSchema de `tools/list` contra
   nombre→input_schema de capacidades; repetir con credencial restringida.
   El conector documents debe anunciar 3.0.1 también en initialize/discover.
4. Crear desde Panel, MCP y procesos automáticos: origen y operación presentes,
   usuario cuando corresponde; una sincronización no cambia la procedencia.
5. Para Littigio seguir el [runbook de reparación](runbooks/littigio-folder-repair.md).
   No repetir ensayos mutantes contra documentos reales como prueba del conector.

## Platform — revisión contractual de entregas

El conector `projects` cubre la administración de contratos, otrosíes, alcances,
fases de ejecución, etapas y guías de validación desde el primer incremento.
La [matriz de paridad](PLATFORM_DELIVERY_MCP_MATRIX.md) relaciona cada acción de
Platform con su herramienta y regla de negocio compartida. El catálogo añade
52 herramientas de entrega y habilita los uploads temporales del conector.

Validar solo en un worktree con `projectapp.settings_test`, en lotes de hasta
20 casos. No invocar estas pruebas contra un conector activo de producción.

1. Consultar opciones/esquemas y espacio; crear/leer/editar cada entidad; rechazar
   un otrosí cuyo contrato pertenece a otro proyecto. Las fases de ejecución
   nunca deben facturar ni alterar el hosting comercial.
2. Previsualizar JSON sin escribir; aplicar mediante `confirm_action`; rechazar
   campos de estado, fuentes ajenas o un espacio cambiado desde la vista previa.
3. Publicar una etapa solo con firma real/constatada y guía completa. Repetir su
   confirmación sin generar otra ronda. Editar pendientes sin alterar conformidades.
4. Constatar firma usando `begin_upload` → `upload_asset_chunk` → `complete_upload`
   y `asset_id`; comprobar PDF real hasta 10 MB y rechazo de assets de otra credencial.
5. Registrar aprobación externa con comunicación entrante recibida y cita válida,
   o documento, revisor original, fecha, canal y referencia explícitos. Guardar
   por separado actor administrativo y revisor original; jamás inferir una
   aprobación desde un mensaje saliente del equipo.
6. Responder con requerimientos y documentos opcionales; consultar/asociar/retirar
   documentos por nivel; descargar PDF autorizado como artefacto temporal. Los
   borradores del cliente permanecen ocultos en lista, detalle y PDF.
7. Restringir la credencial a lectura: ni herramientas directas ni confirmaciones
   previas pueden ejecutar escrituras fuera de su permiso.
8. Descargar el respaldo congelado de una revisión mediante
   `download_delivery_document_pdf` con `review_id` y `evidence_id`; alternativamente
   usar `link_id` para un documento asociado. Los dos orígenes son excluyentes.
   Editar la fuente después de registrar la conformidad no debe cambiar los
   bytes, título ni hash de su respaldo. Un proyecto ajeno falla sin crear artefactos.
9. Consultar `get_delivery_authoring_contract`: devuelve opciones y esquemas,
   sin textos ni contrato seleccionado. Crear guías con
   `create_delivery_guide_prompt`, eligiendo contrato, otrosíes, referencias y
   anexos. No debe incluir contratos hermanos, notas privadas ni fuentes no
   elegidas. La asociación de un anexo no prueba su incorporación jurídica.
10. Reintentar la captura con el mismo `request_id`: conserva un solo contexto
    y no incrementa la versión del espacio. Consultar historial/reabrir mediante
    `list_delivery_prompt_contexts`/`get_delivery_prompt_context` y descargar
    `download_delivery_prompt_source`; el archivo conserva sus bytes y MIME
    originales después de editar el origen. Contextos ajenos deben fallar.
11. Importar guías v2 con contexto y citas verificadas; rechazar citas vacías o
    inexistentes y retirar la procedencia de un requerimiento trazado. V1 manual
    no debe sobrescribir una guía v2; estados y firmas siguen fuera del JSON.
    El fundamento requiere citar contrato/otrosí; un anexo puede complementar
    la evidencia, pero no constituir por sí solo el fundamento contractual.
12. Preparar `create_delivery_reply_prompt` desde una etapa publicada y validar
    `preview_delivery_reply`. No crea mensajes. Fuentes faltantes/parciales o
    incertidumbre exigen alcance indeterminado. Compartir con `add_delivery_message`
    exige `human_reviewed: true`, contexto, citas y clasificaciones; una nueva
    observación pública desde la captura obliga a preparar otro contexto.
13. Intentar eliminar en el panel una referencia o anexo seleccionado de
    `Document`/`ProposalDocument`: respuesta 409 `document_used_in_delivery`,
    mensaje de conservación y original intacto. Un PDF de propuesta no retenido
    mantiene su eliminación normal. La clasificación de fake data excluye las
    capturas/fuentes de la generación automática; se crean solo por selección
    administrativa explícita.
14. Preparar `prepare_delivery_stage_closure_email` sólo con una etapa publicada
    completamente aprobada. Consultar destinatario, asunto, cuerpo y adjuntos
    mediante `get_delivery_stage_closure_email`, sin transporte. Una etapa
    parcial, un cliente ajeno o una credencial distinta deben fallar.
    El cuerpo en texto y HTML debe incluir conversaciones y decisiones públicas,
    autores, fechas, versiones y rondas, también sin adjuntos. Verificar la objeción
    previa y el mensaje de cierre; las notas internas y fuentes privadas no salen.
15. Enviar `send_delivery_stage_closure_email` con confirmación sensible,
    versión vigente, hash de la preparación y revisión humana. Comprobar que
    intento y snapshot persisten antes de SMTP y que repetir la confirmación o
    petición conserva un solo envío. Un fallo posterior a SMTP debe conservar
    resultado desconocido sin reenvío automático.
16. Consultar `list_delivery_stage_closure_emails` y descargar los bytes exactos
    mediante `download_delivery_stage_closure_email_attachment`. Recargar las
    filas desde la base no debe cambiar su almacenamiento privado ni crear una
    URL pública. `prepare_delivery_stage_closure_email_resend` conserva cuerpo,
    archivos y relación con el original; sólo prepara otra vista revisable.

Pruebas focalizadas: `content/tests/views/test_mcp_delivery.py` (19 casos),
`content/tests/views/test_mcp_delivery_contracts.py` (20 casos),
`content/tests/views/test_mcp_delivery_guards.py` (9 casos), más cuatro
verificaciones específicas de `projects` en `test_mcp_contracts.py`.
La autoría seleccionada se cubre en
`content/tests/views/test_mcp_delivery_authoring.py` (20 casos).
El correo de cierre se cubre en
`content/tests/views/test_mcp_delivery_closure_email.py` (17 casos).
La revisión de modelos incluye todos los campos nuevos, con exclusiones
explícitas de almacenamiento privado, captura de IP/navegador de la firma y
recibos internos de idempotencia, huella de captura, instantánea interna de origen
y rutas privadas de fuentes. Contexto y fuente son inmutables. La metadata conserva método y hashes de firma;
la evidencia de aprobación conserva el mensaje original y su procedencia.

Resultados focales ejecutados en el worktree de implementación:

| Lote | Resultado | Evidencia del comportamiento |
| --- | --- | --- |
| `test_mcp_delivery.py` | **19/19 verdes**; repetido con `--nomigrations` tras congelar todos los campos contractuales firmados | Creación real de seis entidades, guías, importación, confirmaciones, publicación, PDF externo, respuestas y errores. |
| `test_mcp_delivery_contracts.py` | **20/20 verdes**, con migraciones reales hasta `0065` | Lecturas por entidad, propiedad de documentos/assets, credencial limitada, descargas, replay y procedencia entrante. |
| Regresión de `test_mcp_delivery_contracts.py` tras autoría seleccionada | **20/20 verdes**, con `--nomigrations` tras `0067` | Discovery de opciones sin textos ni selección automática, compatibilidad documental y confirmaciones existentes. |
| `test_mcp_delivery_guards.py` | **3/3 verdes**, con `--nomigrations` | Firma privada, contrato firmado inmutable antes de publicar y rechazo de una constancia externa que declara método Portal. |
| Nuevas descargas de respaldo en `test_mcp_delivery_guards.py` | **6/6 verdes**, con `--nomigrations` tras `0066` | PDF histórico exacto después de reescribir la fuente, pertenencia al proyecto y cuatro selectores incompletos/ambiguos rechazados. |
| Contratos existentes de `projects` | **4/4 verdes**, con `--nomigrations`; repetidos tras `0067` | Todos los campos clasificados, incluidas capturas y procedencia; metadata accionable, confirmación sensible y adaptadores HTTP coherentes. |
| `test_mcp_delivery_authoring.py` | **20/20 verdes**, con `--nomigrations` tras `0067` | Fuentes elegidas, contextos retenidos/idempotentes, descarga exacta PDF/JSON, citas, faltantes/lectura parcial, importación v2 y respuesta manual revisada. Calidad estricta **100/100**, sin errores, avisos ni sugerencias. |
| Integración de eliminación y clasificación | **11/11 verdes**, con migraciones reales hasta `0067` | Cinco casos de `test_delivery_source_deletion.py` conservan referencias/anexos originales y el borrado normal; seis regresiones comprueban catálogo fake, eliminaciones de propuesta/documento y protección de comunicaciones. Calidad estricta de los cinco casos nuevos **100/100**, sin hallazgos. |

Son **68 casos nuevos** y **4 verificaciones de contrato existentes**, en lotes
separados de hasta 20 casos. Se verificó el transporte real de uploads y las
confirmaciones MCP; no se ejecutaron suites completas ni pruebas mutantes contra
datos de producción.

Los once casos de integración se ejecutaron con migraciones reales para incluir
el catálogo Markdown que consumen los fixtures existentes. No se modificaron
esos fixtures. La clasificación registra `DeliveryPromptContext` y
`DeliveryPromptSource` como exentos de generación automática: las capturas solo
nacen de una selección administrativa explícita.

## Cuentas y hosting por proyecto — P2

Las operaciones nuevas de `projects` son `get_project_billing_options`,
`get_project_hosting`, `get_project_hosting_inventory`,
`get_collection_account_context`, `associate_collection_account_context`,
`preview_project_hosting_reconciliation`, `reconcile_project_hosting`,
`preview_hosting_evidence` y `reconcile_hosting_evidence`.

Validar en settings_test, por lotes de hasta 20 casos:

1. Leer una cuenta pendiente y sus opciones sin exponer notas, metadata, secretos
   o documentos contractuales. Un proyecto ajeno falla sin escritura.
2. Asociar exclusivamente contrato/otrosí del proyecto o su hosting con razón y
   versión; rechazar otrosí de otro contrato, doble naturaleza y cliente ajeno.
3. Previsualizar identidad/evidencias sin persistir. Confirmar con el principal
   real, y rechazar una versión que cambió después de la vista previa.
4. Consultar varios orígenes históricos sin sumarlos ni seleccionar uno por
   texto/importe. Elegir origen operativo y equivalencias expresamente; verificar
   que no se crearon `Payment`, `HostingCycle` ni movimientos contables.
5. Emitir desde ingreso con contexto, o desde hosting con pago existente cuando
   hay suscripción. La obligación ya emitida rechaza duplicación; dos obligaciones
   diferentes admiten dos cuentas. Conservar numeración, snapshot y bytes PDF al
   reclasificar una cuenta histórica.
6. Rechazar mover un otrosí con cuentas; permitir el cambio sin cuentas si lo
   permiten las guardas de delivery. `ProjectContract.project` sigue inmutable.

Pruebas dedicadas: `accounts/tests/billing/`, más las clasificaciones, metadata,
confirmaciones y adaptadores de `projects` y `accounting-billing` en
`content/tests/views/test_mcp_contracts.py`. Las herramientas sensibles mantienen
`financial_effect: none`; la emisión conserva el adaptador contable existente.
No ejecutar validaciones mutantes contra conectores activos de producción.
### Proyectos: eliminación de referencias vacías (2026-10-01)

- `preview_project_delete` devuelve la misma lista de dependencias y cantidades que el modal del panel.
- `delete_project` es sensible: su preview incluye `can_delete` y `blockers`, y no borra antes de `confirm_action`.
- Confirmar un proyecto vacío devuelve `deleted: true` y `project_id`; elimina la estructura automática vacía y conserva auditoría.
- Si se agrega información entre preview y confirmación, devuelve `PROJECT_DELETE_BLOCKED` con `details.blockers`, conservando proyecto y referencias.
- Casos focales: `content/tests/views/test_mcp_project_deletion.py`; el contrato de campos del conector `projects` no cambia.

### IVA contable (2026-10-01)

`create/update_income`, `create/update_expense` y `create/update_hosting`
aceptan `vat_rate` y captura `amount` + `amount_mode` (`before_vat` o
`vat_included`). No combinar captura con el importe financiero anterior
(`total_amount`, o `payment_per_cycle` en hosting). Los reads devuelven
`base_amount`, `vat_amount` y tasa junto al total incluido. Tasa nula indica
histórico sin registrar y cero indica Sin IVA. Panel y MCP comparten
serializers, restricciones de documentos emitidos y auditoría. Liquidaciones
heredan tasa; las retenciones mantienen el flujo de deducciones actual.


## Administración de propuestas y proyectos — 2026-10-07

Las operaciones nuevas usan los mismos serializers, permisos y servicios que
Panel. La credencial sigue limitada a su conector; no habilitan revelación de
secretos ni aceptan una entidad arbitraria al consultar historial.

| Conector | Operaciones incorporadas | Validación principal |
| --- | --- | --- |
| `proposals` y `commercial` | `list_proposal_activity` | Página 1–50, veinte por defecto; cursor firmado ligado a la propuesta |
| `proposals` y `commercial` | `preview_proposal_project_reassignment`, `reassign_proposal_project` | Mismo cliente, impacto vigente, motivo, petición idempotente y confirmación MCP |
| `proposals` y `commercial` | `list_proposal_history`, `get_proposal_history_version`, `compare_proposal_history`, `download_proposal_history_file` | Entidad fijada; archivos mediante asset temporal de la credencial, sin rutas privadas |
| `projects` | `get_project` | Cliente, estado y metadatos; sin credenciales |
| `projects` | `list_project_commercial_phases`, `add_project_commercial_phase`, `update_project_commercial_phase`, `remove_project_commercial_phase`, `reorder_project_commercial_phases` | Aprobación/vínculo previos; relaciones contractuales y hosting protegen la fase |
| `projects` | `get_project_brand`, `upload_project_brand_asset`, `download_project_brand_asset`, `delete_project_brand_asset` | Assets autorizados; eliminación confirmada |
| `projects` | `list_project_history`, `get_project_history_version`, `compare_project_history` | Historial del proyecto, con credenciales protegidas |
| `projects` y `accounting-billing` | `link_project_billing_contract` | Fuente del mismo proyecto/cliente, versión vigente, permiso contable y confirmación; no emite ni altera dinero |

`list_projects` admite `client_profile_id` plano para solicitar únicamente los
proyectos del cliente elegido. La ficha y la raíz documental existentes son la
fuente de la relación; el título de un contrato nunca asigna su proyecto.
Las operaciones documentales `update_document` y `move_documents` ya permiten
corregir cliente/proyecto y carpeta respectivamente. El movimiento es atómico;
no hace falta crear otra carpeta de Littigio.

Comprobar antes del rollout:

1. `tools/list` coincide con el registro local y no repite nombres; los esquemas
   rechazan campos desconocidos y mantienen los argumentos de las operaciones
   existentes. Comprobar también el agregado `commercial`.
2. La reasignación sensible sólo crea una intención al pedirla. Antes de
   `confirm_action`, las relaciones no cambian. El impacto muestra origen,
   destino, IDs y bloqueos; una huella obsoleta no se ejecuta.
3. Recursos con la misma clave en propuestas distintas conviven y sincronizar
   una propuesta no archiva los de la otra. Una procedencia ambigua queda sin
   atribuir y bloquea el traslado; no se adivina en la migración.
4. El historial no devuelve rutas de archivos ni valores sensibles, tampoco
   dentro de cambios/comparaciones. La descarga requiere el asset autorizado.
5. El registro del contrato muestra la fuente concreta y no crea cuenta de
   cobro, pago ni liquidación. Probar la reutilización del mismo vínculo.
6. Tras el deploy, aplicar el inventario y las verificaciones de
   `docs/runbooks/littigio-project-reassignment.md`; guardar recibos privados
   fuera de Git. Hasta entonces no declarar los datos reparados.


## Gestor de la plataforma — incremento 2026-10-07

`projects` conserva su identidad y se presenta como Gestor de la plataforma.
La ampliación de carpetas y hosting convive con integridad de datos y el registro
central; su versión de integración es 3.0.0. Consultar la matriz de entrega para
recursos, modelo de datos,
fuentes confirmadas y avisos. Los contratos de campos incluyen recursos y sus
relaciones, `ProposalApprovalFile` y eventos/intentos de aviso, con archivos,
HTML, snapshots e idempotencia interna excluidos de escritura conversacional.

Slices de transporte: `test_mcp_platform_resources.py` (19 casos),
`test_mcp_delivery_sources.py` (4) y `test_mcp_delivery_notifications.py` (7).
Ejecutarlos separados en un worktree con settings de test; máximo veinte casos
por lote. El incremento reutiliza los servicios de REST y el gateway de avisos,
sin datos ni credenciales reales. Las descargas deben comprobar bytes exactos,
propiedad y ausencia de rutas de almacenamiento en la respuesta. Los avisos
comprueban versión del evento, manifest, credencial, replay y rechazo de estado
incierto. La migración de medios históricos privados y el retiro de sus URLs
públicas se verifican aparte mediante deploy, nunca desde un worktree.

El slice de permisos se encuentra en
`accounts/tests/test_platform_resource_role_boundary.py` (12 casos): cliente
staff sigue siendo cliente para lecturas ajenas, archivados, categoría restringida
y escrituras. El principal técnico MCP sin UserProfile conserva su caso permitido.
# Recursos privados de Platform (S1, 2026-10-07)

Los cuatro FileFields de recursos usan storage privado para cargas futuras.
MCP conserva su descarga como asset temporal ligado a la credencial y su límite
de materialización de 25 MB; REST transmite el original con JWT, propietario/rol
de Platform y selección del hijo dentro del recurso. `file_url` es una ruta
relativa de API, nunca una URL de storage. La clasificación MCP de los campos
permanece igual: la referencia física no se expone.

La lectura histórica no reinterpreta `deliverables/...` como storage privado ni
recurre a media pública para un nombre privado ausente. Nginx y Django DEBUG
deniegan las URLs antiguas. QA debe incluir las cuatro familias y los datos
retenidos, junto con bytes originales, cliente ajeno, archivados y replay del
manifest. El guion y la condición de cierre tras deploy están en
`docs/PLATFORM_RESOURCE_MEDIA.md`.

> Integración de #503 y #504 (2026-10-10): las versiones vigentes de esta
> etapa son Documentos 3.3.0 / 73 herramientas y Proyectos 2.4.0 / 171.
> Los incrementos evitan reutilizar versiones del registro ya publicado en main.
> Los changelogs 3.2.0 / 2.2.0 conservan el alcance original de la migración.

> El cierre conjunto de #503, #504 y #506 publica Documentos 4.0.0 / 73
> herramientas y Proyectos 3.0.0 / 171, incluidas las de integridad de datos.
> El control de esquemas global y los contratos de los demás conectores se conservan.

> Las descripciones de los cuatro uploads compartidos se publican también
> en los demás conectores que admiten archivos. Sus versiones avanzan un parche
> (proposals 2.2.1; accounting-billing/cards, additional-modules, commercial,
> communications, content y partnership-program 2.1.1), sin cambiar argumentos
> ni ejecución. Las huellas se regeneran en vez de reutilizar una versión.

> Building with Us usa la carpeta contractual fijada por ID cuando existe,
> conservando el espejo tras renombrarla. Sin un pin compartido, la ubicación
> manual Contratos conserva sus bloqueos anteriores. Los recibos de migración
> conservan su actor histórico al fusionar clientes o deshacer esa fusión.

### Abonos sin cuenta emitida: crear, corregir y deshacer (2026-10-10)

Validar con una credencial autorizada de `accounting-ledger` (2.3.0) y el
conector compatible `accounting` (1.3.0), usando sólo datos de prueba:

1. Consultar `list_income` para elegir uno o varios esperados de empresa con
   saldo pendiente, sin cuenta o con borrador. Registrar `bulk_settle_incomes`
   con `allocations`, `total_amount`, `period_date` y `notes`; en el conector
   canónico confirmar la vista previa con `confirm_action`.
2. Comprobar un único movimiento en `get_pocket`, sus montos por ingreso y los
   estados `paid`/`partial`. El excedente sigue como saldo a favor del mismo
   cliente; clientes mezclados con excedente deben rechazarse.
3. Invocar `update_income_abono` con `record_id` del movimiento, importe, fecha,
   notas y todo el nuevo reparto. En el canónico confirmar la acción. El ID del
   movimiento debe conservarse y el reparto previo debe desaparecer. Un monto
   superior al saldo disponible debe rechazarse sin cambiar datos.
4. Invocar `delete_income_abono` con el mismo ID y confirmar cuando corresponda.
   Deben borrarse movimiento e imputaciones, con los esperados otra vez pendientes.
   Nunca eliminar por separado un hijo de un abono compartido.
5. Completar un esperado sin cuenta. Verificar el aviso interno «Ingreso completo —
   cuenta pendiente» en Historial, con cuerpo y vínculo al ingreso. Un fallo sólo
   se reintenta para su destinatario; corregir y volver a pagar no genera otro evento.
   Crear su cuenta por el importe completo debe dejarla pagada sin otra entrada.

`settle_income` conserva los ajustes individuales; `create_income`, `update_income`
y `delete_income` siguen sirviendo para pagos individuales no compartidos. Para
cambiar el monto de un abono compartido se usa la corrección del conjunto.

`requires_collection_account` es un dato de sólo lectura del ingreso, calculado
con su saldo y sus documentos. `IncomeCompletionNotice` conserva el evento
interno de envío y queda excluido del CRUD MCP: lo crea la operación financiera
y su reintento se controla desde el Historial, para evitar avisos manuales
duplicados o cambios independientes del pago.
