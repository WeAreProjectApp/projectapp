### FLOW: `admin-accounting-ads`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P3
- **Routes:** `/panel/accounting/ads`
- **Description:** Advertising spend log with a running accumulated column computed over the full history, platform/card filters and modal CRUD. Row actions live behind the leading three-dots button (first column, no visible header): its menu offers **Detalle e historial**, **Ver nota** when the record has a note, **Editar** and **Eliminar** (with confirmation).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-ads-history-settings.spec.js`
