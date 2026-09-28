# User Flow Map

> **Version:** 2.41.0
> **Last updated:** 2026-08-16
> **Scope:** Complete map of end-to-end user navigation flows for projectapp, organized by role.
> **Sources:** Frontend pages (`frontend/pages/`), backend API endpoints (`content/urls.py`, `accounts/urls.py`), route rules (`nuxt.config.ts`).

---
## Table of Contents


1. [Roles](#1-roles)
2. [Conventions](#2-conventions)
3. [Shared Flows (Guest + Admin)](#3-shared-flows-guest--admin)
4. [Guest Flows](#4-guest-flows)
5. [Proposal Flows (Guest via UUID)](#5-proposal-flows-guest-via-uuid)
6. [Admin Flows](#6-admin-flows)
7. [E2E Coverage Index](#7-e2e-coverage-index)
8. [Platform Flows](#8-platform-flows)

---

## 1. Roles


| Role | Description | Auth Required |
|------|-------------|---------------|
| **Guest** | Unauthenticated visitor browsing the public site | No |
| **Admin** | Staff user managing content via the `/panel/` admin frontend | Yes (Django session) |
| **Platform-Admin** | Staff user managing clients, projects and kanban via `/platform/` | Yes (JWT) |
| **Platform-Client** | Invited client accessing their projects via `/platform/` | Yes (JWT) |

> **Excluded:** Django Admin (`/admin/`) is managed by Django's built-in admin interface and is not covered by E2E tests.

---

## 2. Conventions


### Flow ID Format

- **Kebab-case**, prefixed with module name: `public-home`, `blog-list`, `proposal-view`, `admin-blog-create`
- Cross-role flows use `cross-` infix (not applicable in this project currently)

### Priority Levels

| Level | Meaning | Criteria |
|-------|---------|----------|
| **P1** | Critical | Core business flow — blocks release if missing |
| **P2** | High | Important feature — should be covered before release |
| **P3** | Medium | Secondary feature — cover after P1/P2 |
| **P4** | Nice-to-have | Informational pages, low risk |

### Coverage Statuses

| Status | Symbol | Meaning |
|--------|--------|---------|
| Covered | ✅ | E2E spec exists and passes |
| Partial | ⚠️ | E2E spec exists but has known gaps |
| Missing | ❌ | No E2E spec yet |

### Branch Notation

- **[Branch A]** / **[Branch B]** — Alternative outcomes within a flow
- **[Optional]** — Step that may or may not occur

### E2E scope decisions (audit follow-up)

- **TechnicalDocumentEditor (panel):** No dedicated flow ID. Scope remains within `admin-proposal-edit` and `admin-proposal-defaults-config`; client-facing technical reading is covered by `proposal-technical-view`.
- **Panel sidebar (collapse / mobile drawer):** No dedicated flow ID. Exercised indirectly by specs that load `/panel` routes using the admin layout.

### Backend-only and system-triggered flows (not browser E2E)

Entries in `flow-definitions.json` with `roles: ["system"]` and `expectedSpecs: 0` describe **automations** (Huey/cron, alert generation, digests). They remain in the registry for traceability to backend tests but are **out of scope** for Playwright user-journey coverage. Examples: `proposal-pre-expiration-discount-suggestion`, `admin-seller-inactivity-escalation`, `admin-daily-pipeline-digest`, `admin-high-engagement-alert`, `admin-calculator-followup-alert`, `admin-whatsapp-suggestion`, `admin-auto-archive-zombie`, `admin-proposal-engagement-decay-alert`, `admin-proposal-post-rejection-revisit`, `proposal-calculator-abandonment-tracking`.

---

## 8. Platform Flows


> Platform flows cover the `/platform/` section of the application — a JWT-authenticated portal for **platform-admin** and **platform-client** roles. Backend API is served from `accounts/urls.py` under `/api/accounts/`.

### 8.1 Authentication & Onboarding

#### FLOW: `platform-login`

- **Módulo:** platform · **Roles:** platform-admin / platform-client · **Prioridad:** P1
- **Ruta:** `/platform/login` · **API:** `POST /api/accounts/login/`.
- **Recorrido:** escribir email y contraseña, completar reCAPTCHA v2 y enviar.
- **Success:** JWT para usuarios activos; documentos para clientes, dashboard
  para administradores, completar perfil si corresponde; el primer acceso
  envía OTP y navega a verificación sólo después de validar CAPTCHA.
- **Error:** CAPTCHA inválido/expirado o credenciales incorrectas muestran un
  mensaje y requieren una verificación nueva. El botón permanece bloqueado
  mientras falta token o hay un envío en curso.
- **Failure:** script bloqueado, timeout o respuesta inválida de Google bloquean
  el acceso con Reintentar. No hay fallback sin CAPTCHA.
- **Display:** el formulario conserva email y contraseña; el widget informa
  carga, necesidad de verificación, expiración o indisponibilidad.
- **E2E:** `e2e/platform/platform-login.spec.js` conserva las regresiones de
  navegación; `e2e/captcha/platform-login-captcha.spec.js` usa Django real y base
  temporal con el proveedor simulado para éxito, errores y recuperación.

#### FLOW: `platform-verify-onboarding`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P1
- **Routes:** `/platform/verify`
- **API:** `POST /api/accounts/verify/`, `POST /api/accounts/resend-code/`
- **Description:** First-login OTP verification with 6-digit code input, new password set, and redirect based on profile completion.
- **Steps:**
  1. User lands on `/platform/verify` after first login redirect.
  2. Page renders 6-digit code input fields and new password + confirm password fields.
  3. User enters the OTP code received via email.
  4. User sets a new permanent password.
  5. User submits verification form.
  6. API validates OTP, sets password, marks user as onboarded, returns JWT tokens.
- **Branches:**
  - [Branch A — Profile incomplete] User is redirected to `/platform/complete-profile`.
  - [Branch B — Profile complete] User is redirected to `/platform/dashboard`.
  - [Branch C — Invalid code] API returns 400 → error message displayed.
  - [Branch D — Resend code] User clicks "Reenviar código" → `POST /api/accounts/resend-code/` sends new OTP.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-verify.spec.js`

#### FLOW: `platform-complete-profile`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P1
- **Routes:** `/platform/complete-profile`
- **API:** `POST /api/accounts/me/complete-profile/`
- **Description:** Mandatory profile completion form with personal data and optional avatar upload. Middleware gates dashboard access until completed.
- **Steps:**
  1. User lands on `/platform/complete-profile` after verification or login redirect.
  2. Form renders with fields: first name, last name, company name, phone, cédula, date of birth, gender, education level.
  3. User optionally uploads an avatar image (preview displayed).
  4. User fills all required fields and submits.
  5. API sets `profile_completed = true` and saves all fields.
  6. User is redirected to `/platform/dashboard`.
- **Branches:**
  - [Branch A — Validation error] API returns errors → displayed inline under form.
  - [Branch B — Already completed] API returns 400 "El perfil ya fue completado." → user should be on dashboard already.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-complete-profile.spec.js`

### 8.2 Dashboard & Navigation

#### FLOW: `platform-dashboard`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/dashboard` (also `/platform` which redirects here)
- **API:** `GET /api/accounts/me/`, `GET /api/accounts/clients/`, `GET /api/accounts/projects/`
- **Description:** Main landing page after login. Content differs by role.
- **Steps:**
  1. User navigates to `/platform/dashboard`.
  2. Welcome message renders with user's first name.
  3. Page fetches data from API.
- **Branches:**
  - [Branch A — Admin] KPI stat cards render (active/pending/inactive clients). Recent clients table renders with status badges. Module cards link to Projects, Board, Clients.
  - [Branch B — Client] Profile summary card renders. Module cards link to Projects, Board.
  - [Branch C — Redirect] Navigating to `/platform` auto-redirects to `/platform/dashboard`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-dashboard.spec.js`

#### FLOW: `platform-sidebar-navigation`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** All `/platform/*` pages
- **Description:** Left sidebar layout with collapsible navigation, mobile drawer, theme toggle, and logout.
- **Steps:**
  1. User sees left sidebar with logo, navigation sections (Principal, Proyectos, Administración), and user footer.
  2. User clicks a navigation item → page navigates to the selected route.
  3. Active route is highlighted in the sidebar.
- **Branches:**
  - [Branch A — Collapse/Expand] User clicks collapse button → sidebar shrinks to 64px icon-only mode. Click again to expand.
  - [Branch B — Mobile] Screen < md → hamburger button in top bar opens `PlatformMobileDrawer` overlay with full navigation.
  - [Branch C — Theme toggle] User clicks theme button → toggles light/dark mode across all platform pages.
  - [Branch D — Logout] User clicks logout button → `authStore.logout()` clears tokens → redirected to `/platform/login`.
  - [Branch E — Admin-only items] Admin sees "Clientes" and "Pagos" nav items under Administración section; client does not.
  - [Branch F — Profile link] User clicks settings icon → navigates to `/platform/profile`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-sidebar.spec.js`

### 8.3 Projects

#### FLOW: `platform-project-list`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/projects`
- **API:** `GET /api/accounts/projects/`, `POST /api/accounts/projects/`
- **Description:** Project listing with catalog-derived state filters and role-based views.
- **Steps:**
  1. User navigates to `/platform/projects`.
  2. API fetches projects (admin: all; client: own projects only).
  3. Project cards render in a grid with name, client, status badge, progress bar, and dates.
  4. User clicks a project card → navigates to `/platform/projects/:id`.
- **Branches:**
  - [Branch A — Admin filters] Admin sees Todos plus the states present in the returned projects (including Suspendido when applicable) and filters the loaded rows by canonical state id.
  - [Branch B — Admin create] Admin clicks "Nuevo proyecto" → create project modal opens (see `platform-admin-project-create`).
  - [Branch C — Empty state] No projects → empty state message renders.
  - [Branch D — Client view] Client sees only their assigned projects without create button.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-project-list.spec.js`

#### FLOW: `platform-project-detail`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id`
- **API:** `GET /api/accounts/projects/:id/`, `PATCH /api/accounts/projects/:id/`
- **Description:** Project detail hub with stats row, module cards, and admin edit modal.
- **Steps:**
  1. User navigates to `/platform/projects/:id` (or clicks a project card).
  2. Back link to `/platform/projects` renders.
  3. Project header renders with name, status badge, and description.
  4. Stats row renders: progress %, client info, start date, estimated end date (with days remaining).
  5. Module cards render: "Tablero" (active link to board), plus coming-soon placeholders (Solicitudes, Bugs, Entregables).
- **Branches:**
  - [Branch A — Admin edit] Admin clicks "Editar" → modal opens with name, description, status, start/end dates → submit calls `PATCH` API → modal closes and data refreshes.
  - [Branch B — Not found] Invalid project ID → "Proyecto no encontrado" with back link.
  - [Branch C — Board link] User clicks "Tablero" module card → navigates to `/platform/projects/:id/board`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-project-detail.spec.js`

#### FLOW: `platform-admin-project-create`

- **Module:** platform
- **Role:** platform-admin
- **Priority:** P3
- **Routes:** `/platform/projects` (modal)
- **API:** `POST /api/accounts/projects/`
- **Description:** Admin creates a new project via modal form.
- **Steps:**
  1. Admin clicks "Nuevo proyecto" button on projects list page.
  2. Modal opens with form fields: name, description, client selector, start date, estimated end date.
  3. Admin fills required fields and submits.
  4. API creates project and returns details.
  5. Modal closes and project list refreshes with the new project.
- **Branches:**
  - [Branch A — Validation error] Missing required fields → error displayed.
  - [Branch B — Cancel] Admin clicks cancel or outside modal → modal closes without action.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-project-create.spec.js`

### 8.4 Kanban Board

#### FLOW: `platform-kanban-board`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P1
- **Routes:** `/platform/projects/:id/board`
- **API:** `GET /api/accounts/projects/:id/deliverables/`, `GET|POST /api/accounts/projects/:projectId/deliverables/:deliverableId/requirements/`, `POST .../requirements/:id/move/`, `GET .../requirements/:id/` (requirements are scoped to a deliverable).
- **Description:** 3-column kanban board with drag & drop, card detail modal, and completed checklist.
- **Steps:**
  1. User navigates to `/platform/projects/:id/board`.
  2. Back link to project detail renders with project name.
  3. Progress pill renders with percentage and completed count.
  4. Three kanban columns render: "Por hacer" (todo), "En progreso" (in_progress), "En revisión" (in_review).
  5. Requirement cards render in their respective columns with priority dot, scope-item label (the vista/componente/funcionalidad from the proposal; falls back to the legacy "Módulo"/epic for older cards), title, and comment count.
  6. Collapsible "Completados" section renders below columns with done cards as a checklist.
- **Branches:**
  - [Branch A — Admin drag & drop] Admin drags a card from one column to another → `POST .../move/` API updates status → card moves to target column.
  - [Branch B — Admin create card] Admin clicks "Card" button → create modal opens with title, description, priority, column, module, hours → submit creates requirement.
  - [Branch C — Complete card] Admin (or client for in_review) clicks checkmark → card moves to "done" column.
  - [Branch D — Card detail] User clicks any card → detail modal opens showing description, meta (status, scope item, created date), history timeline, and comments section.
  - [Branch E — Client approval] Client sees "Aprobar requerimiento" button for cards in approval status → clicking approves and moves to done.
  - [Branch F — Toggle completed] User clicks "Completados" bar → expands/collapses the done cards list.
  - [Branch G — Scope filter] User picks a vista/componente/funcionalidad (or "Sin agrupar") from the "Alcance" selector → columns and backlog show only cards linked to that scope item. Populated from `GET /api/accounts/projects/:id/scope-items/`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-kanban-board.spec.js`
- **Related:** Scope items and cards are auto-created on proposal acceptance — see `platform-proposal-auto-onboarding`.

#### FLOW: `platform-proposal-auto-onboarding` *(system-triggered, no browser E2E)*

- **Module:** platform
- **Role:** system
- **Priority:** P1
- **Trigger:** A `BusinessProposal` transitions to `accepted` — client response (`respond_to_proposal`) or admin inline (`update_proposal_status`).
- **Description:** Async onboarding provisions the client's platform project so it reflects the accepted proposal. Idempotent (runs once, guarded by `platform_onboarding_completed_at`); the manual "Lanzar a Plataforma" button remains as a re-sync/fallback.
- **Steps (backend):**
  1. Acceptance enqueues `run_platform_onboarding` (with the task's acceptance email suppressed; the view owns the client email).
  2. `handle_proposal_accepted_for_platform` ensures the client `User`, `Project`, root `Deliverable`, and (via the sync) a `ProjectPhase`.
  3. `functional_requirements` items (vistas/componentes/funcionalidades) are mirrored as `ProjectScopeItem` rows keyed by `source_item_id`.
  4. `technical_document` epics/requirements are upserted as Kanban `Requirement` cards keyed by `(phase, source_flow_key)`, each linked to its primary scope item via `linked_item_ids`.
- **Re-sync policy:** preserves client-owned state (`status`, `order`, comments); overwrites proposal-authored content unless the card was manually edited (`content_overridden`); archives scope items removed from the proposal and resurrects re-added ones.
- **Coverage:** Backend tests (`accounts/tests/test_proposal_scope_sync.py`, `test_proposal_platform_onboarding.py`, `content/tests/views/test_proposal_status_and_pdf.py`). No Playwright journey (`roles: ["system"]`, `expectedSpecs: 0`).

#### FLOW: `platform-unified-board`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/board`
- **API:** `GET /api/accounts/projects/`, then per deliverable `GET .../deliverables/:deliverableId/requirements/`
- **Description:** Cross-project view showing active requirement cards grouped by project.
- **Steps:**
  1. User navigates to `/platform/board`.
  2. Page fetches all projects and their active requirements.
  3. Cards render grouped by project with project name headers and summary pills (todo/in_progress/in_review counts).
  4. Each card shows priority dot, title, and module tag.
- **Branches:**
  - [Branch A — Project link] User clicks project name → navigates to `/platform/projects/:id`.
  - [Branch B — Board link] User clicks "Ver tablero" → navigates to `/platform/projects/:id/board`.
  - [Branch C — Empty state] No active requirements → empty state message.
  - [Branch D — Loading] Skeleton/spinner renders while fetching data.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-unified-board.spec.js`

#### FLOW: `platform-kanban-card-comments`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P3
- **Routes:** `/platform/projects/:id/board` (card detail modal)
- **API:** `POST /api/accounts/projects/:projectId/deliverables/:deliverableId/requirements/:id/comments/`
- **Description:** Add public or internal (admin-only) comments on requirement cards.
- **Steps:**
  1. User opens card detail modal (from kanban board flow).
  2. Comments section renders with existing comments (author, date, content).
  3. User types a comment in the input field and clicks "Enviar".
  4. API creates the comment and it appears in the list.
- **Branches:**
  - [Branch A — Internal comment] Admin checks "Comentario interno" checkbox → comment saves with `is_internal: true` → rendered with amber border and "Interno" label (only visible to admins).
  - [Branch B — Client comment] Client can only post public comments (no internal checkbox visible).
  - [Branch C — Empty comment] Submit button disabled when input is empty.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-kanban-comments.spec.js`

### 8.5 Client Management (Admin-only)

#### FLOW: `platform-admin-client-list`

- **Module:** platform
- **Role:** platform-admin
- **Priority:** P2
- **Routes:** `/platform/clients`
- **API:** `GET /api/accounts/clients/`, `POST /api/accounts/clients/`, `POST /api/accounts/clients/:id/resend-invite/`, `DELETE /api/accounts/clients/:id/`
- **Description:** Admin-only client management table with invite, search, filter, and action capabilities.
- **Steps:**
  1. Admin navigates to `/platform/clients`.
  2. Client table renders with columns: client (avatar + name + email), company, status badge, created date, actions.
  3. Status filter tabs render: Todos, Onboarded, Pendientes, Inactivos.
  4. Search input filters clients by name, email, or company.
- **Branches:**
  - [Branch A — Invite client] Admin clicks "Invitar cliente" → modal opens with email, first name, last name, company, phone fields → submit calls `POST /api/accounts/clients/` → creates client + sends invitation email → success message.
  - [Branch B — Resend invite] Admin clicks "Reenviar" on a client row → `POST .../resend-invite/` → success/error message.
  - [Branch C — Deactivate] Admin clicks "Desactivar" → confirm modal → `DELETE /api/accounts/clients/:id/` → client deactivated.
  - [Branch D — Detail link] Admin clicks "Detalle" → navigates to `/platform/clients/:id`.
  - [Branch E — Filter by status] Admin clicks status tab → API refetches with `?filter=` param.
  - [Branch F — Search] Admin types in search → client-side filtering of visible results.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-admin-client-list.spec.js`

#### FLOW: `platform-admin-client-detail`

- **Module:** platform
- **Role:** platform-admin
- **Priority:** P2
- **Routes:** `/platform/clients/:id`
- **API:** `GET /api/accounts/clients/:id/`, `PATCH /api/accounts/clients/:id/`, `DELETE /api/accounts/clients/:id/`, `POST /api/accounts/clients/:id/resend-invite/`
- **Description:** Admin-only client detail page with profile card, edit form, and quick actions.
- **Steps:**
  1. Admin navigates to `/platform/clients/:id`.
  2. Back link to `/platform/clients` renders.
  3. Left column: profile card (avatar, name, email, company, phone, status, created date) + quick actions section.
  4. Right column: edit form (first name, last name, email disabled, company, phone, active toggle).
- **Branches:**
  - [Branch A — Save changes] Admin edits fields and clicks "Guardar cambios" → `PATCH` API updates client → success message.
  - [Branch B — Reset form] Admin clicks "Restablecer" → form reverts to server values.
  - [Branch C — Resend invite] Admin clicks "Reenviar invitación" → API resends → success/error message.
  - [Branch D — Deactivate] Admin clicks "Desactivar acceso" → confirm modal → `DELETE` API deactivates → success message.
  - [Branch E — Reactivate] For inactive clients, admin clicks "Reactivar acceso" → `PATCH` with `is_active: true` → success message.
  - [Branch F — Not found] Invalid client ID → "No encontramos el cliente solicitado" message.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-admin-client-detail.spec.js`

### 8.6 Profile

#### FLOW: `platform-profile-edit`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/profile`
- **API:** `GET /api/accounts/me/`, `PATCH /api/accounts/me/`
- **Description:** View and update personal profile fields with avatar display and role badge.
- **Steps:**
  1. User navigates to `/platform/profile` (via sidebar settings icon).
  2. Profile page renders with avatar, name, role badge, and editable form fields (first name, last name, company, phone, cédula, DOB, gender, education).
  3. User modifies fields and clicks "Guardar cambios".
  4. `PATCH /api/accounts/me/` updates profile.
  5. Success feedback displayed.
- **Branches:**
  - [Branch A — Validation error] Invalid input → API returns errors → displayed inline.
  - [Branch B — Cancel] User navigates away without saving → no changes persisted.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-profile.spec.js`

#### FLOW: `platform-profile-avatar-picker`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/profile`
- **Description:** Open the native image picker from the accessible avatar action without changing the single-image upload contract.
- **Steps:**
  1. User navigates to `/platform/profile`.
  2. User activates “Cambiar foto de perfil”.
  3. The browser opens a single-file chooser restricted to `image/*`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-profile.spec.js`

### 8.7 Change Requests, Bug Reports & Deliverables

#### FLOW: `platform-change-requests`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/changes`, `/platform/changes`
- **API:** `GET/POST /api/accounts/projects/:id/change-requests/`, `POST .../evaluate/`, `POST .../comments/`
- **Description:** Client creates change requests for a project. Admin evaluates (approve/reject/needs clarification) with estimated cost and time. Both roles can comment. Per-project view and unified cross-project view.
- **Steps:**
  1. User navigates to `/platform/projects/:id/changes` or `/platform/changes`.
  2. Change request list renders with status tabs and create button.
  3. Client fills create form (title, description, module, priority, urgency, screenshot).
  4. Admin evaluates: sets status, admin_response, estimated cost/time.
  5. Both roles add comments on individual change requests.
- **Branches:**
  - [Branch A — Create] Client creates a change request → notification sent to admin.
  - [Branch B — Evaluate] Admin evaluates → status changes → notification sent to client.
  - [Branch C — Unified view] `/platform/changes` shows all change requests grouped by project.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-change-requests.spec.js`

#### FLOW: `platform-bug-reports`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/bugs`, `/platform/bugs`
- **API:** `GET/POST /api/accounts/projects/:id/bug-reports/`, `POST .../evaluate/`, `POST .../comments/`
- **Description:** Both roles report bugs with severity, steps to reproduce, expected/actual behavior, device/browser, and screenshot. Admin evaluates with status changes and responses.
- **Steps:**
  1. User navigates to `/platform/projects/:id/bugs` or `/platform/bugs`.
  2. Bug report list renders with status tabs and severity badges.
  3. User fills create form (title, description, severity, steps, expected/actual behavior, environment, device, screenshot).
  4. Admin evaluates: sets status, admin_response, linked_bug.
  5. Both roles add comments.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-bug-reports.spec.js`

#### FLOW: `platform-deliverables`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/deliverables` (list), `/platform/deliverables` (cross-project), `/platform/projects/:id/deliverables/:deliverableId` (full-page ficha — see `platform-deliverable-detail`)
- **API:** `GET/POST /api/accounts/projects/:id/deliverables/`, `POST .../upload-version/`
- **Description:** Admin uploads deliverables (designs, documents, APKs, credentials) with version history. Client downloads files. List UI is implemented as `pages/.../deliverables/index.vue` so nested dynamic routes resolve correctly.
- **Steps:**
  1. User navigates to deliverables page.
  2. Deliverable list renders with category filter tabs and file count.
  3. Admin uploads a new deliverable (title, description, category, file).
  4. Admin uploads new versions of existing deliverables.
  5. Client views and downloads files.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-deliverables.spec.js`

### 8.8 Hosting & Payments

#### FLOW: `platform-hosting-subscription`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P1
- **Routes:** `/platform/projects/:id/payments`, `/platform/payments`
- **API:** `GET /api/accounts/subscriptions/` (unified `/platform/payments` list), `GET/POST/PATCH /api/accounts/projects/:id/subscription/`, `GET /api/accounts/projects/:id/payments/`, `GET /api/accounts/projects/:id/phases/` (per-phase hosting tiers)
- **Description:** The client sees a per-phase hosting cost table and activates a subscription that bills the sum of all started phases at one of three frequencies: quarterly, semiannual or every 9 months. Monthly and annual plans are not offered. Card is the only payment method; after activation the client registers a card (see `platform-hosting-card-setup`) for automatic recurring billing. Admin sees subscription status and stored-card info. Netflix-style active state shows the next automatic renewal date.
- **Steps:**
  1. Client navigates to `/platform/projects/:id/payments`.
  2. If no subscription: a per-phase cost table renders (one row per phase + total) with frequency pills (trimestral/semestral/cada 9 meses — 9 meses has the biggest discount).
  3. Client toggles a pill → the table total recomputes live; clicks "Activar plan {frecuencia}" → `POST .../subscription/`.
  4. Subscription created billing the sum of started phases. Billing always starts on the 1st of a month and the client gets a free hosting period from delivery until that date (≥ 1 month), so the first payment is dated to the 1st (not the activation day) → "Activa el cobro automático" card prompts to register a card.
  5. Client registers a card (`platform-hosting-card-setup`); the first payment is charged on confirm.
  6. After payment: Netflix-style "Suscripción activa" card with the next automatic renewal date; the per-phase table becomes display-only at the fixed frequency.
- **Branches:**
  - [Branch A — Admin view] Admin sees per-phase tier tables with editable `hosting_start_date` per phase (not the client plan selector).
  - [Branch B — Up to date] Active subscription with a stored card and no urgent payment shows the green card + "Se renueva y cobra automáticamente el {date}".
  - [Branch C — Payment due] Shows the payment action card; with a stored card the cron charges it on the due date.
  - [Branch D — Unified view] `/platform/payments` shows all subscriptions across projects.
  - [Branch E — Cancellation] No in-app cancel; the card panel tells the client to contact support by email.
  - [Branch F — Multi-phase proration] A phase with a future `hosting_start_date` shows in the table as reference; when its date arrives the billing cron charges a prorated catch-up for the remaining cycle days and the phase joins the recurring total.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-hosting-subscription.spec.js`

#### FLOW: `platform-hosting-card-setup`

- **Module:** platform
- **Role:** platform-client
- **Priority:** P1
- **Routes:** `/platform/projects/:id/payments`
- **API:** `POST /api/accounts/projects/:id/subscription/card/`, `GET .../subscription/card/:psId/status/`, `POST .../subscription/card/:psId/confirm/`, `POST /api/accounts/projects/:id/payments/:pid/charge/`
- **Description:** Client registers a card once for automatic hosting billing. The card is tokenized into a Wompi payment source; when 3D Secure applies, an authentication flow runs in iframes (hidden for browser-info/fingerprint, visible for the bank challenge) polled every 2s until the source is AVAILABLE. On success the card is stored on the subscription and the first open payment is charged.
- **Steps:**
  1. On the payments page the client clicks "Registrar tarjeta" (or "Cambiar tarjeta" if a card exists).
  2. Card modal opens; client enters number, holder, expiry and CVC, then submits → `POST .../subscription/card/`.
  3. If the payment source needs 3DS: the modal renders the 3DS iframe and polls `.../card/:psId/status/` every 2s.
  4. For `CHALLENGE` the iframe is visible and the client confirms with the bank; browser-info/fingerprint steps run hidden.
  5. When the source is `AVAILABLE`: `POST .../card/:psId/confirm/` stores the card and charges the first open payment.
  6. Modal shows "Tarjeta registrada"; the stored-card panel renders with brand · •••• last4 · expiry.
- **Branches:**
  - [Branch A — No 3DS] Source returns `AVAILABLE` immediately; flow skips the iframe and goes straight to confirm.
  - [Branch B — Declined/Error] Source returns `DECLINED`/`ERROR`; modal shows an error with "Intentar de nuevo".
  - [Branch C — Change card] An existing stored card is replaced; the new payment source overwrites the old one.
  - [Branch D — Manual retry] A `failed` payment shows "Reintentar cobro" → `POST .../payments/:pid/charge/` with the stored card.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-hosting-card-setup.spec.js` (Wompi + 3DS mocked via `:srcdoc` — covers the AVAILABLE happy path and the PENDING → 3DS challenge path)

#### FLOW: `platform-hosting-card-delete`

- **Module:** platform
- **Role:** platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/payments`
- **API:** `DELETE /api/accounts/projects/:id/subscription/card/remove/`
- **Description:** With a card on file, the client can remove it from the payments page. A confirmation modal warns that automatic billing will be disabled; on confirm, the backend best-effort deletes the Wompi payment source and clears the stored-card fields on the subscription, so `has_payment_source` becomes false and the "Activa el cobro automático / Registrar tarjeta" state reappears. The button is hidden for admins and archived subscriptions.
- **Steps:**
  1. On the payments page, with a stored card, the client clicks "Eliminar tarjeta" next to "Cambiar tarjeta".
  2. A confirmation modal opens explaining that automatic billing will be disabled.
  3. Client confirms → `DELETE .../subscription/card/remove/`.
  4. Backend best-effort deletes the Wompi payment source and clears the card fields.
  5. The subscription refreshes; the stored-card panel is replaced by the "Activa el cobro automático" / "Registrar tarjeta" state.
- **Branches:**
  - [Branch A — No card] Endpoint returns 400 when there is no stored card to remove.
  - [Branch B — Wompi delete fails] The card is still cleared locally (best-effort); the client sees success.
- **Coverage:** ✅ Covered (confirm + cancel + error branches; backend + store also unit-tested)
- **E2E Spec:** `e2e/platform/platform-hosting-card-delete.spec.js` (added 2026-07-23)

### 8.9 Notifications

#### FLOW: `platform-notifications`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform/notifications`
- **API:** `GET /api/accounts/notifications/`, `PATCH .../mark-read/`, `POST .../mark-all-read/`, `GET .../unread-count/`
- **Description:** In-app notification center with unread count badge in sidebar, filter tabs, mark-all-read, and click-to-navigate deep links.
- **Steps:**
  1. Sidebar badge shows unread notification count (polled every 30s).
  2. User navigates to `/platform/notifications`.
  3. Notification list renders with filter tabs (Todas/Sin leer/Leídas).
  4. User clicks a notification → marked as read → navigates to relevant project module.
  5. User clicks "Marcar todas como leídas" → all notifications marked read.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-notifications.spec.js`

### 8.10 Kanban Enhancements

#### FLOW: `platform-kanban-json-upload`

- **Module:** platform
- **Role:** platform-admin
- **Priority:** P2
- **Routes:** `/platform/projects/:id/board`
- **API:** `POST /api/accounts/projects/:projectId/deliverables/:deliverableId/requirements/bulk/`
- **Description:** Admin bulk-creates requirements by uploading a JSON file. Includes downloadable example template.
- **Steps:**
  1. Admin clicks "Ejemplo" button → downloads `requerimientos-ejemplo.json` template.
  2. Admin prepares JSON with requirements (title, description, configuration, flow).
  3. Admin clicks "Subir JSON" → file picker opens → selects JSON file.
  4. API creates requirements in bulk → success alert with count.
  5. Backlog section updates with new cards.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-kanban-json-upload.spec.js`

#### FLOW: `platform-requirement-client-review`

- **Module:** platform
- **Role:** platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/board`
- **API:** `GET .../deliverables/:deliverableId/requirements/`, `GET .../requirements/:id/`, `POST .../requirements/:id/move/`
- **Description:** Client reviews completed requirements. Clicking a done card shows: Approve, Request Change, or Report Bug.
- **Steps:**
  1. Client clicks a completed requirement in the "Completados" section.
  2. Card detail modal opens showing description, configuration, flow, and review actions.
  3. Client clicks "Aprobar" → requirement accepted.
  4. Client clicks "Solicitar cambio" → navigates to change requests with pre-filled data.
  5. Client clicks "Reportar bug" → navigates to bug reports with pre-filled data.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-requirement-client-review.spec.js`

### 8.11 Collection Accounts & Deliverable Detail

#### FLOW: `platform-collection-accounts-list`

- **Module:** platform
- **Role:** platform-admin, platform-client
- **Priority:** P2
- **Routes:** `/platform/collection-accounts`
- **API:** `GET /api/accounts/collection-accounts/` (optional query params for admin filters)
- **Description:** Global list of collection accounts; admin sees filters and “New collection account”; client sees “My collection accounts”. Table rows link to detail via Open.
- **Steps:**
  1. User navigates to `/platform/collection-accounts`.
  2. List loads from API → table shows number, title, status, total, due date.
  3. User clicks Open → navigates to `/platform/collection-accounts/:id`.
  4. **[Admin]** User applies project/status filters and Apply filters → list refreshes.
  5. **[Admin]** User clicks New collection account → modal → `POST /api/accounts/collection-accounts/` → redirect to new detail (covered in E2E).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-collection-accounts.spec.js`

#### FLOW: `platform-collection-account-detail`

- **Module:** platform
- **Role:** platform-admin, platform-client
- **Priority:** P2
- **Routes:** `/platform/collection-accounts/:id`
- **API:** `GET/PATCH /api/accounts/collection-accounts/:id/`, `POST .../issue/`, `.../mark-paid/`, `.../mark-cancelled/`, `GET .../pdf/`
- **Description:** Single document view: status, amounts, line items; Download PDF; admin actions Issue / Mark paid / Cancel by status.
- **Steps:**
  1. User opens detail from list or direct URL.
  2. Document loads → title, public number, status, totals, line items render.
  3. User clicks Download PDF → PDF downloaded (blob).
  4. **[Admin — draft]** User clicks Issue → status becomes issued.
  5. **[Admin — issued]** User clicks Mark paid → status becomes paid.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-collection-accounts.spec.js`

#### FLOW: `platform-project-collection-accounts`

- **Module:** platform
- **Role:** platform-admin, platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/collection-accounts`
- **API:** `GET /api/accounts/projects/:id/collection-accounts/`
- **Description:** Project-scoped list of collection accounts with Open links to shared detail route.
- **Steps:**
  1. User navigates from project hub or URL to `/platform/projects/:projectId/collection-accounts`.
  2. List loads → cards or rows per account with status.
  3. User clicks Open → `/platform/collection-accounts/:id`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-collection-accounts.spec.js`

#### FLOW: `platform-deliverable-detail`

- **Module:** platform
- **Role:** platform-admin, platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/deliverables/:deliverableId`
- **Description:** Compatibility route for the retired standalone deliverable page; the resource itself is now opened from the project-scoped resources list.
- **Steps:**
  1. User opens a saved or deep link to `/platform/projects/:id/deliverables/:deliverableId`.
  2. The compatibility page replaces the URL with `/platform/projects/:id/deliverables`.
  3. The project resources list mounts without returning to the retired route or looping.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-deliverables.spec.js`

#### FLOW: `platform-project-data-model`

- **Module:** platform
- **Role:** platform-admin, platform-client
- **Priority:** P2
- **Routes:** `/platform/projects/:id/data-model`
- **API:** `GET/POST /api/accounts/projects/:id/data-model-entities/`, `GET /api/accounts/projects/:id/data-model-entities/template/`
- **Description:** Manage the data model (entity list) for a project. Admin can upload a JSON payload via file or textarea, validate, and sync entities to the backend. Both roles browse the entity table.
- **Steps:**
  1. User navigates to `/platform/projects/:id/data-model` (linked from project detail or sidebar).
  2. Page loads entities from `GET /api/accounts/projects/:id/data-model-entities/`.
  3. **[Admin only]** "Subir modelo de datos" card renders with two template buttons ("Copiar plantilla" / "Descargar plantilla").
  4. Admin copies/downloads the JSON template (`{ entities: [{ name, description, keyFields, relationship }] }`).
  5. Admin uploads a `.json` file via file input OR pastes JSON into the textarea.
  6. Parse/validate runs on `@input`; detected entity count preview renders if valid; error message if invalid JSON.
  7. Admin clicks "Subir modelo de datos" → `POST /api/accounts/projects/:id/data-model-entities/`.
  8. Success banner "Modelo de datos actualizado correctamente." renders.
  9. Entity table refreshes with rows: Entidad | Descripción | Campos clave (badge chips) | Relación.
- **Branches:**
  - [Branch A — Empty state] No entities yet: client sees "No hay modelo de datos definido para este proyecto." Admin sees additional hint "Sube un JSON con las entidades para empezar."
  - [Branch B — Error state] API fetch fails: error message + "Reintentar" button visible.
  - [Branch C — Client role] Upload section not rendered; only entity table (or empty state) shown.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-data-model.spec.js`

### 8.12 Quick Access

#### FLOW: `platform-access-view`

- **Module:** platform
- **Role:** platform-admin
- **Priority:** P2
- **Routes:** `/platform/access`
- **API:** `GET /api/accounts/projects/access/`
- **Description:** Admin-only quick-access hub with a searchable grid of project cards. Each card shows the project name, client, and status badge, plus four clickable URL rows (production, staging, Django admin, repository) and a credential block with copy and reveal controls.
- **Steps:**
  1. Admin navigates to `/platform/access` (via "Accesos" item in the Administración sidebar group).
  2. `GET /api/accounts/projects/access/` fetches the admin-only list with decrypted credentials.
  3. Project cards render in a responsive grid.
  4. Each card shows up to four URL rows; rows with no URL render a dash.
  5. Admin clicks a URL row → external link opens in a new tab.
  6. Admin clicks "Copiar" on a credential field → value copied to clipboard → flash feedback appears.
  7. Admin clicks "Revelar" → password unmasks; "Ocultar" re-masks it.
  8. Admin types in the search input → cards filter by project name, client, or URL substring.
  9. Admin clicks "Actualizar" → list re-fetches from API.
- **Branches:**
  - [Branch A — No projects] API returns empty list → "Todavía no hay proyectos con accesos configurados." empty state.
  - [Branch B — Search no match] Search term matches no project → "Ningún proyecto coincide con esa búsqueda."
  - [Branch C — Access guard] Client role navigates to page → middleware redirects to `/platform/dashboard`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-access.spec.js`

### 8.14 Client Document Portal

#### FLOW: `platform-client-document-portal`

- **Module:** platform
- **Role:** platform-client
- **Priority:** P1
- **Routes:** `/platform/documents`
- **API:** `GET /api/accounts/documents/`, `GET /api/accounts/documents/:uuid/pdf/`
- **Description:** After first login the client lands here. The main contract (`requires_signature`) is shown first, followed by its annexes. Each document can be downloaded as a PDF. The page also surfaces the client's email-verification state to gate signing.
- **Steps:**
  1. Client logs in for the first time, sets password (onboarding), and is redirected to `/platform/documents`.
  2. List loads from `GET /api/accounts/documents/` → main document card + annex rows render.
  3. Client clicks Descargar PDF on the main document or an annex → PDF downloaded (blob).
- **Branches:**
  - [Branch A — Empty] No published documents → "Todavía no tienes documentos disponibles." empty state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-client-documents.spec.js`

#### FLOW: `platform-client-email-validation`

- **Module:** platform
- **Role:** platform-client
- **Priority:** P1
- **Routes:** `/platform/documents`
- **API:** `POST /api/accounts/email/verify/request/`, `POST /api/accounts/email/verify/confirm/`
- **Description:** Client confirms ownership of their account email via a 6-digit OTP before they can sign. The email-validation card shows the current email, sends a code, and accepts the code in an input.
- **Steps:**
  1. On `/platform/documents`, the client sees the "Valida tu correo electrónico" card (only while unverified).
  2. Client clicks Enviar código → `POST /api/accounts/email/verify/request/` sends an OTP to their email.
  3. Client enters the 6-digit code and clicks Validar correo → `POST /api/accounts/email/verify/confirm/`.
  4. On success the card is replaced by a "Tu correo está validado" banner and signing is unlocked.
- **Branches:**
  - [Branch A — Bad code] Wrong/expired code → inline error, stays unverified.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-client-documents.spec.js`

#### FLOW: `platform-client-document-sign`

- **Module:** platform
- **Role:** platform-client
- **Priority:** P1
- **Routes:** `/platform/documents`
- **API:** `POST /api/accounts/documents/:uuid/sign/`
- **Description:** Client accepts/signs the main document via click-to-accept. The Aceptar y firmar button is disabled until the email is verified. A confirmation modal with an acceptance checkbox records the signature (name, timestamp, IP, user-agent) and notifies the team.
- **Steps:**
  1. With a verified email, the client clicks Aceptar y firmar on the main document.
  2. Confirmation modal opens; client ticks "He leído el documento y acepto sus términos." and clicks Confirmar firma.
  3. `POST /api/accounts/documents/:uuid/sign/` records the signature; the card shows "Firmado el <fecha>".
- **Branches:**
  - [Branch A — Email not verified] Button disabled; signing blocked (backend returns 403).
  - [Branch B — Already signed] Endpoint is idempotent; the signed state persists.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-client-documents.spec.js`

### 8.13 Platform Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `platform-client-document-portal` | platform | platform-client | P1 | ✅ Covered | `e2e/platform/platform-client-documents.spec.js` |
| `platform-client-email-validation` | platform | platform-client | P1 | ✅ Covered | `e2e/platform/platform-client-documents.spec.js` |
| `platform-client-document-sign` | platform | platform-client | P1 | ✅ Covered | `e2e/platform/platform-client-documents.spec.js` |
| `platform-login` | platform | platform-admin/client | P1 | ✅ Covered | `e2e/platform/platform-login.spec.js` |
| `platform-verify-onboarding` | platform | platform-admin/client | P1 | ✅ Covered | `e2e/platform/platform-verify.spec.js` |
| `platform-complete-profile` | platform | platform-admin/client | P1 | ✅ Covered | `e2e/platform/platform-complete-profile.spec.js` |
| `platform-kanban-board` | platform | platform-admin/client | P1 | ✅ Covered | `e2e/platform/platform-kanban-board.spec.js` |
| `platform-hosting-subscription` | platform | platform-admin/client | P1 | ✅ Covered | `e2e/platform/platform-hosting-subscription.spec.js` |
| `platform-hosting-card-setup` | platform | platform-client | P1 | ✅ Covered | `e2e/platform/platform-hosting-card-setup.spec.js` |
| `platform-hosting-card-delete` | platform | platform-client | P2 | ✅ Covered | `e2e/platform/platform-hosting-card-delete.spec.js` |
| `platform-dashboard` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-dashboard.spec.js` |
| `platform-sidebar-navigation` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-sidebar.spec.js` |
| `platform-project-list` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-project-list.spec.js` |
| `platform-project-detail` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-project-detail.spec.js` |
| `platform-unified-board` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-unified-board.spec.js` |
| `platform-admin-client-list` | platform | platform-admin | P2 | ✅ Covered | `e2e/platform/platform-admin-client-list.spec.js` |
| `platform-admin-client-detail` | platform | platform-admin | P2 | ✅ Covered | `e2e/platform/platform-admin-client-detail.spec.js` |
| `platform-profile-edit` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-profile.spec.js` |
| `platform-profile-avatar-picker` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-profile.spec.js` |
| `platform-change-requests` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-change-requests.spec.js` |
| `platform-bug-reports` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-bug-reports.spec.js` |
| `platform-deliverables` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-deliverables.spec.js` |
| `platform-notifications` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-notifications.spec.js` |
| `platform-kanban-json-upload` | platform | platform-admin | P2 | ✅ Covered | `e2e/platform/platform-kanban-json-upload.spec.js` |
| `platform-requirement-client-review` | platform | platform-client | P2 | ✅ Covered | `e2e/platform/platform-requirement-client-review.spec.js` |
| `platform-collection-accounts-list` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-collection-accounts.spec.js` |
| `platform-collection-account-detail` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-collection-accounts.spec.js` |
| `platform-project-collection-accounts` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-collection-accounts.spec.js` |
| `platform-deliverable-detail` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-deliverables.spec.js` |
| `platform-project-data-model` | platform | platform-admin/client | P2 | ✅ Covered | `e2e/platform/platform-data-model.spec.js` |
| `platform-access-view` | platform | platform-admin | P2 | ✅ Covered | `e2e/platform/platform-access.spec.js` |
| `platform-admin-project-create` | platform | platform-admin | P3 | ✅ Covered | `e2e/platform/platform-project-create.spec.js` |
| `platform-kanban-card-comments` | platform | platform-admin/client | P3 | ✅ Covered | `e2e/platform/platform-kanban-comments.spec.js` |

### Platform Coverage Summary

- **Total platform flows:** 27
- **P1 (Critical):** 5
- **P2 (High):** 20
- **P3 (Medium):** 2
- **Covered:** 27 (100%)
- **Missing:** 0
- **Deferred:** 0

---

## 9. New Feature Flows (v2.7.0)


> Flows registered during the v2.7.0 audit (documents, admin management, deliverability, public landings). E2E specs were added afterward; coverage below reflects the current Playwright suite (`frontend/e2e/`).

### 9.1 Admin Document Management

#### FLOW: `admin-document-list`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **Description:** View admin documents with title, client/project association and ordered active-state episodes. The exclusive cycle appears before additive signals, every badge carries its open duration, **Solucionar bug** is visually prominent, overflow collapses to `+N`, and a missing cycle reads **Por clasificar**. Association filters and the shared `DocumentActionsSheet` remain available on every breakpoint.
- **Steps:**
  1. Admin navigates to `/panel/documents`.
  2. Document list loads from API (`GET /api/content/documents/`).
  3. Table renders title, client, project, current state episodes, created date and actions.
  3b. Filtering by client/project (or their `none` chips) refetches with `?client=`/`?project=` and mirrors the axes in the URL.
  4. Admin clicks a row → navigates to `/panel/documents/:id/edit`.
  5. Admin clicks the single "Acciones" icon → `DocumentActionsSheet` opens; choosing "Editar contenido" navigates to `/panel/documents/:id/edit`.
  6. "Nuevo Documento" button navigates to `/panel/documents/create`.
- **Branches:**
  - [Branch A — Empty state] No documents → "No hay documentos todavía." with create link.
  - [Branch B — Actions modal] Admin clicks the "Acciones" icon → modal lists every action (edit/rename/move/send-email/download-pdf/copy-markdown/duplicate/delete); selecting one triggers it and closes the modal.
  - [Branch C — Download PDF] From the actions modal → PDF generated and downloaded.
  - [Branch D — Duplicate] From the actions modal → document cloned and list refreshes.
  - [Branch E — Delete] From the actions modal → confirm modal → document removed from list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-list.spec.js`

#### FLOW: `admin-document-gallery`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **Description:** Toggle between the list (table) and gallery (cards) views via the "Lista"/"Galería" segmented control. Gallery cards render a sanitized markdown mini-preview, client/date metadata, ordered active-state episodes with durations and `+N` overflow, plus the shared "Acciones" sheet. Subfolders remain drag-and-drop targets and the chosen mode persists in `localStorage`.
- **Steps:**
  1. Admin navigates to `/panel/documents` (table view by default).
  2. Admin clicks "Galería" → the table swaps out and the card grid renders one card per document.
  3. Cards show the markdown mini-preview, client/date metadata and current state episodes.
  4. Admin clicks a card (or its title link) → navigates to `/panel/documents/:id/edit`.
  5. Admin clicks a card kebab → `DocumentActionsSheet` opens with the full action list.
  6. Admin reloads the page → the gallery view is restored from `localStorage`.
  7. Admin clicks "Lista" → the table view returns.
- **Branches:**
  - [Branch A — Persistence] Reload restores the persisted mode; invalid stored values fall back to `list`.
  - [Branch B — Subfolder cards] Inside a folder, subfolders render as dashed cards; clicking navigates into the folder and dropping a dragged document moves it there.
  - [Branch C — Empty excerpt] Documents without content render a placeholder icon instead of the mini-preview.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-gallery.spec.js`

#### FLOW: `admin-document-unsaved-guard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents/:id/edit`, `/panel/documents/create`
- **Description:** Protección contra salir de un documento creyendo que se guardó algo que no se guardó. Antes, la única señal de trabajo pendiente era que el botón Guardar se habilitaba — y un botón habilitado se lee como "puedes guardar", no como "te falta guardar". Ahora, editar cualquier campo rastreado levanta un aviso permanente (`doc-unsaved-notice` / `doc-create-unsaved-notice`) cuyo título ES la lista de campos pendientes ("Cliente y proyecto sin guardar"); pasados tres campos los cuenta y los detalla en una línea aparte. En el `<aside>` fijo, título, cliente y proyecto llevan además una marca "Sin guardar" (`doc-field-dirty-title` / `-client` / `-project`). Salir de la página, o pulsar el botón global "Actualizar datos" —que antes recargaba encima del formulario sin avisar—, abre una confirmación de tres salidas.
- **Steps:**
  1. Admin abre `/panel/documents/:id/edit` con el documento ya cargado.
  2. Modifica cliente y proyecto en el bloque Identificación.
  3. El aviso aparece nombrando ambos campos y el botón pasa a "Guardar cambios".
  4. Admin intenta salir (link "Volver a documentos", back del navegador o cerrar pestaña).
  5. Se abre el diálogo con las tres salidas.
  6. Al guardar, la confirmación nombra lo guardado ("Se guardó: cliente y proyecto.").
- **Branches:**
  - [Branch A — Guardar y salir] Botón primario: corre el PATCH y recién entonces navega. Si el guardado falla, la navegación se bloquea y el usuario se queda con el error y sus cambios intactos.
  - [Branch B — Salir sin guardar] Botón secundario: navega descartando los cambios, sin PATCH.
  - [Branch C — Seguir editando] Cancelar: misma URL, cambios y aviso intactos.
  - [Branch D — Refresh guardado] "Actualizar datos" con cambios pendientes pregunta antes de recargar por encima.
  - [Branch E — Cuenta emitida] Con una cuenta de cobro emitida (`collection_account_locked`) no se ofrece la salida de guardar: quedan dos, porque el backend rechazaría el PATCH.
  - [Branch F — Crear] En `/panel/documents/create` no hay versión guardada a la que volver: el aviso no ofrece guardar ni descartar, y crear con éxito desarma el guard para que la redirección al editor no interrumpa. Llegar con `?folder=` no ensucia el formulario pese a la sugerencia de cliente por carpeta, aunque el selector de carpeta ya muestre su ruta.
  - [Branch G — Buscar no es editar] Escribir en el selector de cliente o en el de carpeta sin elegir nada no levanta aviso: la selección enlazada se restaura al cerrar.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-unsaved-guard.spec.js`

#### FLOW: `admin-panel-unsaved-guard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/emails`, y el mismo criterio en `/panel/blog/*`, `/panel/portfolio/*`, `/panel/linktrees/:id/edit`, `/panel/hour-packages/*`, `/panel/diagnostics/create`, `/panel/accounting/settings`
- **Description:** El mismo aviso de cambios sin guardar, extendido a los editores de página completa del panel. Se cubre con `/panel/emails` porque es el caso representativo del formato difícil: su estado vive en refs sueltos, no en un objeto `form`. Fija además el límite que importa en páginas con pestañas — cambiar de pestaña es un `router.replace({ query })` sobre la misma ruta y **no** debe disparar el guard de salida; si lo hiciera, cualquier página con pestañas quedaría bloqueada por un modal apenas su formulario tuviera algo pendiente.
- **Steps:**
  1. Admin abre `/panel/emails?tab=defaults`.
  2. Edita el saludo por defecto.
  3. Aparece el aviso nombrando el campo ("Saludo sin guardar").
  4. Al salir de la página, el diálogo ofrece guardar, salir sin guardar o seguir editando.
- **Branches:**
  - [Branch A — Cambio de pestaña] Pasar a Redactar no abre ningún modal y no descarta lo pendiente; al volver, el valor editado sigue ahí. La URL suelta el `?tab=` del modo por defecto a propósito.
  - [Branch B — Guardar y salir] El botón primario dispara el PUT de `emails/defaults/` y recién entonces navega.
  - [Branch C — Campos sin guardado propio] El borrador de la pestaña Redactar (destinatario, asunto, secciones, adjuntos) queda **fuera** del aviso: ese contenido no se guarda, se envía. Es "sin enviar", no "sin guardar", y mezclarlos confundiría las dos cosas.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-panel-unsaved-guard.spec.js`

#### FLOW: `admin-document-folders`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **Description:** Organize admin documents with the folder sidebar and folder-management modals. Folder navigation is independent from the state-filter axis documented in `admin-document-state-filters`. The sidebar shows only **root folders**; subfolders are reached by navigating inside a folder (see `admin-document-folder-hierarchy`). Cada fila dice **de quién es** la carpeta mediante su cliente asociado y la cabecera repite cliente/proyecto al entrar.
- **Steps:**
  1. Admin loads `/panel/documents` — the left sidebar renders root folders only.
  2. Admin clicks a folder entry (e.g., "Cuentas de cobro") → list refreshes with `?folder=<id>`.
  3. Admin clicks "Sin carpeta" → list refreshes with `?folder=none`.
  4. Admin clicks "Todos" → list refreshes without folder param.
  5. Admin opens the folder manager from the sidebar.
  6. Admin creates, renames or archives a folder → the document list refreshes.
- **Branches:**
  - [Branch A — Empty folders] No folders yet → "Sin carpeta" and "Todos" entries only.
  - [Branch B — Create folder] Admin fills name + submits in FolderManagerModal → folder added to sidebar. The "Dentro de:" parent selector defaults to the currently active folder, so creating a folder while standing inside a child folder pre-selects that folder as the parent (still changeable to any folder or root).
  - [Branch C — Delete folder] Deleting a folder is still blocked with HTTP 409 if it holds documents or subfolders (archived content counts too — content is content); documents themselves use `folder = SET_NULL`. Since 2026-08-12 the sidebar row says so up front: the delete icon is disabled with a tooltip, and **archiving** — allowed with content, cascading over subfolders and documents — sits next to it as the way out. See `admin-document-archive`.
  - [Branch D — Assign on create] Creating a document from `?folder=<id>` pre-selects that folder.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-folders.spec.js`

#### FLOW: `admin-document-folder-hierarchy`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **API:** `GET /api/content/documents/document-folders/`, `PATCH /api/content/documents/document-folders/<id>/update/`
- **Description:** Navigate the nested folder hierarchy in the documents view. The sidebar lists only root folders; entering a folder shows its subfolders as navigable rows above its documents, and a breadcrumb above the table tracks the current path. Manual folders can be re-parented by dragging a subfolder row onto another folder, the sidebar, or a breadcrumb segment. Generated branches remain navigable through project/client, document type, issue year and issue month, but their structure and contents are system-owned.
- **Steps:**
  1. Admin loads `/panel/documents` — sidebar shows root folders only (a chevron marks folders that contain subfolders).
  2. Admin clicks a root folder → table shows that folder's subfolder rows on top, then its documents; a breadcrumb `Todos › <Folder>` appears above the table.
  3. Admin clicks a subfolder row → navigates into it; breadcrumb grows (`Todos › <Folder> › <Subfolder>`).
  4. Admin clicks a breadcrumb segment (or "Todos") → navigates back to that level.
  5. Admin drags a subfolder row onto another folder → the dragged folder is re-parented (`PATCH parent`).
  6. Admin navigates `Proyectos → <Proyecto> → Cuentas de cobro → <Año> → <Mes>` and finds issued accounts ordered by their canonical title.
- **Branches:**
  - [Branch A — Only subfolders] A folder with subfolders but no documents still renders the subfolder rows (no empty state).
  - [Branch B — Cycle prevented] Dropping a folder onto itself or one of its descendants is rejected client-side and by the backend serializer.
  - [Branch C — Drop on "Sin carpeta"] Dragging a subfolder onto "Sin carpeta" promotes it to a root folder (`parent = null`).
  - [Branch D — Search active] While a search query is active, subfolder rows are hidden and the search applies to documents only.
  - [Branch E — Generated hierarchy] A folder with `system_key` hides rename, move, archive, delete and drag affordances; the API and Documents MCP reject those mutations and manual document drops.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-folder-hierarchy.spec.js`

#### FLOW: `admin-document-folder-panel-resize`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/documents`
- **API:** none (client-side layout preference; persisted in localStorage `projectapp-documents-folder-width`)
- **Description:** Resize the folder sidebar of `/panel/documents`. The default width (384px) guarantees the longest real folder names (22 characters, live inventory of 2026-08-16) render untruncated — including the active row, which is wider in `font-medium`. A keyboard-accessible drag handle (`role=separator`) lives in the gap between the panel and the documents view: dragging resizes between 240px (the historical width) and 480px, and the width persists on drag end. Double-click on the handle returns to the default and forgets the stored preference. Below `lg` (1024px) the panel stacks above the documents at full width: the handle does not render and the stored width is ignored.
- **Steps:**
  1. Admin loads `/panel/documents` at ≥1024px — sidebar renders at 384px (or the stored width) and every root folder name is readable.
  2. Admin drags the handle right/left → the panel follows the pointer, clamped to 240–480px.
  3. Admin releases → the chosen width is written to localStorage and survives reloads.
  4. Admin double-clicks the handle → width returns to 384px and the stored value is cleared.
  5. Admin focuses the handle and presses ←/→ (±16px), Home (240) or End (480) → same clamp and persistence per keystroke.
- **Branches:**
  - [Branch A — Clamp] Drags beyond either bound stop at 240/480; a tampered or stale stored value re-clamps on load before first paint.
  - [Branch B — Reset] Double-click resets AND removes the key, so a future default change is not shadowed by an old stored value.
  - [Branch C — Keyboard] The handle is a focusable `role=separator` with `aria-valuenow/min/max`; arrows, Home and End resize without a pointer.
  - [Branch D — Mobile stack] Below `lg` the grid is single-column: full-width panel, no handle, stored width inert.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-folder-panel-resize.spec.js` — added 2026-08-16 together with the resizable-panel feature (default width raised 240→384, sized by the live folder inventory and arbitrated by the untruncated-names E2E: 336 truncated the 22-char name, and 352 fell short once the row gained the edit icon from the change-client feature; truncation tooltip via native `title` pre-existed).

#### FLOW: `admin-document-pdf-download`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents/:id/edit`
- **API:** `GET /api/content/documents/<id>/pdf/`
- **Description:** Admin downloads a Document entity as a branded PDF from the document edit page. The "Descargar PDF" button triggers `documentStore.downloadPdf()` which calls the backend generation endpoint.
- **Steps:**
  1. Admin opens `/panel/documents/:id/edit`.
  2. Admin clicks "Descargar PDF".
  3. `isDownloading` state activates (button shows "Descargando...").
  4. Backend generates the PDF and returns a blob.
  5. Browser downloads the file named after the document title.
- **Branches:**
  - [Branch A — Generation in progress] If PDF backend is still being developed, the endpoint may return an error; UI should handle gracefully.
- **Coverage:** ⬜ Missing
- **E2E Spec:** *(not yet written — Document PDF generation feature is in progress)*

#### FLOW: `admin-document-folder-change-client`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **API:** `GET /api/document-folders/<id>/change-client/preview/?client_profile_id=`, `POST /api/document-folders/<id>/change-client/`
- **Description:** Reasignar una carpeta que **ya tiene contenido** pasa por UN camino guiado, con el mismo criterio que el cambio de cliente de un proyecto (PA-55). El PATCH plano se planta con **409 `folder_has_content`** y `FolderFormModal` no se lo traga: eleva el conflicto y abre `FolderChangeClientModal`. Ahí el preview nombra cada bucket — las subcarpetas y documentos que pasan, las **cuentas de cobro emitidas que nunca se reescriben** (un hecho, no un puntero) y lo que alguien asignó a mano a un **tercer cliente**, que conserva el suyo; una subcarpeta de otro cliente **poda su rama entera**, porque cambiar «Kore» por «Ana» no puede meterse en la de Néstor. El modo se elige **cada vez**, sin preselección (*Pasa también el contenido* | *Sólo la carpeta*), y el apply devuelve los `document_ids`/`folder_ids` del preview como token de staleness: un 409 `records_not_found`/`records_changed` recarga el plan en vez de adivinar. Todo corre en una transacción con una fila de auditoría por registro tocado (`AccountingChangeLog`, entidades `document_folder` y `document`).
- **Steps:**
  1. Admin abre el formulario de una carpeta con contenido y le cambia el cliente desde un listbox flotante propiedad del modal, visible por encima del panel en vez de recortado dentro de él.
  2. El PATCH responde 409 y se abre la cascada, ya apuntando al cliente que el formulario proponía.
  3. Admin lee el impacto: lo que pasa, lo que no se toca y por qué.
  4. Admin elige el modo — sin elegirlo, Confirmar sigue deshabilitado.
  5. Admin confirma → la carpeta y (según el modo) su contenido quedan del nuevo cliente; el listado se refresca.
- **Branches:**
  - [Branch A — Sólo la carpeta] El contenido se queda con su cliente; sólo cambia la carpeta.
  - [Branch B — Plan viejo] 409 `records_not_found`/`records_changed` → se recarga el preview y el modo vuelve a pedirse.
  - [Branch C — Vaciar el cliente] Desasignar NO pasa por acá: «a nadie» no es un destino que la cascada pueda expresar, así que quitarle el dueño a la carpeta es un PATCH plano que deja su contenido como está.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-folder-change-client.spec.js` (added 2026-08-16)

#### FLOW: `admin-document-move-folder`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/documents`
- **API:** `PATCH /api/content/documents/<id>/update/`
- **Description:** Admin moves a document to a different folder (or removes it from any folder) via MoveFolderModal from the documents list page. The modal shows all folders from `document-folders/`; clicking a folder PATCHes the document with `folder_id`; "Sin carpeta" sets `folder_id: null`.
- **Steps:**
  1. Admin loads `/panel/documents`.
  2. Admin clicks "Mover a carpeta" button on a document row → `MoveFolderModal` opens.
  3. Modal renders "Sin carpeta" option and all available folder buttons.
  4. Admin clicks a target folder → `documentStore.updateDocument(id, { folder_id })` is called.
  5. On success, modal closes and document list + folder counts refresh.
- **Branches:**
  - [Branch A — Move to folder] Admin selects a named folder → PATCH with `folder_id: <id>`.
  - [Branch B — Remove from folder] Admin clicks "Sin carpeta" → PATCH with `folder_id: null`.
  - [Branch C — Same folder] Clicking the current folder → no PATCH, modal closes.
  - [Branch D — Error] PATCH fails → modal shows "No se pudo mover el documento." error message.
  - [Branch E — Carpeta de otro cliente] La carpeta organiza, no es dueña: un documento **puede** quedar con un cliente distinto al de su carpeta (una cuenta de cobro emitida no puede cambiar de dueño y aun así tiene que poder guardarse donde corresponda). Si el documento **no tiene cliente**, adopta el de la carpeta destino en silencio — heredar no le quita nada a nadie, y lo resuelve el backend. Si ya tiene **otro**, el modal se planta y pregunta (`move-folder-client-choice`): *Conservar su cliente* (default) o *Adoptar el de la carpeta*, que agrega `adopt_folder_client: true` al PATCH. Mismo criterio en el drag&drop.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-move-folder.spec.js` (la pregunta al mover, 2026-08-16)


#### FLOW: `admin-document-send-email`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/documents`
- **API:** `POST /api/emails/send/` (multipart, `document_ids`)
- **Description:** Admin sends a branded email with document PDFs attached from the documents list. The actions sheet's "Enviar por correo" opens `SendDocumentEmailModal` with recipient, subject, greeting, ordered sections (add/remove/move), footer and a picker to attach other documents as PDFs; Edit/Preview tabs mirror the standalone composer. Functional successor of the superseded `admin-proposal-documents-send` flow.
- **Steps:**
  1. Admin loads `/panel/documents` and opens the actions sheet of a document.
  2. Admin clicks "Enviar por correo" → `SendDocumentEmailModal` opens with the document preselected.
  3. Admin fills recipient, subject and section content; optionally attaches more documents.
  4. Admin clicks send → `POST /api/emails/send/` with `document_ids` → success message with the recipient.
- **Branches:**
  - [Branch A — Rate limited] Backend responds 429 → rate-limited message shown.
  - [Branch B — Send error] Other failures render an inline error and keep the modal open.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-send-email.spec.js` (happy path + 429 rate-limited + generic error; added 2026-07-22)

#### FLOW: `admin-document-rename`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **API:** `PATCH /api/documents/<id>/update/`
- **Description:** Admin renames a document from the actions sheet via `RenameDocumentModal`: the input opens prefilled with the current title; saving PATCHes the document and the list shows the new title.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-rename.spec.js` (prefill + PATCH payload + inline-error branch; added 2026-07-22)

#### FLOW: `admin-document-delete`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **API:** `DELETE /api/documents/<id>/delete/`
- **Description:** Admin deletes a document from the actions sheet: "Eliminar" opens a ConfirmModal; confirming deletes and removes the row/card, cancelling keeps it.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-delete.spec.js` (confirm + cancel + error-toast branches; added 2026-07-22)

#### FLOW: `admin-document-archive`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **API:** `PATCH /api/documents/<id>/archive/`, `PATCH /api/documents/<id>/unarchive/`, `PATCH /api/document-folders/<id>/archive/`, `PATCH /api/document-folders/<id>/unarchive/`, `GET /api/documents/?scope=active|archived|all[&folder=<id>][&search=][&order=oldest]`, `GET /api/document-folders/?scope=…[&search=]`, `GET /api/documents/counts/`
- **Description:** Archivar saca algo de circulación sin destruirlo — el punto intermedio que faltaba entre editar y eliminar. Desde 2026-08-12 el archivo es un **árbol navegable** y no una lista plana: dónde se está (`activeFolderId`: `all` | `root` | `none` | `<id>`) y en qué estado se mira (`scope`: `active` | `archived` | `all`, por defecto `active`) son ejes independientes. La regla que gobierna todo: **nada queda restaurado sin ubicación alcanzable** — restaurar reabre la cadena de carpetas contenedoras, y sólo la cadena. Desde 2026-08-15 el ámbito archivado es además un **modo declarado**: «Ver documentos archivados» es un interruptor en la cabecera del panel lateral, fuera de la lista de carpetas, porque como fila entre ellas se leía como un destino más y nada decía que el archivo es el estado en que se ve TODO el panel — volver a «Todos» seguía listando archivados y la única salida era editar la URL a mano.
- **Steps:**
  1. Admin abre la hoja de acciones de un documento → "Archivar" → sale de la lista, con toast, y los contadores del sidebar se recalculan.
  2. Admin intenta eliminar un documento → el modal ofrece "Archivar en su lugar" **antes** de escribir `DELETE`.
  3. Admin archiva una carpeta desde el ícono de su fila en el sidebar → confirmación con el inventario que va a arrastrar.
  4. Admin enciende «Ver documentos archivados» → el listado se rotula con el modo y se tiñe, el panel lateral pasa a listar las carpetas raíz reales (una carpeta archivada entera deja de aparentar que no existe) y todos sus contadores cuentan lo archivado; las carpetas archivadas se ven como **contenedores**, no sus documentos como hermanos.
  5. Admin entra a una carpeta archivada → sus subcarpetas y documentos, con breadcrumb "Archivados › …" para volver.
  6. Admin pulsa "Restaurar" sobre un documento de dentro → vuelve, y con él la cadena de carpetas que lo contenía, reportada en el toast.
  7. Admin cambia el filtro de estado (Todos / Solo activos / Solo archivados) → aplica a carpetas y documentos.
  8. Admin busca por título o cliente → recorre todo el gestor y los dos estados, marcando los resultados archivados.
  9. Admin navega dentro del archivo → el interruptor sigue encendido a cualquier profundidad y la carpeta en la que está parado se resalta (`aria-current="page"`), con el breadcrumb dando la ruta. La regla de resaltado único se retiró: con el modo declarado por el interruptor, apagar la fila activa dejaba al panel sin decir dónde estaba el usuario.
  9b. Admin apaga el modo estando dentro de una carpeta → permanece en ella viendo su contenido activo, y la URL suelta el parámetro. Si la carpeta no guarda nada archivado, el vacío lo dice por su nombre en vez del genérico.
  10. Admin archiva o elimina la carpeta que está viendo — o un ancestro de ella — → la vista se retira al padre de la carpeta afectada (o a Todos), sin quedar parada en una descendiente fantasma.
  11. Admin recarga o comparte la URL → `?folder=&scope=` reconstruyen carpeta y estado (los defaults no se escriben; el scope transitorio de la búsqueda nunca se persiste). La URL manda en los dos sentidos: un parámetro ausente significa el default —así una carpeta vieja no sobrevive a volver al módulo por el menú— y atrás/adelante del navegador reaplican a la vista.
  12. Admin elimina o mueve un documento dentro de una carpeta → la vista se queda en esa carpeta, la misma regla que ya seguía archivar.
- **Branches:**
  - [Branch A — Cascada con memoria] Archivar una carpeta arrastra subcarpetas y documentos, marcando cada uno con la carpeta que lo causó (`archived_via_folder`). Al desarchivarla vuelve sólo lo que ella arrastró: lo que el usuario había archivado por su cuenta se queda archivado.
  - [Branch B — Carpeta con contenido] El ícono de eliminar queda deshabilitado con tooltip en cuanto la carpeta contiene algo, archivado incluido — el mismo criterio del 409 del backend. Archivar, en la fila de al lado, es la salida.
  - [Branch C — Sin carpeta padre] Un documento cuya carpeta fue eliminada mientras estaba archivado vuelve a "Sin carpeta" (`folder` es `SET_NULL`). Si la cadena está rota por un ciclo en los datos, se desengancha ahí a propósito: una ubicación pobre es mejor que ninguna.
  - [Branch D — Restauración por cadena] Restaurar un elemento cuya carpeta sigue archivada reabre la cadena contenedora hasta la raíz y **sólo** la cadena. Antes esto respondía 409 para carpetas y, para documentos, los dejaba activos dentro de una carpeta archivada: invisibles en ambas vistas. La migración 0186 reparó los que ya se habían perdido así.
  - [Branch E — Estado mixto] La consecuencia buscada del branch D: una carpeta activa con contenido archivado dentro. Lo declara con una insignia que, al pulsarla, entra a esa carpeta en su scope archivado.
  - [Branch F — Sin arrastre] Una fila archivada no se arrastra, el interruptor «Ver documentos archivados» no es drop target y no se acepta soltar contenido activo dentro de una carpeta archivada: archivar es siempre un gesto explícito, y nada activo puede acabar sepultado.
  - [Branch G — Salir de la búsqueda navegando] Elegir una carpeta o pulsar la insignia de archivados en plena búsqueda SALE de la búsqueda y navega de verdad (la insignia aterriza en esa carpeta en scope archivado). Antes el watcher de limpieza restauraba el scope previo por debajo y el clic parecía no hacer nada. La búsqueda además muestra el skeleton de la lista mientras vuela y descarta los resultados del término anterior.
  - [Branch H — Restaurar la carpeta actual] Parado dentro de una carpeta archivada, un aviso ofrece «Restaurar esta carpeta» (las filas del listado solo restauran hijas); al éxito la vista SIGUE a la carpeta hacia el scope activo. Los confirms de archivar/eliminar giran mientras corren (`waitForConfirm`) y los botones Restaurar quedan inertes durante la mutación.
  - [Branch I — Portal del cliente] Un documento archivado desaparece del portal del cliente (lista, detalle, PDF y firma — decisión del 13-ago-2026); restaurarlo lo devuelve tal cual. El admin de Django tiene los campos de archivado sellados como readonly y `audit_archive_integrity` audita/repara el invariante en producción.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-archive.spec.js` (added 2026-08-11; jerarquía, restauración por cadena, filtro de estado, búsqueda global y contadores añadidos 2026-08-12; sidebar encendido en profundidad, retirada al padre al archivar un ancestro, salida de búsqueda navegando, restaurar-la-carpeta-actual y persistencia en URL añadidos 2026-08-13; interruptor de modo con rótulo y contadores por ámbito, restaurar-uno-de-dos volviendo a la carpeta en modo normal, y navegación tras eliminar y mover añadidos 2026-08-15). La cascada con memoria, la restauración por cadena y las guardas contra huérfanos nuevos se cubren en backend (`content/tests/services/test_document_archive_service.py`, `content/tests/services/test_document_orphan_repair_migration.py`, `content/tests/management/test_audit_archive_integrity.py`); el portal que excluye archivados, en `accounts/tests/test_client_documents.py`.

#### FLOW: `admin-document-folder-manage`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **API:** `POST /api/document-folders/create/`, `PATCH /api/document-folders/<id>/update/`, `DELETE /api/document-folders/<id>/delete/`, `POST /api/document-folders/reorder/`
- **Description:** Una carpeta se edita con **un solo formulario** (`FolderFormModal`: nombre, carpeta padre, cliente y proyecto) al que se llega desde los tres lugares donde se la usa — la **cabecera** al entrar en ella (`FolderHeader`, que además nombra su cliente y su proyecto), la **fila del panel lateral** (`folder-edit`, junto a archivar y eliminar) y el **lápiz del árbol** del gestor. Los selectores con búsqueda de cliente y proyecto usan la capa flotante compartida del modal, por lo que el panel no recorta sus resultados y una lista larga desplaza sólo el listbox. Hasta 2026-08-16 editar algo ya existente sólo se podía dentro del modal de NUEVA carpeta, en un panel inline que ya no existe: `FolderManagerModal` queda para crear y ordenar el árbol, y su creación rápida hereda cliente y proyecto de la carpeta padre elegida. `admin-document-folders` only covers parent pre-selection on create. El sidebar (`FolderSidebar`) expone además dos íconos por fila, ambos con tooltip: **archivar**, siempre disponible porque es la salida de una carpeta que no se puede borrar; y **eliminar**, deshabilitado en cuanto la carpeta contiene algo — archivado incluido, que es el criterio del 409 del backend. Con la carpeta vacía, eliminar abre `DeleteFolderModal`, que muestra el inventario y exige escribir `DELETE` (sensible a mayúsculas). El ícono del gestor de carpetas delega en ese mismo modal, así que el borrado de carpeta tiene un solo contrato.
- **Coverage:** ✅ Covered (create/rename/delete; sidebar delete con confirmación DELETE y conflicto 409; ícono de eliminar inerte en carpeta con contenido y archivado como salida; drag-reorder not asserted — flaky in CI)
- **E2E Spec:** `e2e/admin/admin-document-folder-manage.spec.js` (added 2026-07-22; sidebar delete added 2026-08-04; rama bloqueada reemplazada por la de archivar 2026-08-11; eliminar vuelve a deshabilitarse y archivar pasa a la fila 2026-08-12; edición desde la fila y desde la cabecera 2026-08-16)

#### FLOW: `admin-document-duplicate`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/documents`
- **API:** `POST /api/documents/<id>/duplicate/`
- **Description:** Admin duplicates a document from the actions sheet; the copy appears in the list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-hosting-card-delete.spec.js` (confirm + cancel + error; added 2026-07-23)

#### FLOW: `admin-document-drag-organize`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/documents`
- **API:** `PATCH /api/documents/<id>/update/` (folder_id), `PATCH /api/document-folders/<id>/update/` (parent)
- **Description:** Admin organizes by drag-and-drop: dragging a document onto a sidebar folder moves it, and dragging a folder onto another folder (or breadcrumb) re-parents it. The modal-based move path is covered by `admin-document-move-folder`; the drag path is not.
- **Coverage:** ❌ Missing
- **E2E Spec:** — (spec not yet written; registered 2026-07-16 audit; DnD needs dispatchEvent-based simulation)

### 9.2 Admin User Management

#### FLOW: `admin-admin-management`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/admins`
- **Description:** Manage platform admin users — list with status filters, invite new admin via modal, deactivate existing admins.
- **Steps:**
  1. Admin navigates to `/panel/admins`.
  2. Admin list loads from API (`GET /api/accounts/admins/`).
  3. Filter tabs render: Todos / Activos / Inactivos.
  4. Each admin row shows avatar, name, email, role, status badge, and actions.
- **Branches:**
  - [Branch A — Invite] Admin clicks "Agregar Administrador" → modal opens with email, name, role fields → submit calls `POST /api/accounts/admins/` → invitation sent.
  - [Branch B — Filter] Admin clicks status tab → list filters client-side.
  - [Branch C — Deactivate] Admin clicks deactivate → confirm → `PATCH /api/accounts/admins/:id/` → status changes.
  - [Branch D — Empty state] No admins → empty state message with invite CTA.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-admin-management.spec.js`

### 9.3 Email Deliverability Dashboard

#### FLOW: `admin-email-deliverability`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/email-deliverability`
- **Description:** Dashboard tracking email send/delivery/bounce/open rates for all proposal-related automated emails. Admin monitors deliverability health.
- **Steps:**
  1. Admin navigates to `/panel/proposals/email-deliverability`.
  2. Dashboard loads email delivery metrics from API.
  3. Stats render: total sent, delivered, bounced, open rate.
  4. Per-proposal email log table shows individual send events.
- **Branches:**
  - [Branch A — Empty state] No emails sent yet → "No hay datos de entregas." message.
  - [Branch B — Date filter] Admin filters by date range → metrics update.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-email-deliverability.spec.js`

### 9.4 Public Landing Pages

#### FLOW: `public-landing-software`

- **Module:** public
- **Role:** guest
- **Priority:** P3
- **Routes:** `/landing-software`
- **Description:** Custom software development landing page with hero section, feature highlights, CTA, and contact form.
- **Steps:**
  1. Guest navigates to `/landing-software`.
  2. Hero section renders with headline and CTA button.
  3. Feature/service highlights section renders.
  4. Contact form or CTA link rendered at the bottom.
- **Branches:**
  - [Branch A — CTA click] Guest clicks primary CTA → scrolls to contact section or navigates to `/contacto`.
  - [Branch B — Locale] Page renders in both ES and EN via locale switcher.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-landing-software.spec.js`

#### FLOW: `public-landing-apps`

- **Module:** public
- **Role:** guest
- **Priority:** P3
- **Routes:** `/landing-apps`
- **Description:** Mobile app development landing page with hero section, feature highlights, platform badges (iOS/Android), CTA, and contact form.
- **Steps:**
  1. Guest navigates to `/landing-apps`.
  2. Hero section renders with headline and CTA button.
  3. Feature/service highlights and platform badges render.
  4. Contact form or CTA link rendered at the bottom.
- **Branches:**
  - [Branch A — CTA click] Guest clicks primary CTA → scrolls to contact section or navigates to `/contacto`.
  - [Branch B — Locale] Page renders in both ES and EN via locale switcher.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-landing-apps.spec.js`

---

### 9.5 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-document-list` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-list.spec.js` |
| `admin-document-gallery` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-gallery.spec.js` |
| `admin-document-unsaved-guard` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-unsaved-guard.spec.js` |
| `admin-panel-unsaved-guard` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-panel-unsaved-guard.spec.js` |
| `admin-document-folders` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-folders.spec.js` |
| `admin-document-folder-hierarchy` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-folder-hierarchy.spec.js` |
| `admin-document-folder-panel-resize` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-document-folder-panel-resize.spec.js` |
| `admin-document-pdf-download` | admin | admin | P2 | ⬜ Missing | — (spec not yet written) |
| `admin-document-move-folder` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-document-move-folder.spec.js` |
| `admin-document-send-email` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-document-send-email.spec.js` |
| `admin-document-rename` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-rename.spec.js` |
| `admin-document-delete` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-delete.spec.js` |
| `admin-document-archive` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-archive.spec.js` |
| `admin-document-folder-manage` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-folder-manage.spec.js` |
| `admin-document-folder-change-client` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-document-folder-change-client.spec.js` |
| `admin-document-duplicate` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-document-duplicate.spec.js` |
| `admin-document-drag-organize` | admin | admin | P3 | ❌ Missing | — (spec not yet written) |
| `admin-task-deadline-notification` | admin | system | P2 | ⬜ Backend-only | N/A |
| `admin-diagnostic-create` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-create.spec.js` |
| `admin-diagnostic-send-initial` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-send.spec.js` |
| `admin-diagnostic-send-final` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-send.spec.js` |
| `admin-diagnostic-email` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-email-documents.spec.js` |
| `admin-diagnostic-documents` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-email-documents.spec.js` |
| `admin-diagnostic-sections` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-sections.spec.js` |
| `admin-diagnostic-activity` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-sections.spec.js` |
| `admin-diagnostic-analytics` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-analytics.spec.js` |
| `admin-diagnostic-engagement-score` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-analytics.spec.js` |
| `admin-diagnostic-prompt` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-prompt.spec.js` |
| `diagnostic-public-view` | diagnostic | guest | P1 | ✅ Covered | `e2e/public/diagnostic-public-view.spec.js` + `e2e/admin/admin-diagnostic-sections.spec.js` |
| `admin-admin-management` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-admin-management.spec.js` |
| `admin-email-deliverability` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-email-deliverability.spec.js` |
| `admin-send-branded-email` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-email.spec.js` |
| `admin-send-proposal-email` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-email.spec.js` |
| `public-landing-software` | public | guest | P3 | ✅ Covered | `e2e/public/public-landing-software.spec.js` |
| `public-landing-apps` | public | guest | P3 | ✅ Covered | `e2e/public/public-landing-apps.spec.js` |

---

## 10. New Feature Flows (v2.9.0)


> Flows registered during the v2.9.0 audit for contract generation, document management, and document sending features on the proposal edit Documents tab. These features are visible only when proposal status is `negotiating`, `accepted`, or `rejected`.

### 10.1 Admin Proposal Contract & Documents

#### FLOW: `admin-proposal-contract-generate`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Documents tab)
- **Description:** Admin generates a development contract from the proposal edit Documents tab. Two source modes: "Contrato por defecto" (structured params form with auto-populated company settings for contractor/client info, banking details, contract date) or "Contrato personalizado" (paste or upload custom Markdown with live preview). Submit calls `POST /api/proposals/:id/contract/save-and-negotiate/`.
- **Steps:**
  1. Admin navigates to `/panel/proposals/:id/edit` for a proposal with status `negotiating`/`accepted`/`rejected`.
  2. Admin clicks the "Documentos" tab.
  3. In the "Contrato de desarrollo" section, admin clicks "Generar contrato de desarrollo" button (visible when no contract exists).
  4. ContractParamsModal opens with "Contrato por defecto" mode selected. Company settings auto-populate contractor fields.
  5. [Branch A — Default] Admin fills/verifies contractor params (name, cedula, email, city, bank details) and client params (name, cedula, email), sets contract date.
  6. [Branch B — Custom] Admin toggles to "Contrato personalizado", pastes or uploads a `.md` file, optionally toggles preview.
  7. Admin clicks "Generar contrato y negociar" → API call to `POST /api/proposals/:id/contract/save-and-negotiate/`.
  8. Contract document appears in the Documents tab with download links.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-contract-generate.spec.js`

Ante un fallo de generación, el modal conserva el borrador y permite reintentar
desde el listado y desde el editor. Sólo se cierra tras guardar correctamente;
durante el envío bloquea nuevos envíos y el cierre.

#### FLOW: `admin-proposal-contract-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Documents tab)
- **Description:** Admin edits an existing contract's parameters via "Editar parámetros" button. ContractParamsModal opens pre-filled with saved params. Submit calls `PUT /api/proposals/:id/contract/update/`.
- **Steps:**
  1. Admin opens Documents tab for a proposal that already has a generated contract.
  2. Admin clicks "Editar parámetros" button next to the contract.
  3. ContractParamsModal opens in edit mode with existing params pre-filled.
  4. Admin modifies fields and clicks "Actualizar contrato".
  5. API call to `PUT /api/proposals/:id/contract/update/`.
  6. Updated contract reflected in Documents tab.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-contract-edit.spec.js`

#### FLOW: `admin-proposal-contract-download`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Documents tab)
- **Description:** Admin downloads contract PDF (final) or draft PDF from the Documents tab. Links visible only when a contract has been generated.
- **Steps:**
  1. Admin opens Documents tab for a proposal with a generated contract.
  2. "Descargar" link points to `GET /api/proposals/:id/contract/pdf/`.
  3. "Borrador" link points to `GET /api/proposals/:id/contract/draft-pdf/`.
  4. [Branch A — No contract] When no contract is generated, section shows "No generado" and no download links.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-contract-download.spec.js`

#### FLOW: `admin-proposal-documents-manage`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Documents tab)
- **Description:** Admin uploads additional documents (otrosí, legal annex, client document, other with custom type label) to a proposal. Existing documents listed with type badges. Non-generated documents can be deleted.
- **Steps:**
  1. Admin opens Documents tab.
  2. "Documentos adicionales" section lists existing uploaded documents with type badge and download link.
  3. Admin fills upload form: title, type (select), file, optionally custom label for "Otro" type.
  4. Admin clicks "Subir" → `POST /api/proposals/:id/documents/upload/` with FormData.
  5. New document appears in the list after refresh.
  6. Admin clicks delete icon on a non-generated document → `DELETE /api/proposals/:id/documents/:docId/delete/`.
  7. Document removed from list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-documents-manage.spec.js`

#### FLOW: `admin-proposal-documents-send`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Documents tab)
- **Description:** Admin selects documents to send to client via email. Checkboxes for main docs (draft contract, commercial PDF, technical PDF) and additional uploaded docs. Opens SendDocumentsModal with editable email fields (subject, greeting, body, per-document descriptions, footer). Submit calls `POST /api/proposals/:id/documents/send/`.
- **Steps:**
  1. Admin opens Documents tab.
  2. "Enviar documentos al cliente" section shows checkboxes: draft contract (disabled if no contract), commercial, technical, plus any additional docs.
  3. Admin selects desired documents.
  4. Admin clicks "Enviar al cliente" button (disabled if no docs selected or no client email).
  5. SendDocumentsModal opens with pre-filled email: subject, greeting with client name, intro body, per-document descriptions, footer.
  6. Admin edits email fields as needed.
  7. Admin clicks "Enviar documentos" → API call to `POST /api/proposals/:id/documents/send/`.
  8. Success message: "Documentos enviados correctamente."
- **Coverage:** ⚠️ Superseded — replaced by `admin-proposal-attach-from-documents` (Apr 22, 2026). The "Enviar documentos" section was removed from the Documents tab; document attachment now happens in the Correos tab via `doc_refs`.
- **E2E Spec:** *(spec deleted; see `e2e/admin/admin-proposal-attach-from-documents.spec.js`)*

### 10.3 Composed Email Flows

#### FLOW: `admin-send-branded-email`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Description:** Admin sends a branded email from the proposal edit page "Correos" tab.
- **Visible when:** Proposal status in `negotiating`, `accepted`, `rejected`
- **Steps:**
  1. Navigate to `/panel/proposals/:id/edit`
  2. Click the "Correos" tab
  3. Fill composer: recipient, subject, greeting, draggable sections (each with an optional Markdown toggle), footer
  4. Optionally attach files (PDF, DOC, DOCX, XLS, XLSX, PNG, JPG, JPEG; max 15 MB)
  5. Preview email in "Vista previa" sub-tab (server-rendered via `POST /api/emails/preview/` with `proposal_id`, shown in a sandboxed iframe)
  6. Click "Enviar correo" → `POST /api/proposals/:id/branded-email/send/`
  7. Verify history updates with new entry
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-email.spec.js`

#### FLOW: `admin-send-proposal-email`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Description:** The **Correos** tab is visible from draft onward. Its first card owns the editable plain-text personalized message used by initial send/re-send. After the first send, it also exposes the proposal follow-up composer; each follow-up is logged as `ProposalChangeLog` activity.
- **Visible when:** Every proposal status; follow-up composer/history appear in `sent`, `viewed`, `negotiating`, `accepted`, and `rejected`.
- **Steps:**
  1. Navigate to `/panel/proposals/:id/edit`
  2. Click the "Correos" tab
  3. Write/preview/save the personalized initial-send message; a draft may save it empty but cannot be sent until completed
  4. For an already-sent proposal, fill the follow-up composer and click "Enviar correo" → `POST /api/proposals/:id/proposal-email/send/`
  5. Verify `ProposalChangeLog` entry created with `change_type=email_sent` and `last_activity_at` updated
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-email.spec.js`

#### FLOW: `admin-standalone-email-composer`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/emails`
- **Description:** Admin composes and sends branded emails from the standalone Emails page (not tied to any proposal). The page has three tabs (Redactar / Historial / Valores por defecto, deep-linked via `?tab=`). Redactar: draggable sections with a per-section Markdown toggle, file attachments and a server-rendered preview of the real branded template. Historial: paginated email history. Uses dedicated standalone endpoints distinct from proposal-scoped email flows.
- **Steps:**
  1. Admin navigates to `/panel/emails` via sidebar navigation (Redactar tab active by default).
  2. Composer loads with defaults from `GET /api/emails/defaults/`.
  3. Admin fills recipient email, subject, greeting, draggable body sections (each with an optional Markdown toggle), and footer.
  4. Optionally attaches files.
  5. Admin opens the "Vista previa" sub-tab → `POST /api/emails/preview/` returns the real `branded_email.html` render (shown in a sandboxed iframe, markdown sections converted server-side).
  6. Admin clicks "Enviar" → `POST /api/emails/send/`.
  7. Success toast renders bottom-right via `usePanelNotify` ("Correo enviado correctamente."); email history updates. Errors surface inline next to the send button and as an error toast.
  8. Admin opens the "Historial" tab and views paginated email history from `GET /api/emails/history/`.
- **Branches:**
  - [Branch A — Empty recipient] Send button disabled when recipient email is empty.
  - [Branch B — File limits] Attachment validation enforces type and size limits.
- **Coverage:** ✅ Covered (section add/remove, send-error alert, history "Cargar más" pagination asserted 2026-07-23; drag-reorder intentionally not asserted — flaky in CI; attachments split to `admin-standalone-email-attachments`)
- **E2E Spec:** `e2e/admin/admin-standalone-email-composer.spec.js`

#### FLOW: `admin-standalone-email-defaults`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/emails?tab=defaults`
- **Description:** Admin configures the defaults used by the standalone email composer from the "Valores por defecto" tab of `/panel/emails`: default greeting (supports `{client_name}` / `{title}` variables), default footer and default signer. Values persist as `EmailTemplateConfig('branded_email').content_overrides`; the configured signer is used for standalone sends and previews (proposal emails keep their per-proposal signer).
- **Steps:**
  1. Admin opens `/panel/emails` and clicks the "Valores por defecto" tab (or deep-links `?tab=defaults`).
  2. Form loads prefilled from `GET /api/emails/defaults/` (`config` + `available_signers` + `available_variables`).
  3. Admin edits greeting/footer and/or picks a signer from the select.
  4. Admin clicks "Guardar valores" → `PUT /api/emails/defaults/` stores the overrides (values equal to defaults or blank are dropped) and a success notification renders.
  5. The composer on the Redactar tab now seeds new emails with the saved values.
- **Branches:**
  - [Branch A — Restore] "Restaurar valores originales" submits the registry/settings defaults, clearing all overrides.
  - [Branch B — Invalid signer] Backend rejects unknown signer keys with 400 (`El firmante seleccionado no es válido.`).
- **Coverage:** ✅ Covered (restore-defaults PUT payload and invalid-signer 400 message asserted 2026-07-23)
- **E2E Spec:** `e2e/admin/admin-standalone-email-composer.spec.js`

#### FLOW: `admin-standalone-email-attachments`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/emails`
- **API:** `POST /api/emails/send/` (multipart with attachments)
- **Description:** Admin attaches files to a standalone email: multiple file input (`.pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg`), client-side type/size validation via `validateEmailAttachments` (`~/utils/emailAttachments`), per-file remove button, and multipart send including the attachments. Split out of `admin-standalone-email-composer` (its documented Branch B) because no test exercises it.
- **Steps:**
  1. Admin fills the composer on `/panel/emails`.
  2. Admin selects one or more files with the "Adjuntar archivos" input.
  3. Invalid type/size files are rejected with a validation message; valid ones list with a remove button.
  4. Admin sends → multipart `POST /api/emails/send/` includes the attachments.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-standalone-email-attachments.spec.js` (upload + multipart send, validation rejection, remove; added 2026-07-22)

---

### 10.4 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-proposal-contract-generate` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-proposal-contract-generate.spec.js` |
| `admin-proposal-contract-edit` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-contract-edit.spec.js` |
| `admin-proposal-contract-download` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-contract-download.spec.js` |
| `admin-proposal-documents-manage` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-documents-manage.spec.js` |
| `admin-proposal-documents-send` | admin | admin | P1 | ⚠️ Superseded | replaced by `admin-proposal-attach-from-documents` (Apr 22, 2026) |
| `admin-send-branded-email` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-email.spec.js` |
| `admin-send-proposal-email` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-email.spec.js` |
| `admin-standalone-email-composer` | admin | admin | P2 | ✅ Covered (drag-reorder not asserted — flaky in CI) | `e2e/admin/admin-standalone-email-composer.spec.js` |
| `admin-standalone-email-defaults` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-standalone-email-composer.spec.js` |
| `admin-standalone-email-attachments` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-standalone-email-attachments.spec.js` |

---

## 11. New Feature Flows (v2.12.0)


> Flows registered during the v2.12.0 audit for the LinkedIn integration (commit `e070c330`). LinkedIn publishing is available on the blog post edit page and requires OAuth connection.

### 11.1 Admin Blog LinkedIn Integration

#### FLOW: `admin-blog-linkedin-connect`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/:id/edit` (LinkedIn fieldset)
- **API:** `GET /api/linkedin/auth-url/`, `POST /api/linkedin/callback/`, `GET /api/linkedin/status/`
- **Frontend pages involved:** `/panel/blog/:id/edit`, `/auth/linkedin/callback`
- **Description:** Admin connects the LinkedIn account to the panel via OAuth 2.0 authorization code flow. The OAuth popup opens, the user authenticates with LinkedIn, and the callback page exchanges the code for encrypted tokens stored server-side.
- **Steps:**
  1. Admin opens `/panel/blog/:id/edit`.
  2. LinkedIn section is shown in the form. Status loads from `GET /api/linkedin/status/`.
  3. Connection status is **disconnected** → "LinkedIn no conectado." label and "Conectar LinkedIn" button are visible.
  4. Admin clicks "Conectar LinkedIn" → `GET /api/linkedin/auth-url/` → popup window opens at the LinkedIn authorization URL.
  5. User authenticates with LinkedIn in the popup.
  6. LinkedIn redirects to `/auth/linkedin/callback?code=...&state=...`.
  7. Callback page exchanges code via `POST /api/linkedin/callback/`.
  8. On success: popup shows "LinkedIn conectado correctamente" and "Puedes cerrar esta ventana." with green checkmark.
  9. Popup sends `postMessage({ type: 'linkedin-connected', data: connection })` to opener window.
  10. Opener window updates `linkedinStatus` → "Conectar LinkedIn" button replaced with profile name and language selector.
- **Branches:**
  - [Branch A — OAuth error] LinkedIn returns `?error=access_denied` → popup shows error message in red.
  - [Branch B — No code] Callback page receives no `code` param → error "No se recibió código de autorización."
  - [Branch C — API error] Backend exchange fails → error displayed in popup.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-linkedin.spec.js`

#### FLOW: `admin-blog-linkedin-publish`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/:id/edit` (LinkedIn fieldset)
- **API:** `POST /api/blog/admin/:post_id/publish-linkedin/`
- **Description:** Admin publishes a blog post summary to LinkedIn directly from the edit page. Requires LinkedIn to be connected and a summary text filled for the selected language.
- **Steps:**
  1. Admin opens `/panel/blog/:id/edit`.
  2. LinkedIn status loads — account is **connected**: green dot + profile name shown.
  3. Admin fills `linkedin_summary_en` (≤1300 chars) or `linkedin_summary_es` textarea with the post summary.
  4. Admin selects language from dropdown ("Publish in English" / "Publicar en Español") — defaults to English (US market focus).
  5. Admin clicks "Publicar en LinkedIn" button (disabled if summary is empty or publish in progress).
  6. API call to `POST /api/blog/admin/:id/publish-linkedin/` with `{ lang }`.
  7. Success: success message "Publicado en LinkedIn correctamente." renders and auto-hides after 5s.
  8. "Última publicación:" timestamp renders with date of last publish.
- **Branches:**
  - [Branch A — API error] Publish fails → error message renders in red.
  - [Branch B — Token expired] Backend auto-refreshes token; if refresh token also expired, error is returned.
  - [Branch C — Empty summary] "Publicar en LinkedIn" button is disabled until summary is filled.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-linkedin.spec.js`

#### FLOW: `admin-qr-cards`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/qr-cards`
- **API:** `GET/POST /api/qr-cards/admin/`, `PATCH /api/qr-cards/admin/:id/update/`, `DELETE /api/qr-cards/admin/:id/delete/`; public redirect at `GET /t/:uuid/` (outside `/api/`).
- **Description:** Admin creates a "tarjeta" (name required, destination URL optional) which gets a UUID and a short public link (`/t/:uuid/`). The QR always encodes the short link, never the destination, so changing the destination later never requires reprinting. Admin can edit the destination, toggle active/inactive, and download a PNG QR with custom foreground/background colors or a transparent background — generated entirely client-side, never persisted.
- **Steps:**
  1. Admin opens `/panel/qr-cards`.
  2. Clicks "Nueva tarjeta", fills a name (destination optional), saves.
  3. Row appears with its short link, "Sin configurar" if no destination was set.
  4. Admin edits the card to set/change `destination_url`.
  5. Admin toggles the row's active switch.
  6. Admin clicks "Descargar QR", adjusts foreground/background color or checks "Fondo transparente", downloads the PNG.
- **Branches:**
  - [Branch A — no destination configured] Scanning the short link shows "Este enlace aún no ha sido configurado." instead of redirecting.
  - [Branch B — inactive card] Scanning the short link shows "Este enlace no está disponible." instead of redirecting.
  - [Branch C — active + configured] Scanning the short link 302-redirects to `destination_url`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-qr-cards.spec.js`

#### FLOW: `admin-linktrees`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/linktrees`, `/panel/linktrees/:id/edit`
- **API:** `GET/POST /api/linktrees/admin/`, `GET /api/linktrees/admin/:id/`, `PATCH /api/linktrees/admin/:id/update/`, `DELETE /api/linktrees/admin/:id/delete/`.
- **Description:** Admin creates a linktree (internal name + unique customizable handle, personal/company kind) and edits its identity block, tiered buttons, PWA-install block and vCard data. The public URL is `/lk/@handle`. Button tiers follow the design system's hard rules — exactly 1 `primary`, at most 1 `featured`, `pair` buttons in twos, at most 6 `row` — enforced by the backend serializer. A linktree can be assigned as the destination of a QR card (`destination_type: linktree`), keeping the printed QR's short link intact.
- **Steps:**
  1. Admin opens `/panel/linktrees`.
  2. Clicks "Nuevo linktree", fills name + handle (with or without `@`), picks the kind, saves — lands on the editor.
  3. Edits identity fields, adds/reorders buttons per tier, configures the PWA block and vCard data, saves.
  4. Copies the public URL or opens it in a new tab.
  5. In `/panel/qr-cards`, edits a card, switches destination to "Linktree" and selects one.
- **Branches:**
  - [Branch A — duplicate/reserved/invalid handle] Backend returns 400 with a specific handle error rendered under the field.
  - [Branch B — tier cardinality violation] Backend returns 400 with the violated rule; the editor surfaces it in an alert.
  - [Branch C — delete with assigned QR cards] Cards fall back to `SET_NULL` and scan as "not configured" until reassigned.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-linktrees.spec.js`

#### FLOW: `public-linktree-view`

- **Module:** public
- **Role:** visitor
- **Priority:** P2
- **Routes:** `/lk/@:handle` (Django clean-URL redirect), `/es-co/lk/@:handle` (SPA page)
- **API:** `GET /api/linktrees/public/:handle/`; QR short link `GET /t/:uuid/` 302s here when the card's destination is a linktree.
- **Description:** Visitor opens a linktree via the QR short link or the clean `/lk/@handle` URL and sees the brand-fixed page (esmerald/lemon palette, Ubuntu): identity block per kind, buttons rendered by tier in order (pairs side by side), vCard download, PWA install block and footer tagline. Buttons without a resolved destination render dashed with a `PENDIENTE` tag and are inert.
- **Steps:**
  1. Visitor scans the QR (or opens `/lk/@handle`) and lands on the SPA page.
  2. Page fetches the public payload by handle and renders the design.
  3. Visitor taps a button: URL/mailto navigate, "Guardar" downloads the `.vcf`, "Añadir a mi pantalla" triggers the install prompt or instructions.
- **Branches:**
  - [Branch A — unknown or inactive handle] Page shows the "Este enlace no está disponible." state (API 404).
  - [Branch B — pending button] Dashed gray render, no navigation on click.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-linktree.spec.js`

### 11.2 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Suggested Spec |
|---------|--------|------|----------|--------|----------------|
| `admin-blog-linkedin-connect` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-blog-linkedin.spec.js` |
| `admin-blog-linkedin-publish` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-blog-linkedin.spec.js` |
| `admin-proposal-advanced-filters` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-advanced-filters.spec.js` |
| `public-privacy-policy` | public | guest | P4 | ✅ Covered | `e2e/public/public-privacy-policy.spec.js` |
| `public-terms-conditions` | public | guest | P4 | ✅ Covered | `e2e/public/public-terms-conditions.spec.js` |
| `admin-proposal-project-schedule` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-proposal-project-schedule.spec.js` |
| `admin-qr-cards` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-qr-cards.spec.js` |
| `admin-linktrees` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-linktrees.spec.js` |
| `public-linktree-view` | public | visitor | P2 | ✅ Covered | `e2e/public/public-linktree.spec.js` |

---

## 12. New Feature Flows (v2.15.0)


> Flows registered during the v2.15.0 audit for the Real Client Entity feature (shipped 2026-04-09). Covers the two client-write flows discovered during the e2e-user-flows-check audit that were not yet registered: editing an existing client profile with propagation, and re-assigning the client on an existing proposal.

### 12.1 Admin Client Profile Update

No active browser flow is registered for client profile editing at this time.

- **Current panel surface:** `/panel/clients/` supports list, filter, expand, standalone create, and orphan delete.
- **Missing UI route:** `/panel/clients/:id/edit` is not implemented in `frontend/pages/panel/clients/` as of 2026-04-10.
- **Backend capability:** `PATCH /api/proposals/client-profiles/:id/` exists and is covered by backend tests, but there is no current panel route that exposes it as a user journey.
- **E2E expectation:** none until a real panel edit surface exists.

### 12.2 Admin Proposal Re-assign Client

#### FLOW: `admin-proposal-update-client`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit`
- **API:** `PATCH /api/proposals/:id/` with `client_id` (new client)
- **Frontend pages involved:** `/panel/proposals/:id/edit`
- **Description:** Admin changes the client linked to an existing draft or active proposal. Uses the same `ClientAutocomplete.vue` component as the create flow. On save, the backend re-assigns `BusinessProposal.client` FK and syncs snapshot fields to the newly selected client's data.
- **Steps:**
  1. Admin opens `/panel/proposals/:id/edit`.
  2. Client autocomplete input shows the current client name.
  3. Admin clears the input and types a different client name to search.
  4. Dropdown shows matching results; admin selects a different client.
  5. Snapshot fields (`client_name`, `client_email`, `client_phone`) update immediately in the form.
  6. Admin clicks "Guardar propuesta".
  7. `PATCH /api/proposals/:id/` is sent with the new `client_id`.
  8. Backend calls `proposal_client_service.sync_snapshot(proposal)` after FK update.
  9. Success toast renders; snapshot fields now reflect the new client.
- **Branches:**
  - [Branch A — New client has placeholder email] Autocomplete badge shows "Sin email real"; proposal automations are paused for this client until a real email is provided.
  - [Branch B — Client cleared without selection] Autocomplete input left empty → proposal save fails validation (client is required for existing proposals).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-update-client.spec.js`

### 12.3 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Suggested Spec |
|---------|--------|------|----------|--------|----------------|
| `admin-proposal-update-client` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-update-client.spec.js` |

---

## 13. Audit Alignment Flows (v2.16.0)


> Retro-documented browser flows that were already registered in `frontend/e2e/flow-definitions.json` and tagged in Playwright specs, but did not yet have full headed entries in this markdown map. Also adds the new `/panel/views` admin reference flow introduced during the audit.

### 13.1 Proposal Audit Additions

#### FLOW: `proposal-countdown-realtime`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** When a proposal expires within 48 hours, the countdown switches from day-based copy to a live HH:MM timer that updates on the client without reloading the page.
- **Steps:**
  1. Client opens a proposal whose `expires_at` is within the 48-hour window.
  2. Countdown UI renders a live hours/minutes timer.
  3. Timer updates on the page over time.
  4. Expiration badge and urgency messaging stay in sync with the live countdown.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-countdown-realtime.spec.js`

#### FLOW: `proposal-resolved-notice-suppression`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Once a proposal's status is resolved (`accepted`, `rejected` or `finished`), the public view stops showing time-sensitive / urgency notices that no longer apply after the client's decision: the expiration countdown badge (`ExpirationBadge.vue`), the limited-time discount banner (`Investment.vue` `.discount-banner`) and the hosting tier discount badges. While the proposal is still open (`sent`/`viewed`) those notices keep showing. The `expired` status is handled separately by the expired-state banner.
- **Steps:**
  1. Client opens a resolved proposal (e.g. status `accepted` or `finished`) whose `expires_at`/`discount_percent` are still set.
  2. The expiration countdown badge does **not** render.
  3. The limited-time discount banner and hosting tier discount badges do **not** render.
  4. Control: an open proposal (`sent`/`viewed`) with the same data still renders those notices.
- **Coverage:** 📝 Documented-only (no dedicated E2E spec yet)
- **Unit coverage:** `frontend/test/components/Investment.test.js` → `resolved-status notice suppression`
- **Suggested E2E Spec:** `e2e/proposal/proposal-resolved-notice-suppression.spec.js`

#### FLOW: `proposal-hosting-plan-terms`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid` (+ downloadable PDF)
- **Description:** The Investment section's current hosting offer shows three payment-frequency tiers (every 9 months 40% / semiannual 20% / quarterly 10%; monthly and annual are not offered) and a "1 free month of hosting" gift bucket. The public view and PDF share the same normalized terms in ES and EN; closed or inactive proposals preserve their historical snapshot. Renewal conditions render ONLY in the PDF, NOT in the web view. Numbers derive from the BusinessProposal model (`hosting_discount_nine_month` carries the maximum 40% discount).
- **Steps:**
  1. Client opens the proposal and scrolls to "Tu inversión y cómo pagar".
  2. The hosting plan shows the three tiers including the highlighted Every 9 months / Cada 9 meses (40%) tier.
  3. The free-month gift bucket renders.
  4. The "Renovaciones" / "Renewals" block does NOT render in the web view (it is PDF-only).
  5. Downloading the PDF reproduces the same tiers, free-month note and the renewal note with the SMLMV+8% formula and example.
- **Coverage:** ✅ Covered
- **Unit coverage:** `frontend/test/components/Investment.test.js` → `hosting: nine-month tier, free month, renewal`
- **E2E Spec:** `e2e/proposal/proposal-hosting-plan-terms.spec.js`

#### FLOW: `proposal-rejection-optional-reason`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The rejection path keeps the reason optional while nudging the client to provide context before submitting a negative response.
- **Steps:**
  1. Client opens the rejection modal from the closing section.
  2. Helper copy explains that feedback is optional but useful.
  3. Client submits rejection without choosing a reason.
  4. Proposal is rejected successfully and the UI moves to the rejection confirmation state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-rejection-optional.spec.js`

#### FLOW: `proposal-calculator-timeline`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** Investment calculator changes the estimated delivery timeline dynamically as optional modules are toggled on or off.
- **Steps:**
  1. Client opens the investment calculator modal.
  2. Baseline weeks are visible before any changes.
  3. Client selects or removes priced modules.
  4. Estimated timeline updates immediately to reflect the module mix.
  5. Confirming the selection preserves the new timeline in the closing state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-timeline.spec.js`

#### FLOW: `proposal-calculator-micro-feedback`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Calculator toggles show transient micro-feedback badges such as positive or negative price deltas when the client adds or removes priced modules.
- **Steps:**
  1. Client opens the investment calculator modal.
  2. Client toggles a module with a price impact.
  3. A transient feedback badge appears near the interaction showing the delta.
  4. Badge fades away while totals remain updated.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-micro-feedback.spec.js`

#### FLOW: `proposal-payment-plan-closing`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Payment milestones are summarized near the accept CTA in the closing section so the client can review the plan without reopening the investment section.
- **Steps:**
  1. Client navigates to the proposal closing section.
  2. Closing card renders payment milestones and labels.
  3. Payment plan stays visible next to the primary accept action.
  4. The displayed plan matches the investment data configured for the proposal.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-payment-plan-closing.spec.js`

#### FLOW: `proposal-post-acceptance-welcome`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** After acceptance, the client sees a welcome-kit style success state with onboarding guidance, downloadable material, and a direct PM communication CTA.
- **Steps:**
  1. Client accepts the proposal from the closing flow.
  2. Proposal switches to the post-acceptance state.
  3. Welcome content renders with next steps and onboarding guidance.
  4. PDF download and PM WhatsApp contact actions are available.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-post-acceptance-welcome.spec.js`

#### FLOW: `proposal-structured-negotiation`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Negotiation modal provides structured reasons and tabs so the client can request changes with more specific context than a free-text note alone.
- **Steps:**
  1. Client opens the negotiation modal from the closing section.
  2. Modal renders structured reason options and adjust/comment tab states.
  3. Client selects reasons and optionally adds custom context.
  4. Client submits the negotiation request and sees success feedback.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-structured-negotiation.spec.js`

#### FLOW: `proposal-conditional-acceptance`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client accepts the proposal while attaching an optional “Acepto, pero…” condition note that is persisted with the response.
- **Steps:**
  1. Client opens the acceptance flow from the closing section.
  2. Client adds an optional condition note.
  3. Client confirms acceptance.
  4. Proposal moves to the accepted state while retaining the condition note.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-conditional-acceptance.spec.js`

### 13.2 Admin Audit Additions

#### FLOW: `admin-dashboard-pipeline-value`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/`
- **Description:** Dashboard shows the pipeline pulse tile summarizing the total investment currently active in the sales pipeline, fed by the consolidated `GET /api/panel/dashboard/` payload.
- **Steps:**
  1. Admin opens the panel dashboard.
  2. Consolidated data loads from `GET /api/panel/dashboard/`.
  3. The pipeline pulse tile renders the total active value and proposal count.
  4. The tile shows a dash when the backend returns no pipeline value.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

#### FLOW: `admin-proposal-create-and-send`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/create`
- **Description:** After creating a proposal with valid client contact data, the admin can send it immediately from the post-create interstitial without first navigating to the edit page.
- **Steps:**
  1. Admin creates a proposal from the create screen.
  2. Post-create modal appears with next actions.
  3. Admin clicks the send action from the modal.
  4. Proposal send endpoint is called and the new proposal moves to the sent state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-create.spec.js`

#### FLOW: `admin-proposal-create-preview`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/create`
- **Description:** Post-create interstitial lets the admin preview, edit, or send the newly created proposal before leaving the creation context.
- **Steps:**
  1. Admin completes proposal creation.
  2. Confirmation modal summarizes the created proposal.
  3. Modal exposes preview and edit actions for the new record.
  4. Admin can move to the edit page directly from the interstitial.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-create.spec.js`

#### FLOW: `admin-discount-analysis-enhanced`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/`
- **Description:** Discount analysis card shows richer context including sample sizes, average discount percentages, and warnings when discount performance differs from the baseline.
- **Steps:**
  1. Admin opens the proposals page dashboard.
  2. Discount analysis card loads from dashboard metrics.
  3. Card renders sample size and average discount context.
  4. Delta warning messaging appears when discount performance trends negatively.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-discount-analysis.spec.js`

#### FLOW: `admin-proposal-inline-status-change`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Proposal status can be updated from every panel surface via the shared `ProposalStatusSelect` badge select (admin mode: ALL statuses selectable). Options are grouped as "Flujo normal" (`available_transitions`) vs "Forzar estado" (everything else). Natural transitions keep their side effects (`draft → sent` delegates to `ProposalService.send_proposal`; `→ finished` sends the confirmation email; `→ accepted` enqueues onboarding); forced jumps require a warning confirm and are side-effect free (save + `ProposalChangeLog` with an "admin forced" marker). Surfaces: proposals table cell, proposals actions modal ("Cambiar estado" row), nested proposals in `/panel/clients/`, and the edit view sticky header + actions modal.
- **Steps:**
  1. Admin opens any surface with the status select (proposals list, clients expanded row, or proposal edit header).
  2. Admin picks a status: natural non-email transitions PATCH directly; `sent`/`finished` naturals and every forced jump show a ConfirmModal first; natural `negotiating` opens the contract modal where the page supports it.
  3. `PATCH /api/proposals/:id/update-status/` is called with `{status}`.
  4. Row/detail refreshes; toast shows "Estado actualizado correctamente" on success, or surfaces `email_delivery` failure with a "Reenviar" action when applicable.
- **Coverage:** ✅ Covered — forced confirm + PATCH, natural no-confirm PATCH, labels/grouping, the `draft → sent` email_delivery failure toast, the edit-header select and the actions-modal "Cambiar estado" row are asserted (2026-07-23). The clients-view select shares the same unit-tested composable (`test/composables/useProposalStatusChange.test.js`) and is not separately asserted.
- **E2E Spec:** `e2e/admin/admin-proposal-inline-status.spec.js` (extend with: email_delivery `ok=false` toast, clients-view/edit-header select smoke, actions-modal "Cambiar estado" row).
- **Backend Tests:** `content/tests/views/test_proposal_status_and_pdf.py`, `content/tests/views/test_mcp_proposals.py`.

#### FLOW: `admin-proposal-scorecard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Edit view surfaces a pre-send scorecard with blockers so the admin can see whether a proposal is ready to be sent.
- **Steps:**
  1. Admin opens a proposal edit page.
  2. Scorecard endpoint loads readiness data for that proposal.
  3. Score and blocker state render in the UI.
  4. Blocking issues prevent sending until the missing data is fixed.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-scorecard.spec.js`

#### FLOW: `admin-proposal-section-completeness`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Edit page shows a section-completeness indicator summarizing how many enabled sections currently have content.
- **Steps:**
  1. Admin opens a proposal edit page.
  2. Completeness summary loads from current section data.
  3. Progress UI shows the percentage of enabled sections with content.
  4. Indicator updates as section content changes.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-section-completeness.spec.js`

#### FLOW: `admin-proposal-zombie-segment`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Proposals dashboard highlights stale “zombie” proposals in a dedicated collapsible segment so the sales owner can triage cold opportunities quickly.
- **Steps:**
  1. Admin opens the proposals page.
  2. Zombie segment renders when stale draft/sent proposals are present.
  3. Segment shows the relevant proposals and alert styling.
  4. Admin can expand or collapse the section while reviewing the stale pipeline.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-zombie-segment.spec.js`

#### FLOW: `admin-view-map`

- **Module:** admin
- **Role:** admin
- **Priority:** P4
- **Routes:** `/panel/views`
- **Description:** Admin explores the complete route inventory in Lista, drills through modules in Mapa, or presents ProjectApp as a contextual journey in Explorador. The operational mode starts with Panel interno, Plataforma de clientes and Experiencias públicas; each space exposes its main modules, representative submodules and dynamically previewed value/context while route/file references remain secondary. Seeded filters and Configuración retain the technical workflow; `ViewMapSettings` persists any of the three default modes and an explicit URL always wins.
- **Steps:**
  1. Admin opens `/panel/views` from the Reference section in the panel sidebar; the configured default view mode and default filters apply when no `?viewMode=`/`?viewTab=` deep-link is present.
  2. Grouped route catalog renders with section totals, seeded filter tabs and a proposal reference guide.
  3. Admin selects a seeded filter tab (e.g. Dashboards) or searches for a route, view name, or file path to narrow the catalog.
  4. Admin clicks the copy button on a view row and sees copied feedback.
  5. Admin toggles to "Mapa" mode: module cards render with operational labels, view counts, sub-module counts and a viewType distribution bar.
  6. Admin clicks a module card, drills into its sub-modules and returns via the breadcrumb; the URL reflects the state for deep-linking.
  7. Admin toggles to "Explorador" and chooses Panel interno, Plataforma de clientes or Experiencias públicas. Hover/focus previews purpose and operational value without changing the URL; click selection writes a shared `?viewMode=explorer&node=<id>` state.
  8. Admin explores Panel and Platform through eight main modules each, or the six public modules that connect acquisition, content/proof, additional modules, financing, proposal and diagnostic experiences. Representative submodules and technical references remain available in progressive disclosure.
  9. Admin starts a guided space tour. `tour=<space-id>` and `node=<module-id>` track ordered progress; next/previous moves between main modules and exiting removes only `tour`, preserving context.
  10. At compact and portrait widths the hierarchy becomes cards; from landscape upward it uses the orbit. Admin can pause rotation, zoom, hide functional relations or rely on reduced motion.
  11. Admin switches to "Configuración", saves any default mode and receives success or failure feedback from the settings request.
- **Outcome matrix:** display ✅ Lista/Mapa plus all three Explorer spaces, responsive representations and dynamic context; success ✅ guided navigation and default-mode persistence; failure ✅ rejected settings save; error n/a because the page exposes bounded controls rather than user-authored values, so invalid modes cannot be submitted through the UI.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-view-map.spec.js`
- **Known gaps:** default-filters autosave from the Configuración section and default-filters application on open are unit-covered only; saved-tab CRUD (create/rename/delete) is unasserted on this view (shared `ProposalFilterTabs` component, exercised in proposals specs).

#### FLOW: `admin-kanban-tasks`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/tasks` (alias `/panel/tareas` redirects here)
- **Description:** Internal Kanban task board for the admin team. Admin creates, edits, moves, and deletes tasks across four columns (Todo, In Progress, Blocked, Done). Tasks have priority labels (low/medium/high), optional assignee, and optional due date shown in red when overdue.
- **Steps:**
  1. Admin navigates to `/panel/tasks` from the "Tareas → Kanban" sidebar entry.
  2. Board renders four columns loaded from `GET /api/content/tasks/`.
  3. Admin clicks "+ Nueva Tarea" → `TaskFormModal` opens.
  4. Admin fills title, priority, optional assignee, due date → submits → task appears in the "Todo" column.
  5. Admin clicks a task card → modal reopens for editing; saves → card updates in place.
  6. Admin drags a task card to another column → `PATCH /api/content/tasks/<id>/update/` fires with new status; board updates.
  7. Admin deletes a task via the modal → `DELETE /api/content/tasks/<id>/delete/` → card removed from column.
- **Branches:**
  - [Branch A — Overdue] Tasks with a past `due_date` render the date in red.
  - [Branch B — Empty column] Columns with no tasks show a ghost-style drop target.
  - [Branch C — Reorder] Dragging a task within the same column calls `PATCH tasks/<id>/reorder/` to renumber positions.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-tasks-kanban.spec.js`

#### FLOW: `admin-task-deadline-notification`

- **Module:** admin
- **Role:** system (no browser interaction)
- **Priority:** P2
- **Routes:** N/A — backend-only
- **API:** Huey periodic task; `PATCH /api/content/tasks/<id>/update/` (internal); Django email backend
- **Description:** Automated email notifications sent to task assignees at 40%, 70%, and 100% of deadline elapsed, and again for overdue tasks. Notification state is tracked via `notified_40`, `notified_70`, `notified_100`, `last_overdue_notified_at` fields added in migration `0089_task_notification_fields.py`. The Huey task runs periodically and skips tasks that have already been notified at each threshold.
- **Steps:**
  1. Huey scheduler triggers the deadline-notification task.
  2. Task queries all `Task` records with a `due_date` and an assignee email.
  3. For each task, time-to-deadline % is computed; if threshold crossed and not yet notified, an email is sent.
  4. The corresponding `notified_*` field is set to `True` to prevent duplicate notifications.
  5. Overdue tasks send a daily reminder until `last_overdue_notified_at` is today.
- **Coverage:** ⬜ Backend-only — no E2E spec needed (expectedSpecs: 0)

### 13.3 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-dashboard-pipeline-value` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-dashboard.spec.js` |
| `admin-proposal-create-and-send` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-create.spec.js` |
| `admin-proposal-create-preview` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-create.spec.js` |
| `admin-discount-analysis-enhanced` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-discount-analysis.spec.js` |
| `admin-proposal-inline-status-change` | admin | admin | P2 | ✅ Covered (clients-view select shares the unit-tested composable) | `e2e/admin/admin-proposal-inline-status.spec.js` |
| `admin-proposal-scorecard` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-scorecard.spec.js` |
| `admin-proposal-section-completeness` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-proposal-section-completeness.spec.js` |
| `admin-proposal-zombie-segment` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-zombie-segment.spec.js` |
| `admin-view-map` | admin | admin | P4 | ✅ Covered | `e2e/admin/admin-view-map.spec.js` |
| `admin-kanban-tasks` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-tasks-kanban.spec.js` |
| `admin-task-deadline-notification` | admin | system | P2 | ⬜ Backend-only | N/A |

---

## 14. New Feature Flows (v2.17.0–v2.20.0)


> Flows registered during the v2.17.0–v2.20.0 audit cycles. Covers Document PDF download (in progress), Web App Diagnostics, document move-folder modal, and task deadline notifications.

### 14.1 Document PDF Download

#### FLOW: `admin-document-pdf-download`

*(See Section 9.1 for full flow detail — this section tracks coverage status only.)*

### 14.2 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-document-pdf-download` | admin | admin | P2 | ⬜ Missing | — (Document PDF generation in progress) |
| `admin-document-move-folder` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-document-move-folder.spec.js` |
| `admin-task-deadline-notification` | admin | system | P2 | ⬜ Backend-only | N/A |
| `admin-diagnostic-create` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-create.spec.js` |
| `admin-diagnostic-send-initial` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-send.spec.js` |
| `admin-diagnostic-send-final` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-send.spec.js` |
| `admin-diagnostic-email` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-email-documents.spec.js` |
| `admin-diagnostic-documents` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-email-documents.spec.js` |
| `admin-diagnostic-sections` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-sections.spec.js` |
| `admin-diagnostic-activity` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-sections.spec.js` |
| `admin-diagnostic-analytics` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-analytics.spec.js` |
| `admin-diagnostic-engagement-score` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-analytics.spec.js` |
| `admin-diagnostic-prompt` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-prompt.spec.js` |
| `diagnostic-public-view` | diagnostic | guest | P1 | ✅ Covered | `e2e/public/diagnostic-public-view.spec.js` + `e2e/admin/admin-diagnostic-sections.spec.js` |

---

## Section 15 — v2.21.0 Gaps (Task Alerts + Diagnostic Lifecycle)


> Flows registered during the v2.21.0 audit cycle. Covers manual task alert management, diagnostic edit, and diagnostic delete.

### 15.1 Task Alert Management

#### FLOW: `admin-task-alert-management`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-task-alert-management` |
| **Module** | tasks |
| **Role** | admin |
| **Priority** | P1 |
| **Status** | ⬜ Missing spec |

**Steps:**
1. Admin navigates to `/panel/tasks`.
2. Admin clicks a task card to open `TaskFormModal` in edit mode.
3. Admin sees the **Alertas** section below the due-date/assignee row.
4. Admin enters a date in the "Fecha" input and an optional note.
5. Admin clicks **+ Agregar** — alert appears in the list with "Pendiente" badge.
6. Admin clicks the **✕** delete button on an alert — alert is removed from the list.
7. Admin closes the modal.

**Expected outcome:** Alerts persist to backend via POST `tasks/{id}/alerts/create/` and DELETE `tasks/{id}/alerts/{alertId}/delete/`.

---

### 15.2 Diagnostic Edit

#### FLOW: `admin-diagnostic-edit`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-edit` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ⬜ Missing spec |

**Steps:**
1. Admin navigates to `/panel/diagnostics`.
2. Admin clicks **Edit** on a diagnostic card.
3. Admin is taken to `/panel/diagnostics/{id}/edit`.
4. Admin modifies one or more fields (title, status, investment amount, etc.).
5. Admin clicks **Guardar** — PATCH sent to `diagnostics/{id}/update/`.
6. Admin sees success feedback; the updated values are reflected in the form.

**Expected outcome:** Diagnostic fields are updated in the backend and reflected in the UI.

---

### 15.3 Diagnostic Delete

#### FLOW: `admin-diagnostic-delete`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-delete` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ⬜ Missing spec |

**Steps:**
1. Admin navigates to `/panel/diagnostics`.
2. Admin clicks **Delete** (or trash icon) on a diagnostic card.
3. A confirmation modal appears asking the admin to confirm deletion.
4. Admin confirms — DELETE sent to `diagnostics/{id}/delete/`.
5. The diagnostic is removed from the list.

**Expected outcome:** Diagnostic is deleted in the backend and removed from the list without a page reload.

---

### 15.4 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-task-alert-management` | tasks | admin | P1 | ✅ Covered | `e2e/admin/admin-task-alerts.spec.js` |
| `admin-diagnostic-edit` | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-edit-delete.spec.js` |
| `admin-diagnostic-delete` | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-edit-delete.spec.js` |

---

## Section 16 — v2.22.0 Gaps (Diagnostic Acuerdo de Confidencialidad)


> Flows registered during the v2.22.0 audit cycle. Covers the new system-generated Acuerdo de Confidencialidad (NDA) PDF on the diagnostic Documentos tab — mirrors the proposal contract pattern (`admin-proposal-contract-{generate,edit,download}`).

### 16.1 Diagnostic NDA Generate

#### FLOW: `admin-diagnostic-confidentiality-generate`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-confidentiality-generate` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P1 |
| **Status** | ✅ Covered |
| **Spec** | `e2e/admin/admin-diagnostic-confidentiality.spec.js` |

**Routes:** `/panel/diagnostics/:id/edit` → Documentos tab.

**Description:** Admin generates the Acuerdo de Confidencialidad (NDA) PDF for a diagnostic. The Documents tab opens with a dedicated "Acuerdo de confidencialidad" section above the send/upload sections. When no NDA exists, the section displays "No generado" plus a copy line ("Plantilla colombiana (Ley 1581/2012). Llena los datos del cliente y consultor para generar el PDF.") and a "Generar acuerdo" CTA. Clicking the CTA opens `ConfidentialityParamsModal` with three field groups: Cliente (nombre/NIT/representante legal/email — pre-filled from `diagnostic.client.name` and `.email` when available), Consultor (nombre — default "Project App SAS"; NIT; email — default "team@projectapp.co"), Datos del acuerdo (ciudad — default "Medellín"; día/mes/año; cláusula penal — default "CINCUENTA SALARIOS MÍNIMOS MENSUALES LEGALES VIGENTES (50 SMMLV)"). Submit POSTs trimmed/non-empty fields to `POST /api/diagnostics/:id/confidentiality/params/` (`{confidentiality_params: {...}}`); backend validates via `ConfidentialityParamsSerializer`, persists to `diagnostic.confidentiality_params`, then calls `_generate_and_save_confidentiality_pdf` which loads the default `ConfidentialityTemplate`, substitutes placeholders, renders the branded ProjectApp PDF (esmeralda + Lemon accent, "ACUERDO DE CONFIDENCIALIDAD" title page, two-column EL CLIENTE / EL CONSULTOR signature block), and creates a `DiagnosticAttachment(document_type='confidentiality_agreement', is_generated=True)`. A `DiagnosticChangeLog(UPDATED, field_name='confidentiality_agreement')` row is appended.

**Steps:**
1. Admin navigates to `/panel/diagnostics/:id/edit` and opens the **Documentos** tab.
2. Admin sees the "Acuerdo de confidencialidad" section with "No generado" label and "Generar acuerdo" button.
3. Admin clicks **Generar acuerdo** — `ConfidentialityParamsModal` opens, prefilling client name/email from the diagnostic plus contractor + city + penal clause defaults.
4. Admin fills the cliente fields (nombre, NIT, representante legal) and confirms the others.
5. Admin clicks **Guardar y generar PDF** → POST `/api/diagnostics/:id/confidentiality/params/`.
6. Modal closes; the section now shows "Generado el {fecha}" plus three buttons: **Descargar**, **Borrador**, **Editar parámetros**.
7. The new attachment also appears in the "Enviar documentos al cliente" section as a checkbox "📋 NDA — Acuerdo de Confidencialidad (borrador con marca de agua)".

**Branches:**
- [Empty params] Admin clicks "Generar acuerdo", leaves all fields blank, submits — request succeeds, PDF is generated with all `_______________` placeholders for missing fields (default `Project App SAS` / `Medellín` / 50 SMMLV still apply for contractor and city).
- [Server failure] If `generate_confidentiality_pdf` returns `None`, response is HTTP 500 `{"error": "Parámetros guardados pero no se pudo generar el PDF."}` (params are still saved — admin can retry generate without re-entering data).

**Expected outcome:** A `DiagnosticAttachment` with `document_type='confidentiality_agreement'` and `is_generated=True` exists for the diagnostic, with a downloadable PDF file.

---

### 16.2 Diagnostic NDA Edit Params

#### FLOW: `admin-diagnostic-confidentiality-edit`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-confidentiality-edit` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/diagnostics/:id/edit` → Documentos tab.

**Description:** Admin re-opens `ConfidentialityParamsModal` via the **Editar parámetros** button on a diagnostic that already has a generated NDA. The form pre-fills from `diagnostic.confidentiality_params` (with the same Project App / Medellín / 50 SMMLV defaults overlaid for any field still blank). Submit hits the same `POST /api/diagnostics/:id/confidentiality/params/` endpoint; the existing `DiagnosticAttachment` row is updated in place — `existing.file.delete(save=False)` then `existing.file.save(filename, ContentFile(pdf_bytes), save=False)` then a single `existing.save()`, so the attachment id is preserved and any prior file is removed from storage.

**Steps:**
1. Admin opens the Documentos tab for a diagnostic that already has an NDA (section header shows "Generado el {fecha}").
2. Admin clicks **Editar parámetros** — `ConfidentialityParamsModal` opens with the saved params pre-filled.
3. Admin modifies one or more fields (e.g. updates the client NIT) and clicks **Guardar y generar PDF**.
4. Modal closes; section header now shows the new "Generado el {fecha}" timestamp.
5. Admin clicks **Descargar** to verify the PDF reflects the new value.

**Branches:**
- [Same id, replaced file] The store updates `current.attachments` in place (matching by id from the response); the row count does not increase.

**Expected outcome:** `diagnostic.confidentiality_params` is updated, the same `DiagnosticAttachment` row is reused, and the rendered PDF reflects the new params.

---

### 16.3 Diagnostic NDA Download

#### FLOW: `admin-diagnostic-confidentiality-download`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-confidentiality-download` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/diagnostics/:id/edit` → Documentos tab.

**Description:** Admin downloads the Acuerdo de Confidencialidad PDF in either of two modes from the Documentos tab. **Descargar** points to `GET /api/diagnostics/:id/confidentiality/pdf/` which returns the saved file via `FileResponse` (streamed, `Content-Type: application/pdf`, filename built via `_confidentiality_filename`). **Borrador** points to `GET /api/diagnostics/:id/confidentiality/draft-pdf/` which generates a fresh PDF with all params forced to `XXX-XXX-XXX` (no real data leaks) and applies `add_watermark_to_pdf` to stamp `BORRADOR` diagonally across each page; returned inline as `HttpResponse`.

**Steps:**
1. Admin opens the Documentos tab for a diagnostic with an existing NDA.
2. Admin clicks **Descargar** — browser opens `/api/diagnostics/:id/confidentiality/pdf/` in a new tab; PDF renders with branded ProjectApp template, title "ACUERDO DE CONFIDENCIALIDAD", and placeholders filled from `confidentiality_params`.
3. Admin clicks **Borrador** — browser opens `/api/diagnostics/:id/confidentiality/draft-pdf/` in a new tab; PDF renders with the same template but every value shows as `XXX-XXX-XXX` plus a diagonal `BORRADOR` watermark.

**Branches:**
- [Not generated] When no NDA exists, neither link is rendered; the section shows "No generado" plus the **Generar acuerdo** CTA. Hitting `/confidentiality/pdf/` directly returns HTTP 404 `{"error": "El acuerdo aún no ha sido generado."}`.

**Expected outcome:** Both URLs return valid PDFs (≥ 50 KB each); the draft includes a watermark and no real client data.

---

### 16.4 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-diagnostic-confidentiality-generate` | diagnostics | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-confidentiality.spec.js` |
| `admin-diagnostic-confidentiality-edit` | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-confidentiality-edit.spec.js` |
| `admin-diagnostic-confidentiality-download` | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-confidentiality-download.spec.js` |
| `admin-diagnostic-documents` (NDA branches) | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-email-documents.spec.js` — base + NDA not-generated ("Generar acuerdo") and generated (download / draft / edit-params) branches (2026-07-23) |

---

## Section 17 — v2.23.0 Gaps (Diagnostic Admin Tab Restructure)


> Flows registered during the v2.23.0 audit cycle. Covers the diagnostic admin edit-page alignment with the proposals admin pattern: tab reorder, conditional visibility of Correos/Documentos by status, and the replacement of the raw-JSON "Plantillas" textarea with a full JSON export/import tab (parity with `admin-proposal-json`). The short-lived "Det. técnico" tab (Pricing + Radiografía sub-tabs) was retired on 2026-04-18 — pricing now lives in General and radiografía is edited as a regular section from Secciones.

### 17.1 Diagnostic JSON Export

#### FLOW: `admin-diagnostic-json-export`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-json-export` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/diagnostics/:id/edit` → JSON tab.

**Description:** Admin opens the JSON tab (replaces the prior "Plantillas" tab). A read-only `<textarea>` renders the full diagnostic serialized as JSON — `{metadata: {title, language, investment_amount, currency, payment_terms, duration_label, size_category, radiography, client: {id, name, email, company}}, sections: [...]}`. The string is lazy-computed from `store.current` so it only rebuilds when the tab is rendered (not on every debounced section save). Three buttons sit above the textarea: **Actualizar** refetches `/api/diagnostics/:id/detail/`; **Copiar** writes the textarea content to the clipboard and flips the label to "¡Copiado!" for ~1.5s; **Descargar** streams a Blob download named `{slug}.json` where `{slug}` is the diagnostic title lowercased with non-alphanumerics collapsed to `-`.

**Steps:**
1. Admin opens `/panel/diagnostics/:id/edit` and clicks the **JSON** tab.
2. Read-only textarea renders with the current diagnostic's full JSON.
3. Admin clicks **Copiar** — clipboard receives the text, label flips to "¡Copiado!" and reverts after ~1.5s.
4. Admin clicks **Descargar** — browser downloads `{slug}.json` with the same payload.
5. Admin clicks **Actualizar** — `fetchDetail` re-hits the server; textarea reflects any server-side changes.

**Branches:**
- [Legacy deep-link] `?tab=plantillas` redirects to `?tab=json` on initial mount and on in-session route changes.

**Expected outcome:** The exported JSON round-trips back through `admin-diagnostic-json-import` without loss.

---

### 17.2 Diagnostic JSON Import

#### FLOW: `admin-diagnostic-json-import`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-json-import` |
| **Module** | diagnostics |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ⬜ Missing spec |

**Routes:** `/panel/diagnostics/:id/edit` → JSON tab (Importar JSON section).

**Description:** Admin imports a full-diagnostic JSON blob from the JSON tab, either by pasting into the import textarea or uploading a `.json` file (FileReader → textarea). `parseImportJson` runs on every `@input`; validation requires the root to be an object (not an array) with `sections` as an array. When parse succeeds, a green preview strip shows Cliente (`metadata.client.name`), # Secciones (`sections.length`), and Inversión (formatted with `formatMoney` + `currency`). **Aplicar JSON** first issues `PATCH /api/diagnostics/:id/update/` with the whitelisted metadata keys (title, language, investment_amount, currency, payment_terms, duration_label, size_category, radiography, client_id from `metadata.client?.id`); if that succeeds it then `POST`s `/sections/bulk-update/` with `{sections: [...]}` using id/title/order/is_enabled/visibility/content_json per row. On success the import state is cleared and `syncForms()` refreshes the Pricing/Radiography forms; on error the apply is aborted with an inline red message.

**Steps:**
1. Admin opens the JSON tab.
2. Admin either pastes a JSON blob into the "Importar JSON" textarea or clicks **Subir .json** and picks a file.
3. Parse succeeds → preview strip shows Cliente / Secciones / Inversión; **Aplicar JSON** button enables.
4. Admin clicks **Aplicar JSON** — metadata PATCH fires first, then bulk sections POST.
5. Success toast: "JSON aplicado correctamente." Textarea clears, preview hides, General-tab pricing fields and the radiografía section reflect the new values.

**Branches:**
- [Invalid JSON] Parse throws → red box with `JSON inválido: {message}`; Aplicar button stays disabled.
- [Wrong root] Root is an array or lacks `sections` → red box: "`sections` debe ser un array." or "El JSON raíz debe ser un objeto con `metadata` y `sections`."
- [Metadata error] Metadata PATCH fails → red box with backend error, sections bulk is skipped (no partial apply).
- [Sections error — metadata not yet applied] Sections bulk fails and no metadata was sent → red box "Error al aplicar las secciones: {error}."
- [Sections error — metadata already applied] Sections bulk fails after metadata succeeded → explicit partial-state red box: "Se aplicaron los datos generales, pero fallaron las secciones: {error}. Corrige el JSON y vuelve a aplicar — la metadata ya está actualizada." Admin knows exactly what persisted and what didn't.

**Expected outcome:** On a valid payload, the diagnostic's metadata and all 8 sections reflect the imported JSON; the JSON export (17.1) round-trips identically.

---

### 17.3 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-diagnostic-json-export` | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-json.spec.js` |
| `admin-diagnostic-json-import` | diagnostics | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-json-import.spec.js` |
| `admin-diagnostic-defaults-config` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-defaults.spec.js` |
| `admin-diagnostic-mark-in-analysis` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-send.spec.js` (`'Marcar en análisis' button POSTs…`) |
| `diagnostic-public-respond` | diagnostic | guest | P1 | ✅ Covered | `e2e/public/diagnostic-public-view.spec.js` (`clicking 'Aceptar propuesta'…`) |
| `admin-proposal-diagnostic-templates` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-diagnostic-templates.spec.js` |
| `admin-diagnostic-markdown-attachment` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-markdown-attachment.spec.js` |
| `admin-defaults-unified` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-defaults-unified.spec.js` |
| `admin-proposal-defaults-slug-pattern` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-defaults-slug-pattern.spec.js` |

---

### 17.5 Diagnostic Defaults Config (Apr 18, 2026)

#### FLOW: `admin-diagnostic-defaults-config`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-defaults-config` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/defaults?mode=diagnostic` (old `/panel/diagnostics/defaults` redirects here).

**Description:** Admin manages the per-language defaults applied to every new `WebAppDiagnostic` from `panel/diagnostics/defaults.vue`. The page mirrors `/panel/proposals/defaults/` but is scoped to diagnostics. Five tabs render from one config payload: **General** (idioma, moneda, inversión, duración, % pagos con auto-sync 100, días de recordatorio/urgencia/expiración), **Secciones** (lista read-only de las 8 secciones del seed activo), **Plantillas de Email** (link a `/panel/email-templates`), **Prompt** (placeholder), **JSON** (vista cruda). Cuando no existe una `DiagnosticDefaultConfig` para el idioma, `GET /api/diagnostics/defaults/?lang=` devuelve los valores hardcoded del seed con 60% inicial / 40% final como pagos por defecto.

**Steps:**
1. Admin abre `/panel/defaults?mode=diagnostic` desde el botón "Valores por Defecto" del header de `/panel/diagnostics` (o el ítem "Defaults" del sidebar con el switch en modo Diagnóstico).
2. La página llama `GET /api/diagnostics/defaults/?lang=es` y popula `generalForm` + `sectionsList` + `rawConfig` vía `applyConfig(data)`.
3. El tab General muestra los inputs precargados (60/40, COP, 21/7/14 días).
4. Admin edita el % inicial — `syncPaymentFinal()` mueve el % final automáticamente para mantener suma=100.
5. Admin presiona "Guardar cambios" → `PUT /api/diagnostics/defaults/` con language + sections_json + payment_initial_pct + payment_final_pct + default_currency + default_investment_amount + default_duration_label + reminder/urgency/expiration days.
6. La respuesta se aplica vía `applyConfig(result.data)` (sin re-fetch). `usePanelToast` muestra "Valores guardados correctamente."
7. Cualquier diagnóstico creado a partir de ahora hereda esos valores en `payment_terms` / `currency` / `investment_amount` / `duration_label`.

**Branches:**
- [Branch A — Reset] Admin presiona "Restablecer a valores del sistema" → `useConfirmModal` muestra "¿Eliminar el config personalizado y volver a los valores del sistema (60/40, COP, 21 días)?" → al confirmar se ejecuta `POST /api/diagnostics/defaults/reset/`, se borra la fila DB y la página recarga el seed hardcoded.
- [Branch B — Cambio de idioma] Admin cambia el `<select>` de idioma → `onLanguageChange` re-llama `GET /defaults/?lang=` con el idioma nuevo. La fila de la otra lengua queda intacta.
- [Branch C — Pagos no suman 100] Si el cliente fuerza valores manuales que no sumen 100 (deshabilitando el sync), el botón Guardar queda disabled y se muestra el aviso "La suma debe ser exactamente 100% (actual: N%)". El backend valida con la misma regla por si la UI se salta.

**Expected outcome:** El `DiagnosticDefaultConfig` para ese idioma queda persistido (o eliminado en el caso del reset). Cualquier llamada subsecuente a `diagnostic_service.create_diagnostic(language=...)` lee el config y lo aplica al nuevo diagnóstico antes de sembrar las secciones.

**Backend Tests:** `content/tests/views/test_diagnostic_defaults_views.py` (16) + `content/tests/models/test_diagnostic_default_config.py` (8).
**Frontend Tests:** `frontend/test/stores/diagnostics.test.js` (`fetchDiagnosticDefaults`/`saveDiagnosticDefaults`/`resetDiagnosticDefaults` — 6 cases).
**E2E Spec:** `e2e/admin/admin-diagnostic-defaults.spec.js`.

### 17.6 Unified Defaults Shell (Apr 20, 2026)

#### FLOW: `admin-defaults-unified`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-defaults-unified` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/defaults` (with `?mode=proposal` or `?mode=diagnostic`).

**Description:** Admin accesses a unified shell page that replaces the two separate defaults pages. A segmented mode switch toggles between the **Propuesta** panel and the **Diagnóstico** panel. The active mode is persisted via query param so reloads and direct links preserve it. The back link adapts to the active mode. Old routes `/panel/proposals/defaults`, `/panel/proposals/email-templates` and `/panel/diagnostics/defaults` redirect here preserving their mode/tab intent.

**Steps:**
1. Admin clicks **"Defaults"** in the Sales section of the sidebar → navigates to `/panel/defaults` (defaults to proposal mode).
2. The mode switch shows **Propuesta** as active (highlighted with `bg-emerald-600`).
3. `ProposalDefaultsPanel` lazy-loads and fetches `GET /api/proposals/defaults/?lang=es`.
4. Admin clicks **"Diagnóstico"** in the mode switch → URL updates to `?mode=diagnostic`, tab param is cleared.
5. `DiagnosticDefaultsPanel` lazy-loads and fetches `GET /api/diagnostics/defaults/?lang=es`.
6. Back link shows "Volver a Diagnósticos" linking to `/panel/diagnostics`.

**Branches:**
- [Branch A — Direct diagnostic link] Navigating to `/panel/defaults?mode=diagnostic` starts in diagnostic mode.
- [Branch B — Old URL redirect] `/panel/proposals/defaults?tab=sections` redirects to `/panel/defaults?mode=proposal&tab=sections`.
- [Branch C — Old URL redirect] `/panel/diagnostics/defaults` redirects to `/panel/defaults?mode=diagnostic`.
- [Branch D — Email templates redirect] `/panel/proposals/email-templates` redirects to `/panel/defaults?mode=proposal&tab=emails`.
- [Branch E — Unknown mode] Unknown `?mode=` value falls back to proposal mode.

**Unit Tests:** `frontend/test/components/DefaultsShell.test.js` (9 cases — mode computed, setMode, backLink).
**E2E Spec:** `e2e/admin/admin-defaults-unified.spec.js`.

---

### 17.7 Diagnostic Lifecycle Transitions Split (Apr 18, 2026)

Two transitions that were previously bundled into other flows now have their own IDs so the registry honestly reflects three distinct admin/client interactions:

#### FLOW: `admin-diagnostic-mark-in-analysis`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-mark-in-analysis` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P1 |
| **Status** | ✅ Covered (assertion already existed under `admin-diagnostic-send-initial`; tag now points to its own flow ID) |

**Routes:** `/panel/diagnostics/:id/edit` — sticky bottom action bar.
**Description:** After the initial diagnostic has been sent (status SENT, `initial_sent_at` stamped), the admin clicks **Marcar en análisis** to acknowledge the client authorized continuing. A `useConfirmModal` warns "¿Confirmar que el cliente autorizó? Se moverá a «En negociación»." On confirm, the store calls `POST /api/diagnostics/:id/mark-in-analysis/`, status transitions SENT → NEGOTIATING, the page toast shows "Diagnóstico en negociación.", and the action bar swaps the button for **Enviar diagnóstico final**.
**Steps:**
1. Admin opens a SENT diagnostic.
2. Admin clicks **Marcar en análisis** in the action bar.
3. Confirmation modal renders.
4. Admin confirms → POST `/mark-in-analysis/`.
5. Status updates to NEGOTIATING; toast shown; button row updates.
**Branches:**
- [Branch — Cancel] Admin cancels the modal → no state change.
- [Branch — API error] Backend returns non-2xx → red toast with the error message; status unchanged.
**E2E Spec:** `e2e/admin/admin-diagnostic-send.spec.js` ("Marcar en análisis" test).

#### FLOW: `diagnostic-public-respond`

| Attribute | Value |
|-----------|-------|
| **ID** | `diagnostic-public-respond` |
| **Module** | diagnostic |
| **Role** | guest |
| **Priority** | P1 |
| **Status** | ✅ Covered (assertion already existed under `diagnostic-public-view`; tag now points to its own flow ID) |

**Routes:** `/diagnostic/:uuid/`.
**Description:** On the public diagnostic page in final phase (status SENT with `final_sent_at` stamped), the footer exposes **Aceptar propuesta** and **Rechazar**. Clicking either calls `POST /api/diagnostics/public/<uuid>/respond/` with `{decision: 'accept' | 'reject'}`. The backend transitions to ACCEPTED or REJECTED, the page swaps to the acceptance / rejection confirmation footer, and the matching toast renders ("Tu aceptación quedó registrada." / "Tu respuesta quedó registrada.").
**Steps:**
1. Client opens a final-phase public diagnostic.
2. Client clicks **Aceptar propuesta** (or **Rechazar**).
3. Frontend POSTs `/respond/`.
4. Confirmation footer renders; status reflected on next refresh.
**Branches:**
- [Branch A — Accept] decision=accept → ACCEPTED, acceptance footer.
- [Branch B — Reject] decision=reject → REJECTED, rejection footer (typically with reason field).
- [Branch C — Already responded] If the diagnostic was already responded to, the respond buttons are hidden and the footer shows the existing response state.
**E2E Spec:** `e2e/public/diagnostic-public-view.spec.js` ("clicking 'Aceptar propuesta'…" test).

---

### 17.4 Out-of-scope behaviors documented but not registered as standalone flows

- **Legacy `?tab=technical|pricing|radiography` deep-links** — retired on 2026-04-18. `LEGACY_TAB_REDIRECTS` now maps `pricing → general`, `radiography → sections`, `technical → sections` so existing bookmarks land on the new owner of that data. Not a user outcome, documented here as a branch.
- **Conditional tab visibility by status** — Correos appears from `sent` onward; Documentos from `negotiating` onward. This is asserted implicitly by `admin-diagnostic-send-initial` (Correos should appear after the transition) and `admin-diagnostic-send-final` / confidentiality flows (Documentos should be available). Added here as a documented branch rather than a new flow since no new user outcome is introduced.

---

## Section 18 — Diagnostic List & Filter Flows (Apr 20, 2026)


> Flows identified during the Apr 20 E2E coverage audit. The diagnostic list page had no registered flow, and the `DiagnosticFilterPanel` + `useDiagnosticFilters` feature (saved tabs, 5 filter dimensions) shipped Apr 18 with no E2E spec or flow ID.

### 18.1 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-diagnostic-list` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-diagnostic-list.spec.js` |
| `admin-diagnostic-filters` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-advanced-filters.spec.js` — own-tag tests: status dimension, Limpiar todo, diagnosticTab URL sync (2026-07-23) |
| `admin-diagnostic-advanced-filters` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-advanced-filters.spec.js` |
| `admin-client-edit` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-client-edit.spec.js` |

---

### 18.2 Diagnostic List

#### FLOW: `admin-diagnostic-list`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-list` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P1 |
| **Status** | ✅ Covered — `e2e/admin/admin-diagnostic-list.spec.js` |

**Routes:** `/panel/diagnostics/`

**Description:** Admin views the list of all `WebAppDiagnostic` records. Each card shows title, client name, status badge (chip), investment amount, language, and creation date. The page exposes a search input, a "Valores por Defecto" header button, and a "+ Nuevo Diagnóstico" button. The list is fetched from `GET /api/diagnostics/` with the active filter params applied.

**Steps:**
1. Admin navigates to `/panel/diagnostics/`.
2. `GET /api/diagnostics/` fires; diagnostic cards render.
3. Admin sees each card with title, client name, status badge.
4. Admin clicks a diagnostic card → navigated to `/panel/diagnostics/:id/edit`.
5. Admin clicks "+ Nuevo Diagnóstico" → navigated to `/panel/diagnostics/create`.
6. Admin clicks "Valores por Defecto" → navigated to `/panel/diagnostics/defaults`.

**Branches:**
- [Branch A — Empty list] When no diagnostics exist, the empty-state copy renders ("Aún no has creado diagnósticos.").
- [Branch B — Search] Admin types in the search input → `searchQuery` filters the list client-side; matching cards remain visible, others hide.

**Expected outcome:** Diagnostic cards are visible; navigation to create/edit/defaults works; empty state renders correctly when list is empty.

**Flow tag:** `ADMIN_DIAGNOSTIC_LIST`

---

### 18.3 Diagnostic Filter Tabs

#### FLOW: `admin-diagnostic-filters`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-filters` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ⬜ Missing spec |

**Routes:** `/panel/diagnostics/`

**Description:** Admin filters diagnostics via `DiagnosticFilterPanel` + `useDiagnosticFilters`. Five filter dimensions: `statuses` (multi-select chip list), `investmentMin` / `investmentMax` (number inputs), `createdAfter` / `createdBefore` (date inputs). Results are filtered client-side on the already-fetched list. Filter state is persisted per saved tab in localStorage (`diagnostic_filter_tabs`). Tab bar mirrors `ProposalFilterTabs` behaviour: up to 12 tabs, add / rename / delete, URL sync via `?tab=<tabId>`.

**Steps:**
1. Admin navigates to `/panel/diagnostics/`.
2. Admin clicks "Filtros" toggle → `DiagnosticFilterPanel` expands.
3. Admin selects one or more statuses (e.g. "sent") → card list updates immediately.
4. Admin enters an investment range → cards outside the range are hidden.
5. Admin clicks "+ Guardar filtro" → modal prompts for tab name → new tab appears in the tab bar.
6. Admin reloads the page and selects the saved tab → the stored filters re-apply.
7. Admin deletes the tab → it disappears from the tab bar.

**Branches:**
- [Branch A — No results] All diagnostics filtered out → "No hay diagnósticos que coincidan con los filtros." empty state renders.
- [Branch B — Reset] Admin clicks "Restablecer" → all filter dimensions clear and full list shows.
- [Branch C — URL deep-link] `/panel/diagnostics/?tab=<tabId>` pre-selects the matching saved tab on load.

**Expected outcome:** Filter dimensions hide/show cards in real-time; tab save/load/delete persists to localStorage; URL reflects active tab.

**Flow tag:** `ADMIN_DIAGNOSTIC_FILTERS`

---

#### FLOW: `admin-diagnostic-advanced-filters`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-advanced-filters` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/diagnostics/`

**Description:** Advanced tab-based filter UI for diagnostics. Default view shows all diagnostics with no active filters. "Filtros" toggle button expands/collapses `DiagnosticFilterPanel` showing the Estados dimension. The "+" button opens a name input to create a saved filter tab (persisted to `localStorage['diagnostic_filter_tabs']`). The search input filters the rendered diagnostic list client-side by title.

**Steps:**
1. Admin navigates to `/panel/diagnostics/`.
2. All diagnostics are visible with no active filters.
3. Admin clicks "Filtros" → `DiagnosticFilterPanel` expands with status chips.
4. Admin clicks "Filtros" again → panel collapses.
5. Admin clicks "+" → name input appears → admin enters a name and confirms → new tab appears in the tab bar.
6. Admin types in the search input → visible cards filter by title immediately.

**E2E Spec:** `e2e/admin/admin-diagnostic-advanced-filters.spec.js` (4 tests).

**Flow tag:** `ADMIN_DIAGNOSTIC_ADVANCED_FILTERS`

---

#### FLOW: `admin-client-edit`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-client-edit` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/clients/`

**Description:** Admin edits an existing client profile from the Clientes list. Clicking the edit (pencil) icon on a client row opens a modal pre-filled with name, email, phone, and company. Admin changes one or more fields and submits. On success (`PUT /api/proposals/client-profiles/:id/update/` → 200), the modal closes. On validation error (400 with field errors), the modal stays open with the server error surfaced.

**Steps:**
1. Admin navigates to `/panel/clients/`.
2. Admin clicks the edit button on a client row (`data-testid="client-edit-{id}"`).
3. Modal opens with all fields pre-filled from the client profile.
4. Admin modifies the name field.
5. Admin clicks "Guardar" / submit.
6. [Branch A — Success] Modal closes; client list may refresh.
7. [Branch B — Error] Modal stays open; validation error message visible.

**E2E Spec:** `e2e/admin/admin-client-edit.spec.js` (3 tests).

**Flow tag:** `ADMIN_CLIENT_EDIT`

---

## Section 19 — Diagnostic Public Client Affordances (Apr 20, 2026)


> Flows added alongside the diagnostic public UI polish: PDF download endpoint, share modal, and dark mode toggle. These three affordances mirror the equivalent proposal client flows (`proposal-download-pdf`, `proposal-share`) and align the diagnostic public view with the proposal client experience.

### 19.1 New Flows Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `diagnostic-public-pdf-download` | diagnostic | guest | P2 | ✅ Covered | `e2e/public/diagnostic-public-affordances.spec.js` |
| `diagnostic-public-share`        | diagnostic | guest | P2 | ✅ Covered | `e2e/public/diagnostic-public-affordances.spec.js` |
| `diagnostic-public-dark-mode`    | diagnostic | guest | P3 | ✅ Covered | `e2e/public/diagnostic-public-affordances.spec.js` |

---

### 19.2 Diagnostic Public PDF Download

#### FLOW: `diagnostic-public-pdf-download`

| Attribute | Value |
|-----------|-------|
| **ID** | `diagnostic-public-pdf-download` |
| **Module** | diagnostic |
| **Role** | guest |
| **Priority** | P2 |
| **Status** | ✅ Covered — `e2e/public/diagnostic-public-affordances.spec.js` |

**Routes:** `/diagnostic/:uuid/`
**Endpoint:** `GET /api/diagnostics/public/:uuid/pdf/` (AllowAny, returns `application/pdf` when status is SENT/ACCEPTED/NEGOTIATING; 404 on DRAFT).

**Description:** The floating `DownloadDiagnosticPdfButton` (`data-testid="download-diagnostic-pdf-btn"`) appears once `store.current` is loaded. Clicking it calls the public PDF endpoint via `fetch()`, creates a blob URL, and triggers a browser download named `Diagnostico_<client>_<DD-MM-YY>.pdf`. The button disables and shows a spinner while the request is in flight and re-enables on completion. PDF is generated by `DiagnosticPdfService` (ReportLab), which renders all enabled sections in order using `pdf_utils` helpers.

**Steps:**
1. Client opens a SENT public diagnostic.
2. Client clicks the floating PDF button.
3. `GET /api/diagnostics/public/<uuid>/pdf/` fires.
4. On 200: blob is downloaded; button re-enables.
5. On error: console error logged; button re-enables.

**Flow tag:** `DIAGNOSTIC_PUBLIC_PDF_DOWNLOAD`

---

### 19.3 Diagnostic Public Share

#### FLOW: `diagnostic-public-share`

| Attribute | Value |
|-----------|-------|
| **ID** | `diagnostic-public-share` |
| **Module** | diagnostic |
| **Role** | guest |
| **Priority** | P2 |
| **Status** | ✅ Covered — `e2e/public/diagnostic-public-affordances.spec.js` |

**Routes:** `/diagnostic/:uuid/`

**Description:** The floating `ShareDiagnosticButton` (`data-testid="share-diagnostic-btn"`) opens a bottom-sheet modal (Teleport to body) with the current URL and a **Copiar enlace** action using `navigator.clipboard`. If `navigator.share` is available (mobile / Chromium with flag), a **Compartir vía apps** button also appears. No backend tracking is performed (silent). Modal closes on backdrop click or the close button.

**Steps:**
1. Client opens the public diagnostic page.
2. Client clicks the share button.
3. Modal renders with "Compartir diagnóstico" heading and "Copiar enlace" button.
4. Client clicks "Copiar enlace" → clipboard receives the URL; button changes to "¡Copiado!" for 2.5 s.
5. [Branch — native share] If `navigator.share` available, client clicks "Compartir vía apps" → OS share sheet opens.

**Flow tag:** `DIAGNOSTIC_PUBLIC_SHARE`

---

### 19.4 Diagnostic Public Dark Mode Toggle

#### FLOW: `diagnostic-public-dark-mode`

| Attribute | Value |
|-----------|-------|
| **ID** | `diagnostic-public-dark-mode` |
| **Module** | diagnostic |
| **Role** | guest |
| **Priority** | P3 |
| **Status** | ✅ Covered — `e2e/public/diagnostic-public-affordances.spec.js` |

**Routes:** `/diagnostic/:uuid/`

**Description:** A fixed bottom-left toggle button (`data-testid="diagnostic-theme-toggle"`) switches between light and dark mode by setting `data-theme` on `[data-diagnostic-wrapper]`. State is persisted to `localStorage['diagnostic-dark-mode']` via `useDiagnosticDarkMode` composable and restored on the next page load. Dark mode applies brand-aligned colors (`#0a1f1c` background, `#143d35` cards, `#E6EFEF` text) via scoped CSS `[data-theme="dark"] :deep(...)` rules.

**Steps:**
1. Client opens the public diagnostic page (light mode by default).
2. Client clicks the toggle (`🌙` icon).
3. `[data-diagnostic-wrapper]` receives `data-theme="dark"`; page styles update.
4. `localStorage['diagnostic-dark-mode']` is set to `"true"`.
5. Client reloads the page → composable reads localStorage on `onMounted`; dark mode is restored.
6. Client clicks the toggle again (`☀️` icon) → reverts to light mode.

**Flow tag:** `DIAGNOSTIC_PUBLIC_DARK_MODE`

---

## Section 20 — Flows Audit Gaps (Apr 20, 2026)


> Flows identified by the `/e2e-user-flows-check` audit as missing from the registry. All three carry `expectedSpecs: 0` and ❌ coverage — they are registered for traceability and to prioritize future E2E work.

---

### 20.1 Admin Proposal → Platform Handoff

#### FLOW: `admin-proposal-platform-handoff`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-proposal-platform-handoff` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P1 |
| **Status** | ✅ Covered |
| **E2E Spec** | `e2e/admin/admin-proposal-platform-handoff.spec.js` |

**Routes:** `/panel/proposals/:id/edit` (actions panel after acceptance)

**Description:** After a proposal is accepted by the client, admin clicks **"Lanzar a plataforma"** — `POST /api/proposals/:id/launch-to-platform/` — which creates a `PlatformProject` linked to the proposal and sends the client an invitation email containing an OTP. Admin sees a **"Ver en plataforma"** action in the proposal actions panel; client then starts the platform onboarding flow (`platform-login` → `platform-verify-onboarding` → `platform-complete-profile`).

**Steps:**
1. Admin navigates to a proposal in `accepted` status.
2. Actions panel shows "Lanzar a plataforma" button.
3. Admin clicks the button → `POST /api/proposals/:id/launch-to-platform/` fires.
4. Backend creates a `PlatformProject` (linked to proposal), sends invitation email with OTP.
5. Admin sees "Ver en plataforma" link in actions panel.
6. Client receives email, clicks link, enters OTP → platform onboarding starts.

**Known gaps:** This cross-module flow (proposal → platform) has no E2E coverage. The backend endpoint (`launch-to-platform`) exists and is tested in Python. An E2E spec would mock both the proposal detail and the `launch-to-platform` POST and verify the UI transition.

**Flow tag:** `ADMIN_PROPOSAL_PLATFORM_HANDOFF`

---

### 20.2 Diagnostic Public Phase Visibility

#### FLOW: `diagnostic-public-phase-visibility`

| Attribute | Value |
|-----------|-------|
| **ID** | `diagnostic-public-phase-visibility` |
| **Module** | diagnostic |
| **Role** | guest |
| **Priority** | P2 |
| **Status** | ❌ Missing — no dedicated E2E spec |

**Routes:** `/diagnostic/:uuid/`

**Description:** The public diagnostic page renders different sections depending on the diagnostic phase. After admin sends **initial phase** (`initial_sent_at` set, status=SENT), the API returns only sections with `visibility ∈ {initial, both}` and sections with `visibility='final'` are absent. After admin sends **final phase** (`final_sent_at` set), sections with `visibility='final'` (e.g. `executive_summary`, `cost`, `timeline`) are also returned.

**Steps:**
1. [Initial phase] Admin sends initial → client opens diagnostic link.
2. API returns only `initial`/`both` sections; `final`-only sections are not in the response.
3. Sidebar index and scroll containers show only the filtered sections.
4. [Final phase] Admin sends final → `final_sent_at` is stamped.
5. Client reloads → API now includes `final`-visibility sections.
6. Sidebar index updates; accept/reject footer appears.

**Known gaps:** `diagnostic-public-view` E2E covers section rendering for a single state but does not explicitly verify which section types appear or disappear when switching between initial and final phases.

**Flow tag:** `DIAGNOSTIC_PUBLIC_PHASE_VISIBILITY`

---

### 20.3 Admin Proposal Section Disable/Enable Toggle

#### FLOW: `admin-proposal-section-disable`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-proposal-section-disable` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |
| **E2E Spec** | `e2e/admin/admin-proposal-section-disable.spec.js` |

**Routes:** `/panel/proposals/:id/edit` (Secciones tab)

**Description:** Admin toggles section visibility (`is_enabled`) from the Secciones tab of the proposal edit page. Each section row has an enable/disable toggle; disabled sections are greyed out in the admin list and excluded from the public proposal view. Complements `admin-proposal-section-reorder` — both operations may be combined.

**Steps:**
1. Admin opens the Secciones tab of a proposal edit page.
2. Each section row shows an enable/disable toggle.
3. Admin clicks the toggle on a section → `PATCH /api/proposals/sections/:id/update/` with `{ is_enabled: false }`.
4. Section row is greyed out in the admin list.
5. Admin visits the public proposal link → the disabled section is not visible.
6. Admin re-enables the section → `PATCH` with `{ is_enabled: true }` → section reappears on public view.

**Known gaps:** `admin-proposal-section-reorder` covers drag reorder only. No E2E explicitly asserts that toggling `is_enabled` removes a section from the public proposal view.

**Flow tag:** `ADMIN_PROPOSAL_SECTION_DISABLE`

---

## Section 21 — Documents Tab Reorganization & doc_refs Attachment (Apr 22, 2026)


> Flows registered during the Apr 22, 2026 reorganization. The Documents tab now serves as a read-only document viewer; sending files is done from the Correos tab using `doc_refs` references — no re-upload needed. The old `admin-proposal-documents-send` flow is superseded.

---

### 21.1 Proposal — Adjuntar desde Documentos

#### FLOW: `admin-proposal-attach-from-documents`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-proposal-attach-from-documents` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P1 |
| **Status** | ✅ Covered |

**Routes:** `/panel/proposals/:id/edit` (Correos tab)

**Description:** Admin attaches existing proposal documents to the email composer without re-uploading them. The "Adjuntar desde Documentos" button opens `AttachFromDocumentsModal` which lists: contract PDF + draft (if a generated contract exists), commercial PDF, technical PDF, and any uploaded `proposal_documents`. Selected items become `doc_refs` badges in the composer. On send, `doc_refs` is included in the POST body and the backend resolves each reference to a real file attachment.

**Steps:**
1. Admin opens the Correos tab of a proposal (status `sent`, `viewed`, `negotiating`, `accepted`, or `rejected`).
2. Admin clicks **"Adjuntar desde Documentos"** button.
3. `AttachFromDocumentsModal` opens with a list of available documents.
4. Admin checks one or more documents; confirm button shows count: "Adjuntar (N)".
5. Admin clicks confirm → modal closes; emerald ref badges appear in the composer attachment area.
6. Admin completes the email and clicks "Enviar correo" → `POST /api/proposals/:id/branded-email/send/` with `doc_refs=[{source, id?}]`.
7. Backend resolves each `doc_refs` entry to a file binary and attaches it to the email.

**E2E Spec:** `e2e/admin/admin-proposal-attach-from-documents.spec.js`

**Flow tag:** `ADMIN_PROPOSAL_ATTACH_FROM_DOCUMENTS`

---

### 21.2 Diagnostic — Adjuntar desde Documentos

#### FLOW: `admin-diagnostic-attach-from-documents`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-attach-from-documents` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered |

**Routes:** `/panel/diagnostics/:id/edit` (Correos tab)

**Description:** Admin attaches existing diagnostic documents to the email composer without re-uploading. The "Adjuntar desde Documentos" button opens `AttachFromDocumentsModal` with: NDA final + NDA draft (if a generated `confidentiality_agreement` attachment exists), all diagnostic MD templates (Diagnóstico de Aplicación, Diagnóstico Técnico, Anexo — Dimensionamiento), and any uploaded `DiagnosticAttachment` files. Selected items become `doc_refs` badges. On send, `doc_refs` is included and the backend resolves each reference.

**Steps:**
1. Admin opens the Correos tab of a diagnostic (status `sent`, `viewed`, `negotiating`, `accepted`, `rejected`, or `finished`).
2. Composer loads `diagnostic-templates/` to populate available MD templates.
3. Admin clicks **"Adjuntar desde Documentos"** button.
4. `AttachFromDocumentsModal` opens; NDA items appear only if a generated `confidentiality_agreement` attachment exists.
5. Admin checks one or more items; confirm button shows count.
6. Admin clicks confirm → badges appear in the composer.
7. Admin completes the email and clicks "Enviar correo" → `POST /api/diagnostics/:id/email/send/` with `doc_refs=[{source, slug?, id?}]`.
8. Backend resolves: `nda_final`/`nda_draft` generate PDF; `template:<slug>` resolves MD; `attachment:<id>` reads the uploaded file.

**E2E Spec:** `e2e/admin/admin-diagnostic-attach-from-documents.spec.js`

**Flow tag:** `ADMIN_DIAGNOSTIC_ATTACH_FROM_DOCUMENTS`

---

### 21.3 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-proposal-attach-from-documents` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-proposal-attach-from-documents.spec.js` |
| `admin-diagnostic-attach-from-documents` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-diagnostic-attach-from-documents.spec.js` |
| `admin-proposal-documents-send` | admin | admin | P1 | ⚠️ Superseded | Replaced by `admin-proposal-attach-from-documents` (Apr 22, 2026); `expectedSpecs: 0` |
| `admin-proposal-slug-edit` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-proposal-slug-edit.spec.js` |

---

## Section 22 — Flows Audit Gaps (Apr 26, 2026)


> Flows surfaced by the `/e2e-user-flows-check` audit on 2026-04-26 from recent feature commits (`4862b149`, `9877df24`, `e827bd38`). All carry `expectedSpecs: 0` and ❌ coverage — registered for traceability and to prioritize future E2E work. Component-level unit tests already exist for several of them.

---

### 22.1 Diagnostic Public Onboarding

#### FLOW: `diagnostic-public-onboarding`

| Attribute | Value |
|-----------|-------|
| **ID** | `diagnostic-public-onboarding` |
| **Module** | diagnostic |
| **Role** | guest |
| **Priority** | P3 |
| **Status** | ❌ Missing — no E2E spec |

**Routes:** `/diagnostic/:uuid/`

**Description:** First-visit tutorial overlay on the public diagnostic page (`DiagnosticOnboarding.vue`, 376 lines) that walks the client through the report's structure with step-by-step tooltips, scroll-to-section behavior, and a "No volver a mostrar" option persisted to `localStorage`. Mirrors `proposal-view-onboarding` for the diagnostic module. Shipped with the diagnostic dark-mode rollout.

**Steps:**
1. Client opens `/diagnostic/:uuid/` for the first time (no `localStorage` skip flag set).
2. `DiagnosticOnboarding` overlay renders centered above the report, showing the first step.
3. Client clicks **"Siguiente"** → tooltip transitions to the next step; the page scrolls so the highlighted section is in view.
4. Final step shows a **"Listo"** button. On click, the overlay dismisses and the skip flag is set.
5. Client reloads the page → onboarding does not reappear.
6. [Branch — opt-out] Client checks **"No volver a mostrar"** at any step and dismisses → skip flag set even mid-tour.

**Known gaps:** Component-level unit tests exist (`DiagnosticOnboarding.test.js`, 227 lines). E2E spec pending; should mock the diagnostic public payload, clear `localStorage`, and assert step navigation, scroll-into-view, and the persistence of the skip flag.

**Flow tag:** `DIAGNOSTIC_PUBLIC_ONBOARDING`

---

### 22.2 Admin Proposal Document Preview

#### FLOW: `admin-proposal-document-preview`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-proposal-document-preview` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P3 |
| **Status** | ✅ Covered |
| **E2E Spec** | `e2e/admin/admin-proposal-document-preview.spec.js` |

**Routes:** `/panel/proposals/:id/edit` (Documents tab)

**Description:** Admin previews proposal attachments inline. PDFs render in an `<iframe>` and images in an `<img>`; DOCX and XLSX render extracted Markdown text and tables with a warning. DOC/XLS and unsupported formats keep preview disabled but retain original-file download.

**Steps:**
1. Admin opens Documentos on a proposal edit page.
2. Admin opens preview for a PDF, image, DOCX, or XLSX attachment.
3. PDF/image retain their original renderer; DOCX/XLSX load the textual Markdown preview.
4. Admin closes the modal through its close control or backdrop.
5. [Branch — unsupported] DOC/XLS keep Copy and Preview disabled with conversion guidance; images keep Copy disabled with OCR guidance. Original download remains available.

**Flow tag:** `ADMIN_PROPOSAL_DOCUMENT_PREVIEW`

---

### 22.3 Admin Diagnostic Document Preview

#### FLOW: `admin-diagnostic-document-preview`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-document-preview` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P3 |
| **Status** | ❌ Missing — no E2E spec |

**Routes:** `/panel/diagnostics/:id/edit` (Documentos tab)

**Description:** From the Documentos tab of the diagnostic edit page, admin clicks the eye icon next to an attachment. A modal opens previewing the file inline — PDF or image, gated by `frontend/utils/filePreview.js`. Replaces the previous inline template-expand behavior on `DiagnosticDocumentsTab.vue`.

**Steps:**
1. Admin opens the Documentos tab on a diagnostic edit page.
2. Each attachment row shows an eye icon when the file is previewable.
3. Admin clicks the icon → preview modal opens with PDF or image.
4. Admin closes the modal via the close button or backdrop click.
5. [Branch — non-previewable] Eye icon hidden; download link only.

**Known gaps:** Component-level unit test exists (`DiagnosticDocumentsTab.spec.js`). E2E spec pending; should mirror `admin-proposal-document-preview` against the diagnostic API surface.

**Flow tag:** `ADMIN_DIAGNOSTIC_DOCUMENT_PREVIEW`

---

### 22.4 Admin Blog Publish Mode

#### FLOW: `admin-blog-publish-mode`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-blog-publish-mode` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ❌ Missing — no E2E spec |

**Routes:** `/panel/blog/:id/edit`

**Description:** From the blog edit page, admin selects how the post should be published via three radio options: **Borrador** (draft), **Publicar ahora** (immediate), or **Programar** (scheduled). Selecting "Programar" reveals a datetime input for `publish_scheduled_for`. If the chosen datetime is in the past, an amber overdue banner (`[data-test="scheduled-overdue-banner"]`) warns that the safety-net Huey task will publish on the next run. The mode is computed by `frontend/utils/blogPublishMode.js` (`resolveBlogPublishMode → { mode, scheduledIso, overdue }`) and submitted with the blog update.

**Steps:**
1. Admin opens `/panel/blog/:id/edit` for an existing post.
2. The publish-mode group renders three radios pre-selected based on the current post state.
3. Admin selects **Programar** → datetime input appears.
4. Admin enters a future datetime → no banner; on save, `publish_scheduled_for` is persisted and `published=false`.
5. Admin enters a past datetime → amber `scheduled-overdue-banner` renders; on save, the post remains unpublished and waits for the safety-net task.
6. Admin selects **Publicar ahora** → on save, the backend marks `published=true` and clears `publish_scheduled_for`.
7. Admin selects **Borrador** → on save, the post is unpublished and unscheduled.

**Known gaps:** Publish-mode radio + scheduled-overdue-banner shipped 2026-04-25 (commit `4862b149`). Unit-tested via `frontend/test/utils/blogPublishMode.test.js`; no E2E spec covers the admin UI yet.

**Flow tag:** `ADMIN_BLOG_PUBLISH_MODE`

---

### 22.5 Admin Blog Overdue Schedule Safety-Net

#### FLOW: `admin-blog-overdue-detection`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-blog-overdue-detection` |
| **Module** | admin |
| **Role** | system |
| **Priority** | P2 |
| **Status** | ⬜ Backend-only — no E2E spec needed (`expectedSpecs: 0`) |

**Routes:** N/A — backend-only

**API:** Huey periodic task; management command `python manage.py publish_blog_post`

**Description:** Backend safety-net for missed schedules: scans `BlogPost` rows where `publish_scheduled_for` is in the past but the post is still unpublished, then publishes them automatically (and triggers the LinkedIn auto-publish if connected). The `publish_blog_post.py` management command is the manual escape hatch for the same logic.

**Steps:**
1. Huey scheduler triggers the periodic task.
2. Task queries `BlogPost.objects.filter(published=False, publish_scheduled_for__lte=now())`.
3. For each row, the post is published and `publish_scheduled_for` is cleared.
4. If the post has a connected LinkedIn account and a non-empty summary, `auto_publish_blog_to_linkedin` is invoked.

**Known gaps:** Backend-only — covered by `backend/content/tests/tasks/test_blog_publish_guards.py` (151 lines). No E2E surface to test.

**Flow tag:** `ADMIN_BLOG_OVERDUE_DETECTION`

---

### 22.6 Coverage Index

| Flow ID | Module | Role | Priority | Status | Suggested Spec |
|---------|--------|------|----------|--------|----------------|
| `diagnostic-public-onboarding` | diagnostic | guest | P3 | ❌ Missing | `e2e/public/diagnostic-public-onboarding.spec.js` |
| `admin-proposal-document-preview` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-proposal-document-preview.spec.js` |
| `admin-diagnostic-document-preview` | admin | admin | P3 | ❌ Missing | extend `e2e/admin/admin-diagnostic-email-documents.spec.js` |
| `admin-blog-publish-mode` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-blog-publish-mode.spec.js` |
| `admin-blog-overdue-detection` | admin | system | P2 | ⬜ Backend-only | N/A |

---

## Section 26 — LinkedIn Content Module (Jul 4, 2026)


> The LinkedIn integration was promoted from the blog edit page to a first-class panel module at `/panel/linkedin`, under the renamed sidebar section **ProjectApp content** (formerly "Website content"). Blog→LinkedIn publishing (Section 11) keeps working unchanged; OAuth store actions moved from `stores/blog.js` to `stores/linkedin.js`.

#### FLOW: `admin-linkedin-module`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/linkedin`
- **API:** `GET /api/linkedin/status/`, `GET /api/linkedin/auth-url/`, `POST /api/linkedin/callback/`, `GET /api/linkedin/posts/`, `POST /api/linkedin/posts/create/`, `PUT /api/linkedin/posts/:id/update/`, `DELETE /api/linkedin/posts/:id/delete/`, `POST /api/linkedin/posts/:id/publish/`
- **Frontend pages involved:** `/panel/linkedin`, `/auth/linkedin/callback`
- **Description:** Admin manages freeform LinkedIn posts: connection card (OAuth popup + token expiry date from `expires_at`), posts list with status chips (Borrador/Programado/Publicado/Fallido), create/edit modal (commentary ≤3000 chars, optional image, optional schedule datetime), publish-now with confirm, delete with confirm. Scheduled posts are auto-published server-side by Huey (per-post ETA task + every-minute sweep with atomic double-publish guards). A daily Huey task emails staff when the token expires in ≤7 days.
- **Steps:**
  1. Admin opens `/panel/linkedin` (sidebar: ProjectApp content → LinkedIn).
  2. Connection card loads from `GET /api/linkedin/status/` (connect/reconnect via the same OAuth popup + postMessage flow as the blog).
  3. Posts list loads from `GET /api/linkedin/posts/` (desktop table / mobile cards via `useIsMobile`).
  4. "Nuevo post" opens the modal → save as draft, or set a future datetime → status `scheduled` + Huey ETA task enqueued.
  5. "Publicar ahora" (confirm modal) → `POST /api/linkedin/posts/:id/publish/` → chip flips to Publicado with link to the LinkedIn post.
- **Branches:**
  - [Branch A — publish failure] LinkedIn API error → status `failed`, `error_message` persisted and shown inline; manual retry allowed.
  - [Branch B — already published] second publish attempt → 409, post immutable (edit blocked).
  - [Branch C — past schedule] `scheduled_at` in the past → 400 validation error.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-linkedin-module.spec.js`
- **Backend tests:** `content/tests/models/test_linkedin_post.py`, `content/tests/services/test_linkedin_post_service.py`, `content/tests/services/test_linkedin_expiry_service.py`, `content/tests/views/test_linkedin_post_views.py`, `content/tests/views/test_linkedin_post_publish.py`, `content/tests/tasks/test_linkedin_post_publish_guards.py`


---

## 19. Diagnostics Phase-1 Hardening Flows (Jul 2026)


> Flow identified during the Jul 6 diagnostics module audit (Phase 1: error
> handling + feedback). A failed list load used to be indistinguishable from
> the empty state; the page now renders a dedicated error state with retry.

#### FLOW: `admin-diagnostic-list-error-retry`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-list-error-retry` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P3 |
| **Status** | ❌ Missing — no E2E spec yet |

**Routes:** `/panel/diagnostics/`

**Description:** When `GET /api/diagnostics/` fails, the list page shows a dedicated error block (`data-testid="diagnostics-error-state"`) with the normalized Spanish error message and a "Reintentar" button that re-fires the fetch. An error notification is also raised via `usePanelNotify`. Distinct from the empty state, which only renders on a successful-but-empty response.

**Steps:**
1. Admin navigates to `/panel/diagnostics/` while the API is failing (5xx/network).
2. `GET /api/diagnostics/` rejects; the error block renders instead of the empty state, plus an error toast.
3. Admin clicks "Reintentar" → the fetch re-fires.
4. On success the table renders; on repeat failure the error block persists.


#### FLOW: `admin-diagnostic-bulk-actions`

| Attribute | Value |
|-----------|-------|
| **ID** | `admin-diagnostic-bulk-actions` |
| **Module** | admin |
| **Role** | admin |
| **Priority** | P2 |
| **Status** | ✅ Covered — `e2e/admin/admin-diagnostic-bulk-actions.spec.js` |

**Routes:** `/panel/diagnostics/`

**Description:** Admin selects diagnostics with the row/header checkboxes; a batch bar appears with "Finalizar aceptados" and "Eliminar" (confirm modal) calling `POST /api/diagnostics/bulk-action/` with `{ids, action}`. Delete prunes the rows locally; finish reloads the list. Results are notified via usePanelNotify. Backend covered by `content/tests/views/test_diagnostic_views_gaps.py::TestBulkDiagnosticAction`. (Ago 2026) La selección la posee `useRowSelection` y se reconcilia contra los diagnósticos cargados, así que eliminar una fila seleccionada desde su menú la descuenta de la barra en vez de dejar dentro un registro que ya no existe — el mismo defecto que tenía la barra de contabilidad.

**Steps:**
1. Admin checks one or more rows (or the header checkbox for the page).
2. The batch bar shows the selection count and actions.
3. Admin clicks "Eliminar" (or "Finalizar aceptados") and confirms in the modal.
4. `POST /api/diagnostics/bulk-action/` fires; the list updates and a notification reports the affected count.

---
