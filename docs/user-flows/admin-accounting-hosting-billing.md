### FLOW: `admin-accounting-hosting-billing`

**Panel · Contabilidad · Hostings** · Superusuario · P1 · `/panel/accounting/hostings`

1. Abre el menú de la fila y elige «Enviar cuenta de cobro». Si falta correo, el menú indica cómo completarlo.
2. El diálogo identifica el proyecto, cliente, hosting y destinatario de esa fila. El resumen compartido con Ingresos muestra origen, fechas, valor, recibido, saldo y documentos del período. Ingresos conserva la selección del servicio. Las diferencias de identidad o de período impiden confirmar y orientan la corrección. Al volver de conciliación se consulta la fila de nuevo.
3. «Cancelar» o Escape cierran el diálogo y conservan el estado del servicio. «Enviar al cliente» envía al escritor de la fila la referencia del pago y la versión revisada. Si cambió el período, hay que revisarlo de nuevo.
4. Una emisión confirmada envía el PDF al destinatario y pausa los avisos hasta la próxima renovación. La fila muestra «Cobro enviado». Si falla el correo, el aviso identifica la cuenta emitida y permite continuar desde Cuentas de cobro.

Pruebas de navegador en `e2e/admin/admin-accounting-hosting-row-context.spec.js` y `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`.
