# Cuentas y hosting por proyecto — P2

## Contrato de producto

Cada cuenta nueva de proyecto tiene exactamente una naturaleza y relaciones
reales: contrato del proyecto, con otrosí opcional de ese contrato, **o** hosting
único del proyecto. Un proyecto puede tener varios contratos, varios otrosí y
muchas cuentas en cada rama. El hosting sigue fuera de los contratos y conserva
sus fases comerciales `ProjectPhase` y sus automatismos actuales.

Una cuenta histórica sin contexto queda **pendiente de asociar**. Su cliente
conserva acceso a lista, detalle y PDF emitido cuando las relaciones de propiedad
son coherentes. No se deduce contrato ni equivalencia de hosting desde texto,
importe, fechas o PDF. Los cobros sin proyecto conservan el flujo contable
existente y no requieren contexto contractual.

Reclasificar no vuelve a emitir, no modifica numeración, estado, importes,
snapshot o bytes del PDF, y no registra ingresos, pagos ni ciclos. La fuente
financiera sigue siendo el Panel. No hay flags nuevos para ocultar cuentas ni
hosting; la decisión de ocultar por defecto pertenece solamente a URL/accesos.

## Relaciones persistentes

| Modelo de P2 | Relaciones y propósito |
| --- | --- |
| `CollectionAccountContext` | Uno por `Document`; FK a `ProjectContract` y otrosí opcional, **o** FK a `ProjectHosting`. Constraint de naturaleza excluyente. |
| `ProjectHosting` | OneToOne a `Project`; OneToOne opcional a la suscripción existente; origen contable operativo explícito. |
| `ProjectHostingAccountingSource` | Varios registros históricos pueden representar un hosting; cada `HostingRecord` pertenece a un solo contexto. |
| `HostingEvidenceGroup` | Decisión administrativa de equivalencia de evidencias existentes dentro de un hosting. |
| `HostingEvidence` | Cada fila referencia exactamente un `Payment`, `HostingCycle` o `Document`; cada evidencia pertenece a un solo grupo. |
| `BillingContextEvent` | Actor, razón, versión y decisión anterior/posterior; separado de movimientos financieros. |

La pertenencia cliente/proyecto/contrato/otrosí/hosting se valida en los servicios
compartidos de Panel, JWT y MCP. Las FKs protegen los padres. El borrado de un
borrador permitido conserva su auditoría; una cuenta usada como evidencia exige
corregir explícitamente esa asociación primero.

No hay backfill que elija relaciones. La migración crea únicamente tablas de
contexto. P0 fijó `0069_p2_project_billing_context`, con padre
`0067_explicit_delivery_authoring_context` y dependencia content `0273`. P0
coordina las hojas paralelas y sus merges sin operaciones. No se han aplicado
migraciones a una base de servicio. La dependencia P3 absorbida por merge es
`4c6e132281554de14a2b303fe7a3b05f012910bf` (PR #460), después de
`dea940345fc37c361f8749d30e1a96ac2bba73ee`. P1 publicado
`b25ad2e080597b7708126b5d865d7ba805253478` (PR #464) se absorbió mediante merge.
La no-op P2 `0072_p2_issues_billing_bridge` depende de `0068_issue_reports` y
`0069_p2_project_billing_context`. La no-op `0074_p2_platform_billing_merge`
reúne `0072` y `0073_p1_delivery_issues_merge`, dejando una sola hoja de accounts.
P1 `bc403871a92258c2b77247aca6533fde0677b357` y P3 M3
`ebbf331d76fedb5f89f3b440f2fdeb50c148e977` se absorbieron por merge en esta rama,
conservando sus implementaciones y aislamiento efectivo de correo.

## Conciliación y emisión

El inventario muestra suscripción, registros contables, cuentas pendientes y
contradicciones. El administrador selecciona expresamente los orígenes y uno
operativo, revisa la vista previa y aplica con razón y versión esperada. No se
retiran orígenes históricos mediante una selección incompleta ni se borra
historia para resolver duplicados.

Los grupos de evidencia se forman por IDs elegidos por administración. Nunca se
suman fuentes no conciliadas como si fueran cobros diferentes. Una corrección de
grupo conserva la decisión anterior en auditoría. Para emitir contra un hosting
que tiene suscripción se selecciona el `Payment` existente: una obligación que
ya tiene cuenta emitida no admite otra. Obligaciones periódicas diferentes sí
admiten cuentas diferentes. Los registros históricos pendientes o un origen
contable no operativo bloquean la nueva emisión hasta su conciliación.

La creación desde ingreso requiere naturaleza y vínculo cuando el ingreso
pertenece a un proyecto. La creación desde hosting utiliza su origen asociado.
Los nuevos orígenes pueden registrar su identidad cuando no existe una
contradicción histórica; este puente no crea pagos/ciclos ni altera Wompi.

## Superficies y autenticación

- Platform: cuentas globales y por proyecto con filtros, agrupaciones, estados,
  vacío/error recuperable, detalle y PDF almacenado; hosting global conduce al
  hosting del proyecto. Usa JWT y `usePlatformApi`.
- Panel: campos de contexto al crear, edición administrativa con razón/version,
  inventario y conciliación de hosting/evidencias. Usa sesión, CSRF y los permisos
  existentes del Panel contable.
- MCP `projects`: nueve operaciones de lectura, vista previa y conciliación.
  Las mutaciones requieren confirmación y revalidan versión/principal/contexto.
- MCP contable: creación/emisión conserva sus adaptadores y acepta el contexto
  explícito, incluido el pago existente al emitir desde hosting.

Los DTO del cliente omiten notas, metadata, razones administrativas y datos
privados del emisor. Las relaciones contradictorias no conceden acceso a un
segundo cliente. Las opciones contractuales del cliente vienen exclusivamente
de sus cuentas visibles y no conceden acceso a documentos de contratos.

## Ciclo de vida de la suscripción

Incremento del 2026-10-09: `accounts/services/hosting_subscription_lifecycle.py`
comparte `plan_change` y `apply_change`. En el MCP `projects`,
`preview_hosting_subscription_change` es lectura y `change_hosting_subscription`
es sensible: exige motivo, `expected_impact_hash` y `confirm_action`. El preview
no escribe y muestra `can_apply`, `blockers`, `warnings`, antes/después de la
suscripción, `voided_payments`, `restored_payments`, `generated_payment`,
`kept_history` e `impact_hash`.

| Acción | Estado de origen | Resultado |
| --- | --- | --- |
| `pause` | `active` o `pending` | `suspended`; pausa manual identificada por el último `BillingContextEvent` de ciclo de vida, `hosting_subscription.pause`. |
| `cancel` | `active`, `pending` o `suspended` | `cancelled`, terminal; `next_billing_date` pasa a null. |
| `resume` | `suspended` por pausa manual | `active`; restaura cobros todavía futuros o abre un ciclo nuevo. Una suspensión por fallos de pago se bloquea con `suspended_by_payment_failure`. |

Reusar `suspended` no añade un estado de suscripción. La pausa no cambia el
estado del proyecto y su sugerencia en el Panel deja de atribuirla a cobros
fallidos. Cada decisión guarda actor, motivo y antes/después en
`BillingContextEvent`, incluidos los IDs de pagos anulados, restaurados o creados.

### Cobros futuros e historia conservada

`effective_date` es una fecha hasta hoy UTC, por defecto hoy; el MCP la congela
al preparar la confirmación. Pausar o cancelar anula los pagos abiertos activos
con **`due_date > effective_date`**: `pending`, `failed`, `overdue` o `processing`
sin transacción Wompi en curso. Pasan a `Payment.status=voided`, con
`is_archived=true` y `archived_at`; cada transición desde el estado anterior
registra `PaymentHistory` con origen manual y referencia al evento. No se borran
los cobros ni su historia. La migración
`accounts.0082_hosting_payment_voided_status` añade `voided` a Payment y a los
estados de PaymentHistory; se aplica durante deploy.

Los pagos ya causados (`due_date <= effective_date`) siguen cobrables y aparecen
en `due_payments_remain_collectible`, pero la pausa/cancelación detiene su débito
automático. Los pagos recibidos, su historia, los ciclos contables y las cuentas
de cobro se conservan. Hosting contable e ingresos esperados se revisan por
separado (`accounting_records_untouched`); un link externo aún publicado se
advierte como `payment_link_outstanding`.

Reanudar restaura sólo los pagos anulados por el evento de esa pausa que siguen
archivados, en `voided` y con vencimiento posterior a la fecha de reanudación.
Recuperan su estado anterior, se desarchivan y añaden historia. Si no queda
ninguno todavía futuro, crea un cobro pendiente y un ciclo desde la fecha de
reanudación, sin cobrar el tiempo pausado. Una cancelación no admite reanudación.

Bloqueos adicionales: suscripción retenida, sin proyecto o archivada;
transición inválida; fecha futura; pago `processing` con transacción Wompi
(`payment_in_flight`); y estado del proyecto que impide facturar al reanudar
(`project_blocks_billing`). El hash se revalida antes de ejecutar, con orden de
locks proyecto → suscripción → ProjectHosting → pagos por pk y lecturas actuales.

`get_project_hosting` incluye los pagos anulados en `subscription.payments`, con
`status`, `is_archived` y `archived_at` read-only. Platform y el historial de
pagos muestran «Anulado»; los locales de billing usan «Anulado»/«Voided». En
`content/mcp/contracts.py`, `HostingSubscription.status` y `next_billing_date`
se clasifican como modificables en `projects` exclusivamente mediante la acción
de ciclo de vida; `accounting-billing` conserva ambos como read-only. Ningún
payload permite fijarlos directamente.

### Guardas de los caminos de cobro

| Camino | Garantía del incremento |
| --- | --- |
| Link, widget, tarjeta nueva y tarjeta guardada | Los cuatro endpoints de pago rechazan pagos archivados y estados no cobrables, incluido `voided`. |
| `_generate_next_payment` | Omite pagos archivados al buscar cobros abiertos y no genera para una suscripción cancelada o en pausa manual. |
| Aprobación tardía | Registra el cobro real como `paid`, lo desarchiva y añade `PaymentHistory.metadata.settled_after_void`, evento `hosting_subscription.settled_after_void` y aviso al administrador después del commit. No reactiva la suscripción ni genera otro ciclo. |
| Registro manual de pago | Conserva cancelación o pausa manual, sin avanzar su próxima fecha ni reactivarla. |
| `_charge_payment_with_source` | Relee y bloquea proyecto, suscripción, ProjectHosting y pago antes de Wompi; un trabajo encolado con estado obsoleto, cobro archivado o suscripción no cobrable se rechaza sin llamar al proveedor. |
| `_onboard_due_phases` | Relee bajo lock el proyecto, la suscripción y la fase antes de activar hosting o crear un prorrateo; exige suscripción activa y proyecto habilitado para facturar. |
| PATCH de `/api/accounts/projects/<id>/subscription/` con `status` | HTTP 400 `subscription_lifecycle_required`; el cambio debe usar el servicio de ciclo de vida. |

**Trade-off vigente:** `_charge_payment_with_source` mantiene la transacción y
los locks durante la llamada a Wompi **y su polling**. Esto serializa la decisión
con la pausa/cancelación, pero prolonga los bloqueos mientras responde el proveedor.
Seguimiento pendiente: un flujo **claim-then-call** que reserve el intento bajo
lock, libere la transacción antes de llamar y concilie después el resultado de
forma idempotente. Ese flujo todavía no está implementado.

Cobertura focal: `accounts/tests/billing/test_hosting_subscription_lifecycle.py`,
`accounts/tests/billing/test_payment_lifecycle_guards.py`,
`content/tests/views/test_mcp_hosting_subscription.py` y los contratos de
`content/tests/views/test_mcp_contracts.py`. Se simula Wompi; SQLite valida los
rechecks y rollback, no la exclusión real de locks MySQL. Recorrido:
[Migración de carpetas por MCP — parte 1](MCP_VALIDATION_RUNBOOK.md#migración-de-carpetas-por-mcp--parte-1-2026-10).

### Cambio de cliente e historia financiera

Las guardas financieras, de entregas y tickets comparten
`accounts/services/project_client_transfer.py`. El preview publica los bloqueos
y un `impact_hash` independiente del modo; el cambio revalida esa huella bajo
lock. Una suscripción cancelada sigue siendo historia financiera y bloquea
transferir el proyecto a otro cliente. La resolución es crear un proyecto nuevo;
`rebase_with_history` queda diferido por la tarjeta del cliente anterior, el
acceso por `project.client` y la falta de una marca de proyecto interno.
Contrato y errores:
[Evaluación compartida y vista previa](ISSUE_CLIENT_TRANSFER_INTEGRATION.md#evaluación-compartida-y-vista-previa-2026-10-09).

## Propiedad e integración

P2 es dueño de `accounts/billing_models.py`, servicios `billing_*` y
`hosting_context`, serializers/views/URLs dedicados, el módulo MCP
`platform_billing_tools`, componentes `platform/billing` y `accounting/billing`,
store `platform-billing`, locales `platformBilling`, pruebas y documentación de
este dominio. Los escritores financieros existentes reciben puentes mínimos.

| Bloque compartido reservado a P2 | Dependencia / integración por P0 |
| --- | --- |
| `accounts/models.py` import y migración aditiva de billing | Nombre P2 `0069`, padre P3 `0067`; P0 integra las hojas paralelas sin operaciones. |
| `accounts/urls.py`, `content/urls.py` includes de billing | Preservar registros P1/P3/P4/P5; módulos nuevos sin reorganizar URLs. |
| Registries/contratos MCP y `mcp_blog.py` | Sólo entradas/modelos/operaciones billing; conservar núcleo delivery de P3. |
| Navegación de cuentas/hosting, imports i18n | Sólo enlaces y claves de billing; sin políticas de accesos P4. |
| Catálogos de vistas, responsive y shards de flows | Datos del dominio y sus docs derivadas; regenerar agregados tras integrar. |
| Seeds y clasificación fake data | Contextos explícitos de fixtures, reset ordenado y guard de entorno; no ejecutar contra servicio. |
| Memoria y runbook MCP | Secciones P2; no reemplazar textos de los otros frentes. |
| `project_service.change_client_apply` | Lock del proyecto → finanzas P2 → delivery P3 → tickets P1 → revocación P4 → dueño/cascada. Las tres guardas están compuestas; la lógica P4 se conserva al absorber su commit publicado. |
| `ProjectAdmin` y `forms_billing` | Formulario y recheck bajo lock, con proyecto original y actor del request; componen finanzas → delivery → tickets y muestran errores DRF con rollback. P4 integra revocación después de estas guardas. |
| `accounts/migrations/0072_p2_issues_billing_bridge` | No-op autorizada por P0 que reúne las hojas `0068` de P1 y `0069` de P2; no altera migraciones anteriores. |
| `accounts/migrations/0074_p2_platform_billing_merge` | No-op reservada, padres publicados `0072` y `0073`; una sola hoja en esta rama, sin operaciones ni aplicación a DB. |
| `accounting_settlement_service` / `accounting_service` | Reserva acotada a las dos entradas de liquidación y escritores directos de ingreso/hosting: Project antes de origen; sin cambios de cálculo, Bolsillo ni automatismos. |
| `delivery_workflow._validate_relations` | Excepción directa acotada: rechazar reparentar un otrosí con cuentas mediante helper P2. P3 mantiene el resto del núcleo. |

`ProjectContract.project` continúa inmutable en REST/MCP. Un otrosí sin cobros
puede cambiar de contrato si las guardas existentes permiten editarlo; uno con
cuentas conserva su contrato. Los cambios de cliente fallidos no dejan cascada,
desprendimiento ni historia parcial.

## Fronteras de escritura y concurrencia

Los escritores reservados toman primero `Project`, después los orígenes
financieros y finalmente `Document`/contexto. Las lecturas iniciales sólo
descubren IDs; las relaciones y el dueño se comprueban otra vez con las filas
actuales bloqueadas. Los bloqueos de origen/documento no usan joins anulables.
La emisión conserva el PDF y la numeración existentes, y un segundo intento
sobre una instancia obsoleta encuentra el estado vigente antes de emitir.

La reserva ampliada incluye únicamente las entradas `settle_expected_income`
y `bulk_settle_expected_incomes` y la frontera de `create_record(INCOME)`.
Comprueban cliente/proyecto y saldo actual antes de crear movimientos. El orden
de asignaciones del usuario, los importes, el split, Bolsillo, los automatismos
y los snapshots conservan sus reglas existentes.

Admin valida el cliente con el proyecto original bajo lock y vuelve a
comprobarlo antes del save. Un rechazo tardío sale de la transacción, revierte
las escrituras y vuelve a mostrar el formulario con el error en el campo; no
expone una excepción DRF como respuesta 500. La integración de las guardas
publicadas de delivery/tickets y de la revocación P4 conserva este orden:
proyecto → finanzas → delivery → tickets → revocación → save.

## Verificación y límites

Las pruebas dedicadas usan SQLite/settings_test y datos propios: aislamiento
cliente/proyecto, exclusión de doble naturaleza, otrosí ajeno, varias ramas,
razón/version, PDF conservado, conciliación explícita, obligaciones periódicas,
reparentado y rollback de dueño. Panel/MCP ejercitan los escritores reales.
Los journeys de navegador usan APIs simuladas y nunca cobran ni contactan a
clientes. Los resultados concretos y CI se registran en el PR.
SQLite valida estados y rollback; no certifica exclusión real ni ausencia de
carreras en MySQL. No se inició un harness MySQL.
El descubrimiento exige encontrar todos los IDs solicitados. Si un ingreso o
hosting fue eliminado antes de esta lectura, la actualización validada contra
la instancia antigua devuelve conflicto 409, sin recrear la fila ni añadir
auditoría parcial. Las dos pruebas realizan primero un DELETE permitido real,
y después ejercitan el escritor con la instancia/serializer ya obsoletos; no
simulan ni certifican una carrera de bloqueo entre conexiones MySQL.

`bulk_assign_client` conserva el contrato interno de ignorar IDs que ya no
existían al descubrir el alcance. Las vistas de asignación de ingreso/hosting
usan `strict_ids=True`: mantienen el 409 con los IDs ausentes del precheck y
rechazan también una desaparición posterior antes de escribir. El helper de
locks continúa estricto sobre las filas descubiertas, con Project antes del
origen, y conserva las guardas de contexto y el rollback del lote. Las pruebas
del intervalo insertan un borrado real después del precheck real; verifican
respuesta HTTP y estado/historia, sin certificar concurrencia MySQL.
El fix tiene 36 casos focales aprobados en lotes de 20 y 16: CRUD contable,
compatibilidad interna y borrado tras precheck en ambos modelos, vistas de
asignación y rechazo de PATCH obsoleto. El gate del archivo nuevo pasó 100/100,
sin errores ni advertencias, con todos los MAILERS aislados en locmem.

El servidor local de navegador usa APIs simuladas contra un backend inexistente.
La fixture pytest dedicada configura `MAILERS.default` y todos los aliases con
locmem, comprueba el backend efectivo y exige ese guard antes de preparar su DB.
No depende del antiguo `EMAIL_BACKEND` para impedir envíos reales.

El cierre local de los puentes incluye 8 casos de Admin con errores visibles y
rollback, 20 cruces delivery/Admin, 17 casos de correo/liquidación/MCP y 17
regresiones contables. Los 8 journeys de hosting existentes también pasaron con
la navegación por proyecto. El build Nuxt pasó; el gate estricto focal registra
19 archivos sin errores ni advertencias. El mapa tiene las 8 rutas de billing y
hosting cubiertas, sin brechas de resultados. Son verificaciones locales: no
sustituyen el CI del head que finalmente se publique.

Sobre las dependencias P1/P3 publicadas se verificaron 55 casos backend
distintos: escritores, desaparición de orígenes, correo, Admin, liquidación y
compatibilidad de emisión. Los cinco perfiles del preview de cuenta pasaron
(uno antes de reiniciar el servidor propio, cuatro después). Los casos fallidos
por conexión local rechazada se repitieron sin cambiar comportamiento de UI.
El gate estricto de los cuatro archivos del cierre pasó: 97/100, sin errores ni
advertencias; conserva nueve sugerencias de docstrings existentes. La hoja de
accounts es únicamente `0074`; Django check y makemigrations dry-run no muestran
problemas ni drift. Registro de flows, catálogo y contrato responsivo coherentes.

Pendientes de integración: P0 coordina el tren de PRs y la composición P4. La revocación de accesos P4 se absorbe por commit publicado; no se copia
desde su worktree. No se cambian el fallo contable ajeno de P3, guías por roles,
prompt/core, enlaces seguros, correos ni políticas de publicación documental.
