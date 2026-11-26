# IVA y vencimiento en las cuentas de cobro de Ingresos

| Conector MCP | Versión anterior | Versión nueva |
| --- | --- | --- |
| `accounting` | 2.2.0 | 2.3.0 |
| `accounting-billing` | 3.1.0 | 3.2.0 |

`preview_collection_account` y `create_collection_account` aceptan dos preferencias opcionales.

- `show_vat` controla el desglose de IVA en el correo y en el PDF. Su valor predeterminado es verdadero. Los importes contables se calculan con la tasa del ingreso.
- Con `due_date_mode=dated`, cero días fija el vencimiento en la fecha de emisión en Bogotá. Con `none`, se omiten el plazo y la fecha fija. La cuenta queda sin vencimiento y sin mora por fecha.

Las solicitudes que omiten el modo conservan la regla histórica de cero días sin fecha. Los reenvíos usan el PDF que se archivó al emitir la cuenta. [Reglas y pruebas de Ingresos](../MCP_VALIDATION_RUNBOOK.md#cuenta-de-cobro-preparada-desde-ingresos)
