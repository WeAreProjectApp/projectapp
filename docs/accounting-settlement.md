# Liquidación unificada de ingresos

## Antecedentes verificados

La revisión se hizo sobre `main` en `17e19f8f`, contrastado con GitHub el
19 de octubre de 2026; no certifica la versión desplegada.

| Cambio | Evidencia | Resultado |
|---|---|---|
| Liquidación individual | PR #110, 16 de julio | Pagos líquidos enlazados al ingreso esperado. |
| Resolver diferencias | PR #137, 28 de julio; #145, 1 de agosto | Deducciones, reprogramaciones y operaciones sin dinero recibido. La diferencia se autocalcula; la retención se captura como importe. |
| Abono múltiple | PR #212, 17 de agosto | Un movimiento de bolsillo y varios pagos, con reparto antiguo primero. No tenía deducciones ni participaciones globales. |
| IVA contable | `342e5761`, 2 de octubre | Tasa por ingreso; captura de base/total incluido y herencia a los pagos. Por decisión previa, no cambia utilidad ni reparto. |
| Reparto automático visible | PR #495, 10 de octubre | Corrige PA-170 para importes que llegan prellenados. |
| Liquidar antes de facturar | PR #509, 10 de octubre | La acción individual pasa al abono básico y relega los ajustes a otro formulario que reinicia los datos. |

Las comisiones y retenciones no se eliminaron. El problema era la separación de
los dos caminos y su exposición. No se encontró un porcentaje automático de
retención ni un tratamiento del IVA como dinero faltante.

## Decisiones confirmadas

- Un modal para uno o varios ingresos, sin cambiar de formulario para ajustar.
- Participaciones globales del dinero recibido, automáticas 50/50 o manuales.
- Deducciones proporcionales. Se distribuye la cobertura del dinero más las
  deducciones del ingreso más antiguo al reciente; luego se separa la comisión.
  Dos pendientes de 100, recibido 180 y comisión 20: cada ingreso registra
  90 recibidos y 10 de deducción. Los centavos usan restos mayores y desempate
  por antigüedad e ID; ningún ingreso recibe más de su saldo.
- El saldo sin asignar sigue pendiente en su ingreso. Crear otro esperado es
  explícito, con origen, concepto, fecha y monto; conserva cliente, proyecto,
  línea de negocio e IVA y reduce el original por el monto trasladado.
- IVA configurable por ingreso desde un interruptor junto al encabezado, antes
  de expandir: apagarlo propone 0 (Sin IVA), encenderlo recupera la última tasa
  positiva del borrador o exige definirla. Tasa nula sigue siendo desconocida.
  Captura antes de IVA o total incluido con desglose de base, impuesto y total.
  La tasa se guarda en el original y se hereda al pago y a saldos reprogramados.
  El total esperado se conserva; pagos, deducciones o cuentas emitidas bloquean
  cambios de tasa, sin impedir liquidar con la tasa actual.
- Los destinos Socios y Bolsillo conservan sus reglas. Solo al bolsillo entra
  el dinero recibido, como un movimiento común; ninguna deducción genera salida.
- Correo por ingreso elegible, al destinatario de su cuenta emitida. Revisar y
  confirmar ocurre en el mismo modal. Sin cuenta puede liquidarse igual;
  el aviso interno de ingreso completo pendiente de facturar se conserva.
- Corrección y reversa integrales. Si un saldo reprogramado ya tiene pagos,
  deducciones o documentos vigentes, o cambian sus condiciones, se bloquean
  y se identifica el registro que impide continuar.

## Contrato operativo

Los adaptadores individual y múltiple comparten el mismo escritor atómico.
`income_ids` solicita la propuesta automática; `allocations` conserva un
reparto manual explícito. Ambos admiten deducciones y reprogramaciones. Los
clientes anteriores pueden seguir enviando los contratos existentes.

`POST accounting/incomes/settlement-preview/` calcula distribución, IVA y
posibles destinatarios sin crear registros. `preview_hash` protege lo revisado
contra cambios posteriores; `request_id` identifica reintentos del mismo pago.
La respuesta de liquidación añade `settlement_id`.

`vat_updates` es opcional en ambos adaptadores, vista previa y corrección, en
REST y MCP. Cada entrada tiene `income_id`, `vat_rate` (0–100, hasta dos
decimales; `null` sin registrar), y opcionalmente `amount` + `amount_mode`
(`before_vat` o `vat_included`, este último por defecto). El total normalizado
de la captura debe coincidir con el dinero imputado al ingreso; no sustituye
`total_amount` ni cambia el total esperado. No admite ingresos ajenos a la
selección ni configuraciones repetidas. Omitirlo conserva el contrato anterior.
La vista previa informa `vat_editable` y `vat_blocked_reason` por fila. El IVA
propuesto participa en `preview_hash` y se registra en los snapshots de la
operación. Una reversión restaura la tasa anterior salvo pagos, deducciones o
documentos posteriores que dependan de ella. Las mismas opciones se publican en
`settle_income`, `bulk_settle_incomes`, `preview_income_settlement` y
`update_income_settlement`, con confirmación MCP antes de escribir.

`GET/PATCH/DELETE accounting/income-settlements/<uuid>/` consulta, corrige y
revierte el conjunto. Escribir exige la revisión actual. Se conserva el
historial de versiones y los efectos de una operación revertida. El mismo
contrato existe en MCP, además de la compatibilidad de los abonos por ID del
movimiento. Los registros anteriores no se migran a grupos inferidos.
Los datos de demostración conservan sus pagos legados sin agrupar. Los recibos
de operación se crean mediante el escritor real y se validan en las pruebas
del flujo, sin fabricar historial de liquidaciones durante la siembra.

Migraciones aditivas: `content.0293` y `content.0294`; `content.0295_merge_accounting_mcp`
une sus dependencias con la unificación MCP. Las aplica el deploy,
nunca esta sesión contra la base desplegada. Las pruebas utilizan
`projectapp.settings_test`, SQLite y
almacenamiento temporal. No se envían correos reales desde estas pruebas.
