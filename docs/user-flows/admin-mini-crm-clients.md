### FLOW: `admin-mini-crm-clients`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** View a Mini-CRM client list with client-status filtering (Todos/Activos/Huérfanos/Inactivos), search, expand client to see linked proposals, and empty state. Since the filters were reorganised by business module (Ago 2026) the status is a **transversal selector next to the search box**, not the top tab row — it qualifies the register itself and combines with any module. The orphan filter counts proposals, projects, diagnostics AND accounting incomes and hostings (a client with only a diagnostic, an income or a hosting is NOT orphan); inactive (manually deactivated) clients are hidden from Todos/Activos/Huérfanos.
- **Steps:**
  1. Admin navigates to `/panel/clients/`.
  2. Client list loads from `GET /api/proposals/client-profiles/`, and the per-status counts from `GET /api/proposals/client-profiles/status-counts/`.
  3. Clients render with name, email, proposal count, and orphan/placeholder/inactive badges.
  4. Admin uses the status selector (data-testid: `clients-status-<id>`), labelled with each option's count — sends `?orphans=true/false` / `?inactive=true` and mirrors the choice in `?status=`.
  5. Admin searches clients by full name, email, or company. Rows and status counts publish together for the latest query; obsolete responses are ignored. No matches clears the cards and pagination; a failed load shows a retry action instead of stale results.
  6. Admin expands a client row to view individual proposals (lazy-loaded via `GET /api/proposals/client-profiles/:id/`).
  7. Pressing the global panel refresh button invalidates the per-client detail cache and refetches expanded rows, so renamed/reassigned proposals show up.
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-mini-crm-clients.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py`
- **Known gaps:** No E2E asserts that the refresh button re-fetches an already-expanded client's proposals (the cache-invalidation fix for stale rename/reassignment); see also `admin-proposal-delete-from-client`.
