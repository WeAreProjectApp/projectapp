### FLOW: `admin-accounting-income-bulk-settle`
- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/accounting/incomes`, `/panel/accounting/pocket`
- **API:** `POST /api/accounting/incomes/bulk-settle/`, `GET /api/accounting/incomes/:id/detail/`, `GET /api/accounting/incomes/`, `GET /api/accounting/pocket/`
- **Description:** La selección muestra valor total y saldo pendiente. Liquidar aplica a uno o varios esperados de empresa con saldo, sin exigir cuenta emitida. El modal propone el reparto del más antiguo al más reciente y permite ajustes manuales; un único movimiento conserva los pagos completos, parciales y el saldo a favor. Sólo al elegir un ingreso ofrece Liquidación con ajustes, que confirma la apertura de un formulario nuevo. Al completar sin cuenta emitida aparece Cuenta pendiente de emitir. El reparto puede consultarse desde ingreso y bolsillo; borrar el movimiento deshace el abono completo.
- **Steps:** seleccionar esperados → Liquidar → revisar/ajustar el reparto → confirmar → filas Pagado/Parcial en la lista, un movimiento en el bolsillo.
- **Branches:** el reparto se consulta también desde el ingreso; valor menor deja el último parcial; valor exacto cubre todo sin tipear; excedente anuncia el saldo a favor; excedente con mezcla de clientes bloquea; 400 del backend deja el modal abierto; el reparto se consulta desde el movimiento del bolsillo.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-income-bulk-settle.spec.js`

## Formulario compacto (2026-10-09)

El modal de abono usa el ancho de formulario (42 rem). Valor recibido y fecha comparten fila, y el destino (Bolsillo ProjectApp) se lee debajo de ella en lugar de ocupar una fila propia.

## Liquidación y cuenta pendiente (2026-10-10)

La selección muestra valor total y saldo pendiente. Liquidar aplica a uno o varios esperados de empresa con saldo, sin exigir cuenta emitida. El modal propone el reparto del más antiguo al más reciente y admite ajustes manuales. Un único movimiento cubre pagos completos y parciales, con saldo a favor cuando corresponde. Sólo para uno ofrece Liquidación con ajustes: el aviso confirma que se abrirá un formulario nuevo sin trasladar valores. Al completar sin cuenta, la fila muestra Cuenta pendiente de emitir. Las validaciones, fallos de servidor, consulta del reparto y reversa completa conservan su comportamiento.
