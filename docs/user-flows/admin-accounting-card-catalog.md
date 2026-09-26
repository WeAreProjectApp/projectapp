### FLOW: `admin-accounting-card-catalog`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/settings`
- **Description:** (Jul 2026) "Catálogo de tarjetas" section inside accounting settings: CRUD over the CreditCard catalog (name, cupo/credit_limit, "extractos desde" month, active toggle) that feeds the Tarjetas form dropdown, the server-side debt computation (cupo − disponible) and the Extractos year/month range. Seeded with T.C 0064 (cupo 8.000.000, extractos desde 2026-05). Delete is blocked with a Spanish error when snapshots/statements reference the card name (deactivate instead). Changes are audited as the `credit_card` entity (visible in Historial).
- **Steps:**
  1. Superuser opens `/panel/accounting/settings` — the section lists catalog rows (GET `/api/accounting/credit-cards/`).
  2. "Agregar tarjeta" appends an empty row; per-row Guardar POSTs `/api/accounting/credit-cards/create/` (or PATCHes `.../update/` for existing rows).
  3. Editing the cupo changes future snapshot computations only (historic debts untouched).
  4. A saved card leads with a three-dots menu (Detalle e historial fed with the stored card, Ver nota, Eliminar) and Eliminar asks for confirmation — an unsaved draft only discards inline; DELETE `.../delete/` returns `credit_card_referenced` (400) when history references the name.
- **Coverage:** ✅ Covered (list, draft-row create, cupo patch, reference-blocked delete with Spanish error)
- **E2E Spec:** `e2e/admin/admin-accounting-statements-card-catalog.spec.js`
