# Gestor de Proyectos MCP 2.2.0

## Cambio de cliente con la misma evaluación en preview y ejecución

`preview_project_client_change` evalúa las tres guardas compartidas: historia
financiera, entregas/contratos y tickets. Devuelve `can_apply`, `blockers`,
`blocker_counts`, `planned.move`, `planned.detach`, `financial_history` e
`impact_hash` independiente del modo. La lectura no escribe y permite conocer
antes de confirmar los mismos impedimentos que detendrán el cambio.

`change_project_client` publica un esquema plano y explícito con `project_id`,
`client_profile_id`, `mode: move|detach` y `expected_impact_hash`. `move` aplica
el plan de traslado; `detach` conserva el cliente de los registros y pierde su
proyecto. Los ingresos con cuenta activa se desvinculan y las conversaciones
conservan su cliente original. El preview sigue siendo la descripción concreta
de los registros afectados; el Panel mantiene sus listas legacy durante esta
compatibilidad.

La preparación rechaza planes bloqueados con `PROJECT_CLIENT_CHANGE_BLOCKED`
y `details.blockers`, sin crear una intención. Si aparece historia antes o
durante `confirm_action`, vuelve a evaluar bajo lock y conserva ese código con
`details.guard_code`, incluido el código de la guarda anterior. Un hash obsoleto
sin ese bloqueo devuelve `STALE_VERSION`. Ningún rechazo cambia dueño ni historia.

El modal Cambiar cliente del Panel muestra los bloqueos y la orientación
`resolution: create_new_project`, oculta los modos y deshabilita Confirmar.
Con preview permitido, exige modo y envía el hash revisado.
Reglas: [evaluación compartida](../ISSUE_CLIENT_TRANSFER_INTEGRATION.md#evaluación-compartida-y-vista-previa-2026-10-09).

## Ciclo de vida de hosting y pagos anulados

Proyectos incorpora `preview_hosting_subscription_change` y
`change_hosting_subscription`, con esquema explícito: `subscription_id`,
`action: pause|cancel|resume`, `effective_date` opcional y, para la escritura,
`reason` y `expected_impact_hash`. La fecha efectiva no puede superar hoy UTC;
se congela al preparar la confirmación. El inventario total es **164 herramientas**.

- `pause` pasa `active`/`pending` a `suspended`. Reutiliza el estado existente;
  un evento `hosting_subscription.pause` distingue la pausa manual del fallo
  de cobro.
- `cancel` acepta `active`/`pending`/`suspended`, deja `cancelled` y
  `next_billing_date: null`; es terminal.
- `resume` sólo acepta una pausa manual. Restaura los pagos anulados por esa
  pausa que todavía vencen después de la fecha efectiva. Si no quedan, abre
  un ciclo desde la reanudación, sin cobrar el tiempo pausado.

Pausa y cancelación anulan cobros abiertos activos con `due_date > effective_date`:
`Payment.status: voided` («Anulado»), `is_archived: true`, fecha de archivo e
historia de la transición. Los pagos ya causados siguen cobrables con aviso,
pero no entran al débito automático de la suscripción pausada/cancelada. Pagos
recibidos, cuentas, ciclos contables e ingresos esperados conservan su historia;
el preview informa lo que queda sin modificar.

El preview incluye antes/después, `voided_payments`, `restored_payments`,
`generated_payment`, `kept_history`, bloqueos, avisos e `impact_hash`. La
escritura requiere confirmación y vuelve a planificar bajo candados de proyecto,
suscripción, hosting y pagos. Conserva motivo, actor y evidencia en
`BillingContextEvent` y `PaymentHistory`.

Los endpoints de link, widget, tarjeta nueva y tarjeta guardada rechazan pagos
archivados o anulados. La cola de débito revalida antes de Wompi; la activación
de fases vuelve a comprobar los estados bajo lock. La generación de pagos no
abre un ciclo para una suscripción cancelada o pausada manualmente. Un pago
manual conserva esos estados. Una aprobación tardía de un cobro anulado se
registra como pagada, desarchiva el pago y deja `settled_after_void`, evento y
aviso al administrador, sin reactivar ni generar otro ciclo.

PATCH directo de `status` de la suscripción devuelve HTTP 400
`subscription_lifecycle_required` (MCP: `SUBSCRIPTION_LIFECYCLE_REQUIRED`);
el cambio debe usar el servicio de ciclo de vida. El PATCH de ajustes relee
proyecto y suscripción bajo candados y guarda sólo los campos solicitados y
los derivados del cambio de plan. No revierte una pausa o cancelación concurrente;
un PATCH vacío no escribe, tampoco actualiza la fecha de modificación.

En `card-pay`, después de tokenizar la tarjeta y antes de crear la transacción
Wompi, se releen proyecto, suscripción, hosting y pago bajo candados. El pago
debe estar sin archivar y en `pending`, `overdue` o `failed`; la suscripción,
activa o pendiente, sin archivar ni contexto de retención y ligada al mismo
proyecto.
Reanudar y los cobros con tarjeta nueva o guardada usan `project_allows_billing`:
también bloquean proyectos sin estado clasificado que requieren revisión.

Entre los bloqueos del preview están `subscription_retained`,
`subscription_without_project`, `subscription_archived`, `invalid_transition`,
`payment_in_flight`, `effective_date_in_future`, `suspended_by_payment_failure`
y, al reanudar, `project_blocks_billing`. Un plan bloqueado devuelve
`SUBSCRIPTION_CHANGE_BLOCKED`; un impacto cambiado, `STALE_VERSION`.

`get_project_hosting` incorpora `is_archived` y `archived_at` en
`subscription.payments`, incluidos los anulados. El Panel muestra «Anulado» y
los locales de billing usan «Anulado»/«Voided».

Los cobros con tarjeta nueva o guardada **mantienen los locks durante la llamada
a Wompi; el de tarjeta guardada, además, durante su polling**. El recheck protege
el estado, pero aumenta la contención y el tiempo de la transacción.
El seguimiento pendiente es **claim-then-call**:
reservar el pago como en proceso antes de contactar al proveedor y separar la
llamada de los locks, conservando los controles de aprobación. SQLite no
certifica estos locks bajo MySQL REPEATABLE READ.
Contrato: [ciclo de vida de hosting](../PLATFORM_PROJECT_BILLING.md#ciclo-de-vida-de-la-suscripción).

## Crear proyectos con una raíz documental existente

`create_project` publica un esquema cerrado con `name` y `client_profile_id`
obligatorios, y `description`, `state_id` y `root_folder_id` opcionales.
Ya no acepta `client_policy`, `portal_policy` ni `document_decisions`.
Con `root_folder_id` adopta una raíz manual mediante el motor de migración y
muestra el plan completo; requiere `confirm_action`. Toda adopción desde
Proyectos usa **`abort_on_conflict` y `abort`, sin decisiones por documento**,
incluida la protección frente a exposición latente de archivados visibles.

Un plan bloqueado devuelve `CONFLICT` con `details.blockers` y `details.hint`
para usar `preview_folder_migration`/`apply_folder_migration` del conector
Documentos. Las confirmaciones pendientes preparadas con las políticas
permisivas o decisiones anteriores devuelven `STALE_VERSION` y requieren una
nueva revisión.

Sin raíz explícita, el alta es inmediata si no hay colisión. Si existe una raíz
manual homónima que admite adopción segura, también exige confirmación. La
respuesta incluye `document_root` con `folder_id`, `adopted` y `migration_id`
(null cuando se creó una raíz nueva).
La adopción automática rechaza cualquier documento marcado visible, tanto
activo como archivado; no basta con que hoy carezca de audiencia.

Nunca se duplica una raíz manual homónima. La comparación recorta espacios e
ignora mayúsculas, incluye archivadas y excluye raíces gestionadas de clientes
u otros proyectos: los proyectos homónimos siguen siendo legales. Una raíz
ambigua, conservada, con conflictos, espejos o elementos congelados exige
resolver `PROJECT_ROOT_NAME_CONFLICT`, con IDs, rutas, motivos y orientación
a `root_folder_id`/migración. La carpeta 66 con Contratos, las decisiones de
235/241 y la política del portal de 69 requieren las herramientas de Documentos.
Renombrar un proyecto tampoco puede apropiarse implícitamente de
una raíz manual homónima; bloquea hasta resolverla.

La regla se comparte entre altas y renombres del Panel y Platform. Las altas
son atómicas; la adopción guarda nombre, padre, dueño y marcador de raíz juntos,
reutiliza la plantilla admisible y deja recibo para deshacer. Las operaciones de
migración se descubren en **Documentos 3.2.0**, sin duplicarlas en Proyectos.
En guardados posteriores, `_synchronize_root` sólo tolera la colisión de nombre
con una raíz manual: conserva el nombre previo de la raíz y registra el choque.
Cualquier otro fallo revierte el guardado del proyecto y los cambios de su
árbol documental.

## Evaluación de `rebase_with_history`

Se evaluó y **se difiere**. La suscripción conserva la tarjeta del cliente
anterior: el siguiente débito le cobraría a él. El acceso a la plataforma sigue
`project.client`: el dueño anterior perdería su historia y el nuevo la vería.
No existe una marca de proyecto interno que acote ese comportamiento.

Cancelar hosting no desbloquea el cambio de cliente: la guarda financiera
considera la historia de suscripciones y hosting aunque estén cancelados.
La resolución disponible es `create_new_project`, conservando el proyecto
histórico. La raíz adoptada/migrada y las decisiones explícitas se tramitan por
las herramientas de Documentos. La cascada existente del cambio de cliente
tampoco reescribe todos los documentos que no son cuentas
de cobro; esa brecha permanece como seguimiento.

## Despliegue y validación

El deploy aplica [accounts.0082](../../backend/accounts/migrations/0082_hosting_payment_voided_status.py)
para las opciones `voided` de Payment y PaymentHistory, además de
[content.0286](../../backend/content/migrations/0286_contracttemplate_mirror_folder.py)
y [content.0287](../../backend/content/migrations/0287_document_ownership_operation.py)
para el pin y los recibos de adopción/migración. No ejecutar migraciones desde
un worktree sobre una base real. Los pagos archivados históricos no se convierten
retroactivamente en `voided`.

Las credenciales de Proyectos con allow-list explícita deben añadir
`preview_hosting_subscription_change` y `change_hosting_subscription`, y permitir
`confirm_action` y las lecturas necesarias. Para migrar carpetas se necesita
además el alcance correspondiente de Documentos. Después del deploy, reconectar
los conectores de **claude.ai** para refrescar `tools/list`; cotejar versiones,
schemas y herramientas con `describe_capabilities`.

Procedimiento con evidencia y plazo del cobro automático:
[runbook de producción](../MCP_VALIDATION_RUNBOOK.md#runbook-post-despliegue-del-caso-real).
Esta nota documenta el código de PR #504, no una cancelación ni migración ya
ejecutada en producción.

## Historia

**2.1.0 nunca tuvo changelog propio.** Esta nota reúne las guardas, el ciclo de
hosting y la creación con raíz revisada desde esa versión. PR #503 comparte la
numeración: el PR que se integre segundo toma el siguiente número y actualiza
sus pins y documentación antes de publicar.
