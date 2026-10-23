### FLOW: `admin-hour-packages-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/hour-packages`
- **Description:** Admin crea un paquete por mercado con nombres y notas bilingües, cupos enteros XS/S/M, vigencia, descuento, orden y activación; revisa la vista previa y errores de validación o guardado.
- **Steps:**
  1. Navegar desde el panel al catálogo o a la pestaña Paquetes de requerimientos de una propuesta.
  2. Revisar cupos por talla y mercado, vigencia, descuento, ahorro y precio más impuestos.
  3. Realizar la acción del flujo; verificar el resultado guardado o el mensaje de error.
- **Branches:** La compra tiene vigencia inicial de 12 meses desde el pago, sin intercambio de tallas. L/XL requieren levantamiento independiente. Configuración permite ajustar cantidades y valores. Alianza tiene cupo mensual separado, no acumulable. Los documentos emitidos y las condiciones históricas no se convierten automáticamente.
- **Coverage:** Ver auditoría y resultados de ejecución de esta rama; la existencia del spec no certifica ejecución.
- **E2E Spec:** `e2e/admin/admin-hour-packages-create.spec.js`
