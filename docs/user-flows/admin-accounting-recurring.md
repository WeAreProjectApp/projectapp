### FLOW: `admin-accounting-recurring`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/recurring`
- **Description:** Recurring operational costs remain normalized to a monthly denominator, but management now happens from each row. **Vigentes** and **Archivados** are separate scopes. In the current scope an inactive payment remains visible for administration but contributes $0 to the monthly COP/USD KPIs, group subtotals, participation percentages and charts; archived rows also stay out of those budget surfaces and out of upcoming-charge notices. The page states that rule next to the scope switch. Both grouped and classic views place the row's leading three-dots action before drag/data columns: detail and history; edit; duplicate; activate/deactivate; mute/reactivate reminders; and archive. Duplicate first GETs a non-persisted draft and opens the ordinary create form with name, price, currency, frequency, method, category and billing day inherited; reminder cadence, notes and archive state are cleared, and the reference date is recalculated from the next occurrence rather than copied. Archive deactivates without deleting and moves the row to Archivados; restore returns it as inactive; permanent deletion appears only there and requires typing `ELIMINAR`. Checkboxes enable atomic bulk activate, deactivate and archive; duplicate stays one-at-a-time. The editable category catalog, drag ordering, custom frequencies, currency conversion, classic view and category chart drill-down remain intact. Charts always use the active budget base and no longer offer an inactive-row toggle. Registering the real expense/pocket movement and a charge-history browser are explicitly deferred to the separate feature that makes a recurring definition an accounting origin. The row menu also offers **Ver nota** right after Detalle e historial when the payment has a note.

#### Interaction matrix

| Interaction | Outcome | Start → action → observable end state |
|---|---|---|
| Inspect current budget | display | Open Recurrentes through the accounting subnav → current rows render → inactive rows show `Inactivo`, 0% participation and do not inflate KPIs/subtotals. |
| Open row actions | display | Click the leading three-dots button → one menu names the row and exposes every action valid for its lifecycle state, starting with Detalle e historial; nothing else shares the 56 px action track. |
| Duplicate | success | Choose Duplicar → review the recalculated prefill → save → a new row is created and the original remains unchanged. |
| Duplicate draft unavailable | failure | Choose Duplicar → draft GET fails → an actionable error appears and no form or record is created. |
| Activate/deactivate | success | Choose the state action → server writes/audits it → row badge, totals, percentages and charts refresh from the active-only base. |
| Mute reminders | success | Choose Silenciar avisos → select a future date or indefinite mode → the row becomes non-notifiable; reopening the menu offers Reactivar avisos. |
| Invalid mute date | error | Choose a date that is empty or not after today → inline validation blocks submission; the API enforces the same rule. |
| Archive and restore | success | Archive + confirm → row leaves Vigentes and appears in Archivados; Restore → it returns to Vigentes as inactive. |
| Permanent delete | error/success | A current row has no delete action; an archived row requires typing `ELIMINAR` before the irreversible request can run. |
| Bulk lifecycle | success | Select visible rows → choose activate/deactivate/archive → review the named selection → one atomic request updates all rows and clears selection. |
| Stale bulk selection | failure | One selected id disappeared or conflicts → the server rejects the whole transaction and the UI reconciles the stale ids without a partial write. |
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-pocket-recurring.spec.js`
