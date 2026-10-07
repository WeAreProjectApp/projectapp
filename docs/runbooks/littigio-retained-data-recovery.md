# Littigio — recuperación de datos conservados (2026-10-07)

Reemplaza a `littigio-project-reassignment.md`: el 07-10 se eliminaron con
eliminación forzada los proyectos 14 y 15 del cliente (perfil 61, usuario 62) y
se conservó el 16, que pasa a ser el definitivo. Este procedimiento usa sólo las
herramientas MCP con vista previa y confirmación (PR de re-adopción auditada);
no escribe la base directamente ni ejecuta comandos en el servidor. Cada lectura
y respuesta se guarda fuera de Git, con fecha, IDs y huellas.

## Compuertas

- **G0** — `tools/list` del conector de proyectos incluye
  `list_project_retention_contexts`, `preview_retained_operation_undo`,
  `undo_retained_operation`, `preview_retained_container_cleanup` y
  `delete_empty_retained_containers`; la vista previa de reasignación acepta
  `hosting_start_date` y `accept_hosting_start`.
- **G1** — respaldo completo de la base justo antes, con su sha256.
- **G2** — fuera de las corridas diarias de 06:00 UTC (cobro de hosting) y
  13:30 UTC (calendario de cobros); sin ediciones de Littigio mientras dura.
- **G3** — visto bueno de revisión y del orquestador por fase, incluida la
  decisión de hosting de S1 con el dato de `get_project_hosting(16)`.

## Inventario previo (y repetido en S9)

| ID | Lectura |
|---|---|
| I1 | `list_project_retention_contexts` con `query.client_profile_id=61` y `query.integrity=1`: contextos de los proyectos 14 y 15, ids vivos por categoría, propuestas afectadas (#117), integridad vacía |
| I2 | `list_change_logs(entity_type="project", action="deleted")`, filas de 14 y 15 |
| I3 | `get_project(16)`, `list_project_commercial_phases(16)`, `get_project_hosting(16)`, `get_project_billing_options(16)` |
| I4 | `list_project_unlinked_records(16)`: registros con `retained`, `duplicates` y `threads` |
| I5 | `get_income_detail` de 245–249 y `get_receivables` (totales de cartera) |
| I6 | `read_document` de 201, 202, 203, 208, 209, 227 y 236: ETag, huella del contenido, `signed_at`, carpeta |
| I7 | `list_document_folders(scope="all")`: 129–135, carpetas del contexto 15, 141–147 y 154 |
| I8 | `list_threads(client_id=61, scope="all")`, `get_thread(12)` y `get_thread(14)` |
| I9 | `get_proposal_approval(117)` (responde, `retained: true`) y `preview_proposal_project_reassignment(117, target_project_id=16)` |

## Pasos

| Paso | Llamada | Verificación | Vuelta atrás |
|---|---|---|---|
| S1 | `preview_proposal_project_reassignment(117 → 16)`; si aparece `pending_hosting_start`, decidir con G3 (`hosting_start_date` futura o `accept_hosting_start`). `reassign_proposal_project` con el `expected_impact_hash` vigente, motivo y `request_id` `littigio-117-to-16`; confirmar | `get_proposal_approval(117).linked_project.id == 16`; la fase de la #117 y sus entregables con los mismos ids en el 16; operación `proposal_reassignment` en I1 | Sin deshacer automático (el origen ya no existe): restaurar sus filas desde G1 con la escritura congelada. Por eso S1 va con GO propio |
| S2 | `reorder_project_commercial_phases(16)` con la fase de la #117 en 1 y la fase 5 (#118) en 2 | Orden en `list_project_commercial_phases(16)` | La misma llamada con el orden inverso |
| S3 | `assign_project_unlinked_records(16)` con `income_ids` 245–249, `document_ids` 201, 202, 203, 208, 209, 227 y 236, `thread_ids` [12] y `reason`; revisar antes los `duplicates` (201 frente a 208); confirmar | `adoptions` en la respuesta; ingresos y documentos con proyecto 16 y editables; documentos en la raíz 141; hilo 12 en el 16; totales de cartera iguales a I5 | `undo_retained_operation` de cada operación (vista previa y confirmación) |
| S4 | Opcional: `create_folder(name="Observaciones", parent_id=154)` | Carpeta bajo 154 | `delete_folder` de la nueva carpeta |
| S5 | `move_documents`: 201, 208 y 236 → 154; 202, 203 y 209 → 154 u «Observaciones»; 227 → 141 | ETag nuevo, contenido, `signed_at` y visibilidad iguales a I6 | `move_documents` de vuelta a 141 |
| S6 | Archivar 201 (versión anterior del contrato) | `is_archived` verdadero | Desarchivar 201 |
| S7 | Hilos: el 12 queda como conversación del proyecto 16 y el 14 sigue como su hilo madre (no se archiva ni se elimina por diseño) | `list_threads(project_id=16)` | `update_thread(12)` no aplica: deshacer S3 |
| S8 | `preview_retained_container_cleanup` del contexto 14 y luego del 15; `delete_empty_retained_containers` con la misma selección (129–135 y los contenedores vacíos del 15) y `request_id` estable; confirmar | I1 sin contenedores pendientes; ninguna carpeta con contenido eliminada | Sin deshacer (sólo vacíos): restaurar desde G1 si hiciera falta |
| S9 | Repetir el inventario | Criterios de aceptación | — |
| S10 | Con GO aparte: `get_project_billing_options(16)` y `link_project_billing_contract` del contrato 208 | Opciones de cobro con 208 | Crea un evento de facturación; revisar antes de aplicarlo |

Las carpetas 80 (raíz del cliente) y 110–114 (árbol automático «Clientes / … /
Sin proyecto») no son datos conservados: se mantienen.

## Criterios de aceptación

- Proyecto 16 con la #117 como fase 1 y la #118 como fase 2.
- Entregables de la #117 en el proyecto 16 con sus ids originales.
- Ingresos 245–249 en el proyecto 16, editables; cartera sin cambios de total.
- Documentos 202, 203, 208, 209, 227 y 236 en carpetas del 16; 201 archivado.
- Hilo 12 en el proyecto 16.
- `get_proposal_approval(117)` responde sin error.
- `list_project_unlinked_records(16)` sin registros ni hilos pendientes.
- `list_project_retention_contexts` de Littigio sin pendientes rastreables.
