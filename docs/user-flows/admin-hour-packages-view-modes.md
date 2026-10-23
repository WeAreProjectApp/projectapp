### FLOW: `admin-hour-packages-view-modes`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/hour-packages`
- **Description:** Admin alterna tabla, tarjetas y comparativa; consulta cupos y precios por mercado y reconoce el mayor descuento entre paquetes activos.
- **Steps:**
  1. Navegar desde el panel al catálogo o a la pestaña Paquetes de requerimientos de una propuesta.
  2. Revisar cupos por talla y mercado, vigencia, descuento, ahorro y precio más impuestos.
  3. Realizar la acción del flujo; verificar el resultado guardado o el mensaje de error.
- **Branches:** La compra tiene vigencia inicial de 12 meses desde el pago, sin intercambio de tallas. L/XL requieren levantamiento independiente. Configuración permite ajustar cantidades y valores. Alianza tiene cupo mensual separado, no acumulable. Los documentos emitidos y las condiciones históricas no se convierten automáticamente.
- **Coverage:** Ver auditoría y resultados de ejecución de esta rama; la existencia del spec no certifica ejecución.
- **E2E Spec:** `e2e/admin/admin-hour-packages-list.spec.js`
