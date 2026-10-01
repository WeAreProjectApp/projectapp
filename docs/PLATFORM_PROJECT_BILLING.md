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
`dea940345fc37c361f8749d30e1a96ac2bba73ee` (PR #460); no se considera su entrega final verde.

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
| `project_service.change_client_apply` | Lock del proyecto → guard financiero P2 → revocación P4 → dueño/cascada. La lógica P4 se conserva al absorber su commit publicado. |
| `ProjectAdmin` | Formulario y guard transaccional para impedir saltar el mismo límite desde Django Admin. |
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

Pendientes de integración: P0 coordina P3 final, el merge de hojas y el orden
de PRs. La revocación de accesos P4 se absorbe por commit publicado; no se copia
desde su worktree. No se cambian el fallo contable ajeno de P3, guías por roles,
prompt/core, enlaces seguros, correos ni políticas de publicación documental.
