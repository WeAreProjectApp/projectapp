### FLOW: `admin-accounting-history-diagnosis`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/history`
- **Description:** The history exists to diagnose, so a row shows what was sent and can send it again. **Ver el correo:** `GET /api/accounting/email-log/<id>/body/` returns the message as delivered (stored once per send in `EmailBody`, shared by the sibling recipient rows) and the panel renders it in a sandboxed `srcdoc` iframe, the same way the composer previews a branded email; sends predating the feature say so instead of opening an empty modal. **Reintentar:** `POST /api/accounting/email-log/<id>/retry/` re-sends to the address on that row and to no one else, only for the notices tied to a single record (`accounting_change`, `collection_account_sent`, `payment_status_team`). The three digests show the menu entry disabled carrying its reason — re-running one would assemble today's summary, not the message that failed. That reason remains reachable through a focusable accessible proxy and one application tooltip, without a duplicate native `title`. The retry lands as a new row linked through `retry_of`, and a retry that fails again reports its cause. Both actions live in the row's leading three-dots menu, which only appears on a send that has one; opening it never expands the row.
- **Steps:**
  1. Superuser opens the Envíos subtab and clicks the eye on a row → the delivered message opens in a modal.
  2. On a failed row, the retry icon re-sends to that recipient; the list and its counts reload so the new attempt is visible.
  3. A failed digest shows the retry disabled, with its reason visible under the label. A send that worked offers no retry at all.
  4. Expanding a row names the records the email was about and, when applicable, the send it was a retry of.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-history-filters.spec.js`
