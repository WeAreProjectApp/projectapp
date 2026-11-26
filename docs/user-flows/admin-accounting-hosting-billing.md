### FLOW: `admin-accounting-hosting-billing`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/hostings`
- **Description:** Desde la fila de Hostings, el operador revisa el servicio, el período inclusivo, el valor, lo recibido, el saldo y el documento existente. Ingresos consulta la misma versión. Confirmar emite la cuenta y envía el PDF. Un conflicto o una versión desactualizada exige volver a revisar. Si falla el correo, la cuenta emitida se puede reenviar.
- **E2E Spec:** `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`
