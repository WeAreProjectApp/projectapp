### FLOW: `admin-accounting-income-bulk-settle`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Route:** `/panel/accounting/incomes`
- **Description:** La selección muestra total original y pendiente. Liquidar abre el mismo modal que la acción individual, con participaciones globales, diferencia e IVA configurable por ingreso.
- **Success:** Cobertura por antigüedad, reparto manual o automático, deducciones proporcionales, saldo pendiente o reprogramado con origen, cero recibido con ajustes y excedente como saldo a favor del mismo cliente. Una vista previa precede el registro; los correos elegibles se revisan dentro del modal.
- **Error:** Bloquea distribuciones excesivas, valores negativos, líneas incompletas, períodos incompletos, participación excesiva y excedente con clientes mezclados. El IVA activado requiere porcentaje válido. Pagos, deducciones o cuentas emitidas bloquean su cambio de tasa, sin impedir registrar el pago. Explica por qué no puede enviar una confirmación.
- **Failure:** Un rechazo de vista previa conserva el formulario. Un conflicto al registrar conserva los datos para volver a revisar. El fallo de correo no deshace el abono.
- **Display:** Un único diálogo con lista, valor recibido, fecha, destino y resumen. Cada ingreso muestra un switch junto a IVA antes de expandir: apagar significa Sin IVA (0 %). La configuración permite capturar base o total incluido y ver base, IVA y total; distingue Sin registrar. Diferencia se abre al faltar dinero. El pie de acciones tiene padding propio. Móvil, tableta vertical y escritorio conservan acciones y contenido alcanzables.
- **Coverage:** Las cuatro clases de resultado tienen recorridos focales; los cinco perfiles de pantalla verifican el modal con IVA expandido. La ruta individual comparte el mismo modal.
- **E2E Spec:** `e2e/admin/admin-accounting-income-bulk-settle.spec.js`

El detalle del bolsillo conserva los importes imputados y los saldos actuales; desde el pago de un ingreso se puede consultar el reparto del abono entre sus ingresos de origen.

Cambiar únicamente entre base y total incluido conserva los centavos recibidos y el reparto automático. Editar el porcentaje en modo total incluido permite seguir ajustando el valor recibido sin conservar una captura desactualizada.
