### FLOW: `admin-accounting-hosting-next-income`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`
- **Description:** La fila de Hostings y el resultado de un pago abren el mismo formulario. Muestra cliente, proyecto, servicio, concepto, tarifa y fechas del siguiente período. El calendario parte del período contractual revisado. Confirmar crea un esperado y al reabrir aparece su referencia. Cancelar conserva el pago. Ante una ventana ambigua, datos faltantes o una versión antigua, el formulario muestra la razón del bloqueo.
- **E2E Spec:** `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`
