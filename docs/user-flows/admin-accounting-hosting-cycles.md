### FLOW: `admin-accounting-hosting-cycles`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`
- **Description:** Cycle payment history per hosting (row menu «Ciclos de pago» → `HostingCyclesModal`): historical modality/amount snapshots remain immutable, while the register form offers quarterly, semiannual and every-9-month cycles and prefills the current contract amount/modality. "Extender vigencia" advances one current modality period. `total_paid`/`cycles_count` recompute from history; deleting a cycle recalculates but never rolls back `valid_to`.
- **Coverage:** ✅ Covered (backfill badge history, register payment with advance_validity, delete with confirm)
- **E2E Spec:** `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`
