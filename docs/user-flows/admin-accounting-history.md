### FLOW: `admin-accounting-history`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/history`
- **Description:** Read-only audit of the module through two tabs (BaseSegmented). **Cambios:** audit trail (server-paginated 20/page) of every accounting change with entity/action/actor/record/date filters and expandable field-level old→new diffs. **Envíos** (Ago 2026): send log (`GET /api/accounting/email-log/`, 20/page) with one row per destination address — fecha, tipo de aviso, destinatario, asunto y estado — filterable by notice type, status, recipient, subject text, source record, client, project and date range; clicking a failed row expands the delivery error, the records the email was about and any retry link. This is the surface that answers "¿por qué no me llegó ese aviso?" and is scoped to the module's own `template_key`s, so proposal traffic sharing the `EmailLog` table stays out. Both subtabs carry the predefined tab strip and URL-persisted filters (`admin-accounting-history-filters`) and a send row can be read and retried (`admin-accounting-history-diagnosis`).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-ads-history-settings.spec.js`

## Liquidación y cuenta pendiente (2026-10-10)

Envíos incluye Ingreso completo — cuenta pendiente, con el ingreso objetivo, destinatarios y estado real de entrega. El aviso interno se crea una vez por ingreso al completarlo sin cuenta emitida.
