# Cobro de períodos y pagos de hosting · 26 de noviembre de 2026

| Conector | Versión anterior | Versión actual |
| --- | --- | --- |
| `accounting` | 2.2.0 | 3.0.0 |
| `accounting-billing` | 3.1.0 | 4.0.0 |
| `accounting-ledger` | 3.1.0 | 4.0.0 |

Las escrituras sobre un servicio de hosting conciliado requieren que el cliente del conector envíe la evidencia que revisó. Para emitir una cuenta, consultar `get_project_hosting_inventory` y enviar `period_version` junto con la obligación devuelta en `billing_period`. Si cambian los hechos, volver a consultar antes de solicitar la emisión.

Para imputar dinero, identificar el cobro por su emisor y folio estable o por un asiento existente del mismo servicio. Reutilizar el `request_id` al reintentar un envío. Otro intento que identifique el mismo cobro recupera la imputación original. Para preparar el ingreso siguiente, consultar la propuesta del servicio y confirmar su versión. Las liquidaciones generales siguen el flujo contable de PA-51.

La revisión de períodos, pagos y próximos ingresos se puede reproducir con las [pruebas y el guion de DEV](../MCP_VALIDATION_RUNBOOK.md#contabilidad-de-hosting-pa-296-pa-298-y-pa-299).
