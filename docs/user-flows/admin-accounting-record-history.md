### FLOW: `admin-accounting-record-history`

- **Module:** admin
- **Role:** superuser
- **Priority:** P1
- **Routes:** `/panel/accounting`
- **Description:** Abre Detalle e historial o Ver historial de cambios desde ingresos, gastos, hosting, recurrentes, bolsillo, Ads, tarjetas, extractos, movimientos, alias, destinatarios, cuentas de cobro y configuración. En todas las tablas y listas contables, Detalle e historial es la primera opción del menú de tres puntos de la fila (en ingresos y cuentas de cobro abre su detalle, que incluye el historial): la columna de acciones mide 56 px y sólo aloja ese botón.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar el historial propio del registro contable y comparar los valores de dos versiones seleccionadas.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Display, success y failure validados en `admin/admin-entity-history.spec.js`; los trece tipos contables tienen cobertura de escritura en backend.
