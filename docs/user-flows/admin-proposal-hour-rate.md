### FLOW: `admin-proposal-hour-rate`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/hour-packages` y `/panel/proposals/:id/edit?tab=hour-rate`
- **Description:** Admin revisa composición y precios del catálogo o edita paquetes manuales para una propuesta. Puede ocultarlos del PDF y adoptar explícitamente la oferta nueva en un borrador histórico; los precios emitidos quedan congelados hasta preparar una revisión.
- **Steps:**
  1. Navegar desde el panel al catálogo o a la pestaña Paquetes de requerimientos de una propuesta.
  2. Revisar cupos por talla y mercado, vigencia, descuento, ahorro y precio más impuestos.
  3. Realizar la acción del flujo; verificar el resultado guardado o el mensaje de error.
- **Branches:** La compra tiene vigencia inicial de 12 meses desde el pago, sin intercambio de tallas. L/XL requieren levantamiento independiente. Configuración permite ajustar cantidades y valores. Alianza tiene cupo mensual separado, no acumulable. Los documentos emitidos y las condiciones históricas no se convierten automáticamente.
- **Coverage:** Ver auditoría y resultados de ejecución de esta rama; la existencia del spec no certifica ejecución.
- **E2E Spec:** `e2e/admin/admin-proposal-hour-rate.spec.js`
