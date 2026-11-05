### FLOW: `admin-procurement-deliveries`

- **Module:** procurement
- **Role:** staff admin
- **Priority:** P2
- **Routes:** `/panel/procurement`
- **Description:** Staff reviews paginated deliveries, attempts, errors and sent snapshots, then confirms retries. Uncertain sends warn to inspect the mailbox; rejected retries retain their dialog.
- **Coverage:** ✅ Covered
- **E2E Spec:** `frontend/e2e/admin/admin-procurement.spec.js` (validado en navegador)
