### FLOW: `admin-accounting-hosting-cycles`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`
- **Description:** Desde Ciclos de pago, el operador revisa un ingreso del mismo servicio, elige el asiento ya acreditado o indica emisor y folio. Revisa importe, fecha, destino y vigencia antes de confirmar. El mismo pago vuelve a mostrar su imputación. Un segundo folio permite otro abono del mismo valor. Un ciclo nuevo puede extender la vigencia incluso con pago parcial. El histórico mantiene sus importes y modalidades. Después de confirmar se ofrecen las acciones de documentar el pago y de preparar el siguiente ingreso.
- **E2E Spec:** `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`
