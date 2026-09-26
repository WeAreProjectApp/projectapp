<!-- GENERATED FILE — assembled from docs/user-flows/ by generate_flow_registry.py. Edit the per-flow files, never this one; on merge conflict, regenerate. -->

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
  - [Branch F — Crear] En `/panel/documents/create` no hay versión guardada a la que volver: el aviso no ofrece guardar ni descartar, y crear con éxito desarma el guard para que la redirección al editor no interrumpa. Llegar con `?folder=` no ensucia el formulario pese a la sugerencia de cliente por carpeta.
  - [Branch G — Buscar no es editar] Escribir en el selector de cliente sin elegir nada no levanta aviso: la selección enlazada se restaura al cerrar.
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


## 3. Shared Flows (Guest + Admin)

### FLOW: `layout-navbar-navigation`

- **Module:** layout
- **Role:** guest/admin
- **Priority:** P2
- **Routes:** All pages
- **Description:** Navigate between pages using the glassmorphism pill navbar with sliding lemon indicator.
- **Steps:**
  1. User sees the glassmorphism pill navbar fixed at the top of the page.
  2. User clicks a navigation link (Custom Software, App Development, Our work, Blog, Contact/WhatsApp).
  3. Page navigates to the selected route.
  4. Lemon pill indicator slides to highlight the active section.
- **Branches:**
  - [Branch A] User toggles language via EN/ES button → page reloads in selected locale (`/en-us/` or `/es-co/`).
  - [Branch B] User clicks Contact (WhatsApp) → external link opens.
  - [Branch C — Mobile] Hamburger menu opens with navigation links + WhatsApp CTA button.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/layout/layout-navbar.spec.js`

### FLOW: `layout-icon-interaction-feedback`

- **Module:** layout
- **Role:** guest / admin / platform-admin / platform-client
- **Priority:** P2
- **Routes:** Transversal; representative E2E route `/panel/views`
- **Description:** Activate an icon-only action, navigation control, opener, or toggle and receive an immediate restrained 420 ms press, upward hop and landing without a border effect. Copy actions additionally confirm the real clipboard result beside the originating control and temporarily replace the copy glyph with a check.
- **Steps:**
  1. The user reaches a surface with an enabled icon-only control.
  2. The user activates the control with pointer, touch, or keyboard.
  3. The glyph immediately presses down, hops upward and settles without moving the control or animating its border.
  4. For copy, the browser resolves the clipboard write.
  5. The same control shows a check plus a nearby success label, then returns to the copy glyph; the clipboard contains the requested reference.
- **Branches:**
  - [Branch A — Clipboard denied] The control keeps the copy glyph, shows a nearby error label and the owning surface keeps its normal error notification.
  - [Branch B — Reduced motion] A static contrast reaction remains visible without transform animation.
  - [Branch C — Coarse pointer] The interactive target is at least 44 × 44 px.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-view-map.spec.js`

### FLOW: `layout-locale-switch`

- **Module:** layout
- **Role:** guest/admin
- **Priority:** P2
- **Routes:** All pages with locale prefix (`/en-us/`, `/es-co/`)
- **Description:** Switch the application language between English and Spanish.
- **Steps:**
  1. User clicks the locale switcher component in the navbar.
  2. User selects a different language.
  3. URL updates with the new locale prefix.
  4. Page content re-renders in the selected language.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/layout/layout-locale.spec.js`

### FLOW: `layout-footer-navigation`

- **Module:** layout
- **Role:** guest/admin
- **Priority:** P3
- **Routes:** All pages
- **Description:** Navigate using footer links and social media links.
- **Steps:**
  1. User scrolls to the footer section.
  2. User clicks a footer link (social media, navigation, or contact).
  3. Page navigates or external link opens.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/layout/layout-footer.spec.js`


## 4. Guest Flows

### FLOW: `public-home`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Routes:** `/`, `/en-us`, `/es-co`
- **Description:** View the public home/landing page with hero, services, study cases, portfolio and contact sections.
- **Steps:**
  1. User navigates to the home page.
  2. Hero section renders with animations.
  3. TechStack section displays technology logos.
  4. Services cards section renders with service offerings.
  5. Study cases section displays project showcases.
  6. Bento grid section renders.
  7. Contract section and contact form section render.
  8. Marquee strips and Book-a-Call section render.
  9. Footer section renders with links.
- **Branches:**
  - [Branch A] User fills contact form → form submits via API → success feedback.
  - [Branch B] User clicks "Book a Call" → external booking link opens.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-home.spec.js`

### FLOW: `public-portfolio`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Routes:** `/portfolio-works`, `/en-us/portfolio-works`, `/es-co/portfolio-works`
- **Description:** Browse portfolio works listing page (Awwwards-style) with hero section, animated gradient, and project cards linking to case study detail pages.
- **Steps:**
  1. User navigates to the portfolio page.
  2. Hero section renders with animated gradient background.
  3. Portfolio works load from API (`GET /api/portfolio/`).
  4. Project cards render with title, excerpt, cover image, and "View" link.
  5. User clicks a project card.
  6. Page navigates to `/portfolio-works/:slug`.
- **Branches:**
  - [Branch A] Empty state renders when no projects are published.
  - [Branch B] Loading spinner renders while data is being fetched.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-pages.spec.js`

### FLOW: `public-portfolio-detail`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Routes:** `/portfolio-works/:slug`, `/en-us/portfolio-works/:slug`, `/es-co/portfolio-works/:slug`
- **Description:** View a single portfolio case study (Awwwards-style) with cover image, content sections, share button, project URL link, and back navigation.
- **Steps:**
  1. User clicks a project from the portfolio listing or navigates directly to `/portfolio-works/:slug`.
  2. Case study data loads from API (`GET /api/portfolio/:slug/`).
  3. Title, excerpt, cover image, and share button render.
  4. Content sections render (JSON-structured content or HTML fallback).
  5. Back link to `/portfolio-works` is visible.
  6. [Optional] "Visit project" link renders if `project_url` exists.
- **Branches:**
  - [Branch A — Not found] 404 page renders with "Back to portfolio" link.
  - [Branch B — Share] User clicks share button to share the case study.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-portfolio-detail.spec.js`

> **Archived Flows:** The following pages were moved to `_archived/` and are no longer accessible via navigation:
> `public-web-designs`, `public-3d-animations`, `public-hosting`, `public-ecommerce-prices`, `public-custom-software`.
> They were previously covered by `e2e/public/public-pages.spec.js`.

### FLOW: `public-about-us` *(ARCHIVED)*

- **Module:** public
- **Role:** guest
- **Priority:** P3
- **Routes:** `/about-us` *(page exists but is no longer linked from navigation)*
- **Description:** View the about us page with team and company information.
- **Status:** ARCHIVED — removed from navbar and footer. No internal links point to this page.
- **Coverage:** ❌ E2E test removed (flow archived)

### FLOW: `public-landing-web-design`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Routes:** `/landing-web-design`, `/en-us/landing-web-design`, `/es-co/landing-web-design`
- **Description:** View the web design landing page (marketing/conversion page).
- **Steps:**
  1. User navigates to the landing web design page.
  2. Landing page content renders with hero, features, CTA.
  3. Contact form section renders.
- **Branches:**
  - [Branch A] User submits contact form → API call → success feedback.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-pages.spec.js`

### FLOW: `public-contact-submit`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Routes:** `/contact`, `/en-us/contact`, `/es-co/contact` → `/contact-success`
- **Description:** Submit a contact form to reach the company.
- **Steps:**
  1. User navigates to the contact page.
  2. Contact form renders with fields (name, email, message, etc.).
  3. User fills in the form fields.
  4. User submits the form.
  5. API call to `POST /api/new-contact/`.
  6. On success, user is redirected to `/contact-success`.
- **Branches:**
  - [Branch A — Validation error] Form shows inline validation errors, user corrects and resubmits.
  - [Branch B — API error] The localized `contact-submit-error` message renders below the submit button and the form remains editable (mechanism added 2026-08-03 — before that the store's `submitError` was never displayed). Covered by the `@outcome:error` spec.
- **Coverage:** ✅ Covered (success + error)
- **E2E Spec:** `e2e/public/public-contact.spec.js`

### FLOW: `public-privacy-policy`

- **Module:** public
- **Role:** guest
- **Priority:** P4
- **Routes:** `/privacy-policy`
- **Description:** View the public privacy policy page with localized content (ES/EN).
- **Steps:**
  1. User navigates to `/privacy-policy`.
  2. Page renders with localized privacy policy content.
  3. SEO meta tags and structured data are present.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-privacy-policy.spec.js`

### FLOW: `public-terms-conditions`

- **Module:** public
- **Role:** guest
- **Priority:** P4
- **Routes:** `/terms-and-conditions`
- **Description:** View the public terms and conditions page with localized content (ES/EN).
- **Steps:**
  1. User navigates to `/terms-and-conditions`.
  2. Page renders with localized terms and conditions content.
  3. SEO meta tags and structured data are present.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/public-terms-conditions.spec.js`

### FLOW: `public-route-not-found`

- **Module:** public
- **Role:** guest
- **Priority:** P3
- **Routes:** `/:slug*`
- **Description:** A guest reaches the public catch-all route after navigating to an unmatched URL. The terminal fallback renders “Page not found”.
- **Steps:**
  1. Guest opens an unmatched public URL.
  2. The catch-all route renders the terminal not-found message.
- **Branches:**
  - [n/a — success] The view has no recovery action or successful completion.
  - [n/a — error] It performs no request or validation that can display an error branch.
  - [failure] An unmatched route resolves to the explicit not-found state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/responsive/public.spec.js`

### FLOW: `blog-list`

- **Module:** blog
- **Role:** guest
- **Priority:** P2
- **Routes:** `/blog`, `/en-us/blog`, `/es-co/blog`
- **Description:** Browse the blog post listing with bilingual support.
- **Steps:**
  1. User navigates to the blog index page.
  2. Blog posts load from API (`GET /api/blog/?lang=es|en`).
  3. Post grid renders with titles, excerpts, and cover images.
  4. Language is resolved from the URL locale prefix.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/blog/blog-list.spec.js`

### FLOW: `blog-detail`

- **Module:** blog
- **Role:** guest
- **Priority:** P2
- **Routes:** `/blog/:slug`, `/en-us/blog/:slug`, `/es-co/blog/:slug`
- **Description:** Read a single blog post with bilingual content.
- **Steps:**
  1. User clicks a blog post from the listing.
  2. Blog post detail loads from API (`GET /api/blog/:slug/?lang=es|en`).
  3. Post content renders with title, content, sources.
  4. Navigation back to blog listing is available.
- **Branches:**
  - [Branch A — Post not found] 404 page or error message displays.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/blog/blog-detail.spec.js`


## 5. Proposal Flows (Guest via UUID)

### FLOW: `proposal-view`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** View a business proposal shared via unique UUID link with horizontal scroll navigation.
- **Steps:**
  1. User opens the proposal URL with UUID.
  2. Proposal data loads from API (`GET /api/proposals/:uuid/`).
  3. Proposal index page renders with title, client info, expiration badge.
  4. User navigates through proposal sections using horizontal scroll (GSAP).
  5. Section counter updates as user navigates.
  6. User reads requirement groups and items within sections.
- **Branches:**
  - [Branch A — Proposal expired] Expired proposal page renders with expiration message.
  - [Branch B — Proposal not found] 404 or error page renders.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-view.spec.js`

### FLOW: `proposal-view-navigation`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** Navigate between proposal sections using prev/next arrow buttons and the ProposalIndex side panel. Includes SectionNavButtons (with `hideLeft` when index is open), ProposalIndex (floating hamburger menu listing all sections), and SectionCounter.
- **Steps:**
  1. User opens the proposal URL.
  2. First section renders. Next button (`nav-side--right`) is visible; Prev button absent.
  3. User clicks next button → transition animation → second section renders.
  4. Prev button (`nav-side--left`) now visible.
  5. User clicks hamburger toggle (`.index-toggle`) → ProposalIndex panel opens.
  6. While index is open, prev button is hidden (`hideLeft` prop).
  7. User clicks an index item → navigates directly to that section → index closes.
  8. On last panel (proposal_closing), next button disappears.
- **Branches:**
  - [Branch A — Index navigation] User jumps to any section via ProposalIndex.
  - [Branch B — Sequential navigation] User steps through each section one by one.
  - [Branch C — Mobile swipe] Touch swipe left/right triggers navigation.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-view-navigation.spec.js`

### FLOW: `proposal-view-onboarding`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** First-visit tutorial overlay (ProposalOnboarding component) that shows step-by-step tooltips guiding the client through the proposal interface. After completion, a reading-time popup appears.
- **Steps:**
  1. User opens the proposal for the first time.
  2. ProposalOnboarding overlay appears with first tooltip step.
  3. User clicks through each onboarding step.
  4. Onboarding completes and emits `@complete` event.
  5. Reading time popup appears: "Tiempo de lectura: ~7 minutos".
  6. User clicks "Entendido" to dismiss popup.
- **Branches:**
  - [Branch A — Returning visitor] Onboarding is skipped if already seen (localStorage flag).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-onboarding.spec.js`

### FLOW: `proposal-section-onboarding`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** Per-section spotlight onboarding tutorials that trigger automatically the first time a client navigates to specific sections. Each section has its own component with a spotlight overlay (blur backdrop + cloned element), progress dots, and positioned tooltip card. Tutorials are skipped for returning visitors (localStorage flag per proposal UUID).
- **Steps:**
  1. Client navigates to the Investment section for the first time (detailed view, with calculator modules).
  2. InvestmentOnboarding component triggers after 800ms delay.
  3. Spotlight highlights the "Personalizar tu inversión" button with a tooltip explaining the calculator.
  4. Client clicks through onboarding steps → completes → localStorage flag set.
  5. [Separate trigger] Client navigates to functional_requirements section.
  6. RequirementsOnboarding component triggers after 800ms delay.
  7. Spotlight highlights requirement group cards with a tooltip explaining how to expand them.
  8. [Separate trigger] Client in executive view navigates to investment section.
  9. ExecutiveInvestmentOnboarding triggers, highlighting the "Ver detalle" teaser button.
- **Branches:**
  - [Branch A — Detailed Investment] InvestmentOnboarding triggers only in detailed view when calculator modules exist.
  - [Branch B — Executive Investment] ExecutiveInvestmentOnboarding triggers only in executive view.
  - [Branch C — Requirements] RequirementsOnboarding triggers in both view modes.
  - [Branch D — Returning visitor] Each tutorial is skipped if already completed (per-UUID localStorage flag).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-section-onboarding.spec.js`
- **Components:** `InvestmentOnboarding.vue`, `RequirementsOnboarding.vue`, `ExecutiveInvestmentOnboarding.vue`

### FLOW: `proposal-executive-to-detailed`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client switches from executive view to the full detailed proposal view via the "Ver Propuesta Completa" button in the ProposalIndex sidebar, or via the teaser button in the executive Investment section. A branded transition overlay (esmerald background with lemon icon + loading text) plays during the mode switch. The page scrolls to top and renders all sections.
- **Steps:**
  1. Client is viewing the proposal in executive mode (filtered sections).
  2. Client opens the ProposalIndex sidebar menu.
  3. Client clicks "Ver Propuesta Completa" button at the bottom of the sidebar.
  4. ProposalIndex emits `switchToDetailed` event and closes.
  5. Branded transition overlay appears (esmerald bg, lemon bouncing icon, "Cargando propuesta completa…").
  6. After ~1s, `viewMode` switches from `'executive'` to `'detailed'`, all sections render.
  7. Overlay fades out, page scrolls to top.
  8. Client can now navigate all proposal sections.
- **Branches:**
  - [Branch A — From sidebar] Client clicks "Ver Propuesta Completa" in ProposalIndex.
  - [Branch B — From Investment teaser] Executive Investment section has a teaser button that also triggers `switchToDetailed`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-executive-to-detailed.spec.js`
- **Components:** `ProposalIndex.vue` (`switchToDetailed` emit), `[uuid]/index.vue` (`handleSwitchToDetailed`)

### FLOW: `proposal-technical-view`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid?mode=technical`
- **Description:** Third gateway option when `technical_document` is enabled: carousel of synthetic panels from `content_json` (intro, stack, architecture, etc.) plus `proposal_closing`. PDF download uses `?doc=technical`. Tracking sends `view_mode: technical`.
- **Outcomes:**
  - `display` — the cover renders the purpose and one index card per section that carries content, each showing that section's weight (`7 capas`, `6 módulos · 38 requerimientos`).
  - `success` — clicking an index card jumps straight to that section, skipping the panels in between.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-technical-view.spec.js`
- **Components:** `ProposalViewGateway.vue`, `TechnicalDocumentPublicPanel.vue`, `[uuid]/index.vue`, `technicalProposalPanels.js`

### FLOW: `proposal-contract-terms`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`, `/proposal/:uuid?mode=legal`
- **Description:** Fourth gateway option, named **Contrato y condiciones**, available only when the proposal is in Spanish and its visibility flag is enabled. It renders two panels from the current global contract template: an introduction with a clause index and one continuous contract document inside a bordered, layered paper surface. This content is independent from the proposal section JSON and from any proposal-specific contract attachment.
- **Outcomes:**
  - `display` — the client reaches the mode through the gateway and sees the generic explanation, draft notice, and real clause titles inside one accessible document surface returned by `GET /api/proposals/:uuid/contract-terms/`.
  - `success` — selecting a clause in the index opens the document panel and scrolls to that clause's stable anchor.
  - `error` — `?mode=legal` cannot bypass the Spanish-language and per-proposal visibility gates; the regular gateway remains visible without the legal option.
  - `failure` — if the global template is temporarily unavailable, the introduction explains the failure and lets the client retry.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-contract-terms.spec.js`
- **Components:** `ProposalViewGateway.vue`, `ContractTermsOverview.vue`, `ContractTermsDocument.vue`, `[uuid]/index.vue`

### FLOW: `proposal-contract-draft-download`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid?mode=legal`
- **Description:** Download the current global contract as an informational draft from the persistent floating **Descargar PDF** action. The introduction does not duplicate the download control. The server forces the default template, masks personal data, omits signatures, adds the `BORRADOR` watermark, and returns it from `GET /api/proposals/:uuid/contract/draft-pdf/`.
- **Outcomes:**
  - `success` — clicking the floating **Descargar PDF** action starts a PDF download from the dedicated draft endpoint.
- **Non-applicable classes:** `error` and `failure` are handled by the browser's native download surface; the proposal does not expose a separate form or recoverable download-error state. `display` is covered by the parent `proposal-contract-terms` flow.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-contract-terms.spec.js`

### FLOW: `proposal-respond`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** Client responds to (accepts/rejects) a business proposal from the ProposalClosing panel. Accept button has visual dominance (larger, glow, pulse animation). Acceptance triggers a confetti celebration animation via `canvas-confetti`.
- **Steps:**
  1. User views the proposal and navigates to the closing panel.
  2. Accept/reject buttons visible when `proposal.status` is `sent` or `viewed`. Accept button is visually dominant (larger, green glow, subtle pulse).
  3. User clicks "Acepto la propuesta" → confirmation modal opens.
  4. User confirms → API call to `POST /api/proposals/:uuid/respond/` with `decision: accepted`.
  5. Success state: confetti animation fires (canvas-confetti), bouncing 🎉 emoji, "¡Propuesta aceptada!" message renders.
- **Branches:**
  - [Branch A — Accept] Client clicks accept → confirm modal → API → confetti animation + success message.
  - [Branch B — Reject] Client clicks "Rechazar propuesta" → reject modal (select reason + comment) → API → smart recovery message.
  - [Branch C — Already responded] Buttons hidden, status message shown.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-respond.spec.js`

### FLOW: `proposal-download-pdf`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Download a proposal as PDF.
- **Steps:**
  1. User views the proposal.
  2. User clicks the download PDF button.
  3. API call to `GET /api/proposals/:uuid/pdf/`.
  4. PDF file downloads to user's device.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-pdf.spec.js`

### FLOW: `proposal-share`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client shares the proposal with a team member or stakeholder via the share button. A tracked share link is created, and the recipient receives an email notification.
- **Steps:**
  1. User views the proposal.
  2. User clicks the share button (ShareProposalButton component).
  3. User fills in recipient name and email.
  4. API call to `POST /api/proposals/:uuid/share/`.
  5. Backend creates a ProposalShareLink record.
  6. Share notification email is sent to the recipient.
  7. Success feedback displays.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-share.spec.js`

### FLOW: `proposal-engagement-tracking`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Qualified tracking of client engagement while viewing a proposal. Loading the document is read-only; after five visible seconds, `useProposalTracking` sends validated section-level time data and the backend atomically records the session, first-view alert, and delivery state.
- **Steps:**
  1. User opens a proposal page.
  2. `useProposalTracking` generates a stable session ID but does not count the document `GET` as a view.
  3. Once the proposal remains visible for five seconds, it sends the first validated heartbeat to `POST /api/proposals/:uuid/track/`.
  4. As the user navigates, 30-second heartbeats update section time; hiding or leaving the page sends a final beacon.
  5. The backend validates the complete payload and atomically creates or updates `ProposalViewEvent` and `ProposalSectionView` records without duplicating the session.
  6. The first qualified session creates a persistent panel alert and queues an email with durable retry state.
  7. [Optional] Revisit, stakeholder, expiration, rejection, and engagement-decay signals are evaluated from confirmed tracking events.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-engagement-tracking.spec.js`


## 6. Admin Flows

### FLOW: `admin-login`

- **Módulo:** auth · **Rol:** admin · **Prioridad:** P1
- **Rutas:** `/panel/login` → `/admin/login/` → destino interno de `next`.
- **Recorrido:** abrir el enlace al Django Admin, completar credenciales y
  reCAPTCHA v2; enviar para crear la sesión y volver a la página solicitada.
- **Success:** CAPTCHA aceptado y credenciales de staff válidas crean la sesión.
- **Error:** token ausente, inválido o expirado bloquea el intento; se requiere
  una verificación nueva tras credenciales incorrectas.
- **Failure:** Google no disponible o script bloqueado deja el acceso cerrado
  con mensaje y Reintentar. Las sesiones previamente abiertas siguen vigentes.
- **Display:** la página de entrada conserva el enlace hacia Django Admin.
- **E2E:** `e2e/auth/auth-admin-login.spec.js` mantiene el hand-off;
  `e2e/captcha/panel-login-captcha.spec.js` recorre el formulario Django real,
  con base temporal y simulación únicamente del proveedor externo.
- **Ejecución:** `npx playwright test --config playwright.captcha.config.js panel-login-captcha.spec.js`.
- La abstención histórica para credenciales/sesión queda reemplazada por estos
  recorridos. POST sin JavaScript, CSRF y permisos se cubren además en backend.

### FLOW: `admin-panel-session-expired`

- **Module:** auth
- **Role:** admin
- **Priority:** P1
- **Routes:** Any `/panel/*` route except `/panel/login` (guarded by `middleware/admin-auth.js`, registered on all 45 panel pages, e.g. `/panel/`, `/panel/proposals`)
- **Description:** A browser without a valid staff session requests a protected `/panel/*` route — either it never authenticated, or a previously valid session expired/was invalidated server-side.
- **Steps:**
  1. User (or a browser with a stale/expired cookie) navigates to a `/panel/*` route other than `/panel/login`.
  2. The `admin-auth` Nuxt middleware calls `GET /api/auth/check/` (`checkAdminAuth` action in `stores/proposals.js`).
  3. Backend `check_admin_auth` returns 401 (no authenticated user) or 403 (authenticated but not staff) instead of the user payload.
  4. Middleware hard-redirects the browser (`window.location.href`, a full page navigation, not `navigateTo`/SPA routing) to `/admin/login/?next=<originally requested path>` and aborts the SPA navigation (`abortNavigation()`).
  5. [Branch] Signing in again on the Django login form returns the user to the originally requested `/panel/*` page via `next`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/auth/auth-admin-login.spec.js` (describe "Admin Panel Session Guard": mocks `GET /api/auth/check/` → 401 and asserts the hard redirect to `/admin/login/?next=/en-us/panel/proposals`)

### FLOW: `admin-impersonate-user`

- **Module:** admin
- **Role:** admin (superuser only)
- **Priority:** P2
- **Routes:** `/panel/admins/` (or Django `/admin/` user page) → `/platform/admin-login` → `/platform/dashboard`
- **Description:** A superuser starts an impersonation session ("Login with this user") to access the platform as the target user for support/QA.
- **Steps:**
  1. Superuser opens `/panel/admins/` and clicks "Login with this user" on a user row (or opens the Django admin user page and clicks the "Log in as this user" button).
  2. Backend `POST /api/accounts/admins/<id>/login-as/` (or the admin `login_as` view) validates the policy, mints JWT tokens, and stores them behind a short-lived single-use exchange code.
  3. A new tab opens `/platform/admin-login?code=...&redirect=/platform` (no tokens on the URL).
  4. The callback page POSTs the code to `POST /api/accounts/impersonation/exchange/`, receives the tokens, and hydrates the session (`GET /api/accounts/me/`).
  5. User lands authenticated on `/platform/dashboard` as the impersonated user.
- **Security:** only active superusers; cannot impersonate another superuser; cannot impersonate inactive users; target must have a platform profile.
- **Coverage:** ⚠️ Pending (registered, E2E spec not yet implemented)
- **E2E Spec:** _suggested:_ `e2e/admin/admin-impersonate-user.spec.js`

### FLOW: `admin-dashboard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/`
- **Description:** View the redesigned global dashboard: pulse KPIs (liquid utility, active pipeline, attention count), cross-module attention radar, and finance / proposals / operations sections fed by one request to `GET /api/panel/dashboard/`.
- **Steps:**
  1. Authenticated admin navigates to `/panel/`.
  2. The page fetches `GET /api/panel/dashboard/` (single consolidated payload) and shows skeletons while loading.
  3. Pulse tiles, attention radar and the module sections render; section headers deep-link to each module.
  4. The "+ Crear" dropdown offers quick creation shortcuts (propuesta, documento, tarea, gasto).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

### FLOW: `admin-dashboard-finance-gate`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/`
- **Description:** Financial KPIs (liquid utility pulse tile and Finanzas section) render only when the backend payload carries finance data; staff non-superusers receive `finance: null` and never see financial figures. The gate is enforced server-side in `panel_dashboard` view.
- **Steps:**
  1. Staff (non-superuser) admin opens `/panel/`.
  2. `GET /api/panel/dashboard/` responds with `finance: null` and no finance-derived attention items.
  3. The dashboard renders proposals and operations only; no utility tile or Finanzas section.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

### FLOW: `admin-dashboard-attention-radar`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/`
- **Description:** Cross-module actionable list: overdue collection accounts, failed emails (7d), overdue tasks, proposals sent-unopened >7d and upcoming recurring payments, each with severity accent (danger/warning/info) and a deep-link to its module. Shows a positive state when nothing needs attention.
- **Steps:**
  1. Admin opens `/panel/` with pending items in the payload's `attention` list.
  2. Radar renders one row per item, ordered by severity, with Spanish copy and module label.
  3. Clicking a row navigates to the owning module (e.g. `/panel/tasks`).
  4. With an empty list, the radar shows "Nada requiere tu atención".
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

### FLOW: `admin-dashboard-error-retry`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/`
- **Description:** A failed `GET /api/panel/dashboard/` load replaces the dashboard with a global error state; the Reintentar button refetches and restores the full dashboard once the API recovers.
- **Steps:**
  1. Admin opens `/panel/` while the dashboard endpoint fails (5xx).
  2. The error state renders with a Reintentar button and a panel notification fires.
  3. Clicking Reintentar refetches; on success the pulse/radar/sections render.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

### FLOW: `admin-dashboard-quick-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/`
- **Description:** The dashboard header "+ Crear" dropdown offers quick navigation to create a proposal, document, task or expense.
- **Steps:**
  1. Admin opens `/panel/` and clicks "+ Crear".
  2. The dropdown lists Propuesta / Documento / Tarea / Gasto.
  3. Selecting an option navigates to the corresponding module route.
- **Coverage:** ✅ Covered (menu destinations + real navigation to expenses). Covering this flow surfaced and fixed a real bug: `BaseDropdown` rendered `to` items through `<component :is="'NuxtLink'">`, which cannot resolve Nuxt auto-imported components — the menu items were dead `<nuxtlink>` elements with no href (fixed with `resolveComponent`).
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

### FLOW: `admin-dashboard-stats-modals`

- **Module:** admin
- **Role:** admin (finance modal: superuser only)
- **Priority:** P2
- **Routes:** `/panel/`
- **Description:** The pulse tiles open descriptive-statistics modals (StatsModal: BaseModal 5xl + BaseTabs + ApexCharts). The "Pipeline activo" tile opens the proposals modal — tabs Tendencia (stacked trend), Embudo (horizontal funnel by status), Valor por etapa (avg value per stage) and Conversión (monthly conversion line + radial close rate) — which lazily fetches `GET /api/proposals/dashboard/` once per modal lifetime (heavy endpoint, cached in a local ref, never fetched on dashboard load). The superuser-gated "Utilidad líquida" tile opens the finance modal computed client-side from the finance block: Evolución (expected/liquid/expenses area), Utilidad (monthly utility bars + margin strip) and Deuda y compromisos (credit utilization radial + debt/pocket/recurring strip).
- **Steps:**
  1. Admin opens `/panel/` and clicks the "Pipeline activo" tile (button with hover/focus affordance).
  2. The proposals modal opens, fetches the proposals dashboard once and renders the Tendencia tab.
  3. Switching tabs (v-if panels) renders the funnel/value/conversion charts.
  4. Superuser clicks "Utilidad líquida" → finance modal renders from data already loaded.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-dashboard.spec.js`

### FLOW: `admin-proposal-list`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/`
- **Description:** View the list of all business proposals. Table includes heat score badge (1-10, color-coded), "días sin actividad" red badge for inactive proposals, WhatsApp quick-action in dropdown, and a floating metrics manual button.
- **Steps:**
  1. Admin navigates to `/panel/proposals/`.
  2. Proposals load from API (`GET /api/proposals/`) with `heat_score` per proposal.
  3. Proposal table renders with status, client, dates, 🔥 heat score column, and inactivity badges.
  4. Actions dropdown includes "Enviar por WhatsApp" with pre-filled contextual message.
  5. Floating "?" button opens the MetricsManual slide-over with searchable metric definitions.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-list.spec.js`

### FLOW: `admin-proposal-advanced-filters`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Admin uses advanced filter panel with 11 dimensions (status, project type, market type, currency, language, investment range, heat score range, view count range, created date range, last activity date range, active status) and saves filter combinations as named tabs (max 12) with localStorage persistence and URL sync.
- **Steps:**
  1. Admin navigates to `/panel/proposals/` and clicks "Filtros" toggle button.
  2. Filter panel expands with responsive grid of filter controls.
  3. Admin selects filter values (e.g., status pills, project type dropdown, date range).
  4. Proposal table updates in real-time (client-side filtering, single-pass).
  5. Admin clicks "+" tab button → inline input appears → types tab name → clicks "Guardar".
  6. New named tab appears in tab bar; filters are persisted to localStorage.
  7. Admin reloads page → saved tabs persist; clicking a tab restores its filters.
  8. Admin right-clicks tab context menu → "Renombrar" or "Eliminar".
  9. "Todas" tab resets all filters. "Limpiar filtros" button clears active filters.
  10. URL updates with `?tab=<tabId>` for deep-linking.
- **Branches:**
  - [Branch A — Tab limit] When 12 tabs exist, "+" button is disabled with tooltip.
  - [Branch B — Mobile] Tab bar collapses to `<select>` dropdown below `md` breakpoint.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-advanced-filters.spec.js`

### FLOW: `admin-proposal-project-schedule`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/<id>/edit?tab=schedule`
- **Description:** Admin sets per-stage start/end dates (design, development) for an accepted proposal in the Cronograma tab, sees proportional status badges (faltan / vencida / completada), and marks stages as completed to silence deadline alerts. The daily Huey task `notify_proposal_stage_deadlines` reads these dates and emails the team a 70%-elapsed warning + every-3-day overdue reminder.
- **Steps:**
  1. Admin opens an accepted proposal via `/panel/proposals/<id>/edit`.
  2. Admin clicks the "Cronograma" tab (only visible when status is `accepted` or `finished`).
  3. Tab shows two stage cards: Diseño and Desarrollo.
  4. Admin types start_date and end_date for the Diseño stage and clicks "Guardar fechas".
  5. PUT `/api/proposals/<id>/stages/design/` succeeds; the stage card status badge updates ("Faltan X días" / "Vencida hace X días").
  6. Admin clicks "Marcar como completada" → POST `/api/proposals/<id>/stages/design/complete/` → badge becomes "🟢 Completada".
- **Branches:**
  - [Branch A — Validation] When start_date > end_date, the form shows an inline error and no request is sent.
  - [Branch B — Tab visibility] When the proposal is in `draft`/`sent`/`viewed`/`negotiating`, the Cronograma tab is hidden.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-project-schedule.spec.js`

### FLOW: `admin-proposal-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/create`
- **Description:** Create a new business proposal (manual mode) with 12 auto-generated default sections.
- **Steps:**
  1. Admin navigates to `/panel/proposals/create`.
  2. Page loads with Manual / Importar JSON tab toggle.
  3. Manual tab is active by default — form renders with Título, Nombre del cliente, Email del cliente, Idioma, etc.
  4. Admin fills in the fields and submits.
  5. API call to `POST /api/proposals/create/`.
  6. Backend auto-creates 12 default sections and returns the full proposal.
  7. Admin is redirected to `/panel/proposals/:id/edit`.
- **Branches:**
  - [Branch A — Validation error] Form shows errors, admin corrects and resubmits.
  - [Branch B — JSON import] Admin switches to "Importar JSON" tab (see `admin-proposal-create-from-json`).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-create.spec.js`
- **Known gaps:** Hosting defaults seeding on mount (hosting_percent + hosting_discount_* from GET `proposals/defaults`, 2026-07) is not asserted — the spec's defaults mock only carries `expiration_days`. The JSON-tab `total_investment` now uses `BaseCurrencyInput` (live thousand separators) and its formatting is not asserted.

### FLOW: `admin-proposal-create-from-json`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/create` (JSON import tab)
- **Description:** Admin creates a proposal by importing a pre-filled JSON payload. Alongside section data, `_meta.optional_metadata.email_intro` carries a generated plain-text message explaining the client's problem, this proposal's solution, and the expected outcome. The UI flattens that value to the API `email_intro` field; it remains editable later in **Correos**. Missing sections still fall back to defaults, while an omitted message is allowed only for a saved draft and blocks direct send.
- **Steps:**
  1. Admin navigates to `/panel/proposals/create`.
  2. Admin clicks "Importar JSON" tab.
  3. JSON textarea/file input appears.
  4. Admin pastes or loads a valid JSON payload (must include `sections.general.clientName`; generated artifacts should also include `_meta.optional_metadata.email_intro`).
  5. Admin submits.
  6. API call to `POST /api/proposals/create-from-json/` with `ProposalFromJSONSerializer` validation.
  7. Backend creates the proposal, persists `email_intro`, and creates all section records with the provided `content_json`.
  8. Admin is redirected to `/panel/proposals/:id/edit`.
- **Branches:**
  - [Branch A — Missing general key] Validation error `sections.general required`.
  - [Branch B — Past expires_at] Validation error on date.
  - [Branch C — Partial sections] Unspecified sections default to template defaults.
  - [Branch D — `_meta` key] Stripped from sections before saving.
  - [Branch E — Missing message] Draft creation remains valid, but "Crear y Enviar" stays unavailable until a message is provided.
- **Coverage:** ✅ Covered — JSON flattening/persistence and direct-send gating are exercised in the create E2E spec; serializer/API persistence are pytest-covered.
- **E2E Spec:** `e2e/admin/admin-proposal-create.spec.js`

### FLOW: `admin-proposal-client-autocomplete`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/create` (Manual tab), `/panel/proposals/:id/edit`
- **API:** `GET /api/proposals/client-profiles/search/?q=<term>`
- **Description:** Client picker autocomplete in the proposal create/edit form. Admin types a search term; backend returns matching clients (by name, email, or company) from the mini-CRM. Selecting a client auto-fills the snapshot fields (name, email, phone, company). When no match is found, a "Crear nuevo" button sets the typed value as a brand-new client name without triggering another search.
- **Steps:**
  1. Admin navigates to `/panel/proposals/create` and activates the Manual tab (or opens `/panel/proposals/:id/edit`).
  2. The autocomplete input (`[data-testid="client-autocomplete-input"]`) is visible.
  3. Admin types 2+ characters → `GET /api/proposals/client-profiles/search/?q=...` fires (debounced).
  4. Matching results render as a dropdown (`[data-testid="client-autocomplete-option-:id"]`) showing name, email, company, and total proposals count.
  5. Admin clicks a result → `#create-client-name`, `#create-client-email`, phone and company snapshot fields auto-populate.
- **Branches:**
  - [Branch A — No match] Dropdown shows "Crear nuevo" button (`[data-testid="client-autocomplete-create-new"]`) → clicking it sets the typed value as the client name and clears the dropdown.
  - [Branch B — Placeholder client] When the selected client has `is_email_placeholder=true`, the email field remains empty and the placeholder hint is shown (see `admin-proposal-client-no-email`).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-client-autocomplete.spec.js`

### FLOW: `admin-proposal-client-no-email`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/create` (Manual tab)
- **API:** `POST /api/proposals/` (omitted `client_email`)
- **Description:** Admin creates a proposal without providing a client email. The backend generates a placeholder email (`cliente_<id>@temp.example.com`), flags the client as `is_email_placeholder=true`, and pauses all automations for that client (e.g., reminder / overdue stage notifications). A hint banner informs the admin that email-based automations will be paused until the email is filled in.
- **Steps:**
  1. Admin navigates to `/panel/proposals/create` (Manual tab).
  2. Admin fills `#create-client-name` and leaves `#create-client-email` blank.
  3. Placeholder hint text (e.g., "email temporal" / "automatizaciones pausadas") renders near the email input.
  4. Admin submits the form → `POST /api/proposals/` with `client_email=""`.
  5. Backend creates the proposal and a placeholder client profile with `automations_paused=true`.
  6. Admin is redirected to `/panel/proposals/:id/edit`; the client snapshot shows the placeholder email.
- **Branches:**
  - [Branch A — Fill email later] Admin edits the client email from the proposal edit page later → the placeholder flag clears and automations resume (handled by `admin-mini-crm-clients` or proposal edit).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-client-autocomplete.spec.js`

### FLOW: `admin-proposal-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Edit an existing business proposal.
- **Steps:**
  1. Admin navigates to `/panel/proposals/:id/edit`.
  2. Proposal data loads from API (`GET /api/proposals/:id/detail/`).
  3. Edit form renders pre-filled with current data.
  4. Admin modifies proposal details, sections, requirements.
  5. Admin saves changes.
  6. API call to `PATCH /api/proposals/:id/update/`.
  7. Success feedback displays.
- **Branches:**
  - [Branch A] Admin reorders sections → `POST /api/proposals/:id/reorder-sections/`.
  - [Branch B] Admin updates individual section → `PATCH /api/proposals/sections/:id/update/`.
  - [Branch C — item traceability] In the Det. técnico tab, editor sections render collapsed by default (2026-08 perf round): the admin expands "Módulos del producto" (`technical-section-toggle-epics`), opens the requirement's "Vincular alcance/ítems (n)" disclosure (`technical-req-links-toggle`), and checks the commercial-item boxes (grouped by functional_requirements card, `technical-req-item-links`) that write `linked_item_ids`; saving (button always visible below the sections) persists them via the same section update endpoint. These links power the public nested requirements modal and the commercial PDF sub-rows. The JSON sub-tab mounts only when selected.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-edit.spec.js` (includes linked_item_ids save test)
- **Known gaps:** The automations toggle now uses positive polarity (ON = automations running, 2026-07); no E2E asserts knob position / `aria-checked`, and the toggle has no `data-testid` (only `aria-label="Activar automatizaciones"`).

### FLOW: `admin-proposal-contract-terms-visibility`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/create`, `/panel/proposals/:id/edit`
- **Description:** Decide whether a Spanish proposal exposes the generic **Contrato y condiciones** mode. The switch defaults to visible for new and existing proposals, is unavailable for English proposals, and persists as top-level proposal metadata without changing the proposal prompt or section JSON.
- **Outcomes:**
  - `success` — the creation form submits the selected visibility and the edit switch persists an immediate visibility change.
  - `failure` — when the edit request fails, the switch returns to its previous state and the admin sees an error notification.
- **Non-applicable classes:** `error` has no independent invalid Boolean input. `display` is asserted as the precondition and final state of the success/failure interactions rather than a separate read-only flow.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-contract-terms-visibility.spec.js`

### FLOW: `admin-proposal-slug-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (General tab → URL personalizada)
- **Description:** Admin sets or regenerates the human-friendly slug for the public proposal URL. The slug replaces the UUID in the shared link (`/proposal/<slug>/`) making it feel personal to the client. Includes format validation, uniqueness check, and one-click regeneration from client name.
- **Steps:**
  1. Admin opens a proposal and stays on the General tab.
  2. The slug input shows the current slug (auto-generated on creation from default pattern or client name).
  3. Admin types a new slug in the input field (lowercase, numbers, hyphens only).
  4. Client validates format with regex `/^[a-z0-9]+(?:-[a-z0-9]+)*$/`; red error shown for invalid format.
  5. Admin clicks "Guardar URL" → `PATCH /api/proposals/:id/update/` with `{ slug }`.
  6. Server validates uniqueness; 400 error surfaced in UI if taken.
  7. Success state (✓) shown; copy-link button and preview href update to use new slug.
  8. [Branch] Admin clicks "Regenerar" to reset slug from client name via `toSlug(clientName)`.
- **Branches:**
  - [Branch A — Valid format] Save succeeds, slug persists, public URL updates.
  - [Branch B — Invalid format] Red error message blocks save.
  - [Branch C — Duplicate slug] Server 400 → "Esa URL ya está en uso" message.
  - [Branch D — Regenerate] Slug input pre-filled with `toSlug(clientName)`; admin can still modify before saving.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-slug-edit.spec.js`

### FLOW: `admin-proposal-section-edit-form`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Sections tab)
- **Description:** Admin edits a proposal section using the structured form fields. Each of the 17 section types has its own form layout (greeting, executive_summary, context_diagnostic, conversion_strategy, roi_projection, design_ux, creative_support, development_stages, process_methodology, functional_requirements, timeline, investment, value_added_modules, proposal_summary, final_note, next_steps, technical_document). When saved in form mode, `_editMode: 'form'` is stored in content_json and the client sees the structured presentation.
- **Steps:**
  1. Admin opens a proposal in edit mode and navigates to the "Secciones" tab.
  2. Admin selects a section to edit.
  3. SectionEditor renders the form fields specific to the section type.
  4. Admin fills/modifies the form fields (text inputs, textareas, repeatable items).
  5. Admin clicks "Guardar Sección".
  6. Component emits save event with `{ sectionId, payload: { title, is_wide_panel, content_json } }`.
  7. content_json includes `_editMode: 'form'` (no `rawText`).
  8. API call to `PATCH /api/proposals/sections/:id/update/` with the content_json.
  9. Backend stores the content_json as-is in the ProposalSection model.
  10. Success feedback "✓ Guardado" displays.
  11. Next time admin expands the section, it opens in "Formulario" mode.
- **Branches:**
  - [Branch A — Each section type] Form layout differs: greeting has clientName + inspirationalQuote; executive_summary has paragraphs + highlights; conversion_strategy has steps with bullets; functional_requirements has nested groups with items; timeline has phases with tasks; investment has whatsIncluded + paymentOptions; etc.
  - [Branch B — Repeatable items] Admin adds/removes steps, stages, phases, groups, items, badges, payment options, contact methods via + / Eliminar buttons.
  - [Branch C — Client view] When `_editMode: 'form'`, the client-facing proposal renders the section using its structured component (e.g., ExecutiveSummary, ConversionStrategy).
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-proposal-section-form.spec.js`

### FLOW: `admin-proposal-hour-rate`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit?tab=hour-rate` (Tarifa por hora tab)
- **Description:** Admin sets the hourly rate of the hour packages for one proposal. In **automático** (the default) the rate keeps syncing from the `HourPackage` catalog, so a catalog edit reaches every PDF. In **manual** the proposal carries its own base rate — and optionally a rate for an individual package — while names, hours and discounts still come from the catalog. The manual value is stored on the proposal and never touches the catalog or any other proposal.
- **Steps:**
  1. Admin opens a proposal in edit mode and selects the "Tarifa por hora" tab.
  2. The tab loads the catalog for the proposal's nationality and renders a preview of the table the PDF prints (Paquete / Horas / Dcto. / Tarifa/hora / Total).
  3. Admin switches the control to "Manual"; the rate input appears, pre-filled from the catalog.
  4. Admin types a rate; every row of the preview recalculates live (rate × (1 − discount), × hours).
  5. Optionally, admin sets a rate for a single package, which overrides the base rate for that row only.
  6. Admin clicks "Guardar" → `PATCH /api/proposals/sections/:id/update/` writes `hourPackagesMode`, `manualHourlyRate`, `manualCurrency` and `manualPackageRates` into the commercial_conditions `content_json`.
  7. The generated PDF seeds the packages from the catalog and overlays the manual rates.
- **Branches:**
  - [Branch A — Back to automatic] The manual rate is kept, not discarded; the catalog value rules while automatic is on, and re-enabling manual restores the saved rate.
  - [Branch B — No section] A proposal without the commercial_conditions section shows an empty state with a "Crear la sección" button.
  - [Branch C — Empty catalog] With no active packages for the nationality, a warning shows and the preview falls back to the snapshot stored on the proposal.
  - [Branch D — Currency changed] If the proposal's nationality changed after the manual rate was set, the tab reverts to automatic and warns, so a COP amount is never reprinted as USD.
  - [Branch E — Disabled section] If commercial_conditions is disabled, a banner warns that these packages will not reach the PDF.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-hour-rate.spec.js`
- **Unit Tests:** `test/components/SectionEditor.test.js`
- **Backend Tests:** `content/tests/views/test_section_update_views.py`
- **Known gaps:** The `commercial_conditions` and `value_added_modules` editors are not exercised by the spec; their money fields (`hourlyRate` base and per-package, `min_price_usd/cop`) now use `BaseCurrencyInput` (2026-07).

### FLOW: `admin-proposal-section-edit-paste`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Sections tab)
- **Description:** Admin uses the "Pegar contenido" mode to save raw text content for a section. The paste textarea auto-syncs from form fields via `formToReadableText()`. When saved in paste mode, `_editMode: 'paste'` and `rawText` are stored in content_json. The client-facing proposal renders paste sections using `RawContentSection.vue` — a rounded card with markdown rendering — instead of the structured component.
- **Steps:**
  1. Admin opens a section in the SectionEditor.
  2. Admin clicks the "Pegar contenido" toggle button (switches from "Formulario" mode).
  3. A large textarea (rows=18) appears, pre-filled with `formToReadableText()` output from the current form fields.
  4. Admin types or pastes content (supports Markdown formatting).
  5. Admin clicks "Guardar Sección".
  6. content_json includes `_editMode: 'paste'` and `rawText` with the textarea content.
  7. API call to `PATCH /api/proposals/sections/:id/update/`.
  8. Backend stores `_editMode` and `rawText` in content_json.
  9. Success feedback "✓ Guardado" displays.
  10. Next time admin expands the section, it opens in "Pegar contenido" mode (remembers last saved mode).
- **Branches:**
  - [Branch A — Form auto-sync] As admin fills form fields, the paste textarea dynamically updates when toggling to paste mode.
  - [Branch B — Toggle back to form] Admin switches back to "Formulario" → saves with `_editMode: 'form'`, no `rawText`.
  - [Branch C — Empty paste] Saves `rawText` as empty string.
  - [Branch D — Client view] When `_editMode: 'paste'`, the client-facing proposal renders `RawContentSection` with the section title and the pasted content in a rounded card (`bg-gray-50/80 backdrop-blur-sm border rounded-2xl`) with Markdown rendered via `marked` + `DOMPurify`.
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-proposal-section-paste.spec.js`
- **Unit Tests:** `test/components/SectionEditor.test.js`
- **Backend Tests:** `content/tests/views/test_section_update_views.py`

### FLOW: `admin-proposal-section-reorder`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Secciones tab)
- **Description:** Admin reorders the sections within a proposal.
- **Steps:**
  1. Admin views the sections list in the edit page.
  2. Admin changes the order of sections.
  3. API call to `POST /api/proposals/:id/reorder-sections/` with `{ sections: [{id, order}] }`.
  4. Sections re-render in the new order.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-section-reorder.spec.js`

### FLOW: `admin-proposal-section-dirty-guard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Secciones tab)
- **Description:** Unsaved-changes protection in the section editor.
- **Steps:**
  1. Admin edits a field of an expanded section; a «Sin guardar» badge appears on the section header.
  2. Collapsing the dirty section opens a confirmation modal («Cerrar sin guardar» / «Seguir editando»).
  3. Cancelling keeps the editor open with the edits intact; confirming discards them and clears the badge.
  4. Route navigation, page unload and the panel refresh button also confirm before discarding dirty sections.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-section-dirty-guard.spec.js`

### FLOW: `admin-proposal-section-add-delete`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Secciones tab)
- **Description:** Admin adds a missing section type and deletes sections from the editor.
- **Steps:**
  1. Admin clicks «＋ Agregar sección»; the modal lists only the types not yet present.
  2. Picking a type calls `POST /api/proposals/:id/sections/create/` (seeded from language defaults) and the new section appears expanded at the end.
  3. The trash action on a section header asks for confirmation and calls `DELETE /api/proposals/sections/:id/delete/`.
  4. Deleting `functional_requirements` with a confirmed calculator selection is blocked by the backend (`fr_has_confirmed_selection`) and the error surfaces as a notification.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-section-add-delete.spec.js`

### FLOW: `admin-proposal-section-sync`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Secciones tab → SyncPreviewModal)
- **Description:** Admin reconciles a section's `content_json` against the canonical default for that `section_type`. The SyncPreviewModal shows a server-computed diff (added / removed / changed keys), and on apply the section is overwritten with the merged payload. Mounted at `frontend/components/BusinessProposal/admin/SyncPreviewModal.vue` from `pages/panel/proposals/[id]/edit.vue:42`.
- **Steps:**
  1. Admin opens the proposal edit page and selects a section.
  2. Admin triggers "Sincronizar con default" → `GET /api/proposals/sections/:id/sync-preview/` returns the diff payload.
  3. SyncPreviewModal renders the diff (keys to add / overwrite / drop) with side-by-side preview.
  4. Admin clicks "Aplicar" → `POST /api/proposals/sections/:id/apply-sync/` overwrites `content_json` and returns the updated section.
  5. UI refreshes the section in place (no page reload).
- **Branches:**
  - [Branch A — No drift] Diff is empty; modal shows "Sin cambios" and the apply button is disabled.
  - [Branch B — Cancel] Admin closes the modal without applying; section unchanged.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-section-sync.spec.js`
- **Note:** The modal only appears when saving a `technical_document` section on a proposal whose platform project already exists (`has_project: true`). An E2E would need to mock the full proposal detail with a launched project, simulate the section editor save flow, and intercept both `sync-preview/` and `apply-sync/`. The cost outweighs the P2 value; component-level coverage of `SyncPreviewModal.vue` would be a better fit.
- **Suggested E2E Spec:** `e2e/admin/admin-proposal-section-sync.spec.js`

### FLOW: `admin-proposal-functional-requirements-form`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Sections tab → functional_requirements section)
- **Description:** Admin manages functional requirement groups (Views, Components, Features, Admin Module) and their items using the form interface. Each item has an editable "ID (enlace técnico)" field — the stable id (`item-<group>-<slug>`) used by the technical document's `linked_item_ids` for item↔requirement traceability. Missing ids are auto-assigned on save (client mirror + backend `ensure_functional_requirements_item_ids`). The section preview mirrors the public render, including the per-item "Ver requerimientos (N)" links built from the proposal's technical_document.
- **Steps:**
  1. Admin opens the functional_requirements section editor.
  2. Four default groups render: Views, Components, Features, Admin Module.
  3. Admin edits group fields: icon, title, description.
  4. Admin adds items to a group: icon, name, description, optional stable id (auto-generated on save when empty).
  5. Admin removes items from a group.
  6. Admin adds additional modules via "+ Agregar módulo adicional".
  7. Admin saves the section → content_json includes groups[] and additionalModules[] with per-group `_editMode` and per-item stable `id`.
  8. [Preview] Admin opens the section preview → items with linked technical requirements show the same "Ver requerimientos (N)" affordance the client sees.
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-proposal-requirements.spec.js`
- **Unit Tests:** `test/components/SectionEditor.test.js`, `test/components/SectionPreviewModal.test.js`
- **Backend Tests:** `content/tests/views/test_section_update_views.py`

### FLOW: `admin-proposal-functional-requirements-paste`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Sections tab → functional_requirements section)
- **Description:** Admin uses the per-group "Pegar contenido" mode to save raw text for individual requirement groups. Each group and additional module has its own paste toggle. When a group is in paste mode, the client-facing proposal renders that group as a `RawContentSection` with Markdown.
- **Steps:**
  1. Admin opens the functional_requirements section editor.
  2. Admin clicks "Pegar contenido" on a specific group (e.g., Views).
  3. A textarea (rows=10) appears within that group, pre-filled via `groupToReadableText()`.
  4. Admin types or pastes content.
  5. Admin saves the section → group's `_editMode: 'paste'` and `rawText` are stored in content_json.
  6. On next open, the group remembers paste mode.
- **Branches:**
  - [Branch A — Mixed modes] Some groups in form mode, others in paste mode → each saved independently.
  - [Branch B — Client view] Groups with `_editMode: 'paste'` render as `RawContentSection` in the client proposal.
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-proposal-requirements.spec.js`
- **Unit Tests:** `test/components/SectionEditor.test.js`
- **Backend Tests:** `content/tests/views/test_section_update_views.py`

### FLOW: `admin-proposal-delete`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Delete an existing business proposal from the proposals list.
- **Steps:**
  1. Admin views the proposal list.
  2. Admin clicks delete on a proposal.
  3. A confirmation modal appears requiring the admin to type `DELETE`.
  4. Admin confirms deletion.
  5. API call to `DELETE /api/proposals/:id/delete/`.
  6. On success: proposal is removed (list refreshed) and a success toast shows.
  7. On `409 Conflict` (proposal linked to a launched project via `ProjectPhase`, `on_delete=PROTECT`): the proposal stays and an error toast shows the backend message.
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-proposal-delete.spec.js`
- **Known gaps:** The existing spec only navigates + mocks the endpoint; it does not exercise the confirm modal (type `DELETE`), the success toast + list refresh, or the `409` blocked-delete path for project-linked proposals.

### FLOW: `admin-proposal-delete-from-client`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Delete a specific proposal from a client's expanded row in the Mini-CRM clients view.
- **Steps:**
  1. Admin opens `/panel/clients` and expands a client row to see its linked proposals.
  2. Admin clicks delete on a specific proposal.
  3. A confirmation modal appears requiring the admin to type `DELETE`.
  4. Admin confirms → `DELETE /api/proposals/:id/delete/`.
  5. On success: the client detail is refetched (proposal disappears) and a success toast shows.
  6. On `409 Conflict` (linked to a launched project): the proposal stays and an error toast shows.
- **Coverage:** ❌ Missing
- **E2E Spec:** _none yet (suggested: `e2e/admin/admin-proposal-delete-from-client.spec.js`)_

### FLOW: `admin-proposal-duplicate`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Duplicate an existing proposal to create a new draft copy with the same sections and content.
- **Steps:**
  1. Admin views the proposal list or detail page.
  2. Admin clicks "Duplicar" on a proposal.
  3. API call to `POST /api/proposals/:id/duplicate/`.
  4. Backend creates a new proposal with status=draft, copying all sections and content.
  5. Admin is redirected to the new proposal's edit page.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-duplicate.spec.js`

### FLOW: `admin-proposal-comment`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Add internal comments to a proposal for team collaboration.
- **Steps:**
  1. Admin opens a proposal in edit mode.
  2. Admin writes a comment in the comment field.
  3. API call to `POST /api/proposals/:id/comment/`.
  4. Comment is saved and a changelog entry is created.
  5. Comment notification email is sent to the client.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-comment.spec.js`

### FLOW: `admin-proposal-analytics`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Analytics tab)
- **Description:** View detailed analytics for a single proposal including engagement funnel, section time heatmap, device breakdown, shared links, session history, suggested actions, CSV export, and the durable delivery state of the first-view alert. Technical engagement unifies `technical_document` (sección) and `technical_document_public` (paneles en modo técnico) for skip list, funnel, `technical_engagement`, engagement score, and CSV “Metric group”.
- **Steps:**
  1. Admin opens a proposal and navigates to the Analytics tab.
  2. ProposalAnalytics component loads data from `GET /api/proposals/:id/analytics/`.
  3. Summary cards and the first-view alert state render, including attempts, confirmed delivery time, or the last delivery error.
  4. Comparison badges show performance vs portfolio average.
  5. Engagement funnel visualization renders (Sent → Viewed → Engaged → Responded).
  6. Section time heatmap shows color-coded bars per section.
  7. Shared links table renders if any ProposalShareLinks exist.
  8. Activity timeline and session history display.
  9. [Optional] Admin clicks "Exportar CSV" to download analytics data.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-analytics.spec.js`

### FLOW: `admin-proposal-dashboard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/` (Dashboard KPI section)
- **Description:** View global KPI dashboard for all proposals: total proposals, conversion rate, average time to first view, average time to response, average value by status, status distribution, top rejection reasons, monthly trends, discount vs no-discount close rates, win rate by predominant tracking view mode (ejecutiva / completa / técnica), and top drop-off section scoped to commercial section types (excluye doc. técnico y paneles sintéticos).
- **Steps:**
  1. Admin navigates to `/panel/`.
  2. ProposalDashboard component loads data from `GET /api/proposals/dashboard/`.
  3. KPI cards render with total proposals, conversion rate, avg time metrics.
  4. Status distribution chart renders.
  5. Top rejection reasons list renders.
  6. Monthly trend data renders.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-dashboard.spec.js`

### FLOW: `admin-proposal-defaults-config`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/defaults?mode=proposal` (old `/panel/proposals/defaults` redirects here)
- **Description:** Admin manages the default section configurations used when creating new proposals. Supports both ES and EN languages. Changes are saved to a DB-backed config and applied to all future proposals. Includes reset-to-hardcoded functionality.
- **Steps:**
  1. Admin navigates to `/panel/defaults?mode=proposal` via the "Defaults" sidebar item or the "Valores por Defecto" button on the proposals list page.
  2. Default sections load from API (`GET /api/proposals/defaults/?lang=es`).
  3. Language selector allows switching between Español and English.
  4. Section accordion list renders with all default sections (same structure as proposal edit).
  5. Admin expands a section and edits its content using SectionEditor (form or paste mode).
  6. Section is marked as "Modificado" locally.
  7. Admin clicks "Guardar Todos los Cambios".
  8. API call to `PUT /api/proposals/defaults/` with the full sections_json array plus `base_updated_at`, the version loaded in step 2.
  9. Success feedback displays.
- **Branches:**
  - [Branch A — Reset] Admin clicks "Restaurar valores originales" → confirmation modal → `POST /api/proposals/defaults/reset/` → sections reload from hardcoded defaults.
  - [Branch B — Language switch with unsaved changes] Confirmation prompt warns about losing changes.
  - [Branch C — Stale snapshot (failure)] The stored config moved on since step 2 (a migration, or another admin saving) → `PUT` answers `409 stale_defaults` → the panel shows "Los valores por defecto cambiaron desde que abriste esta página." and **keeps the pending edits on screen**, so the admin chooses between refreshing and re-applying them. Without this the snapshot would rewind the stored defaults and every proposal created afterwards would inherit the rewound content.
- **Coverage:** ⚠️ Partial — `display` covered; `success` and `failure` have no qualifying E2E test.
- **E2E Spec:** `e2e/admin/admin-proposal-defaults.spec.js` (5 tests, all `@outcome:display`)
- **Backend Tests:** `content/tests/views/test_proposal_defaults_views.py`, `content/tests/models/test_proposal_default_config.py`, `content/tests/services/test_proposal_service.py::TestGetDefaultSectionsFromDB`

### FLOW: `admin-proposal-defaults-slug-pattern`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/defaults?mode=proposal` (General tab)
- **Description:** Admin configures the default slug pattern used when new proposals are created. The pattern supports `{client_name}`, `{project_type}`, and `{year}` placeholders. A live preview below the input shows the slugified result (e.g., `{client_name}` → `/proposal/empresa-demo`). Saved to `ProposalDefaultConfig.default_slug_pattern`.
- **Steps:**
  1. Admin navigates to `/panel/defaults?mode=proposal`.
  2. General tab renders. Slug pattern input shows current value (default: `{client_name}`).
  3. Live preview below input updates reactively as admin types, showing the `toSlug()` result.
  4. Admin edits the pattern (e.g., `{client_name}-{year}`).
  5. Admin clicks "Guardar" → `PUT /api/proposals/defaults/` with `{ default_slug_pattern }`.
  6. Future proposals auto-generate slugs using the new pattern.
- **Branches:**
  - [Branch A — Valid pattern] Pattern saved; new proposals use the pattern.
  - [Branch B — Custom text] Any free-text pattern (no placeholders) works; becomes a fixed prefix with collision suffix appended.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-defaults-slug-pattern.spec.js`

### FLOW: `admin-email-templates-config`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/email-templates`
- **Description:** Admin manages email template content customization. Lists all email templates (client, internal, contact) with category filter. Admin can edit text fields (greeting, body, CTA, subject), toggle templates on/off, preview rendered HTML with sample data, and reset to defaults.
- **Steps:**
  1. Admin navigates to `/panel/proposals/email-templates`.
  2. Template list loads from API (`GET /api/email-templates/`).
  3. Category filter buttons (Todos, Cliente, Interno, Contacto) allow filtering.
  4. Admin clicks a template row to expand the editor.
  5. Template detail loads from API (`GET /api/email-templates/:key/`).
  6. Admin edits text fields (greeting, body, cta_text, subject) and toggles active/inactive.
  7. Admin clicks "Guardar Cambios" → `PUT /api/email-templates/:key/`.
  8. Success feedback displays.
- **Branches:**
  - [Branch A — Preview] Admin clicks "Vista previa" → `GET /api/email-templates/:key/preview/` → modal with rendered HTML iframe.
  - [Branch B — Reset] Admin clicks "Restaurar" → confirmation modal → `POST /api/email-templates/:key/reset/` → template reverts to defaults.
  - [Branch C — Disable] Admin toggles template off → emails of this type stop being sent.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-email-templates.spec.js`
- **Backend Tests:** `content/tests/views/test_email_template_views.py`

### FLOW: `admin-client-email-copy-settings`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/emails?tab=defaults`
- **Description:** El administrador abre **Emails → Configuración** y gestiona una lista de copias universales separada de los destinatarios de avisos internos. La pantalla declara que la copia es BCC, advierte que cada destinatario aumenta el volumen SMTP y de bandeja, avisa que Seguridad incluye OTP/credenciales cuyo cuerpo pueden consultar los administradores, y permite segmentar cada dirección en ocho familias: Propuestas, Diagnósticos, Documentos y comunicaciones, Cuentas de cobro, Contabilidad, Plataforma, Tareas y operación y Seguridad y acceso.
- **Interacciones y outcomes:**
  1. **display:** navegar desde el panel, abrir Configuración y ver dirección, estado, ocho familias, modo BCC y advertencias de volumen/seguridad con los datos reales de la respuesta.
  2. **success:** agregar una dirección, cambiar sus familias, pausarla/reactivarla o eliminarla; cada acción persiste por su endpoint propio y actualiza la fila.
  3. **error:** intentar agregar un duplicado o guardar una selección inválida muestra el detalle de validación del backend.
  4. **failure:** un fallo 5xx al mutar conserva el estado anterior y muestra que la operación no se completó.
- **E2E Spec:** `e2e/admin/admin-client-email-copy-settings.spec.js`

### FLOW: `admin-client-email-copy-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/emails?tab=history`.
- **Description:** El administrador expande cualquier envío principal y ve debajo la lista **Copias internas (BCC)**. Cada intento muestra dirección y estado enviado/fallido/omitido; los fallos enseñan el error SMTP y los omitidos explican la deduplicación, sin convertirlos en otra fila principal ni habilitar reintento.
- **Interacciones y outcomes:**
  1. **display:** navegar al historial, expandir un envío con datos reales y comprobar destinatarios BCC, estado, error independiente y omisión por duplicado.
  2. **success:** n/a; consultar la traza no muta datos.
  3. **error:** n/a; no hay entrada de usuario que validar en este bloque de lectura.
  4. **failure:** n/a como acción del usuario; el fallo SMTP de la copia es precisamente el dato persistido que cubre el outcome `display`.
- **E2E Spec:** `e2e/admin/admin-client-email-copy-settings.spec.js`

### FLOW: `admin-client-communications`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/communications`
- **API:** `GET/POST /api/communications/threads/`, `POST /api/communications/threads/tab-counts/`, `GET /api/communications/threads/:id/`, `POST /api/communications/threads/:id/messages/`, `GET/PATCH /api/accounts/panel-preferences/communications/`, `POST /api/accounts/panel-preferences/communications/reset/`, `/api/accounts/saved-filter-tabs/`, `POST /api/accounts/saved-filter-tabs/reset/`
- **Description:** El administrador abre «Configuraciones» junto a «Nuevo hilo» y administra preferencias personales de navegación, orden, paginación, canal inicial, ayuda y ancho, persistidas por cuenta entre dispositivos. La navegación enumera todos los proyectos aunque tengan cero hilos, conserva PRUEBA entre los activos y ubica Candle en «Proyectos archivados» por su ciclo. También identifica y busca varios hilos mediante resúmenes compactos de título y metadata, sin contenido del mensaje ni desplazamiento horizontal, navega por proyecto, cliente o «Sin proyecto», aplica filtros prediseñados con conteos completos, combina criterios y guarda recortes propios diferenciados. La tira se puede restablecer sin borrar las vistas propias; el contenido completo permanece en el detalle modal y cada hilo conserva mensajes entrantes o salientes con canal, fecha, estado y documentos referenciados.
- **Steps:**
  1. El administrador entra a Comunicaciones desde el panel y navega por proyectos o clientes en un panel ajustable, con conteos que incluyen sus hilos.
  2. Encuentra «Configuraciones» inmediatamente al lado de «Nuevo hilo» y abre una pantalla interna que sustituye temporalmente el listado sin perder su contexto.
  3. Define navegación inicial, orden, hilos por página, ancho lateral, canal inicial y visibilidad de la ayuda; guarda sólo los cambios y los recupera al volver, incluso desde otro dispositivo.
  4. Puede descartar cambios pendientes, restablecer las preferencias personales o restablecer las pestañas de fábrica sin eliminar sus vistas propias.
  5. Identifica cada hilo por asunto, cliente, proyecto, canal, estado, cantidad, fecha y borradores; el cuerpo de los mensajes no aparece en el índice.
  6. Cambia entre recientes, antiguos o alfabético y recupera el criterio activo al volver al listado; una URL o vista guardada explícita conserva prioridad.
  7. Elige «Sin proyecto» cuando necesita consultar conversaciones todavía no asociadas a uno y busca por cliente, proyecto, asunto o contenido.
  8. Elige de un clic un recorte prediseñado —primero «Borradores pendientes»— y consulta su conteo aunque sea cero; «Enviados sin respuesta» limita el resultado a hilos abiertos con salidas enviadas todavía no respondidas.
  9. Combina varios valores dentro de un filtro, guarda el recorte con nombre como vista propia y reordena la tira según su uso.
  10. Ajusta el ancho de la navegación para leer nombres largos y recupera ese ancho en otra visita.
  11. Selecciona un hilo; el detalle se abre sobre la lista y muestra la línea de tiempo, sus estados y documentos referenciados.
  12. Cierra el aviso del registro manual y puede reabrirlo desde la ayuda contextual.
  13. Escribe o pega el texto exacto y registra una salida como borrador o enviada, o una entrada como recibida; los mensajes nuevos parten del canal personal y las respuestas conservan el canal original.
  14. Cierra el detalle o vuelve atrás y recupera el mismo contexto de navegación y filtros.
- **Branches:**
  - [Branch A — Display] La navegación muestra el catálogo completo de proyectos y clientes, incluidos proyectos con conteo cero, PRUEBA activo, Candle archivado y «Sin proyecto»; el modal presenta juntos lo enviado, lo recibido y los documentos referenciados.
  - [Branch B — Resumen compacto] En viewport angosto aparecen varias tarjetas identificables sólo por el título y la metadata operativa, sin contenido del mensaje ni desplazamiento horizontal interno.
  - [Branch C — Orden persistente] El criterio elegido se guarda en la cuenta, queda activo y vuelve a aplicarse en una visita posterior sin parámetro explícito en la URL.
  - [Branch D — Conteos prediseñados] Todos los filtros de fábrica muestran su conteo, incluido cero.
  - [Branch E — Sin respuesta] El recorte aplica estado abierto, salida enviada y ausencia de respuesta.
  - [Branch F — Configuración y restablecimiento] La acción adyacente a «Nuevo hilo» abre la pantalla interna y permite restaurar preferencias o prediseñados sin borrar ni alterar las vistas propias.
  - [Branch G — Recorte guardado] La selección por cliente y los estados múltiples se guardan y restauran como una vista identificada como «Propia».
  - [Branch H — Búsqueda] La consulta global encuentra por cliente, proyecto, asunto o contenido sin perder el alcance activo.
  - [Branch I — Alcance de canal] El cierre del aviso se guarda en la cuenta al recargar y puede reabrirse desde ayuda.
  - [Branch J — Navegación ajustable] El panel lateral guarda el ancho elegido en la cuenta y permite leer nombres largos.
  - [Branch K — Preferencias personales] Canal y paginación se guardan explícitamente, sobreviven otra visita y el canal elegido inicia el siguiente mensaje nuevo.
  - [Branch L — Registro exitoso] Un mensaje saliente queda con estado `sent`, canal preferido y fecha explícita.
  - [Branch M — Error de negocio] La API rechaza el registro y el panel conserva el texto, mostrando la razón.
  - [Branch N — Fallo de carga] El listado no está disponible y el panel mantiene un reintento visible.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-client-communications.spec.js`
- **Unit Tests:** `test/components/CommunicationSettingsPanel.spec.js`, `test/components/CommunicationThreadTable.spec.js`, `test/composables/useCommunicationFilters.spec.js`, `test/composables/useCommunicationPanelWidth.spec.js`, `test/stores/communicationPreferences.test.js`, `test/stores/communications.test.js`
- **Backend Tests:** `accounts/tests/test_communication_panel_preferences.py`, `content/tests/views/test_communication_views.py`, `content/tests/views/test_communication_filters.py`

- **Lectura e identificación (2026-09-25):** buscar `#ID` exacto o número junto al texto; IDs visibles en lista, hilo, mensajes y documentos vinculados. Ir al inicio/final desplaza sólo el histórico. La redacción empieza plegada con mensajes existentes; Responder/Editar borrador la abre. Detalles del mensaje y formulario conservan valores al plegarse. Copiar es un icono directo; Marcar enviado vive en Más.

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
  5. Admin searches clients by name, email, or company.
  6. Admin expands a client row to view individual proposals (lazy-loaded via `GET /api/proposals/client-profiles/:id/`).
  7. Pressing the global panel refresh button invalidates the per-client detail cache and refetches expanded rows, so renamed/reassigned proposals show up.
- **Coverage:** ⚠️ Partial
- **E2E Spec:** `e2e/admin/admin-mini-crm-clients.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py`
- **Known gaps:** No E2E asserts that the refresh button re-fetches an already-expanded client's proposals (the cache-invalidation fix for stale rename/reassignment); see also `admin-proposal-delete-from-client`.

### FLOW: `admin-client-create-standalone`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Create a new client profile standalone (without a proposal) from the clients page via the "+ Nuevo cliente" modal. Email is optional — if omitted the backend generates a placeholder `cliente_<id>@temp.example.com` and the client shows a placeholder badge.
- **Steps:**
  1. Admin clicks "+ Nuevo cliente" button (data-testid: `clients-new-button`).
  2. Modal opens with name, email, phone, company fields.
  3. Admin fills the form (email is optional).
  4. Admin clicks "Crear cliente" (data-testid: `clients-new-submit`).
  5. API call to `POST /api/proposals/client-profiles/create/` — backend calls `proposal_client_service.get_or_create_client_for_proposal`.
  6. New client appears at the top of the list (store prepends it).
- **Branches:**
  - [Branch A — With email] Client created with real email, no badge.
  - [Branch B — Without email] Backend generates `cliente_<id>@temp.example.com`; client row shows 📧 placeholder badge.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-mini-crm-clients.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py::TestCreateProposalClient`

### FLOW: `admin-client-delete-orphan`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Delete an orphan client (zero proposals, platform projects, diagnostics, accounting incomes and hostings — the five-block guard) via the trash icon that appears only on orphan rows. A confirm modal prevents accidental deletion.
- **Steps:**
  1. Admin navigates to `/panel/clients/` (or switches to Huérfanos tab).
  2. Orphan client rows show a trash icon (data-testid: `client-delete-<id>`).
  3. Admin clicks the trash icon.
  4. ConfirmModal appears with warning text.
  5. Admin confirms → `DELETE /api/proposals/client-profiles/:id/delete/`.
  6. Client row is removed from the list (store filters it out client-side).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-mini-crm-clients.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py::TestDeleteProposalClient`, `content/tests/views/test_proposal_clients_views.py::TestOrphanFlagTransitionsAfterProposalDelete`

### FLOW: `admin-client-delete-protected`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Active clients (those with linked proposals or platform projects) do NOT show the delete trash icon. The backend also enforces this with a 400 + `client_has_proposals` / `client_has_projects` error code if the API is called directly.
- **Steps:**
  1. Admin navigates to `/panel/clients/`.
  2. Clients with `is_orphan: false` render WITHOUT a trash icon.
  3. Attempting DELETE via API returns `400 { error: 'client_has_proposals', count: N }`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-mini-crm-clients.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py::TestDeleteProposalClient::test_delete_with_proposals_returns_400_with_error_code`

### FLOW: `admin-client-archived-tab`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Archive a client (sets `UserProfile.archived_at` and `archived_by`) from the row toggle, and browse archived clients under the "Archivados" option of the transversal client-status selector (next to the search box since the Ago 2026 filter reorganisation, labelled with its own match count). "Archivado" is the entity-lifecycle word shared with projects, whose non-active bucket the panel already labels the same way; the per-item switches in Documentos and Comunicaciones say "Ver documentos archivados" / "Ver comunicaciones archivadas" so the two senses never collide. Archived clients are hidden from Todos/Activos/Huérfanos (backend default excludes `archived_at IS NOT NULL`); Archivados sends `?archived=true`, and the pre-rename `?inactive=` spelling is still accepted so bookmarked URLs keep working. Archiving is independent from `auth.User.is_active`, which is a separate axis owned by `/platform/clients`.
- **Steps:**
  1. Admin navigates to `/panel/clients/`.
  2. Admin clicks the archive icon (data-testid: `client-toggle-archived-<id>`) on an active client, or flips "Archivado" in the edit modal (`clients-edit-archived`). Both open the same modal (`client-archive-modal`); the identity `PATCH` refuses `is_archived` with `client_archive_transition_required`, so there is no shortcut past it.
  3. `GET /api/proposals/client-profiles/:id/archive-preview/` names the projects the cascade will move to "Suspendido" and what it costs (`client-archive-impact`): future incomes cancelled, future hosting charges archived, and that reactivating does not undo it. Confirm stays disabled until the impact is on screen.
  4. `POST /api/proposals/client-profiles/:id/archive/` echoes one `impact_token` per project; the backend answers 409 `projects_changed` if the set moved since the preview. Success toast shows; the row leaves the current status on reload.
  5. Admin picks "Archivados" in the status selector (data-testid: `clients-status-archived`) — list reloads with `?archived=true`, the URL gains `?status=archived` and rows show the "Archivado" badge.
  6. Clicking the icon again opens the same modal, which states that the projects stay suspended, and `POST .../unarchive/` clears `archived_at`/`archived_by` while leaving them alone.
- **Coverage:** ✅ Covered — status filtering, the archive preview with its impact copy, and the unarchive branch with its "projects stay suspended" warning are asserted (2026-08-15; vocabulary renamed and cascade added 2026-08-31).
- **E2E Spec:** `e2e/admin/admin-clients-archived-tab.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py::TestArchivedClients`, `content/tests/views/test_client_archive_views.py`, `accounts/tests/test_client_archive_service.py`

### FLOW: `admin-clients-filter-presets`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`, `/panel/accounting/hostings/`
- **Description:** Read the client list **by business module** instead of a flat strip of filters (Ago 2026 reorganisation). **Level 1** is the module — Todos, Propuestas, **Diagnóstico**, Proyectos, **Hosting** (its own module, not a corner of Contabilidad: it is a service line with a life of its own and its subfilters grow with PA-51), Contabilidad and **Documentos** (the documento→cliente/proyecto association turned into level-1 cuts, Ago 2026). Picking one does **not** narrow the list; it decides which subfilters level 2 offers, which is precisely what lets a module hold both a cut and its complement ("Con hosting cobrado" next to "Sin hosting"). **Level 2** holds the sixteen subfilters: the seven proposal-status cuts (Draft, Sent/Viewed, Negociación, Accepted, Expired, Rejected, Finished — code-level entries since migration 0049 dropped the seeded `SavedFilterTab` rows, freeing the twelve saved-tab slots for the admin's own), **Con proyecto activo** / **Sin proyecto**, **Con hosting cobrado** (≥1 hosting with `is_active`, the very flag the client card renders as "Vigente", so the number reconciles with the Hostings tab) / **Con hosting (histórico)** / **Sin hosting**, **Sin datos de facturación** (no `nit`, `cedula` nor `billing_code` — `billing_code` is stored NULL, the other two `''`), and the four Documentos cuts — **Con documentos** / **Sin documentos** / **Con documentos sin proyecto** (the review list the retroactive folder pass leaves behind) / **Con carpeta** (Ago 2026), reading `documents_count` / `documents_no_project_count` / `document_folders_count` computed over ACTIVE rows. Los tres primeros cuentan documentos vía `Document.client_user`; el cuarto cuenta la relación de la CARPETA (`DocumentFolder.client_user`), no las carpetas donde el cliente tiene documentos: una carpeta suya sin nada adentro todavía dice de quién es. Every subfilter carries its match count **in parentheses, always shown, `(0)` included**, computed over the loaded rows after the status and search cuts so the number equals what pressing it returns. The hosting and project cuts ride the formal PA-25 FK via `active_hostings_count` / `active_projects_count`, annotated as `Subquery` aggregates — never text or project names. A subfilter is a set of values of the **filter panel's own controls**, not an opaque predicate: so each one can equally be rebuilt from the panel, combined with the others and with the panel's advanced filters, saved as a named tab under its module, and removed by its chip — which drops the tab highlight with it, because tab, chip and panel are three views of one state. Chips name the module they come from. Whatever does not fit the row moves into a "Más" menu instead of being clipped. The **client status** (Todos/Activos/Huérfanos/Inactivos) is transversal: next to the search box, with its own server-computed counts, mirrored in `?status=` and combinable with any module. Selecting a subfilter stamps `?clientTab=<id>` and `?clientModule=<module>` (shareable, survives reload); pressing it again clears the cut but stays in the module. Deactivated clients stay out by default even holding live hostings (the endpoint hides them; "Inactivos" remains an explicit opt-in). While the Hosting module is being read every row shows its hosting count, which for superusers doubles as the jump into `/panel/accounting/hostings?client=<id>` — landing there already filtered. While **Documentos** is active the row pill shows `<N> docs · <fecha del último>` (data-testid `client-documents-<id>`, no superuser gate — documents shares this page's admin gate) and jumps into `/panel/documents?client=<id>`. La píldora sigue al **corte**, no sólo al módulo: leyendo «Con carpeta» el número que importa es cuántas carpetas tiene, así que muestra `<N> carpetas` (data-testid `client-folders-<id>`) sin la fecha —que no dice nada de una carpeta vacía que sí es suya— y salta al mismo lugar. **(Ago 2026)** Two more modules join that row. **Diagnóstico** reads two sources on purpose: *Con diagnóstico facturado* reads the income (`origin=diagnostic`, write-offs excluded) so a diagnostic billed without its `WebAppDiagnostic` ever being created is not hidden, while *Sin diagnóstico* and *Diagnóstico sin propuesta posterior* read the entity — the latter anchored on `Coalesce(initial_sent_at, created_at)`, because a proposal written while the diagnostic still sat in draft cannot be its outcome, and expressed as a `~Exists` rather than a `NOT IN` because `BusinessProposal.client` is nullable. **Emails** is the transversal one, riding the `EmailLog.client`/`audience` pair this ticket materialised: its four cuts count only what was addressed to the client, so *Sin contacto en los últimos 30 días* deliberately includes whoever never received anything, the same way *Con hosting cobrado* sits inside *Con hosting (histórico)*.
- **Responsive contract:** En 412 px y 835 px sólo búsqueda + resumen de filtros preceden al primer cliente; estado, módulo, subfiltro, filtros avanzados y configuración viven en un único drawer. La fila se vuelve ficha apilada con identidad, datos, conteos, contexto y menú táctil; los detalles expandidos se convierten en tarjetas rotuladas y mover propuestas/diagnósticos tiene una alternativa explícita al drag. Desde 1195 px regresan los dos niveles visibles. El ancho máximo en 2560 px es 1400 px.
- **Steps:**
  1. Admin navigates to `/panel/clients/`; the full list renders and the module row (data-testid: `clients-module-<id>`) offers the eight business modules.
  2. Admin picks a module — the list does **not** change; level 2 swaps to that module's subfilters, each showing its count in parentheses.
  3. Admin clicks a subfilter (data-testid: `filter-tabs-tab-hosting-charged`) — the list narrows client-side and the URL gains `?clientTab=hosting-charged&clientModule=hosting`.
  4. Typing in the search box (data-testid: `clients-search-input`) refetches server-side and the subfilter keeps narrowing the result; neither annuls the other. The status selector likewise combines instead of replacing.
  5. Opening the filter panel (data-testid: `clients-filter-toggle`) shows the cut as a module-prefixed chip; removing it (data-testid: `client-filter-chip-hostingStatus`) restores the full list and un-highlights the tab, leaving any other cut applied. The same control can rebuild the cut from scratch.
  6. Clicking the applied subfilter again clears it: full list, `?clientTab` gone, still in the module.
  7. While the Hosting module is being read, the row pill (data-testid: `client-hostings-<id>`) navigates to `/panel/accounting/hostings?client=<id>`, which seeds the client multi-select on arrival. Non-superusers see the count as plain text (accounting is superuser-only).
  8. While the Documentos module is being read, the row pill (data-testid: `client-documents-<id>`) shows `<N> docs · <fecha del último>` and navigates to `/panel/documents?client=<id>`, landing on the manager with the client axis already applied.
  9. Under the Diagnóstico module, `filter-tabs-tab-diagnostic-unconverted` lists the clients whose diagnostic no proposal ever followed — the cut that had no way of being asked for before.
  10. Under Emails, the row pill (data-testid: `client-emails-<id>`) shows how many emails went out and the date of the last one, and opens the history modal (data-testid: `client-emails-modal`); the same modal opens from the `client-view-emails-<id>` button on the expanded ficha, without going through the filter.
  11. Inside the modal a segmented control (data-testid: `client-emails-audience`) switches between **Al cliente** and **Internos**, refetching per group because the endpoint paginates; the eye opens the message as delivered and a failed row can be retried, with proposal rows carrying their own blocked reason instead of the digests'.
- **Coverage:** ✅ Covered — module grouping without narrowing, counts before applying (including `(0)`), narrowing + URL stamp, toggle-off, chip removal dropping the tab, rebuilding a predefined filter from the panel, shared-link restore, search composition, the transversal status, the pre-filtered handoff into Hostings, the Documentos subfilter counts and the pre-filtered handoff into Documents are all asserted (2026-08-16); los tres cortes de Diagnóstico, los cuatro de Emails, el pill de contacto de la fila y el modal con sus dos grupos también (2026-08-16). El display responsivo está cubierto en los cinco anchos reales (2026-08-22).
- **E2E Specs:** `e2e/admin/admin-clients-filter-presets.spec.js`, `e2e/admin/admin-responsive-documents-clients-projects.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py::TestPresetAnnotations`, `content/tests/views/test_proposal_clients_views.py::TestDocumentsModuleAnnotations`, `content/tests/views/test_proposal_clients_views.py::TestClientStatusCounts`, `accounts/tests/test_seed_filter_tabs.py::TestDropClientStatusTabsMigration`

### FLOW: `admin-clients-documents-section`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`, `/panel/documents`
- **Description:** The expanded client row (ficha) lists the client's **five most recent active documents** — title linking into `/panel/documents/:id/edit`, project, status and created date (data-testid `client-document-row-<id>`) — fed by the `documents` + `documents_total` keys the detail endpoint nests next to proposals/projects/hostings/incomes. "Ver todos (N)" (data-testid `client-documents-all-<id>`) jumps into `/panel/documents?client=<profileId>`: a client's documents are reachable from their ficha without touching the filters. The relation also works backwards — the document editor's "Ver cliente" link lands here with `?highlight=<profileId>`, a single-use param that expands that client's ficha and scrolls to the row (mirror of `/panel/projects?highlight=`), degrading silently if the client is not among the loaded rows.
- **Steps:**
  1. Admin expands a client row in `/panel/clients` → the ficha loads the detail payload.
  2. The "Documentos" section renders the last 5 documents with project, status and date; half-linked ones show a dash in Proyecto.
  3. Clicking a document title opens `/panel/documents/:id/edit`.
  4. Clicking "Ver todos (N)" opens `/panel/documents?client=<id>` with the association filter seeded.
- **Branches:**
  - [Branch A — Sin documentos] A client with no active documents renders no section (the ficha stays as before).
  - [Branch B — highlight] Arriving with `?highlight=<profileId>` expands that ficha, scrolls to the row and strips the param from the URL.
- **Coverage:** ✅ Covered — section rows with project + editor link, and the pre-filtered "Ver todos" handoff (2026-08-16).
- **E2E Spec:** `e2e/admin/admin-clients-documents-section.spec.js`
- **Backend Tests:** `content/tests/views/test_proposal_clients_views.py::TestDocumentsModuleAnnotations`

### FLOW: `admin-client-drag-reassign`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Reassign a proposal or diagnostic to a different client by dragging its row (from an expanded client card) and dropping it on another client's card header, or on the matching zone of another expanded client: proposals on the proposals zone, diagnostics on the diagnostics zone (zones are type-matched — a zone of the other type ignores the drop; the header accepts both types). Native HTML5 DnD; every drop target highlights on hover. The drop PATCHes `client_id` on the item's update endpoint, then refreshes both affected clients + the list silently and in place (no loading skeleton — the page does not visually "reload"), and shows a success toast with a "Deshacer" action (reverse PATCH). Diagnostics also rebuild their client snapshot (`sync_diagnostic_snapshot`). Touch devices are not supported — fallback is the client picker on the edit pages.
- **Steps:**
  1. Admin expands a client card to reveal its proposals/diagnostics tables.
  2. Admin drags a row (data-testid: `client-proposal-row-<id>` / `client-diagnostic-row-<id>`).
  3. Hovering another client header (data-testid: `client-header-<id>`) highlights it; on an expanded client, the matching zone (data-testid: `client-proposals-zone-<id>` / `client-diagnostics-zone-<id>`) also highlights and accepts the drop. Dropping on the source client, or on a zone of the other item type, is a no-op.
  4. Drop → `PATCH /api/proposals/:id/update/` or `PATCH /api/diagnostics/:id/update/` with `{client_id}`.
  5. Both clients' expanded details refetch and overwrite in place, and the list refreshes silently (`fetchClients({silent:true})`, no skeleton) respecting the active tab; the toast offers "Deshacer".
- **Coverage:** ✅ Covered — proposal/diagnostic drops on headers and zones, same-client and type-mismatch no-ops, and the "Deshacer" toast action reassigning the item back to its source client (2026-07-23).
- **E2E Spec:** `e2e/admin/admin-clients-drag-reassign.spec.js`
- **Backend Tests:** `content/tests/views/test_diagnostic_views_gaps.py::test_update_diagnostic_with_client_id_reassigns_and_resyncs_snapshot`, `content/tests/views/test_proposal_clients_views.py::TestProposalCreateWithClientId::test_proposal_update_with_client_id_switches_profile_and_resyncs_snapshot`

### FLOW: `admin-proposal-send`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/`, `/panel/proposals/:id/edit`
- **Description:** Send a proposal to a client via email. The canonical **Correos** tab is available while the proposal is still a draft and owns the editable plain-text personalized message (`BusinessProposal.email_intro`). The message explains the client's problem, how this proposal solves it, and the expected business outcome. A draft may save it empty, but every send is blocked until it contains text. The delivered email keeps the predefined body and inserts the message immediately after it, before payment/timeline/commercial blocks; the commercial PDF is attached automatically. Editing the proposal later does not rewrite historical email snapshots.
- **Steps:**
  1. Admin views the proposal edit page or the actions modal in the list page.
  2. Admin opens **Correos**, writes or adjusts the message, previews it if desired, and clicks "Guardar mensaje". The tab saves only `{ email_intro }`; it does not overwrite unsaved changes in other tabs.
  3. Admin clicks "Enviar al Cliente".
  4. The scorecard checks client data, commercial readiness, and a nonblank personalized message. A missing message appears as a blocker with "Completar en Correos"; no send request is made.
  5. Once all checks pass, admin confirms → `POST /api/proposals/:id/send/`.
  6. Backend validates the message again before snapshots or state changes, changes status to `sent`, renders predefined body → personalized message → commercial blocks, attaches the PDF, sends, and returns `email_delivery`.
  7. `email_delivery.ok=true` shows "Propuesta enviada al cliente"; a delivery failure shows its detail/reason instead of false success.
- **Branches:**
  - [Error — Missing message] The scorecard and backend return the `missing_email_intro` blocker before any send side effect.
  - [Failure — Delivery] SMTP/template failure leaves an explicit warning even if the proposal state was advanced.
  - [Display — History] The exact sent body is stored in the delivery snapshot and remains immutable after later edits.
- **Coverage:** ✅ Covered — independent Correos save, missing-message blocker, successful send and delivery-failure feedback are E2E-covered; ordering, backend atomicity, PDF metadata and immutable snapshots are pytest-covered.
- **E2E Spec:** `e2e/admin/admin-proposal-send.spec.js`

### FLOW: `admin-proposal-multi-send`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Send one email containing 2–10 same-client proposals. The modal groups eligible proposals by status and requires a nonblank personalized message on every selected item. Missing items show "Falta mensaje" plus a link to that proposal's **Correos** tab; an aggregate warning disables the send. The email renders each proposal as a numbered phase with that proposal's own `email_intro` and PDF. Backend prevalidates the complete set before any snapshot or state transition.
- **Steps:**
  1. Admin opens `/panel/proposals/:id/edit` for a client that has another eligible proposal.
  2. Admin clicks the lightning-bolt button next to "Guardar cambios".
  3. `ProposalActionsModal` opens; admin clicks "Enviar varias propuestas como un solo correo" (`data-testid=proposal-action-send-multi`).
  4. `ProposalMultiSendModal` opens, listing the client's other proposals grouped by status. The current proposal is pre-checked and locked.
  5. Admin selects one or more additional proposals. If any selected item lacks a message, the modal identifies it and keeps the action disabled.
  6. With 2–10 valid selections, admin clicks send → `POST /api/proposals/:id/send-multi/` with `proposal_ids`.
  7. Backend validates same client, count, and every message before side effects; then it renders each phase's message, attaches N PDFs, and applies draft→sent, expired→reopen, or resend timer transitions.
  8. Modal closes on success and shows "Correo enviado al cliente con N propuestas." A server failure keeps the modal open with an error.
- **Coverage:** ✅ Covered — success, missing-message validation, and server failure are E2E-covered; per-phase rendering and all-or-nothing validation are pytest-covered.
- **E2E Spec:** `e2e/admin/admin-proposal-multi-send.spec.js`

### FLOW: `admin-proposal-resend`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`, `/panel/proposals/:id/edit`
- **Description:** Resend an already-sent proposal with its saved personalized message. The resend modal preloads `email_intro` and allows editing it. A nonblank message is mandatory; "Guardar y re-enviar" persists the edit, creates an audit entry, keeps `expires_at`, resets send/reminder timers, and dispatches the email again. The new delivery gets the new text while previous delivery snapshots remain immutable.
- **Steps:**
  1. Admin opens the actions modal for a proposal whose status is `sent`/`viewed`.
  2. Admin clicks "Re-enviar".
  3. The editor opens with the previously saved message. Admin may add or remove content.
  4. If the result is blank, the action remains disabled and no request is made.
  5. Admin clicks "Guardar y re-enviar" → `POST /api/proposals/:id/resend/` with `{ email_intro }`.
  6. Backend validates before persistence/side effects, saves the changed message, resets timers, and re-sends.
  7. Success toast says "Propuesta re-enviada al cliente"; delivery failure keeps the editor available and surfaces `email_delivery.detail || email_delivery.reason`.
- **Coverage:** ✅ Covered — retained-message preload/edit payload, blank-message error, success and email-delivery failure are E2E-covered; persistence, audit log, no-side-effect validation and historical immutability are pytest-covered.
- **E2E Spec:** `e2e/admin/admin-proposal-resend.spec.js`

### FLOW: `admin-proposal-reopen-from-expired`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (General tab — date picker, and JSON re-import panel)
- **Description:** Recover an `expired` proposal by extending `expires_at` to a future date. The validator no longer blocks re-saving when the date is left unchanged, so admins can fix any other field on an expired proposal; when the date does move into the future, `ProposalService.reopen_if_unexpired` auto-reverts `status` from `expired` to `viewed` (when `view_count > 0`) or `sent`, and logs an "Auto-reopened from expired…" entry in `ProposalChangeLog`. Same behavior on both update paths (form PATCH and JSON re-import PUT).
- **Steps:**
  1. Admin opens an expired proposal at `/panel/proposals/:id/edit`. The status badge reads "Expirada".
  2. Admin moves the `expires_at` datetime input to a future date (or pastes a JSON with a future `expires_at` in the JSON re-import panel).
  3. Admin clicks Save.
  4. PATCH `/api/proposals/:id/update/` (form) or PUT `/api/proposals/:id/update-from-json/` (JSON path).
  5. Backend persists `expires_at` and `status` in a single save; `ProposalChangeLog` records the auto-reopen.
  6. UI refreshes — the status badge no longer shows "Expirada"; the proposal returns to `sent`/`viewed`.
- **Branches:**
  - [Branch A — form path] PATCH `/update/`. Status reverts to `viewed` if `view_count > 0`, else `sent`.
  - [Branch B — JSON path] PUT `/update-from-json/`. Same reopen logic; `ProposalFromJSONSerializer` reads the bound proposal via `context={'proposal': proposal}` to skip the future-only check when `expires_at` is unchanged.
  - [Branch C — keep `expires_at` unchanged] Admin edits other fields on an expired proposal without touching the date. Save succeeds (no longer blocked by validator); `status` stays `expired`.
- **Coverage:** ✅ Covered (JSON path + the General-tab PATCH `/update/` reopen with the header status reverting from expired; asserted 2026-07-23)
- **E2E Spec:** `e2e/admin/admin-proposal-reopen-from-expired.spec.js`

### FLOW: `admin-proposal-update-from-json`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (JSON re-import panel)
- **Description:** Re-import a complete JSON payload over an existing proposal — distinct from `admin-proposal-create-from-json` which creates a new proposal. The admin pastes/uploads JSON in the edit screen; the store calls `PUT /api/proposals/:id/update-from-json/` which replaces metadata and each known section's `content_json`. Unrecognized section keys come back as a `warnings` array; sections not present in the payload are left unchanged.
- **Steps:**
  1. Admin opens `/panel/proposals/:id/edit` and switches to the JSON re-import panel.
  2. Admin pastes (or uploads) a JSON payload that follows the `create-from-json` template shape.
  3. Admin clicks "Actualizar desde JSON".
  4. Frontend store calls `proposalStore.updateProposalFromJSON(id, payload)` → `PUT /api/proposals/:id/update-from-json/`.
  5. Backend validates via `ProposalFromJSONSerializer` (with the bound proposal in context, so an unchanged past `expires_at` is allowed), updates metadata fields, replaces section `content_json` for matching keys, and logs each changed field.
  6. Success toast "Propuesta actualizada desde JSON."; if the JSON contained unmapped section keys, the response includes a `warnings` array which the UI surfaces.
- **Branches:**
  - [Branch A — happy path] Valid JSON → 200 with refreshed proposal payload.
  - [Branch B — unknown section keys] Payload includes unrecognized keys → 200 + `warnings` listing them.
  - [Branch C — invalid `expires_at`] New value in the past → 400 from `validate_expires_at` (unless the value matches the proposal's stored `expires_at`).
- **Coverage:** ✅ Covered (happy path, unknown keys riding the PUT with a 200+warnings response, and the keep-expires_at-on-expired branch; asserted 2026-07-23). Note: the API's `warnings` array is pytest-covered but not currently surfaced by the JSON tab UI.
- **E2E Spec:** `e2e/admin/admin-proposal-update-from-json.spec.js`

### FLOW: `admin-proposal-prompt`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/:id/edit` (Prompt tab)
- **Description:** Admin copies, edits, downloads and resets the commercial and technical proposal-generation prompts from the Prompt tab (`ProposalPromptTab.vue`, localStorage-persisted via `useSellerPrompt`/`useTechnicalPrompt`). Parallel of `admin-diagnostic-prompt`.
- **Steps:**
  1. Admin opens a proposal's edit page and switches to the Prompt tab.
  2. Admin copies, edits, downloads or resets either prompt.
- **Coverage:** ❌ Missing
- **E2E Spec:** — (suggested: `e2e/admin/admin-proposal-prompt.spec.js`)

### FLOW: `admin-proposal-dev-checklist`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/:id/edit` (Desarrollo tab, accepted proposals only)
- **Description:** Admin generates, copies and downloads a Markdown developer checklist from the Desarrollo tab (`DevChecklistTab.vue`, client-side `buildDevChecklistMarkdown`). The tab only appears when the proposal status is `accepted`.
- **Steps:**
  1. Admin opens an accepted proposal's edit page; the Desarrollo tab is visible.
  2. Admin refreshes, copies or downloads the checklist markdown.
- **Coverage:** ❌ Missing
- **E2E Spec:** — (suggested: `e2e/admin/admin-proposal-dev-checklist.spec.js`)
- **E2E Spec (suggested):** `e2e/admin/admin-proposal-update-from-json.spec.js`

### FLOW: `admin-proposal-manual-alerts`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Create, view, and dismiss manual seller alerts/reminders for proposals. Auto-alerts now include: seller_inactive (🏷️ no follow-up >3d), zombie (💀 sent >7d, no views, no activity), late_return (🔄 client returned after ≥5d gap).
- **Steps:**
  1. Admin navigates to `/panel/proposals/`.
  2. Alerts panel shows auto-alerts (not_viewed, not_responded, expiring_soon, seller_inactive, zombie, late_return) merged with manual alerts from API (`GET /api/proposals/alerts/`).
  3. Each alert type has a distinct icon (👁️‍🗨️, ⏳, 🔥, 🏷️, 💀, 🔄).
  4. Admin clicks "+ Crear recordatorio" to open the create alert form.
  5. Admin selects a proposal, alert type (reminder/followup/call/meeting/custom), date, and message.
  6. Admin submits → API call to `POST /api/proposals/alerts/create/`.
  7. New alert appears in the panel with dismiss (✕) button.
  8. Admin clicks ✕ → API call to `PATCH /api/proposals/alerts/:id/dismiss/` → alert removed from list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-manual-alerts.spec.js`

### FLOW: `admin-proposal-win-rate-dashboard`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Dashboard displays win rate segmented by project type, market type, and combination. Backend computes accepted/(accepted+rejected+expired) per type.
- **Steps:**
  1. Admin opens the KPI Dashboard on the proposals page.
  2. Dashboard loads data from `GET /api/proposals/dashboard/` including `win_rate_by_project_type`, `win_rate_by_market_type`, `win_rate_by_combination`.
  3. Two side-by-side bar charts show win rates by project type and market type (best type highlighted).
  4. Combination table shows project×market cross-tab for combos with ≥2 proposals.
- **Coverage:** ✅ Covered — `frontend/e2e/admin/admin-proposal-win-rate.spec.js`

### FLOW: `admin-proposal-engagement-score`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Analytics tab)
- **Description:** ProposalAnalytics displays an engagement score (0-100) per proposal, computed from recent sessions, investment section time, unique stakeholders, response recency, and revisits.
- **Steps:**
  1. Admin opens the Analytics tab for a proposal.
  2. Analytics loads from `GET /api/proposals/:id/analytics/` including `engagement_score`.
  3. Engagement score card renders with color-coded level (green ≥70, yellow ≥40, red <40) and contextual recommendation text.
- **Coverage:** ✅ Covered — `frontend/e2e/admin/admin-proposal-analytics.spec.js`

### FLOW: `admin-proposal-metrics-manual`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/`
- **Description:** Floating "?" button opens a slide-over panel (MetricsManual component) with searchable definitions of all metrics: conversion rate, engagement score, heat score, time-to-first-view, win rate, zombie proposals, late returns, seller inactivity, etc.
- **Steps:**
  1. Admin clicks the floating "?" button (bottom-right corner).
  2. MetricsManual slide-over opens with search bar and 16 metric definitions.
  3. Admin types in search bar → results filter in real-time.
  4. Each metric shows name, description, calculation method, and recommended action.
  5. Admin clicks outside or ✕ to close.
- **Coverage:** ✅ Covered — `frontend/e2e/admin/admin-proposal-metrics-manual.spec.js`

### FLOW: `admin-proposal-batch-actions`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Admin selects multiple proposals via checkboxes and performs batch actions (re-send, expire, delete). A sticky action bar appears at the top when at least one proposal is selected. Includes a select-all checkbox in the table header.
- **Steps:**
  1. Admin navigates to `/panel/proposals/`.
  2. Admin clicks checkboxes on individual proposal rows (or the header checkbox to select all visible).
  3. Sticky batch action bar appears showing "{N} seleccionada(s)" with action buttons.
  4. Admin clicks a batch action (🔄 Re-enviar, ⏰ Expirar, or 🗑️ Eliminar).
  5. Confirmation dialog appears.
  6. Admin confirms → API call to `POST /api/proposals/bulk-action/` with `{ ids, action }`.
  7. On success, selection is cleared and proposal list refreshes.
- **Branches:**
  - [Branch A — Cancel] Admin clicks "Cancelar" → selection is cleared, action bar disappears.
  - [Branch B — Selected proposal deleted] (Ago 2026) La selección la posee `useRowSelection` y se reconcilia contra las propuestas cargadas: eliminar desde el menú de una fila seleccionada la descuenta de la barra —y sólo a ella— y la barra se va sola al quedar vacía. Antes era un `Set` en memoria que nadie revalidaba, el mismo defecto que tenía la barra de contabilidad.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-batch-actions.spec.js`

### FLOW: `admin-proposal-actions-modal`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals`, `/panel/proposals/:id/edit`, `/proposal/:uuid?preview=1`
- **API:** `GET /api/proposals/:uuid/` when the public preview tab loads; the modal itself renders from proposal data already loaded by the edit/list view.
- **Description:** Admin opens an actions modal from a proposal row or the proposal edit page. The modal exposes the available actions for that context; public preview opens the client-facing proposal in a new tab without recording engagement. Send/Resend visibility is conditional on proposal status.
- **Steps:**
  1. Admin is on the proposal listing `/panel/proposals`.
  2. Admin clicks the actions icon (⋮) on a proposal row.
  3. Actions modal opens with buttons: Edit, Preview, Send/Resend, Copy, WhatsApp, Duplicate, Toggle, Delete.
  4. [Branch A — Draft] "Send" action visible; "Resend" hidden.
  5. [Branch B — Sent/Viewed] "Resend" action visible; "Send" hidden.
  6. [Branch C — Public preview] Admin opens the edit-page actions modal and clicks "Vista previa pública".
  7. A new tab renders the proposal with the preview banner and without tracking the visit.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-actions-modal.spec.js`

### FLOW: `admin-proposal-engagement-decay-alert`

- **Module:** admin
- **Role:** system
- **Priority:** P2
- **Routes:** N/A (backend-triggered)
- **Description:** When a client views fewer sections in a session compared to their average from previous sessions (below 50% of the average), the system creates an `engagement_decay` ProposalAlert. The alert is rate-limited to one per 3 days per proposal. It appears in the alerts panel on the proposals list page.
- **Steps:**
  1. Client views a proposal and engagement data is sent via `POST /api/proposals/:uuid/track/`.
  2. Backend compares current session section count to the average of previous sessions.
  3. If current count < 50% of average, and no `engagement_decay` alert exists for the last 3 days, a new alert is created.
  4. Alert message includes section counts: "{clientName} vio {N} secciones vs promedio anterior de {avg}. Posible pérdida de interés."
  5. Alert appears in the admin proposals list alerts panel.
- **Coverage:** ⚠️ Backend-only
- **Backend Tests:** `content/tests/views/test_proposal_views.py`

### FLOW: `admin-proposal-post-rejection-revisit`

- **Module:** admin
- **Role:** system
- **Priority:** P2
- **Routes:** N/A (backend-triggered)
- **Description:** When a client revisits a proposal that was previously rejected, the system creates a `post_rejection_revisit` ProposalAlert. This signals potential reconsideration and appears in the admin alerts panel.
- **Steps:**
  1. Client opens a proposal URL where `status = 'rejected'`.
  2. Backend detects the rejected status in `retrieve_public_proposal`.
  3. A `post_rejection_revisit` ProposalAlert is created with message: "{clientName} revisitó la propuesta rechazada. Posible reconsideración."
  4. Alert appears in the admin proposals list alerts panel.
- **Coverage:** ⚠️ Backend-only
- **Backend Tests:** `content/tests/views/test_proposal_views.py`

### FLOW: `admin-proposal-json-import-warnings`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/create` (JSON import tab)
- **Description:** When importing a proposal from JSON, the backend validates the payload and returns warnings for any section keys that don't map to known section types. Warnings are non-blocking — the proposal is still created, but the admin is informed of unmapped keys that were ignored.
- **Steps:**
  1. Admin switches to "Importar JSON" tab on the create page.
  2. Admin pastes a JSON payload containing extra or misspelled section keys.
  3. Admin submits → API call to `POST /api/proposals/create-from-json/`.
  4. Backend validates with `ProposalFromJSONSerializer`, identifies unmapped keys.
  5. Proposal is created successfully with known sections populated.
  6. Response includes `warnings` array listing unmapped section keys.
  7. Frontend displays warnings to the admin.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-create.spec.js`

### FLOW: `proposal-welcome-back`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Returning client sees a welcome-back overlay with their name and last visited section. Progress is persisted in localStorage per proposal UUID.
- **Steps:**
  1. Client opens a proposal they've previously visited.
  2. On animation complete, the system checks `localStorage` for saved progress (`proposal-{uuid}-progress`).
  3. If progress exists (sectionIndex > 0), welcome-back overlay appears: "Bienvenido de nuevo, [name]. La última vez llegaste hasta [section]."
  4. Client clicks "Continuar donde lo dejé" → navigates to saved section.
  5. Client clicks "Empezar desde el inicio" → dismisses overlay.
  6. Onboarding tutorial is skipped for returning visitors.
- **Branches:**
  - [Branch A — First visit] No saved progress → normal onboarding flow.
  - [Branch B — Preview mode] Welcome-back is skipped in preview mode.
- **Coverage:** ✅ Covered — `frontend/e2e/proposal/proposal-welcome-back.spec.js`

### FLOW: `proposal-process-methodology`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** New "Proceso y Metodología" section with a 5-step visual pipeline (Discovery → Diseño → Desarrollo → QA → Lanzamiento). Horizontal on desktop, vertical timeline on mobile. Each step shows icon, title, description, and optional "Tu aporte" client action tag.
- **Steps:**
  1. Client navigates to the Process & Methodology section.
  2. Section renders with intro text and 5-step pipeline.
  3. Active steps are highlighted with green styling.
  4. Client action tags indicate what input the client provides at each stage.
- **Coverage:** ✅ Covered — `frontend/e2e/proposal/proposal-process-methodology.spec.js`

### FLOW: `proposal-value-added-modules`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The "Value Added Modules" section (`section_type: value_added_modules`) renders a card grid of included-free items. Each card is resolved from the proposal's `functional_requirements` groups using `module_ids`. Cards show module title, icon, justification text, and a "Gratis" badge. An optional `footer_note` appears below the grid. Falls back to "Incluido sin costo adicional" when no `title` is set in `content_json`. Each card may carry per-module conditions (`content_json.conditions[id]`): when the proposal's effective total is below the module minimum (in the proposal currency), a "Disponible en proyectos desde $X" badge is shown ("condicionado", the module is never hidden); a duration badge ("Disponible por N meses") and a discretionary note may also appear. A "Términos y condiciones" button, placed opposite "Ver detalle", opens a per-module terms modal (`ModuleTermsModal`) without triggering the card's detail modal.
- **Steps:**
  1. Client navigates to the Value Added Modules section.
  2. Section title and intro text render.
  3. Each module card resolves its title and icon from `functional_requirements.content_json.groups`.
  4. Each card shows the justification text from `content_json.justifications`.
  5. A "Gratis" badge appears on every card.
  6. Optional `footer_note` renders at the bottom of the section.
  7. [Optional] Clicking a card opens the shared requirements modal; items with linked technical requirements show the same nested "Ver requerimientos (N)" link as `proposal-functional-requirements-modal` (pass-through covered by `test/components/ValueAddedModules.test.js`).
  8. [Optional] When a module minimum is not met, the "Disponible en proyectos desde $X" badge renders; a duration badge renders when `duration_months` is set.
  9. [Optional] Clicking "Términos y condiciones" opens the `ModuleTermsModal` with the module terms, without opening the detail modal.
- **Coverage:** ✅ Covered — `frontend/e2e/proposal/proposal-value-added-modules.spec.js` (card grid, condition badges, and terms modal)
- **Known gaps:** The terms modal now renders `**bold**` via `renderInlineBold` (2026-07) but the spec's mock terms carry no `**` markers, so bold output is unasserted. The canonical card order (admin → manual → kpi_dashboard → analytics → ai_automation, 2026-07) is not asserted either.

### FLOW: `proposal-calculator-modules`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** Calculator modal displays core calculator modules in order: PWA (40%), AI (invite-only), Conversiones Inteligentes (invite-only), Facturación Electrónica (60%), Pasarela Internacional (20%), Pasarela Regional (20%), Email Marketing (10%), Reportes y Alertas (20%, selected by default), Multi-idioma (15%). An informational badge at the **top** of the modal explains items are optional. Selecting a calculator module **adds** ~1 week to the timeline.
- **Steps:**
  1. Client navigates to the Investment section and clicks "Personalizar tu inversión".
  2. Calculator modal opens with informational badge at the top.
  3. Modules appear in the specified order: PWA, AI, Smart Conversions, Electronic Invoicing, International Payments, Regional Payments, Email Marketing, Reports & Alerts, Multi-idioma.
  4. PWA module appears unselected by default, with price as +40% of total.
  5. AI module appears with "Agendar llamada" label instead of price and a purple creative invite note.
  6. Reports & Alerts module appears selected by default with price as +20% of total.
  7. Selecting a module adds ~1 week to estimated timeline; deselecting an investment module reduces ~1 week.
  8. Client confirms selection → modal closes, total updates on Investment section.
- **Branches:**
  - [Branch A — AI invite] Client selects AI module → invite note visible, no cost added.
  - [Branch B — FR integration] Selected calculator modules appear in Functional Requirements section.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-modules.spec.js`

### FLOW: `proposal-calculator-selected-first`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** When the calculator modal opens, groups containing pre-selected (`default_selected`) modules are sorted to the top so the client sees included modules first without scrolling.
- **Steps:**
  1. Client opens the proposal and navigates to the Investment section.
  2. Client clicks "Personalizar tu inversión".
  3. Calculator modal opens with selected module groups sorted to the top.
  4. Unselected module groups appear below.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-modules.spec.js`

### FLOW: `proposal-expired-graceful`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** When a client opens an expired proposal, the backend returns HTTP 410 Gone and creates a `post_expiration_visit` alert. The frontend renders a graceful `ProposalExpired` component with the client name, proposal title, a WhatsApp reactivation CTA, and an email contact option.
- **Steps:**
  1. Client opens a proposal URL where `expires_at` is in the past.
  2. API call to `GET /api/proposals/:uuid/` returns HTTP 410 with partial proposal data.
  3. Backend creates a `post_expiration_visit` ProposalAlert for the seller.
  4. Frontend detects 410 status and sets `loadError = 'expired'`.
  5. `ProposalExpired` component renders with personalized message: "{clientName}, esta propuesta ha expirado".
  6. WhatsApp reactivation button pre-fills a message mentioning the proposal title.
  7. Email contact button links to team email.
- **Branches:**
  - [Branch A — Post-rejection revisit] If the proposal was rejected and the client revisits, a `post_rejection_revisit` alert is also created.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-expired-graceful.spec.js` (410 fallback + 200 expired_meta banner)
- **Known gaps:** When the full proposal still renders with the persistent expired banner (`pages/proposal/[uuid]/index.vue` `isExpired`), the top-left index toggle must drop below the banner (`ProposalIndex` `bannerActive` → `top-28 sm:top-20`) so the two don't overlap. No E2E asserts this no-overlap; only a unit test (`test/components/ProposalIndex.test.js`) covers the offset class.

### FLOW: `proposal-magic-link-request`

- **Module:** proposal
- **Role:** guest (on expired proposal view)
- **Priority:** P1
- **Routes:** `/proposal/:uuid` or `/proposal/:slug` (when expired)
- **Description:** A guest who lands on an expired proposal submits their email through the form in `ProposalExpired.vue:160` to receive a fresh magic-link. Backend looks up active proposals by client email and sends a new email with the link(s). This is the recovery path that complements `proposal-expired-graceful` (which only covers the expired-state visuals).
- **Steps:**
  1. Guest opens an expired proposal URL → `ProposalExpired` component renders.
  2. Guest types their email into the input and submits the form.
  3. Frontend calls `proposalStore.requestMagicLink(email)` → `POST /api/proposals/request-link/` with `{ email }`.
  4. Backend looks up non-finished proposals belonging to the email; if found, sends a new email with the magic link(s).
  5. UI shows a success confirmation ("Te enviamos un enlace nuevo a tu correo").
- **Branches:**
  - [Branch A — Email not found] Backend returns 404 / generic message; UI shows neutral feedback (avoid leaking which emails are clients).
  - [Branch B — Network error] Submit fails; UI surfaces a retry message.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-magic-link-request.spec.js`

### FLOW: `proposal-calculator-abandonment-tracking`

- **Module:** proposal
- **Role:** guest (via shared UUID link) / system
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The calculator modal tracks whether the client confirms or abandons their module selection. On close without confirming, an `abandoned` event is sent. On confirm, a `confirmed` event is sent. Both are stored as `ProposalChangeLog` entries and aggregated in the admin dashboard as `calc_abandonment_rate` and `dropped_modules`.
- **Steps:**
  1. Client opens the calculator modal in the Investment section.
  2. Client toggles modules (selects/deselects).
  3. [Branch A — Confirm] Client clicks "Confirmar selección" → `confirmed` event sent via `POST /api/proposals/:uuid/track-calculator/`.
  4. [Branch B — Abandon] Client closes modal without confirming → `abandoned` event sent automatically.
  5. Backend creates `ProposalChangeLog` with `calc_confirmed` or `calc_abandoned` change type.
  6. Dashboard aggregates data: `calc_abandonment_rate` = abandoned / (abandoned + confirmed), `dropped_modules` = most frequently deselected modules.
- **Coverage:** ⚠️ Backend-only
- **Backend Tests:** `content/tests/views/test_proposal_views.py`

### FLOW: `proposal-investment-calculator`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **API:** (client-side only — no API call for toggling)
- **Description:** Client reviews readable payment rows in the Investment section, opens the calculator modal, toggles optional feature modules on/off, sees dynamic total investment and estimated timeline update in real time, and confirms or cancels the selection.
- **Outcomes:**
  - `display` — at laptop width, every payment keeps amount, currency, and `+ IVA` together on one line.
  - `success` — the client opens the calculator, changes optional modules, and confirms the resulting selection.
- **Steps:**
  1. Client views the proposal and navigates to the Investment section.
  2. The payment list leaves room for its labels and keeps each complete tax-qualified amount together.
  3. Client clicks "Personalizar tu inversión" to open the calculator modal.
  4. Client toggles optional feature modules — total investment and timeline update dynamically.
  5. Client clicks "Confirmar selección" → modal closes; closing section reflects updated total.
  6. [Branch B — Abandon] Client closes modal without confirming → selection reverts.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-investment-calculator.spec.js`

### FLOW: `proposal-comment-from-closing`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client submits a written comment from the proposal closing panel via a comment modal. This is distinct from the full accept/reject/negotiate response flow.
- **Steps:**
  1. Client is viewing the proposal closing section.
  2. Client opens the comment modal from the closing panel.
  3. Client types a comment and submits.
  4. Comment is recorded; confirmation feedback shown.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-comment-flow.spec.js`

### FLOW: `proposal-rejection-smart-recovery`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** After a client rejects a proposal, context-specific recovery cards render based on the rejection reason, each with appropriate CTAs (e.g., schedule call, adjust budget, revisit later).
- **Steps:**
  1. Client rejects the proposal and sees the rejection confirmation screen.
  2. Recovery cards render based on the rejection reason provided.
  3. Each card shows a relevant CTA (schedule a call, request changes, revisit later).
  4. Client can click a CTA to take the suggested recovery action.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-rejection-recovery.spec.js`

### FLOW: `proposal-schedule-followup-reminder`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** After rejecting with reason "not the right time", the client clicks the "🔔 remind me later" CTA in the recovery card (`ProposalClosing.vue` `scheduleReminder`), which POSTs `proposals/:uuid/schedule-followup/` and flips the button to a scheduled-confirmation state. The only recovery CTA that mutates server state.
- **Steps:**
  1. Client rejects the proposal choosing "not the right time".
  2. Recovery card renders with the reminder CTA.
  3. Client clicks it → `POST /api/proposals/:uuid/schedule-followup/`.
  4. Button flips to the scheduled ✅ state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-rejection-recovery.spec.js` (schedule-followup test)

### FLOW: `proposal-functional-requirements-modal`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client clicks a functional requirement group card in the proposal to open a detail modal showing individual requirement items with icons and descriptions. Items with linked technical requirements (`linked_item_ids` in the technical document, matched by the item's stable `id`) additionally show a "Ver requerimientos (N)" link that opens a nested `LinkedRequirementsModal` listing each requirement's title, priority badge, and description (no configuration/usageFlow). Works in both detailed and executive modes; legacy proposals without item ids show no link.
- **Steps:**
  1. Client views the functional requirements section of the proposal.
  2. Client clicks a requirement group card.
  3. Detail modal opens listing individual items with icons and descriptions.
  4. [Branch — linked requirements] Client clicks "Ver requerimientos (N)" under an item → nested modal opens with the technical requirements that implement that item; closing it returns to the group modal.
  5. Client closes the modal by clicking outside or the close button.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-requirements-modal.spec.js` (includes nested-modal, executive-mode, and legacy-fallback tests)

### FLOW: `proposal-negotiate`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** Client clicks "Necesito ajustes" from the ProposalClosing panel to open a negotiation flow. The response is sent to the backend with `decision: negotiating`, which pauses automations and logs the event.
- **Steps:**
  1. Client navigates to the closing panel.
  2. Client clicks "Necesito ajustes" (amber button).
  3. Confirmation modal opens.
  4. Client confirms → API call to `POST /api/proposals/:uuid/respond/` with `decision: negotiating`.
  5. Backend sets `automations_paused = True` and status to `negotiating`.
  6. Success message displays with WhatsApp CTA for further discussion.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-negotiate.spec.js`

### FLOW: `admin-proposal-quick-send`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Admin sends or re-sends a proposal directly from the proposals list without entering the edit page. Draft proposals show a "📤 Enviar" button; sent/viewed proposals show "🔄 Re-enviar". A confirmation modal prevents accidental sends.
- **Steps:**
  1. Admin views the proposals list.
  2. For draft proposals with client_email: "📤 Enviar" button is visible in the row.
  3. Admin clicks "📤 Enviar" → confirmation modal opens: "¿Enviar esta propuesta?".
  4. Admin confirms → API call to `POST /api/proposals/:id/send/`.
  5. Success: proposal status changes to `sent`, list refreshes.
  6. For sent/viewed proposals: "🔄 Re-enviar" button is visible → confirm dialog → `POST /api/proposals/:id/resend/`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-list.spec.js`

### FLOW: `admin-proposal-quick-log`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/`
- **Description:** Admin registers a seller activity (call, meeting, follow-up, note) directly from the proposals list via the actions modal, without entering the proposal detail. Opens a quick-log modal with activity type selector and description field.
- **Steps:**
  1. Admin opens the actions modal (⋮) for a proposal.
  2. Admin clicks "📝 Registrar actividad".
  3. Quick-log modal opens showing client name and proposal title.
  4. Admin selects activity type (call, meeting, follow-up, note).
  5. Admin enters a description.
  6. Admin clicks "Registrar" → API call to `POST /api/proposals/:id/log-activity/`.
  7. Success: modal closes, proposal list refreshes with updated `last_activity_at`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-quick-log.spec.js`

### FLOW: `proposal-discount-multi-section`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** When a proposal has an active discount, the discount badge is consistently visible across three sections: Investment (banner with % OFF), Calculator modal (footer badge), and ProposalClosing (special price badge). This ensures the client is always aware of the time-limited offer.
- **Steps:**
  1. Client opens a proposal with `discount_percent > 0`.
  2. Investment section shows a discount banner with percentage and days remaining.
  3. Calculator modal shows a discount badge in the footer.
  4. Closing section shows a "Precio especial" badge above the accept button.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-discount-multi-section.spec.js`

### FLOW: `proposal-onboarding-mobile-swipe`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** On mobile devices, the onboarding tutorial replaces positioned tooltips with a fullscreen swipe carousel overlay. Users navigate steps by swiping left/right or tapping next/back buttons. Desktop retains tooltip-based onboarding.
- **Steps:**
  1. First-time visitor opens a proposal on a mobile device.
  2. ProposalOnboarding detects `isMobile` and renders fullscreen overlay.
  3. User swipes left/right or taps navigation buttons to progress through steps.
  4. On completion, onboarding emits `@complete` and sets localStorage flag.
  5. Reading time popup appears.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-onboarding-mobile-swipe.spec.js`

### FLOW: `proposal-og-meta-personalized`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P3
- **Routes:** `/proposal/:uuid`
- **Description:** Personalized Open Graph meta tags are set dynamically so WhatsApp/social media previews show the client name and proposal title. Uses `useHead` with computed `og:title` and `og:description`.
- **Steps:**
  1. Proposal page loads and fetches proposal data.
  2. `useHead` sets `og:title` to "Propuesta para {client_name}".
  3. `og:description` includes client name and proposal title in the appropriate language.
  4. When the proposal URL is shared on WhatsApp/social media, the personalized preview is shown.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-og-meta-personalized.spec.js`

### FLOW: `admin-proposal-dashboard-auto-refresh`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals/`
- **Description:** The ProposalDashboard KPI panel auto-refreshes every 60 seconds when open. A manual "Actualizar" button and "last updated" label are also available. Auto-refresh pauses when the dashboard is collapsed.
- **Steps:**
  1. Admin views the proposals list with the dashboard open.
  2. Dashboard fetches data on first open.
  3. Every 60 seconds, data refreshes automatically if the panel is open.
  4. "Actualizar" button triggers manual refresh with spin animation.
  5. "justo ahora" / "hace Xs" label shows time since last refresh.
  6. Collapsing the dashboard stops auto-refresh; expanding resumes it.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-dashboard-auto-refresh.spec.js`

### FLOW: `proposal-summary-kpis`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The Proposal Summary section displays personalized KPI cards at the top, sourced from `content_json.kpis`. Each KPI shows a value, label, and source citation, while the standard investment card keeps the currency and `+ IVA` suffix visible. KPIs are editable in the admin SectionEditor and included in the JSON template.
- **Steps:**
  1. Client navigates to the Proposal Summary section.
  2. KPI cards render from `content.kpis` array with value, label, and source.
  3. Below KPIs, standard summary cards render and the investment card preserves its currency and tax suffix.
  4. Admin can add/edit/remove KPIs in the SectionEditor for proposal_summary.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-summary-kpis.spec.js`

### FLOW: `proposal-roi-projection`

- **Module:** proposal
- **Role:** guest (via shared UUID link); admin (edits via SectionEditor)
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** ROI Projection / Business Outcomes section. Renders configurable KPI cards (visualizations/day, ad reach, MRR, payback, year-1 revenue) and per-scenario blocks (Conservative / Realistic / Optimistic) with metric rows and an emphasis flag for totals; closes with an optional CTA note. The section sits at `order=4`, between `conversion_strategy` and `investment`, so the sponsor sees quantified business outcomes BEFORE the price ask. The section is **web-only** — it has no PDF renderer (sections without a renderer are silently skipped). Migration 0118 backfilled an empty disabled row in every existing proposal so admins can enable + populate per-proposal without breaking legacy flows.
- **Steps:**
  1. Client opens `/proposal/:uuid` and selects "Propuesta Completa" in the gateway.
  2. Client navigates past `greeting`, `executive_summary`, `context_diagnostic`, `conversion_strategy` panels.
  3. ROI Projection panel renders if the section's `is_enabled=true`.
  4. KPI cards display value, label, optional sublabel, and source citation.
  5. Scenarios block lists each scenario with metric rows; metrics with `emphasis=true` get bolded total styling.
  6. CTA note (if any) renders inside a primary-tinted banner closing the section.
- **Branches:**
  - [Branch A — Disabled section] When `is_enabled=false`, the panel is filtered out of `displayPanels` (regression-tested for the 31 legacy proposals that received the row via migration 0118).
  - [Branch B — Empty arrays] When `kpis` and `scenarios` are empty, only header/subtitle/CTA render without breaking the layout.
  - [Branch C — Admin edit] Admin form in `SectionEditor.vue` lets admins drag-reorder KPIs and scenarios; round-trip JSON persistence is validated by `test/components/admin-sectionEditorUtils-roi.test.js`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-roi-projection.spec.js`
- **Unit Tests:** `test/components/admin-sectionEditorUtils-roi.test.js`, `test/composables/useLinkify-html-escape.test.js`
- **Backend Tests:** `content/tests/test_roi_projection.py`

### FLOW: `admin-proposal-log-activity`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` (Activity tab)
- **Description:** Admin manually logs a seller activity on a proposal. Activity types include call, meeting, follow-up, and note. The activity is stored as a ProposalChangeLog entry and updates `last_activity_at`.
- **Steps:**
  1. Admin opens a proposal edit page and navigates to the Activity tab.
  2. Admin selects an activity type and enters a description.
  3. Admin submits → API call to `POST /api/proposals/:id/log-activity/`.
  4. Backend creates a ProposalChangeLog entry and updates `last_activity_at`.
  5. Activity timeline refreshes with the new entry.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-log-activity.spec.js`

### FLOW: `proposal-calculator-new-modules`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The investment calculator displays additional default modules: Email Marketing (10%), i18n (15%), and Gift Cards (20%). KPI Dashboard has been removed from the calculator and is now included by default (like Analytics). Conversion Tracking moved to integrations (see `proposal-calculator-integrations`).
- **Steps:**
  1. Client opens the calculator modal.
  2. Email Marketing module appears unselected with price as +10% of total.
  3. i18n module appears unselected with price as +15% of total.
  4. Gift Cards module appears unselected with price as +20% of total.
  5. Client toggles modules → total investment and timeline update in real-time.
  6. KPI Dashboard is NOT shown in the modal (included by default like Analytics module).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-new-modules.spec.js`

### FLOW: `proposal-calculator-biometric-module`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The investment calculator exposes `biometric_verification_module` as a provider-billed integration: ID document reading + OCR, facial recognition, liveness detection, antifraud + KYC, frictionless digital onboarding, and a verifications panel. Because the integration provider invoices the end client directly, the module follows the `is_invite=True, price_percent=0` pattern (same as `ai_module` and `integration_conversion_tracking`). Two sibling modules — `qr_generator_module` (25%) and `content_generator_module` (30%, with editorial calendar + scheduling) — are added to the catalog at the same time but are regular non-invite calculator modules; their structural behavior is already covered by `proposal-calculator-modules` and `proposal-calculator-new-modules`.
- **Steps:**
  1. Client opens the calculator modal on a proposal that includes `biometric_verification_module`.
  2. Module row renders with the bilingual title "🪪 Verificación y Validación Biométrica (Integración API)".
  3. Module shows "Agendar llamada" badge instead of a price (because `is_invite=True, price_percent=0`).
  4. Client clicks the module row → `invite_note` is revealed ("Te invitamos a una llamada... un proveedor especializado factura el servicio directamente al cliente final").
  5. Selecting the module does NOT alter the total investment (provider-billed; verified at the unit level by `computeWeeksAddition — does not count invite modules`).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-biometric-module.spec.js`

### FLOW: `proposal-calculator-behavior-tracking-module`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The investment calculator exposes `behavior_tracking_module` as a priced add-on (30% of the base investment, `default_selected: False`): first-party user behavior tracking installed in the client's own product — session/open registry, views opened + time per view (up to 15 tracked views), interest map, journey funnel with drop-off (1 main funnel), built-in behavior panel (up to 8 KPIs / 4 charts), device breakdown, and 12-month data retention with explicit exclusions (no screen recording, click heatmaps or cross-site tracking). It is the same capability the platform uses in its own proposal analytics tab, productized for clients.
- **Steps:**
  1. Client opens the calculator modal on a proposal that includes `behavior_tracking_module`.
  2. Module row renders under the bilingual label "👣 Rastreo de Comportamiento" with `+30%` pricing over the base total (e.g. base $4.000.000 COP → +$1.200.000).
  3. Client expands the module → 7 scope-closed items are listed.
  4. Selecting the module raises the effective total by base×30% and rescales payment options.
  5. In technical mode, an epic with `linked_module_ids: ["module-behavior_tracking_module"]` is hidden while the module is deselected and shown once selected (same gating as other additional modules).
- **Coverage:** ⚠️ Pending (registered, E2E spec not yet implemented; catalog data verified by `backend/content/tests/services/test_proposal_service.py` and migration tests, calculator mechanics structurally covered by `proposal-calculator-modules` / `proposal-investment-calculator`)
- **E2E Spec:** _suggested:_ `e2e/proposal/proposal-calculator-behavior-tracking-module.spec.js`

### FLOW: `proposal-calculator-integrations`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** The investment calculator displays integration groups as individually toggleable calculator modules: International Payments (20%), Regional Payments Colombia (20%), Electronic Invoicing / DIAN (60%), and Conversion Tracking Meta & Google Ads (invite-only, 0%). Each was previously grouped under a single `integrations_api` group and now has its own pricing, selection state, and invite attributes.
- **Steps:**
  1. Client opens the calculator modal.
  2. International Payments integration appears unselected with price as +20% of total.
  3. Regional Payments (Colombia) integration appears unselected with price as +20% of total.
  4. Electronic Invoicing integration appears unselected with price as +60% of total.
  5. Conversion Tracking integration appears with "Agendar llamada" invite-only label and invite note.
  6. Client selects International Payments → total investment increases by 20%.
  7. Client selects Electronic Invoicing → total investment increases by 60%.
- **Branches:**
  - [Branch A — Conversion Tracking invite] Client sees invite note, no cost added.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-integrations.spec.js`

### FLOW: `admin-blog-list`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/`
- **Description:** View the paginated list of all blog posts (admin view with both languages).
- **Steps:**
  1. Admin navigates to `/panel/blog/`.
  2. Blog posts load from API (`GET /api/blog/admin/?page=1&page_size=15`).
  3. Blog table renders with title_es, title_en, status, dates.
  4. Pagination controls appear if total pages > 1 (prev/next + page numbers).
  5. "Calendario" button links to calendar view.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-list.spec.js`

### FLOW: `admin-blog-calendar`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/calendar`
- **Description:** Weekly calendar view showing scheduled, published, and draft blog posts.
- **Steps:**
  1. Admin navigates to `/panel/blog/calendar`.
  2. Calendar loads current week posts from API (`GET /api/blog/admin/calendar/?start=YYYY-MM-DD&end=YYYY-MM-DD`).
  3. Week grid renders Mon–Sun with posts color-coded: green (published), blue (scheduled), gray (draft).
  4. Admin uses ← / → arrows to navigate weeks, "Hoy" button to return to current week.
  5. Clicking a post card navigates to its edit page.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-calendar.spec.js`

### FLOW: `admin-blog-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/create`
- **Description:** Create a new bilingual blog post.
- **Steps:**
  1. Admin navigates to `/panel/blog/create`.
  2. Blog form renders with bilingual fieldsets (ES + EN: title, excerpt, content).
  3. Admin fills in both language versions.
  4. Admin optionally uploads a cover image.
  5. Admin submits the form.
  6. API call to `POST /api/blog/admin/create/`.
  7. On success, admin is redirected to blog list.
- **Branches:**
  - [Branch A — Validation error] Form shows errors, admin corrects and resubmits.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-create.spec.js`

### FLOW: `admin-blog-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/:id/edit`
- **Description:** Edit an existing bilingual blog post.
- **Steps:**
  1. Admin navigates to `/panel/blog/:id/edit`.
  2. Blog post data loads from API (`GET /api/blog/admin/:id/detail/`).
  3. Edit form renders pre-filled with current bilingual data.
  4. Admin modifies content.
  5. Admin saves changes.
  6. API call to `PATCH /api/blog/admin/:id/update/`.
  7. Success feedback displays.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-edit.spec.js`

### FLOW: `admin-blog-delete`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/blog/`
- **Description:** Delete an existing blog post.
- **Steps:**
  1. Admin views the blog list.
  2. Admin clicks delete on a blog post.
  3. Confirmation dialog appears.
  4. Admin confirms deletion.
  5. API call to `DELETE /api/blog/admin/:id/delete/`.
  6. Blog post is removed from the list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-delete.spec.js`

### FLOW: `admin-blog-create-from-json`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/blog/create` (JSON import tab)
- **Description:** Create a blog post by importing a structured JSON payload with content_json sections, template download, validation, and preview.
- **Steps:**
  1. Admin navigates to `/panel/blog/create`.
  2. Admin clicks "Importar JSON" tab.
  3. Admin pastes or uploads a valid JSON payload.
  4. Admin submits.
  5. API call to `POST /api/blog/admin/create/` with structured content_json.
  6. On success, admin is redirected to blog list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-create.spec.js`

### FLOW: `admin-portfolio-list`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/portfolio/`
- **Description:** View the list of all portfolio works with status badges, edit/duplicate/delete actions.
- **Steps:**
  1. Admin navigates to `/panel/portfolio/`.
  2. Portfolio works load from API (`GET /api/portfolio/admin/`).
  3. Table renders with title, slug, status (published/draft/archived), dates.
  4. Admin sees action links: edit, duplicate, delete.
  5. "Nuevo Proyecto" button links to create page.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-portfolio-list.spec.js`

### FLOW: `admin-portfolio-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/portfolio/create`
- **Description:** Create a new portfolio work via manual form (bilingual fields, cover image, project URL, content JSON, SEO) or JSON import.
- **Steps:**
  1. Admin navigates to `/panel/portfolio/create`.
  2. Page loads with Manual / Importar JSON tab toggle.
  3. Manual tab is active by default — form renders with ES/EN fieldsets.
  4. Admin fills title, tagline, project URL, cover image, content JSON, SEO fields.
  5. Admin submits.
  6. API call to `POST /api/portfolio/admin/create/`.
  7. On success, admin is redirected to portfolio list.
- **Branches:**
  - [Branch A — JSON import] Admin switches to "Importar JSON" tab, pastes JSON, submits via `POST /api/portfolio/admin/create-from-json/`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-portfolio-create.spec.js`

### FLOW: `admin-portfolio-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/portfolio/:id/edit`
- **Description:** Edit an existing portfolio work including bilingual fields, cover image upload, content JSON, and SEO meta.
- **Steps:**
  1. Admin navigates to `/panel/portfolio/:id/edit`.
  2. Portfolio work data loads from API (`GET /api/portfolio/admin/:id/detail/`).
  3. Edit form renders pre-filled with current data.
  4. Admin modifies content.
  5. Admin saves changes.
  6. API call to `PATCH /api/portfolio/admin/:id/update/`.
  7. Success feedback displays.
- **Branches:**
  - [Branch A] Admin uploads a new cover image via `POST /api/portfolio/admin/:id/upload-cover/`.
  - [Branch B] "Ver en público" link opens the public page in a new tab.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-portfolio-edit.spec.js`

### FLOW: `admin-portfolio-delete`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/portfolio/`
- **Description:** Delete an existing portfolio work.
- **Steps:**
  1. Admin views the portfolio list.
  2. Admin clicks delete on a portfolio work.
  3. Confirmation dialog appears.
  4. Admin confirms deletion.
  5. API call to `DELETE /api/portfolio/admin/:id/delete/`.
  6. Portfolio work is removed from the list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-portfolio-delete.spec.js`

### FLOW: `admin-hour-packages-list`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/hour-packages`
- **Description:** View the hour-package catalog filtered by nationality tabs (COL/EXT/USA); prices show in the currency derived from the nationality (COL→COP, EXT/USA→USD) with computed effective rate and total.
- **Steps:**
  1. Admin navigates to `/panel/hour-packages`.
  2. Packages load from API (`GET /api/hour-packages/admin/?nationality=COL`) — Colombia tab is active by default.
  3. Table renders name, hours, rate/h, discount, effective rate, total and active badge.
  4. Admin switches nationality tab → list refetches with that nationality and prices change currency.
  5. Empty tabs show a hint that proposal creation falls back to default packages.
  6. "Nuevo paquete" button links to the create page carrying the active nationality.
- **Coverage:** ✅ Covered (list, nationality tabs, empty state, pagination across pages and the mobile card variant; asserted 2026-07-23. View modes tracked in `admin-hour-packages-view-modes`.)
- **E2E Spec:** `e2e/admin/admin-hour-packages-list.spec.js`

### FLOW: `admin-hour-packages-view-modes`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/hour-packages`
- **Description:** Switch the catalog between Tabla, Tarjetas and Comparativa (pricing tiers with a "Mejor tarifa" highlight); the initial mode comes from the settings singleton.
- **Steps:**
  1. Admin opens `/panel/hour-packages` — `GET /api/hour-packages/admin/settings/` decides the initial view mode.
  2. Admin switches the view-mode segmented control (Tabla / Tarjetas / Comparativa).
  3. Tarjetas renders a card grid with effective rate, discount badge and totals; Comparativa renders side-by-side tiers highlighting the best effective rate.
  4. Edit/Eliminar remain available from every mode.
- **Coverage:** ⚠️ Missing
- **E2E Spec:** _pending_

### FLOW: `admin-hour-packages-config`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/hour-packages`
- **Description:** Configuración section: per-nationality base hourly rates (propagate to the whole catalog on save), default view mode, and restore a nationality's catalog to the canonical defaults ladder.
- **Steps:**
  1. Admin switches the page section segmented to "Configuración" — the three base-rate inputs (Colombia COP, Extranjero USD, USA USD) come prefilled from `GET /api/hour-packages/admin/settings/`.
  2. "Guardar tarifas" PATCHes `/api/hour-packages/admin/settings/update/`; the backend propagates each changed rate to every package of that nationality (active and inactive) and responds with `updated_packages` counts, surfaced in the success toast. The Catálogo table reflects the new rates. Rates `<= 0` are rejected client-side; a server failure surfaces an error toast. Existing proposals keep their snapshot — only new proposals seed the updated rates.
  3. Saving a default view mode PATCHes the same settings endpoint and toasts.
  4. "Restablecer" per nationality opens a ConfirmModal and POSTs `/api/hour-packages/admin/restore-defaults/`; the catalog of that country is replaced with the default ladder (1h/20h/60h/180h) and the base rate in settings resets to the default.
- **Coverage:** ✅ Covered (base rates: display prefill, success save + propagation reflected in catalog, client-side error, server failure toast; asserted 2026-07-28. Default view mode and restore-defaults remain unasserted in E2E — backend covered in `test_hour_package_views.py`.)
- **E2E Spec:** `e2e/admin/admin-hour-packages-config.spec.js`

### FLOW: `admin-accounting-statements`

- **Module:** admin
- **Role:** admin (superuser)
- **Priority:** P2
- **Routes:** `/panel/accounting/statements`
- **Description:** Monthly credit-card statement ledger (extractos): 12-month processed/draft/pending grid per card, inline detail with totals, category bars and transactions, finalize/reopen lifecycle, learned merchant aliases, MCP chat kick-off prompt. Since Jul 2026 the year selector options come from the backend (`year_options`, derived from the card catalog's `statements_since` — 2026-05 for T.C 0064, so 2025 no longer renders) and months before that date show a gray "No aplica" chip instead of "Pendiente"; drafts also allow editing the statement header (modal over PATCH `.../update/`; card/period read-only) and adding transactions manually (create mode of the tx modal over POST `.../transactions/batch/`); every statement has a "Documento del extracto" block to upload/view/replace/delete the bank PDF (POST `.../pdf/upload/`, .pdf only, 15 MB max; DELETE `.../pdf/delete/`).
- **Steps:**
  1. Superuser opens `/panel/accounting/statements` — `GET /api/accounting/statements/status/?year=` renders the 12-month grid with backend-driven `year_options`; months before `statements_since` show "No aplica" and card chips show Procesado/Borrador.
  2. Clicking a chip loads `GET /api/accounting/statements/:id/` — detail shows stat cards (Compras/Pagos/Intereses/Saldo), category bars, the PDF block and the transactions table (unidentified lines flagged).
  3. On a draft: "Editar encabezado" (modal PATCH `.../update/`), "Agregar transacción" (tx modal in create mode → POST `.../transactions/batch/`), per-line Editar (modal PATCH `.../transactions/:txId/update/` — fecha, descripción, comercio, categoría, cuota, valor and notes) and Eliminar, plus **single-click** inline editing of fecha/descripción/comercio/categoría/cuota/valor directly in the table (same PATCH; a dashed underline and a hover pencil mark the cells as editable). Comercio is a combobox over the learned merchant catalog that still accepts free text; picking a catalog entry also sends its `default_category` when the row is still `other`, and any non-empty merchant save offers "¿Recordar este comercio?" → POST `/api/accounting/merchant-aliases/learn/` (upserts by normalized descriptor and back-applies to the statement's other unidentified rows). Clearing comercio restores the "Sin identificar" badge; cuota is captured as a structured cuota/total number pair; negative amounts (refunds) edit inline keeping their sign. Finalizar validates Σ vs purchases_total (±1 COP) and offers a forced close on mismatch; Eliminar removes the statement after confirm.
  4. On a processed statement: Reabrir returns it to draft. The cells stay editable — saving one first asks "¿Reabrirlo para corregirlo?" and, on confirm, POSTs `.../reopen/` before the PATCH (the backend keeps refusing writes on non-draft statements). "Agregar transacción" and per-line Eliminar stay hidden: those are structural changes and still require the explicit Reabrir button.
  5. "Documento del extracto": Subir PDF / Ver PDF / Reemplazar / Eliminar (with confirm) manage the bank PDF kept as documentation; the statement reminder email nags every 8 days until the previous month is processed with its PDF attached.
  6. "Comercios aprendidos" lists the learned merchant aliases with the same single-click inline editing as the transactions table over *Texto a mapear*, *Comercio* and *Categoría* (PATCH `/api/accounting/merchant-aliases/:id/update/`), plus per-row delete. Comercio is the same combobox over the merchant catalog. The descriptor comes back re-normalized by the backend (uppercased, reference codes of 5+ digits dropped), and one already owned by another alias is refused with "Ya existe un alias para ese texto." leaving the row untouched; clearing *Texto a mapear* or *Comercio* is blocked client-side before any request. Unlike the transaction cells this never asks to reopen the statement — aliases are a global catalogue — and the corrected alias governs the next statements rather than back-applying to rows already saved.
  7. "Copiar prompt" copies the Spanish kick-off prompt for the claude.ai accounting connector (statements are created from chat via `create_statement`).
- **Coverage:** ✅ Covered — all four outcome classes (grid year options + "No aplica", detail load, manual tx add, finalize lifecycle, PDF delete with confirm, single-click inline merchant edit with PATCH body, alias learning accepted and declined, catalog pick filling the category, structured cuota valid + invalid, negative amount kept negative, backend 400 surfaced in Spanish, reopen-and-edit on a processed statement and its cancel path, plus inline alias editing: rename with PATCH body, descriptor normalization, category change, the empty-name guard that sends no request, and the duplicate-descriptor 400). Header-edit modal, forced close, the standalone Reabrir button and alias delete remain unasserted.
- **E2E Spec:** `e2e/admin/admin-accounting-statements-card-catalog.spec.js`, `e2e/admin/admin-accounting-statements-inline-edit.spec.js`

### FLOW: `admin-clients-config-tab`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/clients`
- **Description:** Trailing "Configuraciones" pill swaps the client list for the shared ViewSettingsPanel (saved-filter-tabs reset + defaults link).
- **Steps:**
  1. Admin clicks the right-aligned "Configuraciones" pill in the status-tab row.
  2. The list area is replaced by the settings panel: "Restablecer" for the Clientes view opens a ConfirmModal and POSTs `accounts/saved-filter-tabs/reset/` (view=client); saved tabs reload on success.
  3. "Abrir defaults" links to `/panel/defaults`.
  4. Clicking any status pill returns to the list.
- **Coverage:** ⚠️ Missing
- **E2E Spec:** _pending_

### FLOW: `admin-proposals-config-tab`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/proposals`
- **Description:** Fixed trailing "Configuraciones" tab in the proposals filter-tab bar swaps the list for the shared ViewSettingsPanel (saved-filter-tabs reset + proposals defaults link).
- **Steps:**
  1. Admin clicks the right-aligned "Configuraciones" tab (mobile: the "⚙ Configuraciones" option of the tabs select).
  2. The list area is replaced by the settings panel: "Restablecer" for the Propuestas view POSTs `accounts/saved-filter-tabs/reset/` (view=proposal) behind a ConfirmModal; tabs reload on success.
  3. "Abrir defaults de propuestas" links to `/panel/proposals/defaults`.
  4. Selecting any filter tab (or "Todas") closes the panel and restores the list.
- **Coverage:** ⚠️ Missing
- **E2E Spec:** _pending_

### FLOW: `admin-hour-packages-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/hour-packages/create`
- **Description:** Create an hour package with nationality, bilingual name/note, hours, hourly rate, discount, order and active flag; the currency is derived from the nationality and a live preview shows effective rate and total.
- **Steps:**
  1. Admin navigates to `/panel/hour-packages/create` (nationality preselected from query param).
  2. Admin fills the form; the preview recalculates effective rate/total.
  3. Admin submits.
  4. API call to `POST /api/hour-packages/admin/create/`.
  5. On success, admin is redirected to the list; validation errors render per field.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-hour-packages-create.spec.js`

### FLOW: `admin-hour-packages-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/hour-packages/:id/edit`
- **Description:** Edit an existing hour package; form prefilled from the detail endpoint, preview recalculates and a partial PATCH persists the changes.
- **Steps:**
  1. Admin navigates to `/panel/hour-packages/:id/edit`.
  2. Package data loads from API (`GET /api/hour-packages/admin/:id/detail/`).
  3. Admin edits rate/discount/fields; preview recalculates.
  4. Admin saves → `PATCH /api/hour-packages/admin/:id/update/`.
  5. On success, admin returns to the list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-hour-packages-edit.spec.js`

### FLOW: `admin-hour-packages-delete`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/hour-packages`
- **Description:** Delete an hour package from the list with a confirmation modal; already-created proposals are not affected.
- **Steps:**
  1. Admin views the hour-packages list.
  2. Admin clicks delete on a package.
  3. ConfirmModal appears.
  4. Admin confirms → `DELETE /api/hour-packages/admin/:id/delete/`.
  5. The row disappears from the list.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-hour-packages-delete.spec.js`

### FLOW: `admin-financing-distribution`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/:locale/panel/financing`
- **Interaction:** Navigate from Comercial, copy or open the public URL, download the booklet, inspect the public preview and retry a failed content request. If the active 60-hour package is absent, read the catalog warning before sharing.
- **Outcomes:** `display`, `success`, `failure`
- **Evidence:** panel financing page, panel navigation and public financing endpoints.

### FLOW: `admin-financing-agreement-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/partnership-program?tab=agreements`, `/panel/partnership-program/new`, `/panel/partnership-program/:id`
- **Interaction:** Crear un borrador de otrosí desde el registro administrativo.

| Outcome | Inicio → acción → resultado observable |
|---|---|
| `display` | Abrir **Financiación → Otrosíes** → ver métricas, filtros y registros vigentes o el estado vacío. |
| `success` | Pulsar **Nuevo otrosí** → seleccionar un cliente → verificar su identidad precargada → completar contrato, alcance, monto elegible y abono inicial → crear → abrir el borrador con el calendario de cuotas definido por la política vigente. |
| `error` | Enviar datos incompletos o inválidos → el API y el formulario señalan los campos → los datos ya escritos permanecen disponibles. |
| `failure` | Fallar la carga del registro → mostrar un estado de error explícito sin presentar una lista vacía engañosa. |

- **Reglas:** el cliente debe estar activo; propuesta y proyecto opcionales deben pertenecerle; el valor equivalente debe quedar dentro del rango inclusivo vigente; el abono debe respetar el mínimo derivado del análisis de riesgo; las cuotas deben sumar exactamente el saldo y usar la cantidad y ventana de vencimiento de la revisión congelada.
- **Coverage:** ✅ Covered
- **Modalidad:** seleccionar cinco años muestra el compromiso de exclusividad conceptual de Project App. y pide delimitar sector, nicho, producto y conceptos en el alcance. Tres años excluye ese compromiso adicional. Los borradores resuelven el texto según la selección; los documentos preparados conservan su snapshot.
- **E2E Spec:** `e2e/admin/admin-financing-agreements.spec.js`
- **Backend Tests:** `content/tests/views/test_financing_agreements.py`, `content/tests/services/test_financing_agreement_service.py`

### FLOW: `admin-financing-agreement-lifecycle`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/financing/:id`
- **Interaction:** Gestionar el otrosí y su documento firmado a través de estados auditables.

| Outcome | Inicio → acción → resultado observable |
|---|---|
| `display` | Abrir un otrosí → ver estado, ciclo, revisión de política congelada, resumen, calendario, acciones permitidas e historial de responsables. |
| `success` | En un borrador anterior, confirmar la adopción de la política vigente → validar valores y reemplazar plantilla/calendario; marcar listo → congelar número/texto; descargar borrador marcado **BORRADOR · SIN FIRMA**; registrar PDF firmado → activar; certificar pago o cancelar con nota; archivar/restaurar sólo estados terminales. |
| `error` | Omitir PDF o nota obligatoria, subir un archivo inválido o intentar una transición no permitida → conservar el estado y mostrar validación. |
| `failure` | Fallar la carga o una mutación → mostrar el problema sin simular que el estado cambió. |

- **Privacidad:** el PDF firmado no tiene URL pública; sólo se descarga desde un endpoint autenticado y no se publica bajo `/media/`.
- **Cobranza:** la cláusula de mora queda documentada y auditable, pero este flujo no modifica automáticamente Hosting ni contabilidad.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-financing-agreements.spec.js`
- **Backend Tests:** `content/tests/views/test_financing_agreements.py`

### FLOW: `admin-financing-agreement-second-cycle`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/financing/:id`
- **Interaction:** Aprobar una segunda financiación dentro de la modalidad de cinco años.

| Outcome | Inicio → acción → resultado observable |
|---|---|
| `display` | Abrir el primer ciclo completado de cinco años → ver **Aprobar segundo ciclo**; una modalidad de tres años no ofrece la acción. |
| `success` | Confirmar la evaluación manual de riesgo → crear un único borrador de ciclo 2 → navegar a él con modalidad y vigencia original bloqueadas para edición. |
| `error` | El primer ciclo no está pagado, pertenece a tres años o ya tiene ciclo 2 → rechazar la aprobación sin crear otro registro. |
| `failure` | Fallar la operación de aprobación → permanecer en el primer ciclo y mostrar el error para reintentar con seguridad. |

- **Regla temporal:** el calendario del ciclo 2 debe terminar dentro de la vigencia original; aprobarlo no reinicia ni extiende los cinco años de exclusividad.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-financing-agreements.spec.js`
- **Backend Tests:** `content/tests/services/test_financing_agreement_service.py`, `content/tests/views/test_financing_agreements.py`

### FLOW: `admin-document-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents/create`
- **Description:** Crea un documento desde Markdown pegado (con preview vivo) o cargado desde archivo. El bloque Identificación conserva la asociación opcional `ClientAutocomplete` (`doc-client-autocomplete`, con creación inline) + `ProjectSelect` (`doc-project-select`, `allowNoClient`): elegir primero el proyecto completa su cliente, elegir primero el cliente filtra los proyectos y limpiar el cliente limpia el proyecto. Una carpeta puede aportar su cliente/proyecto como valor heredado; sólo cuando no los declara se usa la sugerencia por mayoría estricta de documentos, siempre editable. El acceso compacto `doc-client-note-open` abre **Notas**: como todavía no existe un documento, la acción **Aplicar al borrador** y sus avisos explican que falta crearlo para guardar la colección privada.
- **Steps:**
  1. Admin navega a `/panel/documents/create`.
  2. La vista ofrece **Pegar Markdown** y **Cargar Archivo**.
  3. Admin completa el título y, opcionalmente, cliente/proyecto en cualquier orden.
  4. Admin puede abrir **Agregar notas**, completar los mensajes y agregar notas personalizadas. El modal advierte que aún no se guardan.
  5. Admin pulsa **Aplicar al borrador**; la vista confirma que todavía falta crear el documento y muestra el estado compacto de la colección.
  6. En **Pegar Markdown**, escribe o pega contenido y revisa el preview vivo; en **Cargar Archivo**, selecciona un `.md` y revisa el contenido cargado.
  7. Admin pulsa **Crear Documento**.
  8. `POST /api/documents/create-from-markdown/` recibe markdown, asociaciones, presentación, los tres mensajes privados y `client_custom_notes` (lista vacía si se omitió).
  9. Al guardar, admin navega al Gestor Documental.
- **Branches:**
  - [Display — notas] Cancelar cierra el modal sin aplicar el borrador; cada asunto, mensaje, título y contenido se puede copiar por separado con `📋`.
  - [Display — persistencia] El modal y la notificación posterior nombran el documento pendiente; aplicar al borrador no llama al servidor.
  - [Error — nota incompleta] Una nota personalizada sin título o contenido no se puede aplicar y muestra validación inline.
  - [Display — preview] Admin puede mostrar u ocultar el panel de preview sin perder el markdown.
  - [Success — asociación] El payload siempre lleva `client`/`project`, incluido `null`; una asociación heredada o sugerida nunca bloquea la edición manual.
  - [Error — validación] Campos obligatorios faltantes o un rechazo 400 muestran errores y conservan al admin en la página de creación.
  - [Failure — servidor] Un fallo 5xx conserva todas las notas en el formulario para reintentar sin volver a redactarlas.
- **Coverage:** ✅ Covered (paste, carga de archivo, asociaciones y notas privadas en display/success/error/failure; las casillas de portada y el estilo viajan en el mismo payload, pero se auditan en sus flows específicos).
- **E2E Spec:** `e2e/admin/admin-document-create.spec.js`

### FLOW: `admin-document-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents/:id/edit`
- **Description:** Edita contenido, asociación cliente/proyecto, visibilidad en el portal y presentación de un documento manual. La entrada desde el gestor conserva carpeta, filtros, búsqueda, archivo, vista y página en un `from` interno validado; las salidas explícitas restauran ese contexto, mientras una entrada directa o no confiable vuelve a la raíz. Debajo del título, la ruta discreta `Documentos / …` muestra la jerarquía real y cada tramo enlaza al contenido de esa carpeta con hover y foco visibles. La cabecera reserva el ancho de las acciones, limita el título a dos líneas y mantiene visibilidad/cliente sin empujar los controles; debajo muestra los estados concurrentes con su duración. **Acciones** contiene las salidas PDF y queda separado de **Cancelar/Guardar**. La asociación guardada ofrece backlinks y conserva el `client_name` heredado cuando no existe relación. La barra de Markdown permite copiar o pegar contenido; su preview inline y su vista completa se centran sobre un ancho de página y acotan el alto con scroll interno. `doc-client-note-open` conserva los mensajes para el cliente, guarda esa metadata directamente y administra observaciones normalizadas enlazables con **Solucionar bug**. Una propuesta enviada o una cuenta de cobro emitida abre en esta misma ruta como registro PDF inmutable: identidad, asociación, carpeta, mensajes y workflow no se editan; se previsualiza y descarga exactamente el archivo guardado, mientras las observaciones privadas sí siguen disponibles. Nada de esta metadata aparece en el PDF ni en el portal del cliente.
- **Steps:**
  1. Admin llega desde el gestor a `/panel/documents/:id/edit` con su origen canónico en `from`; `GET /api/documents/:id/detail/` carga el documento.
  2. El formulario aparece precargado con título, ruta navegable de carpetas, contenido, visibilidad, asociación, configuración visual, episodios vigentes y notas privadas.
  3. Admin puede abrir **Ver notas**, **Editar notas** o **Agregar notas**, según el estado guardado.
  4. Revisa o modifica los mensajes, crea/edita/elimina notas personalizadas y pulsa **Guardar cambios**.
  5. `PATCH /api/documents/:id/update/` persiste sólo los tres mensajes y la lista completa `client_custom_notes`.
  6. El modal se cierra y la vista confirma **Notas guardadas**; cualquier otro cambio del editor continúa marcado como pendiente.
  7. Admin modifica o guarda por separado cualquier otro dato necesario.
- **Branches:**
  - [Display — cuenta emitida] Una cuenta de cobro emitida reemplaza el editor Markdown por un visor acotado del PDF archivado y muestra consecutivo, total, fechas, notas y observaciones de emisión. El PDF y los mensajes quedan bloqueados; las observaciones privadas normalizadas se pueden crear, editar, resolver o eliminar.
  - [Display — versión generada] Una propuesta archivada muestra el aviso de inmutabilidad, reemplaza el editor Markdown por el panel acotado del PDF guardado y deja una sola descarga. Sus mensajes quedan bloqueados, pero las observaciones privadas se pueden crear, editar, resolver o eliminar.
  - [Display — preview proporcional] El preview Markdown inline toma el alto de contenido corto, limita ancho y alto en pantallas amplias y activa scroll interno cuando el contenido crece; la vista completa conserva el mismo ancho de página.
  - [Success — ruta de carpetas] **Documentos**, **Sin carpeta** y cada ancestro del path son enlaces reales; un clic abre el gestor en ese nivel y conserva el ámbito archivado cuando corresponde.
  - [Display — volver] **Volver a documentos** y las demás salidas explícitas restauran la lista con su contexto y foco; el guard interviene si hay cambios sin guardar. Back del navegador conserva su semántica nativa y un `from` directo, externo o de otro módulo cae a la raíz localizada.
  - [Success — PDF] Preview y descarga usan la configuración guardada; **Acciones** permite descargar PDF Amigable o Profesional.
  - [Success — visibilidad] El interruptor persiste `is_client_visible` sin modificar el ciclo de trabajo.
  - [Success — estados] La administración de episodios y su historial se cubre en `admin-document-state-workflow`.
  - [Success — copiar Markdown] **Copiar** escribe todo `content_markdown` al portapapeles y muestra **Copiado** temporalmente.
  - [Success — pegar Markdown] **Pegar** inserta el texto en el cursor (o al final si no hay foco) y muestra **Pegado** temporalmente.
  - [Error — validación] Un rechazo 400 mantiene el modal abierto, conserva el borrador y muestra el error del campo.
  - [Failure — servidor] Un fallo 5xx mantiene el modal abierto con toda la colección editada para reintentar.
- **Coverage:** ✅ Covered (las notas privadas satisfacen display/success/error/failure; el retorno cubre salida explícita, Back nativo y fallback no confiable; el breadcrumb ejecuta navegación real; asociaciones, Markdown, previews proporcionales, PDF archivado y guard tienen cobertura propia o compartida en los specs).
- **E2E Spec:** `e2e/admin/admin-document-edit.spec.js`, `e2e/admin/admin-document-return-navigation.spec.js`

### FLOW: `admin-document-thread`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/documents`, `/panel/documents/:id/edit`
- **API:** `GET /api/documents/:id/thread/`, `GET /api/document-threads/candidates/`, `GET/POST /api/document-threads/`, `PATCH/DELETE /api/document-threads/:id/`
- **Description:** El administrador forma una historia cronológica con documentos ubicados en cualquier carpeta, cliente o proyecto. Cada documento puede pertenecer a un solo hilo y la relación se consulta desde un espacio de trabajo con pestañas para asignación, detalle y cronología.
- **Steps:**
  1. El administrador abre las acciones de un documento y elige «Hilo de documentos», usa el indicador del editor, hace clic en el badge «Hilo · N» de la lista, o entra por «Hilos» y elige uno del índice.
  2. En «Relacionar» asigna un nombre, busca documentos por título, carpeta, cliente o proyecto y define la fecha de cada hito.
  3. Guarda al menos dos documentos; el listado muestra «Hilo · N» y el modal abre luego en «Cronología».
  4. Selecciona un hito para consultar su contenido markdown o su PDF en «Detalle».
- **Branches:**
  - [Branch A — Display] La cronología ordena por fecha ascendente y conserva la posición relativa cuando dos fechas coinciden; los archivados siguen visibles con su estado.
  - [Branch B — Success] El hilo puede cruzar carpetas, clientes y proyectos; renombrar, cambiar fechas o miembros actualiza la misma relación.
  - [Branch C — Error] Todo candidato bloqueado se explica: el ocupado por otro hilo nombra ese hilo y su tamaño, y el ya agregado al borrador lo dice también; el conflicto 409 mantiene el modal abierto con una explicación.
  - [Branch F — Index] «Hilos» enumera los hilos con búsqueda, orden (reciente, último hito, A–Z) y rango de fechas, y abre cada uno por su primer miembro; sin hilos explica cómo crear el primero.
  - [Branch D — Failure] Un fallo al consultar el hilo conserva el espacio de trabajo y presenta el error sin inventar una relación vacía.
  - [Branch E — Lifecycle] Archivar conserva la membresía, eliminar se bloquea hasta retirar el documento y dejar un solo miembro disuelve el hilo con confirmación.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-thread.spec.js`
- **Unit Tests:** `test/components/DocumentThreadModal.spec.js`, `test/components/DocumentThreadIndexModal.spec.js`, `test/stores/document_threads.test.js`, `test/components/DocumentActionsSheet.spec.js`, `test/components/DocumentsTable.spec.js`, `test/components/DocumentCard.spec.js`
- **Backend Tests:** `content/tests/services/test_document_thread_service.py`, `content/tests/views/test_document_thread_views.py`

### FLOW: `proposal-view-paste-rendering`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** Client views proposal sections that use paste mode (`_editMode: 'paste'`). Paste-mode sections render as `RawContentSection` with markdown rendering in a styled card, while form-mode sections render their structured Vue components. Mixed form/paste proposals show each section in its correct mode.
- **Steps:**
  1. Client opens a proposal containing sections with `_editMode: 'paste'`.
  2. Paste-mode sections render `RawContentSection` with section title, index number, and a rounded card with markdown content.
  3. Markdown features (headings, bold, lists, blockquotes) render correctly via `marked` + `DOMPurify`.
  4. Form-mode sections in the same proposal render their structured components (no `RawContentSection`).
- **Branches:**
  - [Branch A — All form] Proposal with all form-mode sections renders zero `RawContentSection` components.
  - [Branch B — Mixed] Proposal with some paste and some form sections renders each correctly.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-view-paste-rendering.spec.js`

### FLOW: `proposal-sticky-bar-accept` *(ARCHIVED)*

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** ~~P2~~ Archived
- **Routes:** `/proposal/:uuid`
- **Description:** ~~Client accepts the proposal from the sticky bottom bar (ProposalResponseButtons) while browsing any section.~~ **ARCHIVED** — `ProposalResponseButtons` component was removed from production. Acceptance is now handled via `ProposalClosing` section buttons.
- **Coverage:** N/A (feature removed)
- **E2E Spec:** —

### FLOW: `admin-diagnostic-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/diagnostics/create` → `/panel/diagnostics/:id/edit`
- **Description:** Admin creates a new WebAppDiagnostic by searching for an existing client via autocomplete (reuses `/api/proposals/client-profiles/search/`), selecting language, and submitting. The service seeds 8 JSON sections (`purpose`, `radiography`, `categories`, `delivery_structure`, `executive_summary`, `cost`, `timeline`, `scope`) from `content.seeds.diagnostic_template` and redirects to the edit page.
- **Steps:**
  1. Admin navigates to `/panel/diagnostics/create`.
  2. Types in the client search input (autocomplete fetches from `client-profiles/search`).
  3. Selects a client from the dropdown — submit button becomes enabled.
  4. Optionally sets a custom title.
  5. Clicks "Crear diagnóstico" → POST `/api/diagnostics/create/`.
  6. Redirected to `/panel/diagnostics/:id/edit`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-create.spec.js`

### FLOW: `admin-diagnostic-send-initial`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/diagnostics/:id/edit`
- **Description:** Admin sends the initial-phase diagnostic to the client from the edit page, transitioning status DRAFT → SENT (stamps `initial_sent_at`). Then promotes the diagnostic to NEGOTIATING once the client authorises the work. Public view exposes only sections whose `visibility ∈ {initial, both}`.
- **Steps:**
  1. Admin navigates to `/panel/diagnostics/:id/edit` (status: DRAFT).
  2. Clicks "Enviar envío inicial" → POST `/api/diagnostics/:id/send-initial/`.
  3. Status transitions to SENT; `initial_sent_at` stamped; client email dispatched; response body carries `email_ok` flag.
  4. After client confirmation, admin clicks "Marcar en análisis" → POST `/api/diagnostics/:id/mark-in-analysis/`.
  5. Status transitions to NEGOTIATING.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-send.spec.js`

### FLOW: `admin-diagnostic-send-final`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/diagnostics/:id/edit`
- **Description:** Admin completes pricing and radiography data, finalises the `categories` section with findings/recommendations + the `executive_summary` section with severity counts, then sends the final-phase diagnostic from NEGOTIATING state, transitioning back to SENT with `final_sent_at` stamped. Public view now also exposes sections whose `visibility = final`.
- **Steps:**
  1. Admin updates pricing fields in the General tab and radiography data in the Secciones tab (as of 2026-04-18 the Pricing and Radiografía sub-tabs live in General/Secciones; the former "Det. técnico" tab was retired).
  2. Fills findings, strengths, and recommendations for each of the 14 categories in the Secciones tab.
  3. Completes the Resumen Ejecutivo section with severity counts + narrative.
  4. Clicks "Enviar diagnóstico final" → POST `/api/diagnostics/:id/send-final/`.
  5. Status returns to SENT; `final_sent_at` stamped; email sent to client with the public link.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-send.spec.js`

### FLOW: `admin-diagnostic-sections`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/diagnostics/:id/edit` (Secciones tab)
- **Description:** Admin edits each of the 8 JSON sections through typed form components. Each section has its own form (paragraphs, severity scale, 14-category findings/recommendations, radiography table, timeline day distribution, cost payment description, etc.). Edits are debounced 600 ms and PATCHed to `/sections/:id/update/`. A per-section "Restaurar contenido por defecto" action reloads from the seed. The tab header shows a **completeness indicator** (progress bar + percentage) that counts how many enabled sections have non-empty `content_json`. Raw-JSON export/import is a separate flow (`admin-diagnostic-json-export` / `admin-diagnostic-json-import`).
- **Steps:**
  1. Admin opens the Secciones tab — the completeness bar renders at the top and the 8 seeded section cards render (collapsed).
  2. Expands a section, edits its typed form (e.g., appends a finding in the Categorías section).
  3. After 600 ms of inactivity the change PATCHes; saving indicator flips to "Guardado HH:MM".
  4. Completeness percentage and color band (≥80 emerald / ≥50 amber / otherwise red) update as enabled sections gain content.
  5. A `section_updated` entry appears in the Actividad timeline.
- **Branches:**
  - [Visibility toggle] Changing `visibility` between `initial` / `final` / `both` changes what the public page shows per phase.
  - [Disable] Unchecking "Activa en la vista pública" hides the section without deleting it and removes it from the completeness denominator.
  - [Reset] "Restaurar contenido por defecto" restores the section from `content.seeds.diagnostic_template.default_sections()` via POST `/sections/:id/reset/`.
  - [Completeness indicator] Progress bar reflects `sectionsWithContent / enabledSectionsCount`; empty content + disabled sections both drop the ratio.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-sections.spec.js`

### FLOW: `admin-diagnostic-activity`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` (Actividad tab)
- **Description:** Admin reviews the `DiagnosticChangeLog` timeline for a diagnostic and logs manual notes (note / call / meeting / followup). Automated entries are appended by the backend on creation, status transitions, section edits, email sends, and client responses.
- **Steps:**
  1. Admin navigates to the Actividad tab.
  2. Selects a change_type, types a description, clicks "Registrar" → POST `/activity/create/`.
  3. New entry appears at the top of the timeline with icon + color + timestamp.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-sections.spec.js`

### FLOW: `admin-diagnostic-analytics`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` (Analytics tab)
- **Description:** Admin reviews full analytics dashboard at parity with proposal analytics: engagement score (0–100 color-coded), 6 summary KPI cards (total views, unique sessions, first view, reading time, coverage %, last visit), global comparison (3 metrics with ↑↓ arrows), funnel with drop-off % per section, device breakdown (desktop/mobile/tablet via user-agent), suggested actions (heuristic), skipped sections warning, section interest heatmap + top-2 insights, section engagement table, activity timeline (DiagnosticChangeLog), sessions history (last 50, no Mode column), and CSV export. No view-mode comparison, no share-links table (not applicable to diagnostics).
- **Steps:**
  1. Admin navigates to the Analytics tab — GET `/analytics/` fires on mount.
  2. Engagement score card renders with color-coded level label.
  3. Summary cards show total_views, unique_sessions, first_viewed_at, etc.
  4. Funnel rows render with section names and drop-off percentages.
  5. Device breakdown card shows desktop/mobile/tablet counts.
  6. CSV export button triggers download via `window.open`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-analytics.spec.js` (also smoke-tested in `e2e/admin/admin-diagnostic-sections.spec.js`)

### FLOW: `admin-diagnostic-engagement-score`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` (Analytics tab — Engagement Score card)
- **Description:** Engagement score card renders with the correct color-coded label based on score value: ≥70 → "Alto engagement — prioridad de follow-up" (emerald), 40–69 → "Engagement moderado" (yellow), <40 → "Bajo engagement — necesita atención" (red). Card is hidden when `engagement_score` is null.
- **Steps:**
  1. Admin opens Analytics tab with score ≥70 → sees "Alto engagement" in emerald.
  2. Admin opens Analytics tab with score <40 → sees "Bajo engagement" in red.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-analytics.spec.js`

### FLOW: `admin-diagnostic-prompt`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` (Prompt tab)
- **Description:** Admin copies / edits / downloads the two diagnostic prompts used with an LLM to draft content — "Propuesta comercial" (fills the 8-section JSON narrative) and "Detalle técnico" (fills the `categories` section with per-category findings at the 4 severity levels). State is persisted per browser via `localStorage` using `usePromptState({storageKey, defaultPrompt})`.
- **Steps:**
  1. Admin navigates to the Prompt tab.
  2. Selects a sub-tab (Comercial / Técnico).
  3. Clicks Copiar / Editar / Descargar / Restaurar — prompt text round-trips through `localStorage`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-prompt.spec.js` (5 tests: sub-tabs visible, edit mode, save custom, restore original, technical sub-tab).

### FLOW: `admin-diagnostic-email`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` → Correos tab
- **Description:** Admin sends a follow-up branded email to the client from the Correos tab of the diagnostic detail page. The composer supports a recipient address, subject, greeting, draggable body sections (each with an optional Markdown toggle), footer, and optional file attachments. The "Vista previa" sub-tab shows the real branded template server-rendered via `POST /api/emails/preview/`. Email history shows previous sends with expandable metadata (sections stored as legacy strings or `{text, markdown}` objects).
- **Steps:**
  1. Admin navigates to `/panel/diagnostics/:id/edit`.
  2. Clicks the "Correos" tab → composer loads with defaults from `GET /api/diagnostics/:id/email/defaults/`.
  3. Fills in sections and clicks "Enviar correo" → `POST /api/diagnostics/:id/email/send/` (FormData).
  4. On success, history list refreshes and shows the new send.
  5. Email is logged in `EmailLog` with `metadata.diagnostic_uuid`.
- **Branches:**
  - [Error] If client has no email, send button is disabled.
  - [Rate limit] Backend enforces 1 send/minute; 429 surfaces as an error message.
  - [NDA attachment] Admin checks "Adjuntar acuerdo de confidencialidad" → `attach_confidentiality: '1'` appended to FormData → backend generates confidentiality PDF and attaches it to the email; if PDF generation fails (missing diagnostic params), backend returns 400 and frontend shows `sendError`.
- **Coverage:** ✅ Covered (including NDA checkbox branch, Apr 20 2026)
- **E2E Spec:** `e2e/admin/admin-diagnostic-email-documents.spec.js`

### FLOW: `admin-diagnostic-documents`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` → Documentos tab
- **Description:** Admin uploads, manages, and sends file attachments (PDF, Word, Excel, images) to the client from the Documentos tab of the diagnostic detail page. Supports document types: `confidentiality_agreement` (system-generated, see `admin-diagnostic-confidentiality-*` flows), `amendment`, `legal_annex`, `client_document`, `other`.
- **Steps:**
  1. Admin navigates to `/panel/diagnostics/:id/edit`.
  2. Clicks the "Documentos" tab.
  3. Fills in the upload form (title, type, file) and clicks upload → `POST /api/diagnostics/:id/attachments/upload/`.
  4. The new attachment appears in the list.
  5. Admin selects one or more attachments via checkboxes and clicks "Enviar al cliente".
  6. `SendDiagnosticDocumentsModal` opens to compose the send email.
  7. Admin submits → `POST /api/diagnostics/:id/attachments/send/`.
  8. Email is logged in `EmailLog` with `metadata.diagnostic_uuid`, `metadata.attached_doc_ids`, and `metadata.extra_filenames`.
- **Branches:**
  - [No email] Send button disabled when no client email configured.
  - [No selection] Send button disabled until at least one checkbox is checked (counts both `selectedIds` and `selectedMainDocs`).
  - [NDA included] When the diagnostic has a generated NDA, an extra checkbox "📋 NDA — Acuerdo de Confidencialidad (borrador con marca de agua)" appears above the attachment list. When checked, the send payload includes `documents: ['confidentiality_agreement']` and the backend appends a freshly-generated draft NDA (with `BORRADOR` watermark and `XXX-XXX-XXX` placeholders) to the email.
  - [Delete] Admin clicks delete on a non-generated attachment → `DELETE /api/diagnostics/:id/attachments/:att_id/delete/` → row removed.
  - [Delete blocked] Generated NDA attachments (`is_generated=true`) cannot be deleted; backend returns HTTP 400 `{"error": "No se puede eliminar un documento generado por el sistema; regénerelo desde Editar parámetros."}`. They are filtered out of the user-attachments list, so the trash icon is not rendered for them.
- **Coverage:** ✅ Covered (base flow); 🟡 NDA-checkbox branch + delete-blocked branch not yet asserted
- **E2E Spec:** `e2e/admin/admin-diagnostic-email-documents.spec.js`

### FLOW: `admin-proposal-diagnostic-templates`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit` → "Documentos & Plantillas" tab
- **Description:** Admin accesses 3 static markdown diagnostic templates (Diagnóstico de Aplicación, Diagnóstico Técnico, Anexo — Dimensionamiento) from the proposal edit page. Tab is visible when `proposal.status ∈ {sent, viewed, negotiating, accepted, rejected}` — the same condition as the Correos tab. Each template card shows the title, filename, and last-modified date. Three actions are available per card: **Copiar contenido** (fetches `GET /api/diagnostic-templates/:slug/` and writes to clipboard via `navigator.clipboard.writeText`; shows "¡Copiado!" feedback for 2 s; per-slug response cached in component `ref` to avoid duplicate requests), **Descargar .md** (Blob + temporary `<a download>` link click), and **Vista previa** (toggles an inline `<pre>` block with raw markdown).
- **Steps:**
  1. Admin opens a proposal in `sent` or later status via `/panel/proposals/:id/edit`.
  2. Admin clicks the "Documentos & Plantillas" tab.
  3. Template list fetches `GET /api/diagnostic-templates/` → 3 cards render.
  4. Admin clicks "Copiar contenido" on a card → detail fetch → clipboard write → "¡Copiado!" appears.
  5. Admin clicks "Descargar .md" → Blob download triggers.
  6. Admin clicks "Vista previa" → inline `<pre>` block expands; "Ocultar" collapses it.
- **Branches:**
  - [Tab hidden] When `proposal.status === 'draft'`, the tab is not rendered.
  - [Proposal documents sub-section] `ProposalDocumentsTab` (contract, generated PDFs) is only shown within this tab for `negotiating|accepted|rejected` — not for `sent|viewed`.
- **API:** `GET /api/diagnostic-templates/` (list), `GET /api/diagnostic-templates/:slug/` (detail + content_markdown)
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-diagnostic-templates.spec.js`
- **Unit Tests:** `frontend/test/components/ProposalDiagnosticTemplatesSection.test.js`
- **Backend Tests:** `backend/content/tests/views/test_diagnostic_template_views.py`

### FLOW: `admin-diagnostic-markdown-attachment`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/diagnostics/:id/edit` → Correos tab
- **Description:** When a diagnostic is in `negotiating` status, a "Crear documento desde markdown" button appears in the Correos tab of the diagnostic edit page. Admin uses it to compose a custom branded PDF (e.g., expanded scope, technical annex, pricing supplement) and attach it to the email composer without uploading a pre-built file.
- **Steps:**
  1. Admin opens a diagnostic in `negotiating` status via `/panel/diagnostics/:id/edit`.
  2. Admin clicks the "Correos" tab.
  3. "Crear documento desde markdown" button is visible.
  4. Admin clicks the button → `MarkdownAttachmentModal` opens.
  5. [Optional] Admin clicks one of the three **Plantillas base** buttons (Diagnóstico de Aplicación / Diagnóstico Técnico / Anexo) → `GET /api/diagnostic-templates/:slug/` fetches the template markdown and writes it to the clipboard; button shows "¡Copiado!" for 2 s. Subsequent clicks reuse an in-memory cache.
  6. Admin fills in the **Título** (text input) and **Contenido en Markdown** (textarea).
  7. Admin optionally unchecks one or more cover toggles (Portada / Subportada / Contraportada).
  8. Admin clicks "Vista previa" → `POST /api/diagnostics/:id/email/markdown-attachment/` fires (FormData with title, markdown, cover booleans).
  9. Backend generates PDF via `DocumentPdfService.generate_from_markdown()` and returns it inline (`Content-Disposition: inline`).
  10. Axios fetches the response as a Blob → `URL.createObjectURL` → `<iframe>` renders the preview.
  11. Admin clicks "Adjuntar" → Blob is converted to a `File` object, emitted via `@attach` → appended to the email composer's attachment list.
  12. Success toast "Adjunto «title.pdf» agregado al correo." appears.
  13. Modal closes automatically.
- **Branches:**
  - [Button absent] When `diagnostic.status !== 'negotiating'`, the button is not rendered.
  - [Preview disabled] "Vista previa" button stays disabled until both title and markdown are non-empty.
  - [Cache reuse] If admin generates a preview, changes nothing, and clicks "Adjuntar", a second POST is skipped — the previously fetched Blob is reused (tracked via `previewSnapshot` vs `currentSnapshot` comparison).
  - [Template fetch error] If `GET /api/diagnostic-templates/:slug/` fails, `error.value` shows "No se pudo copiar la plantilla." and the button re-enables.
- **API:** `POST /api/diagnostics/:id/email/markdown-attachment/`, `GET /api/diagnostic-templates/:slug/`
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-diagnostic-markdown-attachment.spec.js`
- **Unit Tests:** `frontend/test/components/MarkdownAttachmentModal.test.js`
- **Backend Tests:** `backend/content/tests/views/test_diagnostic_email_markdown_attachment.py`

### FLOW: `diagnostic-public-view`

- **Module:** diagnostic
- **Role:** guest (via UUID link in email)
- **Priority:** P1
- **Routes:** `/diagnostic/:uuid`
- **Description:** Client opens the public diagnostic link (no Nuxt global header — `layout: false`) and navigates the 8 JSON-driven section components (Purpose / Radiography / Categories / DeliveryStructure / ExecutiveSummary / Cost / Timeline / Scope). Navigation is via a floating sidebar index (`DiagnosticIndex.vue`) — hamburger toggle top-left, panel slides in with numbered badges and visited checkmarks. Server-side filtering returns only sections whose `visibility ∈ {phase, both}` where `phase = 'final' if final_sent_at else 'initial'`. Per-section dwell time is recorded via `DiagnosticViewEvent` + `DiagnosticSectionView`; the final row is flushed via `navigator.sendBeacon` on tab unload.
- **Steps:**
  1. Client navigates to `/diagnostic/:uuid` (no auth required).
  2. Page fetches GET `/api/diagnostics/public/:uuid/` (auto-increments `view_count`) and generates a client-side `session_id`.
  3. POST `/track/` with `session_id` creates a `DiagnosticViewEvent`.
  4. [Branch: SENT + no `final_sent_at`] — Only `initial`/`both` sections are returned by the API and appear in the sidebar index.
  5. [Branch: SENT + `final_sent_at`] — Sections with `final` visibility (e.g. `executive_summary`) also appear; footer shows accept/reject buttons.
  6. Client opens the sidebar (hamburger button) and clicks a section → sidebar closes, section changes, POST `/track-section/` fires with elapsed seconds.
  7. Client clicks "Aceptar propuesta" → POST `/api/diagnostics/public/:uuid/respond/` with `decision: 'accept'`.
  8. Status transitions to `accepted`; acceptance footer replaces the CTA.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/public/diagnostic-public-view.spec.js` + `e2e/admin/admin-diagnostic-sections.spec.js` (initial-phase visibility filter)


## 7. E2E Coverage Index

| Flow | Module | Priority | Outcomes | expectedSpecs |
|---|---|---|---|---|
| `admin-accounting-ads` | admin | P3 | display,success,error | 2 |
| `admin-accounting-card-catalog` | admin | P2 | display,success,error | 4 |
| `admin-accounting-cards` | admin | P2 | display,success,error | 5 |
| `admin-accounting-collection-create` | admin | P1 | display,failure,error,success | 11 |
| `admin-accounting-collection-detail` | admin | P1 | display,success | — |
| `admin-accounting-collection-grouping` | admin | P2 | display,success,failure | 4 |
| `admin-accounting-collections` | admin | P2 | display,success,failure | 9 |
| `admin-accounting-dashboard` | admin | P1 | display,success | 8 |
| `admin-accounting-empty-state-cta` | admin | P4 | display | 2 |
| `admin-accounting-expenses-crud` | admin | P2 | display,success,error | 4 |
| `admin-accounting-export` | admin | P2 | success | 1 |
| `admin-accounting-filters` | admin | P1 | display,success | 23 |
| `admin-accounting-history` | admin | P2 | display,success | 6 |
| `admin-accounting-history-diagnosis` | admin | P2 | display,success,error | 4 |
| `admin-accounting-history-filters` | admin | P2 | display,success | 7 |
| `admin-accounting-hosting-billing` | admin | P1 | display,success,failure | 3 |
| `admin-accounting-hosting-client` | admin | P1 | display,success,failure | 4 |
| `admin-accounting-hosting-cycles` | admin | P2 | display,success,error,failure | 3 |
| `admin-accounting-hosting-inline-edit` | admin | P3 | — | 0 |
| `admin-accounting-hostings` | admin | P2 | display,success,error | 3 |
| `admin-accounting-income-bulk-settle` | admin | P1 | success,error,failure,display | 8 |
| `admin-accounting-income-client` | admin | P1 | display,success,failure,error | 10 |
| `admin-accounting-income-crud` | admin | P1 | display,success,error,failure | 37 |
| `admin-accounting-income-reminder-mute` | admin | P1 | display,success,error,failure | 6 |
| `admin-accounting-list-error-retry` | admin | P3 | failure,display | 1 |
| `admin-accounting-pocket` | admin | P2 | display,success,error | 6 |
| `admin-accounting-project-bulk-assign` | admin | P1 | success,failure | 3 |
| `admin-accounting-project-coherence` | admin | P1 | success | 1 |
| `admin-accounting-receivables` | admin | P1 | display,success,failure | 11 |
| `admin-accounting-record-history` | admin | P1 | display,success,failure | — |
| `admin-accounting-recurring` | admin | P2 | display,success,error,failure | 27 |
| `admin-accounting-settings` | admin | P2 | display,success,error,failure | 12 |
| `admin-accounting-settings-reset-tabs` | admin | P3 | — | 0 |
| `admin-accounting-statements` | admin | P2 | display,success,error,failure | 9 |
| `admin-accounting-stats-modals` | admin | P2 | display | 1 |
| `admin-additional-modules-catalog` | admin | P1 | success,display,failure | 5 |
| `admin-additional-modules-explainer` | admin | P3 | success | 1 |
| `admin-additional-modules-explainer-visibility` | admin | P2 | success,failure | 2 |
| `admin-additional-modules-manage` | admin | P1 | success,error,failure | 4 |
| `admin-additional-modules-pdf` | admin | P2 | success,failure | 2 |
| `admin-additional-modules-quick-access` | admin | P1 | success,display | 3 |
| `admin-additional-modules-reorder` | admin | P2 | success,failure | 2 |
| `admin-additional-modules-share` | admin | P1 | success,error,failure,display | 4 |
| `admin-additional-modules-share-video` | admin | P2 | success,display | 3 |
| `admin-admin-management` | admin | P3 | display,success,error | 1 |
| `admin-auto-archive-zombie` | admin | P3 | — | 0 |
| `admin-blog-calendar` | admin | P2 | display | 1 |
| `admin-blog-create` | admin | P2 | display,success,error | 1 |
| `admin-blog-create-from-json` | admin | P2 | display,success,error | 1 |
| `admin-blog-delete` | admin | P3 | success | 1 |
| `admin-blog-edit` | admin | P2 | display,success,error | 1 |
| `admin-blog-linkedin-connect` | admin | P2 | display,success,error | 1 |
| `admin-blog-linkedin-publish` | admin | P2 | display,success,failure | 1 |
| `admin-blog-list` | admin | P2 | display | 1 |
| `admin-blog-overdue-detection` | admin | P2 | — | 0 |
| `admin-blog-publish-mode` | admin | P2 | display,success | 1 |
| `admin-calculator-followup-alert` | admin | P2 | — | 0 |
| `admin-client-archived-tab` | admin | P2 | display,success,failure | 1 |
| `admin-client-change-history` | admin | P2 | display,success,failure | — |
| `admin-client-communications` | admin | P1 | display,success,error,failure | 15 |
| `admin-client-create-standalone` | admin | P2 | success,error | 1 |
| `admin-client-delete-orphan` | admin | P2 | display,success | 1 |
| `admin-client-delete-protected` | admin | P2 | error | 1 |
| `admin-client-document-signed-notification` | admin | P2 | — | 0 |
| `admin-client-drag-reassign` | admin | P2 | success,failure | 1 |
| `admin-client-edit` | admin | P2 | display,success,error | 1 |
| `admin-client-email-copy-history` | admin | P2 | display | 1 |
| `admin-client-email-copy-settings` | admin | P1 | display,success,error,failure | 7 |
| `admin-client-email-validated-notification` | admin | P2 | — | 0 |
| `admin-client-first-login-notification` | admin | P2 | — | 0 |
| `admin-clients-config-tab` | admin | P3 | — | 0 |
| `admin-clients-documents-section` | admin | P2 | display,success | 2 |
| `admin-clients-filter-presets` | admin | P2 | display,success | 17 |
| `admin-communication-folders` | admin | P1 | display,success,error,failure | — |
| `admin-daily-pipeline-digest` | admin | P2 | — | 0 |
| `admin-dashboard` | admin | P2 | display | 1 |
| `admin-dashboard-attention-radar` | admin | P1 | display | 2 |
| `admin-dashboard-error-retry` | admin | P1 | failure,display | 1 |
| `admin-dashboard-finance-gate` | admin | P1 | display | 1 |
| `admin-dashboard-pipeline-value` | admin | P2 | display | 2 |
| `admin-dashboard-quick-create` | admin | P3 | display,success | 2 |
| `admin-dashboard-stats-modals` | admin | P2 | display | 1 |
| `admin-defaults-unified` | admin | P2 | success,display | 1 |
| `admin-diagnostic-activity` | admin | P2 | success | 1 |
| `admin-diagnostic-advanced-filters` | admin | P2 | display,success | 1 |
| `admin-diagnostic-analytics` | admin | P2 | display,failure | 2 |
| `admin-diagnostic-attach-from-documents` | admin | P2 | display,success | 1 |
| `admin-diagnostic-bulk-actions` | admin | P2 | success | 1 |
| `admin-diagnostic-confidentiality-download` | admin | P2 | display | 1 |
| `admin-diagnostic-confidentiality-edit` | admin | P2 | success,error | 1 |
| `admin-diagnostic-confidentiality-generate` | admin | P1 | success,error | 1 |
| `admin-diagnostic-create` | admin | P1 | success,error | 3 |
| `admin-diagnostic-defaults-config` | admin | P2 | display,success,error,failure | 1 |
| `admin-diagnostic-delete` | admin | P2 | success | 1 |
| `admin-diagnostic-document-preview` | admin | P3 | — | 0 |
| `admin-diagnostic-documents` | admin | P2 | display,success,error,failure | 1 |
| `admin-diagnostic-edit` | admin | P2 | success,error | 1 |
| `admin-diagnostic-email` | admin | P2 | display,success,error | 1 |
| `admin-diagnostic-engagement-score` | admin | P2 | display | 1 |
| `admin-diagnostic-filters` | admin | P2 | display | 1 |
| `admin-diagnostic-json-export` | admin | P2 | display | 1 |
| `admin-diagnostic-json-import` | admin | P2 | success,error | 1 |
| `admin-diagnostic-list` | admin | P1 | display | 1 |
| `admin-diagnostic-list-error-retry` | admin | P3 | failure,display | 1 |
| `admin-diagnostic-mark-in-analysis` | admin | P1 | success | 1 |
| `admin-diagnostic-markdown-attachment` | admin | P2 | display,success,failure | 1 |
| `admin-diagnostic-prompt` | admin | P2 | success | 1 |
| `admin-diagnostic-sections` | admin | P1 | display,success,failure | 1 |
| `admin-diagnostic-send-final` | admin | P1 | success,error | 2 |
| `admin-diagnostic-send-initial` | admin | P1 | success,error | 1 |
| `admin-discount-analysis-enhanced` | admin | P3 | display | 1 |
| `admin-document-archive` | admin | P2 | success,failure,display | 1 |
| `admin-document-change-history` | admin | P1 | display,success,failure | — |
| `admin-document-create` | admin | P2 | display,success,error,failure | 1 |
| `admin-document-delete` | admin | P2 | success,failure | 1 |
| `admin-document-drag-organize` | admin | P3 | success | 0 |
| `admin-document-duplicate` | admin | P3 | success,failure | 1 |
| `admin-document-edit` | admin | P2 | display,success,error,failure | 2 |
| `admin-document-email-history` | admin | P1 | display | — |
| `admin-document-folder-change-client` | admin | P2 | success,error | 1 |
| `admin-document-folder-hierarchy` | admin | P2 | display | 1 |
| `admin-document-folder-manage` | admin | P2 | success,error,failure | 1 |
| `admin-document-folder-panel-resize` | admin | P3 | display,success | 1 |
| `admin-document-folders` | admin | P2 | display,success | 1 |
| `admin-document-gallery` | admin | P2 | display | 1 |
| `admin-document-list` | admin | P2 | display,success,failure | 1 |
| `admin-document-move-folder` | admin | P1 | display,success,failure | 3 |
| `admin-document-navigation` | admin | P1 | display,success,failure | 1 |
| `admin-document-observation-delete` | admin | P1 | display,success,failure | 1 |
| `admin-document-pdf-download` | admin | P2 | success,failure,display | 1 |
| `admin-document-pdf-preview` | admin | P2 | display | 1 |
| `admin-document-rename` | admin | P2 | success,failure | 1 |
| `admin-document-send-email` | admin | P1 | success,failure | 1 |
| `admin-document-state-filters` | admin | P1 | display,success,failure | 1 |
| `admin-document-state-workflow` | admin | P1 | display,success,error,failure | 1 |
| `admin-document-states-manage` | admin | P1 | display,success,error,failure | 1 |
| `admin-document-thread` | admin | P1 | display,success,error,failure | 1 |
| `admin-document-title-column-resize` | admin | P2 | display,success | 1 |
| `admin-document-unsaved-guard` | admin | P2 | display,success,failure | 1 |
| `admin-email-deliverability` | admin | P3 | display | 1 |
| `admin-email-templates-config` | admin | P2 | display,success,error | 1 |
| `admin-financing-agreement-create` | admin | P1 | display,success,error,failure | 4 |
| `admin-financing-agreement-lifecycle` | admin | P1 | display,success,error,failure | 11 |
| `admin-financing-agreement-second-cycle` | admin | P1 | display,success,error,failure | 5 |
| `admin-financing-distribution` | admin | P1 | display,success,failure | — |
| `admin-financing-explainer` | admin | P3 | success | 1 |
| `admin-financing-explainer-visibility` | admin | P2 | success,failure | 2 |
| `admin-financing-settings` | admin | P1 | display,success,error,failure | 4 |
| `admin-high-engagement-alert` | admin | P2 | — | 0 |
| `admin-hour-packages-config` | admin | P3 | success,error,failure,display | — |
| `admin-hour-packages-create` | admin | P2 | display,success,error | 1 |
| `admin-hour-packages-delete` | admin | P2 | success,failure | 1 |
| `admin-hour-packages-edit` | admin | P2 | display,success,error | 1 |
| `admin-hour-packages-list` | admin | P2 | display | 1 |
| `admin-hour-packages-view-modes` | admin | P3 | — | 0 |
| `admin-impersonate-user` | admin | P2 | success,error | 1 |
| `admin-kanban-tasks` | admin | P2 | display,success,failure | 1 |
| `admin-layout-title-mapping` | admin | P3 | display | 1 |
| `admin-linkedin-module` | admin | P2 | display,success,failure | 1 |
| `admin-linktree-branding` | admin | P2 | success,error,failure,display | — |
| `admin-linktree-templates` | admin | P1 | success,error,failure,display | — |
| `admin-linktrees` | admin | P2 | success,error | 1 |
| `admin-login` | auth | P1 | success,error,failure,display | 1 |
| `admin-mcps` | admin | P2 | display,success,error,failure | 10 |
| `admin-mini-crm-clients` | admin | P2 | display | 3 |
| `admin-monitoring-case-follow-up` | monitoring | P1 | display,success,error,failure | — |
| `admin-monitoring-case-list` | monitoring | P1 | display,success,failure | — |
| `admin-monitoring-case-note` | monitoring | P2 | success,error,failure,display | — |
| `admin-monitoring-reports` | monitoring | P2 | display,success,failure | — |
| `admin-outbound-email-history-attachments` | admin | P1 | display | — |
| `admin-outbound-email-history-body` | admin | P1 | display | 1 |
| `admin-outbound-email-history-filter` | admin | P1 | display | 1 |
| `admin-outbound-email-history-resend` | admin | P1 | success,failure | — |
| `admin-panel-projects` | admin | P1 | display,success,error | 17 |
| `admin-panel-session-expired` | auth | P1 | error | 1 |
| `admin-panel-unsaved-guard` | admin | P2 | display,success,failure | 1 |
| `admin-partnership-legacy-redirects` | admin | P2 | success,error | — |
| `admin-portfolio-create` | admin | P2 | display,success,error | 1 |
| `admin-portfolio-delete` | admin | P2 | display,success | 1 |
| `admin-portfolio-edit` | admin | P2 | display,success,error | 1 |
| `admin-portfolio-list` | admin | P2 | display | 1 |
| `admin-project-access-detail` | admin | P1 | display,failure | — |
| `admin-project-access-field-edit` | admin | P1 | success,error,failure | — |
| `admin-project-access-notes` | admin | P2 | display,success,error,failure | — |
| `admin-project-access-secrets` | admin | P1 | display,success,failure | — |
| `admin-project-brand` | admin | P2 | success,error,failure,display | — |
| `admin-project-change-client` | admin | P2 | display,success | 2 |
| `admin-project-change-history` | admin | P1 | display,success,failure | — |
| `admin-project-fly-create` | admin | P2 | success,error | 4 |
| `admin-project-inline-assign-offer` | admin | P2 | success | 1 |
| `admin-project-lifecycle-states` | admin | P1 | display,success,error,failure | 7 |
| `admin-project-state-catalog` | admin | P1 | display,success,error,failure | 9 |
| `admin-proposal-actions-modal` | admin | P1 | display,success | 1 |
| `admin-proposal-advanced-filters` | admin | P2 | display | 1 |
| `admin-proposal-analytics` | admin | P2 | display | 1 |
| `admin-proposal-attach-from-documents` | admin | P1 | success | 1 |
| `admin-proposal-batch-actions` | admin | P2 | success,display | 1 |
| `admin-proposal-change-history` | admin | P1 | display,success,failure | — |
| `admin-proposal-client-autocomplete` | admin | P1 | display | 1 |
| `admin-proposal-client-no-email` | admin | P2 | success | 1 |
| `admin-proposal-comment` | admin | P3 | success | 1 |
| `admin-proposal-contract-download` | admin | P2 | display | 1 |
| `admin-proposal-contract-edit` | admin | P2 | success | 1 |
| `admin-proposal-contract-generate` | admin | P1 | success | 1 |
| `admin-proposal-contract-terms-visibility` | admin | P2 | success,failure | 1 |
| `admin-proposal-create` | admin | P1 | success,error | 1 |
| `admin-proposal-create-and-send` | admin | P2 | success,error | 1 |
| `admin-proposal-create-from-json` | admin | P1 | success,error | 1 |
| `admin-proposal-create-preview` | admin | P2 | success,display | 1 |
| `admin-proposal-dashboard` | admin | P2 | display | 1 |
| `admin-proposal-dashboard-auto-refresh` | admin | P3 | display | 1 |
| `admin-proposal-defaults-config` | admin | P2 | success,display,failure | 1 |
| `admin-proposal-defaults-slug-pattern` | admin | P2 | success | 1 |
| `admin-proposal-delete` | admin | P2 | success,error | 1 |
| `admin-proposal-delete-from-client` | admin | P2 | success,error | 1 |
| `admin-proposal-dev-checklist` | admin | P3 | — | 0 |
| `admin-proposal-diagnostic-templates` | admin | P2 | display | 1 |
| `admin-proposal-discount-offer-send` | admin | P2 | success,failure | 1 |
| `admin-proposal-document-markdown` | admin | P2 | success,error,failure,display | — |
| `admin-proposal-document-preview` | admin | P3 | display | 1 |
| `admin-proposal-documents-manage` | admin | P2 | success | 1 |
| `admin-proposal-documents-send` | admin | P1 | — | 0 |
| `admin-proposal-duplicate` | admin | P2 | success | 1 |
| `admin-proposal-edit` | admin | P1 | success,error | 1 |
| `admin-proposal-engagement-decay-alert` | admin | P2 | — | 0 |
| `admin-proposal-engagement-score` | admin | P2 | display | 1 |
| `admin-proposal-first-view-retry` | admin | P1 | success,failure | 2 |
| `admin-proposal-formalization-delivery` | admin | P1 | success,error,failure,display | — |
| `admin-proposal-functional-requirements-form` | admin | P1 | success,error | 1 |
| `admin-proposal-functional-requirements-paste` | admin | P1 | success,error | 1 |
| `admin-proposal-hour-rate` | admin | P1 | success,display,failure | 1 |
| `admin-proposal-inline-status-change` | admin | P2 | success,failure | 1 |
| `admin-proposal-json-import-client-picker` | admin | P2 | success | 1 |
| `admin-proposal-json-import-warnings` | admin | P2 | success | 1 |
| `admin-proposal-list` | admin | P1 | display | 1 |
| `admin-proposal-log-activity` | admin | P2 | success,failure,display | 1 |
| `admin-proposal-manual-alerts` | admin | P2 | success | 1 |
| `admin-proposal-metrics-manual` | admin | P3 | display | 1 |
| `admin-proposal-multi-send` | admin | P1 | success,error,failure | 1 |
| `admin-proposal-platform-handoff` | admin | P1 | success,failure | 1 |
| `admin-proposal-post-rejection-revisit` | admin | P2 | — | 0 |
| `admin-proposal-project-schedule` | admin | P1 | success,error | 1 |
| `admin-proposal-prompt` | admin | P3 | success | 1 |
| `admin-proposal-quick-log` | admin | P2 | success | 1 |
| `admin-proposal-quick-send` | admin | P2 | success,failure | 1 |
| `admin-proposal-reopen-from-expired` | admin | P1 | success,error | 1 |
| `admin-proposal-resend` | admin | P2 | success,error,failure | 1 |
| `admin-proposal-scorecard` | admin | P2 | display | 1 |
| `admin-proposal-section-add-delete` | admin | P2 | success,error | 1 |
| `admin-proposal-section-completeness` | admin | P3 | display | 1 |
| `admin-proposal-section-dirty-guard` | admin | P2 | success | 1 |
| `admin-proposal-section-disable` | admin | P2 | success | 1 |
| `admin-proposal-section-edit-form` | admin | P1 | success,error | 1 |
| `admin-proposal-section-edit-paste` | admin | P1 | success,error | 1 |
| `admin-proposal-section-reorder` | admin | P2 | success,failure | 1 |
| `admin-proposal-section-sync` | admin | P2 | success | 1 |
| `admin-proposal-send` | admin | P1 | success,error,failure | 1 |
| `admin-proposal-slug-edit` | admin | P1 | success,error | 1 |
| `admin-proposal-update-client` | admin | P2 | success,error | 1 |
| `admin-proposal-update-from-json` | admin | P2 | success,error | 1 |
| `admin-proposal-win-rate-dashboard` | admin | P2 | display | 1 |
| `admin-proposal-zombie-segment` | admin | P2 | display | 1 |
| `admin-proposals-config-tab` | admin | P3 | — | 0 |
| `admin-pwa-install` | admin | P2 | success,display,failure | — |
| `admin-pwa-offline` | admin | P2 | success,failure | — |
| `admin-qr-cards` | admin | P2 | success | 1 |
| `admin-secure-link-create` | admin | P1 | success,error | — |
| `admin-secure-link-manage` | admin | P1 | success,display | — |
| `admin-seller-inactivity-escalation` | admin | P2 | — | 0 |
| `admin-send-branded-email` | admin | P2 | display,success,failure | 1 |
| `admin-send-proposal-email` | admin | P2 | display,success,failure | 1 |
| `admin-standalone-email-attachments` | admin | P2 | success,error | 1 |
| `admin-standalone-email-composer` | admin | P2 | display,success,failure | 1 |
| `admin-standalone-email-defaults` | admin | P2 | display,success,error | 1 |
| `admin-styleguide` | admin | P3 | display | 1 |
| `admin-task-alert-management` | admin | P1 | display,success,failure | 1 |
| `admin-task-deadline-notification` | admin | P2 | — | 0 |
| `admin-view-map` | admin | P4 | display,success,failure | 1 |
| `admin-whatsapp-suggestion` | admin | P2 | — | 0 |
| `blog-detail` | blog | P2 | display,failure | 1 |
| `blog-list` | blog | P2 | display | 1 |
| `diagnostic-public-dark-mode` | diagnostic | P3 | success | 1 |
| `diagnostic-public-onboarding` | diagnostic | P3 | — | 0 |
| `diagnostic-public-pdf-download` | diagnostic | P2 | success | 1 |
| `diagnostic-public-phase-visibility` | diagnostic | P2 | — | 0 |
| `diagnostic-public-respond` | diagnostic | P1 | success,failure | 1 |
| `diagnostic-public-share` | diagnostic | P2 | success | 1 |
| `diagnostic-public-view` | diagnostic | P1 | display,failure | 2 |
| `layout-footer-navigation` | layout | P3 | success | 1 |
| `layout-icon-interaction-feedback` | layout | P2 | success,failure,display | — |
| `layout-locale-switch` | layout | P2 | success | 1 |
| `layout-navbar-navigation` | layout | P2 | success | 1 |
| `platform-access-view` | platform | P2 | — | 0 |
| `platform-admin-client-detail` | platform | P2 | success,error,failure,display | 1 |
| `platform-admin-client-list` | platform | P2 | success,error,display | 1 |
| `platform-admin-project-create` | platform | P3 | success,error | 1 |
| `platform-bug-reports` | platform | P2 | success,display | 1 |
| `platform-change-requests` | platform | P2 | success,display | 1 |
| `platform-client-document-portal` | platform | P1 | success,display | 1 |
| `platform-client-document-sign` | platform | P1 | success,error | 1 |
| `platform-client-email-validation` | platform | P1 | success,error | 1 |
| `platform-collection-account-detail` | platform | P2 | — | 0 |
| `platform-collection-accounts-list` | platform | P2 | — | 0 |
| `platform-complete-profile` | platform | P1 | success,error | 1 |
| `platform-dashboard` | platform | P2 | — | 0 |
| `platform-deliverable-detail` | platform | P2 | success | 1 |
| `platform-deliverables` | platform | P2 | success,error,display | 1 |
| `platform-hosting-card-delete` | platform | P2 | success,failure | 1 |
| `platform-hosting-card-setup` | platform | P1 | success,error | 1 |
| `platform-hosting-subscription` | platform | P1 | success,error,display | 1 |
| `platform-kanban-board` | platform | P1 | success,display | 1 |
| `platform-kanban-card-comments` | platform | P3 | success,display | 1 |
| `platform-kanban-json-upload` | platform | P2 | success,error,display | 1 |
| `platform-layout-title-mapping` | platform | P3 | display | 1 |
| `platform-legacy-route-redirects` | platform | P2 | success | 1 |
| `platform-login` | platform | P1 | success,error,failure | 1 |
| `platform-notifications` | platform | P2 | success,display | 1 |
| `platform-password-reset` | platform | P1 | success,error | 1 |
| `platform-profile-avatar-picker` | platform | P2 | success | 1 |
| `platform-profile-edit` | platform | P2 | success,error,display | 1 |
| `platform-project-access-detail` | platform | P1 | display,success,error,failure | — |
| `platform-project-collection-accounts` | platform | P2 | display | 1 |
| `platform-project-data-model` | platform | P2 | success,error,display | 1 |
| `platform-project-detail` | platform | P2 | success,display | 1 |
| `platform-project-list` | platform | P2 | success,display | 1 |
| `platform-proposal-auto-onboarding` | platform | P1 | — | 0 |
| `platform-requirement-client-review` | platform | P2 | success,display | 1 |
| `platform-sidebar-navigation` | platform | P2 | success,display | 1 |
| `platform-unified-board` | platform | P2 | — | 0 |
| `platform-verify-onboarding` | platform | P1 | success,error | 1 |
| `proposal-calculator-abandonment-tracking` | proposal | P2 | — | 0 |
| `proposal-calculator-behavior-tracking-module` | proposal | P2 | success | 0 |
| `proposal-calculator-biometric-module` | proposal | P2 | display | 1 |
| `proposal-calculator-integrations` | proposal | P2 | success | 1 |
| `proposal-calculator-micro-feedback` | proposal | P2 | display | 1 |
| `proposal-calculator-modules` | proposal | P1 | success | 1 |
| `proposal-calculator-new-modules` | proposal | P2 | success | 1 |
| `proposal-calculator-reopen-after-nav` | proposal | P1 | success | 1 |
| `proposal-calculator-selected-first` | proposal | P2 | display | 1 |
| `proposal-calculator-timeline` | proposal | P1 | success | 1 |
| `proposal-closing-contact` | proposal | P2 | display | 1 |
| `proposal-comment-from-closing` | proposal | P2 | success | 1 |
| `proposal-conditional-acceptance` | proposal | P2 | success | 1 |
| `proposal-contract-draft-download` | proposal | P2 | success | 1 |
| `proposal-contract-terms` | proposal | P1 | display,success,error,failure | 1 |
| `proposal-countdown-realtime` | proposal | P3 | display | 1 |
| `proposal-discount-multi-section` | proposal | P2 | display | 1 |
| `proposal-download-pdf` | proposal | P2 | success | 1 |
| `proposal-engagement-tracking` | proposal | P2 | success | 1 |
| `proposal-executive-to-detailed` | proposal | P2 | display | 1 |
| `proposal-expired-graceful` | proposal | P1 | failure | 1 |
| `proposal-functional-requirements-modal` | proposal | P2 | display | 1 |
| `proposal-hosting-plan-terms` | proposal | P2 | display | 2 |
| `proposal-investment-calculator` | proposal | P1 | success,display | 1 |
| `proposal-kickoff-disclosure` | proposal | P2 | display | 1 |
| `proposal-magic-link-request` | proposal | P1 | success | 1 |
| `proposal-negotiate` | proposal | P1 | success | 1 |
| `proposal-og-meta-personalized` | proposal | P3 | display | 1 |
| `proposal-onboarding-mobile-swipe` | proposal | P3 | display | 1 |
| `proposal-payment-plan-closing` | proposal | P2 | display | 1 |
| `proposal-post-acceptance-welcome` | proposal | P1 | display | 1 |
| `proposal-pre-expiration-discount-suggestion` | admin | P2 | — | 0 |
| `proposal-process-methodology` | proposal | P2 | display | 1 |
| `proposal-rejection-optional-reason` | proposal | P2 | success | 1 |
| `proposal-rejection-smart-recovery` | proposal | P2 | display | 1 |
| `proposal-resolved-notice-suppression` | proposal | P2 | display | 1 |
| `proposal-respond` | proposal | P1 | success | 1 |
| `proposal-roi-projection` | proposal | P1 | display | 1 |
| `proposal-schedule-followup-reminder` | proposal | P2 | success | 1 |
| `proposal-section-onboarding` | proposal | P3 | success | 1 |
| `proposal-share` | proposal | P2 | success | 1 |
| `proposal-slug-access` | proposal | P1 | display,failure | 3 |
| `proposal-sticky-bar-accept` | proposal | P2 | — | 0 |
| `proposal-structured-negotiation` | proposal | P2 | success | 1 |
| `proposal-summary-kpis` | proposal | P2 | display | 1 |
| `proposal-technical-view` | proposal | P2 | display,success | 1 |
| `proposal-value-added-modules` | proposal | P2 | display | 1 |
| `proposal-view` | proposal | P1 | display,failure | 1 |
| `proposal-view-navigation` | proposal | P1 | display | 1 |
| `proposal-view-onboarding` | proposal | P3 | display | 1 |
| `proposal-view-paste-rendering` | proposal | P2 | display | 1 |
| `proposal-welcome-back` | proposal | P2 | success,display | 1 |
| `public-about-us` | public | P3 | — | 0 |
| `public-additional-modules-catalog` | public | P1 | success,display,failure | 5 |
| `public-additional-modules-detail` | public | P1 | success | 1 |
| `public-additional-modules-explainer` | public | P2 | display,success,failure | 6 |
| `public-additional-modules-guide` | public | P2 | success,display | 2 |
| `public-additional-modules-pdf` | public | P2 | success,failure | 2 |
| `public-additional-modules-share` | public | P1 | success,display,failure | 4 |
| `public-additional-modules-theme` | public | P2 | success,display,failure | 2 |
| `public-contact-submit` | public | P1 | success,error | 1 |
| `public-financing-explainer` | public | P2 | display,success,failure | 4 |
| `public-financing-guide` | public | P2 | success,display | 2 |
| `public-financing-language` | public | P2 | success | — |
| `public-financing-load` | public | P1 | failure,success | — |
| `public-financing-overview` | public | P1 | display | — |
| `public-financing-pdf` | public | P2 | success,failure | — |
| `public-financing-share` | public | P2 | success,failure | — |
| `public-financing-terms` | public | P2 | success | — |
| `public-financing-theme` | public | P2 | success,failure | — |
| `public-home` | public | P1 | display | 1 |
| `public-landing-apps` | public | P3 | display | 1 |
| `public-landing-software` | public | P3 | display | 1 |
| `public-landing-web-design` | public | P2 | display | 1 |
| `public-linktree-view` | public | P2 | success,display,failure | 2 |
| `public-portfolio` | public | P2 | display | 1 |
| `public-portfolio-detail` | public | P2 | display,failure | 1 |
| `public-privacy-policy` | public | P4 | display | 1 |
| `public-route-not-found` | public | P3 | failure | 1 |
| `public-secure-link-create` | public | P1 | success,error | — |
| `public-secure-link-reveal` | public | P1 | success,display,failure | — |
| `public-terms-conditions` | public | P4 | display | 1 |


## Section 23 — Accounting Module (superuser-only) (Jul 2, 2026)

Internal accounting module for the company owners (Gustavo & Carlos). Every subview lives under `/panel/accounting/*` behind the `admin-auth` + `superuser-only` middlewares; the backend enforces `IsSuperUser` on every `/api/accounting/*` endpoint regardless of the UI. Every create/update/delete is audited in `AccountingChangeLog` and emailed to the recipients configured in settings (async via Huey).

### FLOW: `admin-accounting-dashboard`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting`
- **Description:** Annual financial overview fed by `GET /api/accounting/dashboard/?year=`: expected vs liquid income, expenses, expected/liquid utility, pocket balance, per-partner cards, 12-month breakdown, operative cost cards and latest card snapshots. The hero “Utilidad líquida” embeds the former utility-statistics modal as a default-open accordion with evolution, margin and partner tabs; the old “Utilidad por mes” mini-chart and statistics icon/modal are gone. Hero cards align at their natural height so the statistics content no longer leaves a large blank column. Company totals aggregate the company ledger only (personal-ledger records are excluded); the “ProjectApp (Empresa)” card shows the full company ledger, and Gustavo/Carlos cards combine their company participation with their personal ledger. Year selector re-fetches the summary and persists as a query param. The “Evolución” section renders two theme-aware ApexCharts — expected vs liquid vs expenses per month, and card-debt evolution from snapshots — filtered by the year plus a client-side month-range selector; a “Exportar Excel” button downloads the workbook and the Tarjetas table links to card history. The subnav orders Bolsillo second, right after Resumen. The Contabilidad quick-access group links to Cuentas de cobro instead of Ads; Ads remains available in the internal accounting subnav.
- **Steps:**
  1. Superuser opens `/panel/accounting`.
  2. Stat cards render the summary totals; partner cards show Gustavo/Carlos (participation + personal) and ProjectApp (Empresa) company totals.
  3. Monthly table lists the 12 months with a totals row.
  4. The default-open utility accordion exposes evolution, margin and partner views and can be collapsed.
  5. Superuser switches the year → summary re-fetches.
  6. “Nuevo ingreso” opens the income modal from the dashboard.
  7. “Cuentas de cobro” in the accounting quick-access menu opens `/panel/accounting/collections`, and no Ads shortcut is rendered there.
- **Branches:**
  - [Branch A — gating] Staff non-superuser navigating to any `/panel/accounting*` route is redirected to `/panel`; the Accounting sidebar section is hidden.
  - [Success] Superuser uses the accounting quick-access link to reach Cuentas de cobro.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-dashboard.spec.js`

### FLOW: `admin-accounting-receivables`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting`, `/panel/accounting/incomes`
- **Description:** The “Pendiente por cobrar” card is a global, manually curated forecast. Its value is the sum of the original amounts of open expected company incomes that are both selected and green/high. The modal reads `GET /api/accounting/receivables/` and has three tabs: detail and totals grouped by traffic-light state (green/high, orange/medium, red/low and unclassified), a flat selected summary, and candidate management. Candidate management opens grouped by client, can regroup by project or switch to a classic flat list, and shows count, original total, paid amount and open balance for each group. Closing and reopening the modal restores grouped-by-client without persisting the previous presentation. Toggle and color save independently with `PATCH /api/accounting/incomes/:id/update/`: choosing a level never activates the switch. A soft semantic circle accompanies the full level label, and an unassigned level renders a neutral circle with “Sin clasificar”. The same contract appears in the Ingresos list, create/edit form and income detail. The help legend floats inside the modal overlay so it remains fully readable. Closing an income by collecting it fully, writing it off or moving it outside the company ledger removes it from the selection while preserving its last color; existing states are not rewritten.
- **Steps:**
  1. Superuser opens the accounting summary and sees the green selected total on “Pendiente por cobrar”.
  2. Superuser opens the card and reviews totals and rows by state.
  3. Superuser opens “Gestionar candidatos” and sees the rows grouped by client with totals per group.
  4. Superuser can regroup the filtered rows by project or switch to the classic flat list.
  5. Superuser changes a toggle or traffic-light state and the row saves immediately.
  6. Superuser can make the same change directly from an expected row in Ingresos.
- **Branches:**
  - [Display] The modal exposes all three tabs, keeps selected rows without a color under “Sin clasificar”, and renders its help legend above the modal content.
  - [Display] Candidate management defaults to client grouping on every open, supports project grouping and a classic flat list, and recalculates group totals after filtering.
  - [Success] A saved color leaves the manual switch unchanged; only toggling inclusion changes the forecast and its green summary/card.
  - [Failure] A failed load leaves a visible retry action; a failed update preserves the previous row and raises an error notification.
  - [Error n/a] The controls only emit catalog values and booleans, so there is no user-entered validation state; invalid payloads are covered at the serializer/API layer.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-dashboard.spec.js`, `e2e/admin/admin-accounting-incomes.spec.js`

### FLOW: `admin-accounting-stats-modals`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting`
- **Description:** Descriptive-statistics surfaces on the Resumen. “Ingresos líquidos”, “Gastos {year}” and “Deuda tarjetas” remain clickable cards that open StatsModal with their tabbed charts. Utility statistics moved into the “Utilidad líquida” hero as a default-open accordion, so there is no utility statistics icon or modal. All charts share `useChartTheme`, including foreground, legend, tooltip and center-label colors for dark mode. Income/expense views read `GET /api/accounting/stats/?year=` lazily and cache per year; utility and card views compute client-side.
- **Steps:**
  1. Superuser clicks the income, expense or card-debt stat card on the Resumen.
  2. The modal opens; income/expense modals fetch `accounting/stats/` once per year (loading skeleton meanwhile).
  3. Tabs switch between chart views (v-if panels so ApexCharts mounts visible).
  4. Utility tabs are immediately available inside the default-open hero accordion and can be collapsed.
  5. Changing the page year drops the cached stats and the next modal open refetches.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-dashboard.spec.js`

### FLOW: `admin-accounting-income-client`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/incomes`, `/panel/clients`
- **Description:** Each income records the client it came from. The income form carries a searchable client picker (with inline client creation, so an unregistered client never blocks the entry) and an **Origen** control for the business line (desarrollo / hosting / diagnóstico / otro); the client stays **optional**, because a refund or a financial yield legitimately has none. The table shows a **Cliente** column; the filter panel gains **Cliente** (options derived from the loaded rows, plus a "Sin cliente" sentinel) and **Origen**; and a **"Sin cliente"** builtin tab isolates the rows still to complete. Those are completed in bulk from the shared `ClientBulkAssignBar` — the same component `/panel/accounting/hostings` uses, so the two views cannot drift apart. Checkboxes select rows (or every filtered row at once). The bulk bar holds only the selection count and one **[Acciones]** menu; **"Asignar cliente"** opens `BulkAssignModal` (picker + live plan + a confirm gated with the reason on the line beside it, while no client is picked — an empty picker no longer means unlink), and **"Desvincular cliente"** only appears in the menu when a selected row actually has a client. The menu opens upward (the bar is sticky at the bottom) and separates linking from collecting with a divider. Either way the scope is named *before* anything is written — how many rows gain a client, how many change one and **from which client**, the rows already on the target that will not move, and the full scrollable list of affected records. Only the rows that actually change travel in `POST /api/accounting/incomes/bulk-assign-client/` (one audit entry per income), and the toast afterwards reports how many the server really wrote. **"Totales por cliente"** opens a read-only modal breaking the FILTERED incomes into billed / collected / pending / weight per client with a totals row — the period is whatever the active filters say. Settling an income carries its client and origin into the liquid child and the follow-up expected records, and a client holding incomes can no longer be deleted (`client_has_incomes`, same guard family as proposals/projects/diagnostics). (Ago 2026) The list also renders **agrupada por cliente**: the backend setting `income_default_view_mode` (card "Vista de ingresos" in Configuración, default `grouped`) decides the landing mode on **every** visit; the in-page **Agrupado/Clásico** segmented toggle lasts only the session — deliberately unlike recurrentes' localStorage. The grouped table (`IncomeGroupedTable`, subgrid clone of the recurrentes one without drag) groups the WHOLE filtered set via `groupByClient` — per-client collapsible headers, a trailing "Sin cliente" bucket flagged "por completar", billed/collected/pending footer totals, and the row actions (liquidar, cuenta de cobro, write-off) intact; pagination stays classic-only, while sorting is shared: **Mes** opens newest-first and toggles oldest/newest; **Total** cycles highest/lowest/default Mes order. In grouped mode the selected order applies inside each client group without changing the billed-desc group ranking or the trailing "Sin cliente" bucket. The active sort survives filters, quick tabs, view changes and later visits through browser storage. (Ago 2026) Cada encabezado **se lee como una unidad al inicio de la fila**: nombre del cliente con sus `(N)` registros y, a continuación y pegados a él, Facturado, Pendiente y Participación en lo facturado, cada uno en su propio bloque con la etiqueta encima del valor (en cuerpo menor y color secundario, así que el nombre conserva el peso visual). Ese bloque de dos líneas es lo que volvió legibles las cifras; **repartirlas a lo ancho de la fila quedó probado y descartado**, porque en una tabla ancha terminan tan lejos del nombre que vuelven a leerse como columnas de otra cosa. La separación entre los tres bloques es uniforme y compacta, sin separadores —cada bloque ya trae su etiqueta—, y el nombre con su conteo va centrado verticalmente contra los bloques de dos líneas. Un nombre largo cede espacio y elipsiza en vez de empujar una cifra fuera de la fila o partirla; los importes nunca se comprimen. El pie recibe el mismo tratamiento, así que la tabla se lee igual de arriba a abajo —conserva el orden Facturado · Pendiente · Cobrado—, a costa, a propósito, de la alineación vertical entre filas: cada nombre mide distinto. Los dos importes se pintan **siempre, el cero incluido** (misma regla que el pie y el modal de totales), la etiqueta del porcentaje dice qué ES la cifra (la parte del grupo dentro de lo facturado, no cuánto del grupo está facturado), y bajo `sm` los bloques bajan **juntos** a una segunda línea bajo el nombre, sin estirarse ni cortarse. Mismo tratamiento en el encabezado de grupo de recurrentes, el único otro con totales —que además estrena la misma redacción en su porcentaje, “Participación en pagos activos”—, y el modal de totales por cliente acota el nombre para que no parta los importes. (Ago 2026) **La selección múltiple ya vive también en la agrupada** — que es justamente donde se ve el bucket "Sin cliente", los candidatos naturales de la asignación masiva: checkbox por fila, checkbox por grupo (marca/limpia todo el cliente, con estado **indeterminado** mientras sólo va parte) y un "seleccionar todos" en la cabecera que abarca **todos los grupos**; como esta vista no pagina, eso es exactamente el conjunto filtrado. Un grupo colapsado declara cuántos de sus ingresos siguen seleccionados (siguen contando para la acción masiva), la selección la guarda la página y por eso **sobrevive al alternar Agrupado ↔ Clásico**, y la misma `ClientBulkAssignBar` —ahora **sticky abajo**, tanto aquí como en hostings, porque la lista agrupada puede ser larga— ofrece las mismas acciones desde su menú y avisa `· N fuera del filtro actual` cuando parte de lo seleccionado dejó de pasar los filtros: la acción los incluye igual y la confirmación los lista uno por uno. A **"Sin cliente"** KPI card (`without_client_count`, whole filtered set — legacy rows in past years included) surfaces the completion debt, the search box also matches the linked client's name/company (`q` server-side too), reassigning an expected's client **cascades to its settled liquids** (update + bulk paths, one audit row per child), creating a cuenta de cobro adopts the client on an orphan income or rejects a mismatched one, and each unassigned row in the classic table wears the **"sin vincular"** pill (mirror of hostings; the grouped bucket already carries its flag). Sibling fix on hostings: reassigning a hosting's client refreshes the billing snapshot (serializer + bulk paths — a stale `client_email` routed the cuenta to the previous client's inbox), with same-request overrides winning.
- **Steps:**
  1. Superuser creates or edits an income and picks its client and origin (or creates the client inline).
  2. The Cliente column and the Cliente/Origen filters read the ledger by client; the "Sin cliente" tab lists what is still unassigned.
  3. Selecting rows reveals the bulk bar. "Asignar cliente" stays off until a client is picked, with the reason on screen; "Desvincular cliente" only shows up when the selection has a client to lose.
  4. Either action confirms first: the modal breaks the selection into what gains a client, what changes one and from whom, and lists every affected record. On open it focuses the search input and immediately shows a permanent in-flow catalog — no click or typing is required. The name header toggles A-Z/Z-A and remembers that choice between openings; typing filters the visible rows, later pages load progressively inside the catalog, and an empty catalog or unmatched filter offers inline client creation. Every row identifies the client by name, company and email and flags missing email. At least five complete rows are visible; a long catalog owns the only scrollbar while the modal and its four-row review stay still. On a compact viewport the modal fills the screen. Cancelling writes nothing.
  5. On confirm only the rows that change are sent, and the toast reports how many the server actually modified.
  6. "Totales por cliente" answers how much each client was billed and how much is still pending, over the filtered set.
- **Error cases:**
  - [No client picked] "Asignar cliente" is disabled and the bar reads "Elige un cliente para poder asignar." — no request leaves the page.
  - [Selection already on the target] "Asignar cliente" is disabled with "Todo lo seleccionado ya tiene a {cliente}."
  - [Nothing linked] "Desvincular cliente" is not rendered at all.
  - [Cancelled confirmation] No request fires and the selection survives untouched.
  - [Selected record deleted] (Ago 2026) La selección se reconcilia contra lo que existe de verdad: el id borrado se descarta solo —**sólo ése**, así que de tres seleccionados y uno eliminado quedan dos— el contador y el aviso "· N fuera del filtro actual" se recalculan sobre filas reales, y la barra se oculta sola cuando ya no queda nada que asignar, sin recargar ni pulsar Cancelar. Aplica a cualquier acción que cambie el conjunto, porque la reconciliación cuelga de los datos (`useRowSelection`) y no del handler que los cambió.
  - [Record deleted while the confirmation was open] `POST /api/accounting/incomes/bulk-assign-client/` responde **409 `records_not_found`** nombrando `missing_ids` y **no escribe nada** — una edición masiva se confirma contra un alcance nombrado, así que corre entera o no corre. El panel descarta esos ids de la selección y recarga la lista.
- **Coverage:** ✅ Covered (client column + Sin cliente tab, bulk assignment confirming the scope before the payload, permanent catalog visible without typing, persisted A-Z/Z-A order, filtering and progressive loading inside the list-only scroll, five complete client rows, four-row review visible at once, full-screen compact modal, the disabled-assign guard, the unlink action sending only the linked rows, totals modal breakdown, grouped landing mode dictated by the backend setting, Mes/Total sorting within each group with browser persistence, session-only toggle back to classic writing nothing, la selección depurándose tras un borrado —clásica, agrupada y tras "Seleccionar los N filtrados"— y el 409 reconciliando)
- **E2E Spec:** `e2e/admin/admin-accounting-incomes.spec.js`

### FLOW: `admin-accounting-income-crud`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/incomes`
- **Description:** Income records (expected vs liquid) with editable 50/50 partner split and a ledger selector ("Contabilidad": Empresa / Personal Gustavo / Personal Carlos). Personal-ledger records belong 100% to their owner and are excluded from company totals. Expected company rows expose a “Previsión” column with an independent candidate toggle and green/high, orange/medium or red/low confidence selector; changing the color never activates the toggle. A semantic circle accompanies the complete label in the list, forecast modal, create/edit form and income detail, with a neutral “Sin clasificar” state. Duplicating always clears both forecast fields. Modal create/edit, ConfirmModal delete, notify toasts, and automatic pocket-movement sync for liquid incomes bound to the ProjectApp pocket (company ledger only). Its indicator cards use the shared fixed label/value/reserved-support structure, so all heights match, and every visible card has contextual help plus an explicit filtering action. Since Aug 2026 the list lands on the builtin "Solo esperados" tab instead of "Todas", and the ledger has no column of its own (it stays a filter). The list opens ordered by **Mes**, newest first; Mes toggles newest/oldest and **Total** cycles highest/lowest/default Mes order. The active order survives filters, quick tabs, Agrupado/Clásico changes and later visits through browser storage. The form also carries the client and origin fields — see `admin-accounting-income-client`.
- **Responsive contract:** En 412 px y 835 px la cabecera muestra exactamente dos resúmenes — **Resultado anual** y **Detalle operativo** — y sus drawers conservan las siete preguntas originales (esperado, líquido, perdido, mes actual, principal origen, sin cliente y sin proyecto). La primera fila queda dentro de la pantalla inicial del teléfono. Desde 1195 px se muestran cuatro tarjetas detalladas. Los cinco anchos de referencia verifican cantidad, alturas parejas y acceso al detalle.
- **Steps:**
  1. Superuser opens the incomes list, which opens already narrowed to the uncollected expected rows (kind badge, collection badge, month, totals per partner), and may activate an indicator to apply its year/month/kind/search/missing-relation filter.
  2. "Nuevo ingreso" opens the modal; PartnerSplitInput defaults to an exact 50/50 of the total, and the period field (shared PeriodDateField) defaults to today's exact date with a toggle down to month-only. Edits always open in full-date mode showing the stored day (01 remains the month-only storage sentinel; the toggle still downgrades to month). (Ago 2026) With **Origen Hosting** the single date swaps for the period the income covers: inicio (same exact-day toggle), fin and a **Periodicidad** selector reusing the recurring-payments catalog. The block is laid out in the order it is filled — **Periodicidad** rides in the top row beside **Tipo**, because how often is decided before the dates it proposes, and **inicio** and **fin** share the row below so the range reads left to right instead of splitting into two loose dates; the exact-day toggle sits under inicio, the date it applies to, and the cadence shortcuts under both. Its hint says what the control does for the operator ("Al elegirla se calcula la fecha de fin del período") rather than where the catalog came from. Picking a cadence recomputes on the spot: it writes the inclusive end — inicio + cadence − 1 day, day clamped like `add_months` — and, with no inicio yet, opens the window on the period after the last one recorded. `GET /api/accounting/incomes/period-suggestion/` resolves that antecedent by client, narrowed by project (an income has no FK to a hosting, so `origin` is only a label), and the inicio field says which period this one follows; a client's first charge falls back to today, and a client holding several active hostings with no project to tell them apart gets no proposal rather than a guessed one. Moving inicio carries fin with it keeping the cadence, and writing fin by hand turns the cadence to **Personalizada** instead of leaving the selector claiming a length the window no longer has; under "Personalizada" both dates are handwritten and nothing recomputes. The recompute watches the values rather than the keystrokes, so it also fires when inicio is written programmatically — switching the origin, or a shortcut — which is where the first delivery silently did nothing. The three fields are required for hosting (legacy rows complete their period on first edit; the backend derives `period_date` from the inicio so orderings and KPIs keep one axis), fin must come after inicio — refused inline under the field before the submit, not only by the serializer — and other origins keep the single date, clearing any stray window. Switching the origin still keeps everything typed, with one correction: a create's untouched "today" default is boilerplate, not an answer, so it no longer carries into the window, which is what lets the antecedent fill it. The recorded window pre-fills the cuenta de cobro's "Período facturado" and appends three columns to the income export.
  3. Submit POSTs `/api/accounting/incomes/create/` → success toast + audit + email.
  4. Row edit prefills the modal and PATCHes `.../update/`.
  5. Row delete asks for confirmation and DELETEs `.../delete/`.
  6. An expected row shows its fulfilment state in its own "Cobro" column, computed from the liquid records linked to it: Pagado (light-green row), Parcial (amber row + the outstanding amount inline) or Pendiente (untinted, "—"). Its “Previsión” column allows immediate candidate and traffic-light changes as independent actions; choosing a color preserves the switch. The same pair is editable in the income form and readable in detail. Non-expected rows do not expose an active control, while a closed row can retain its historical classification.
  7. "Liquidar" on an expected row opens a modal prefilled with the pending amount; the destination defaults to Bolsillo ProjectApp (Socios is the explicit choice) and the payment period asks for the exact date by default, prefilled with today (the "Registrar el día exacto de pago" toggle downgrades the input to month-only when only the month is known). Submitting POSTs `/api/accounting/incomes/:id/settle/`, which registers a liquid record with `expected_income` set. The expected row is kept, so the projection and partial payments both survive.
  8. If the amount received is below the pending balance, the modal reveals "Saldo por resolver" with a live remaining counter and two collapsible, repeatable groups (a fixed hint under the pending block announces the mechanism at open, and the deductions group auto-expands once per open the moment the shortfall appears — an untouched auto-added row neither blocks the submit nor reaches the payload, so leaving the balance pending stays one click). "No es un cobro pendiente, es un gasto" books the shortfall as an expense with its concept (Comisión plataforma de pago / Comisión bancaria / Retención en la fuente / Otro, the last one requiring free text). "Sí lo voy a cobrar: crear ingreso esperado" reschedules it as one or more new expected incomes inheriting the parent's ledger, destination and partner ratio. Both can be combined in one settlement. Since Aug 2026 the amount received may be 0 as long as the shortfall is fully allocated: a residual-only settlement that creates no liquid record and sends no payment email — the rescue path for old partial collections whose fee-sized residual would otherwise stay "Parcial" forever (also scriptable via the `resolve_income_residual` management command).
  9. "Marcar como perdido" writes the row off (PATCH `kind=lost`) after a ConfirmModal.
  10. "Duplicar" — offered on every row whatever its state, and in the income detail modal — GETs `/api/accounting/incomes/:id/duplicate-draft/` and opens the form seeded with the original's concept, amounts, split, ledger, client, project, origin and notes, always as "Esperado". It writes nothing: confirming goes through the ordinary create POST, which flashes the new row and announces it as "Ingreso duplicado" so it reads apart from a manual alta. While the draft is in flight the row's three-dots button spins and refuses a second click, since the action menu closes the moment it is clicked. (Ago 2026) The rule behind that list is that **the fields governing the shape of the form are always inherited** — `origin` (single date or covered window), `ledger` (partner split or single value) and `period_cadence` (the length of the window) — unless the intent of the action overrides them, and `kind` and `destination` are the two declared overrides. They are the ones that go unnoticed when the copied fields are enumerated and the ones that break the loudest when they are missing: the form opens configured for a different kind of income than the one being copied. The copy stays faithful rather than helpful: an original with no `origin` — most of the book, which predates the field — duplicates into a form with no origin, and a `BaseAlert` under the Origen control says exactly that ("El ingreso original no tiene origen registrado…") instead of letting a blank that explains nothing read as a copy that failed.
  11. The duplicate's date is the one field that is never copied. When the hosting behind the income resolves unambiguously the draft proposes the next cycle and labels it under the field; otherwise the field opens empty and its `required` blocks the save. Because most of the book carries no `origin` and no client, that lookup resolves for almost nothing, so the form also offers cadence shortcuts — "+1 mes", "+3 meses", "+6 meses", "+1 año" — computed server-side from the original's date (`add_months`, which clamps the day). Picking one fills the field, marks itself pressed, writes in month granularity when the exact-day toggle is off, and overrides the hosting proposal when the two disagree. (Ago 2026) On a **hosting** form the shortcuts stop being a second mechanism: they set the Periodicidad selector and the inclusive fin follows, and they are offered whenever a period is being **opened** — creating or duplicating — but never while editing one already on the book, since a charge already recorded should not change period on one click. Each shortcut anchors on the antecedent, not on what the form currently shows: the client's last recorded fin when creating, and the draft's `period_anchor` when duplicating. That is what makes "+1 año" then "+1 mes" re-lengthen the same window instead of walking a period further forward on every click, and their pressed state reads back from cadence and inicio together, so a window the operator has since moved stops claiming to be the one the button opens. (Ago 2026) **A duplicate counts from the record it copies, never from today.** The draft states what it counted off and the form anchors its own arithmetic there, in three grounds. A recorded window proposes inicio = day after the recorded fin with the cadence's own length ("income_period"; "Personalizada" repeats the recorded duration); a legacy row whose client resolves to a single active hosting falls back to the catalog ("hosting_cycle"). Both fix the inicio, so changing the periodicidad in the modal only moves the fin. When the original has neither — no window, and several active hostings with no project to tell them apart, which is the majority of the book until it is completed — the anchor is the original's own **fecha** ("original_date"). Nothing is prefilled there, because only the cadence can state how long that period lasted: picking one opens the window where that period would have closed, `fecha del original + periodicidad`, the same count the "+N meses" shortcuts already made server-side. That anchor floats — another periodicidad moves the whole window, since the fin it counts from is precisely what was never recorded — while an inicio written by hand is never moved by a later cadence. A `BaseAlert` over the block says which of the three grounds it was and names the dates, because a date that appears on its own cannot be told apart from a guess. Today is reached only when the original carries no fecha either, and the notice says so: the range chains with nothing.
- **Branches:**
  - [Branch A] Manual split: turning off the 50/50 toggle allows custom per-partner amounts (sum must not exceed the total; backend validates too).
  - [Branch B] Backend 400 → error toast with the Spanish backend message; modal stays open.
  - [Branch C] Personal ledger: selecting "Personal Gustavo/Carlos" hides the partner split and the pocket destination, shows a single "Valor" field, and the backend normalizes the split to the owner (pocket destination rejected).
  - [Branch D] Partial payment: liquidating for less than the pending amount leaves the expected row Parcial; liquidating again accumulates against the same parent.
  - [Branch E] Write-off is not offered once a row has liquidations — the backend rejects it, because it would drop the full expected amount while its liquid children keep counting. The remainder is registered as a separate lost record instead.
  - [Branch F] Written-off rows drop out of the expected projection and the utility but stay visible (and searchable/exportable) under "Todos"; a builtin "Perdidos" quick tab (never persisted server-side, no rename/delete menu) isolates them with one click, alongside the "Pérdidas" segment in the filter panel, the "Total perdido" chip and the "Perdido (año)" KPI. (Until Jul 2026 they were hidden from the Todos working set and the export.)
  - [Branch I] Three builtin tabs ship with the view: "Solo esperados" (`kind=expected` + `paymentStatus=pending`, the landing tab), "Hosting esperados" (the same plus the search term `hosting`, which seeds the search box) and "Perdidos". Being builtin they never drift: editing a filter under them stays local instead of rewriting the tab, which is why the landing tab is not a seeded saved one (migration `accounts/0043` retired the saved "Solo esperados"). `?accounting_incomeTab=all` is the way to open the full list, and picking any non-default tab writes its id into that query param, so a reload keeps the chosen view.
  - [Branch G] Settlement allocation: whatever is moved out of the expected record (deductions + follow-up incomes) is subtracted from its total, so it closes with no orphan balance. Anything left unallocated simply stays pending, exactly as before — the modal says so instead of leaving it silent. Over-allocating past the shortfall disables the submit, and the backend rejects it too with a Spanish 400.
  - [Branch H] A settlement deduction is an `ExpenseRecord` flagged with `deduction_type` and linked to its origin via `source_income` (migration `content/0173` backfilled the link from the `income:<pk>:settlement` stamp and re-grossed the parents earlier settlements had netted): it books no pocket movement (the money never entered the pocket), keeps the expected income **gross** and counts as **payment credit** toward it — liquid children + linked deductions add up to the parent's total, so a fee-settled income still reads Pagado. Under the gross convention it **reduces expected utility** like any expense, while liquid utility subtracts only operational spending (the liquid total already arrives net of every fee — subtracting deductions there would double-count). It shows in the Gastos tab with a "Descuento de ingreso" pill whose tooltip names the origin income, filters by "Tipo de deducción" (shared catalog with the liquidation modal) or "Naturaleza", totalizes in the "Deducciones (año)" KPI with a per-type breakdown and in Operativo/Deducciones chips over the filtered rows, exports with "Tipo de deducción" + "Ingreso origen" columns, and is reported apart as `deductions_total` on the accounting dashboard. Deductions are created from Liquidar only: manual writes can neither set nor clear `deduction_type`, and editing one hides the pocket toggle behind a hint.
  - [Branch J] Duplicating (Aug 2026) always produces an **expected** record, whatever the original was — reopening the next period of an already collected hosting is the case it exists for — and never carries what belonged to the original occurrence: settlement links, cuenta de cobro, deductions, history and silenced reminders all stay behind, so the duplicate enters the payment calendar clean. The proposed date is the original's plus one hosting cycle, resolved server-side by matching the client (narrowed by project) among active hostings when the origin is Hosting; an ambiguous or absent match leaves the field empty and its `required` blocks the save until a date is chosen. A failing draft raises "No se pudo preparar el duplicado" and opens no form. (Ago 2026) **Origen is required** on every income the form writes — creating, editing and duplicating alike. `BaseSegmented` carries no native `required`, so the refusal is the form's own ("Elige la línea de negocio del ingreso."), held back until the first submit attempt so a freshly opened form never opens complaining; the write serializer enforces the same rule on create and on any update that writes the field, which is what turns editing a legacy row into the gradual backfill of the book. A partial PATCH that does not touch `origin` leaves the record as unclassified as it was, and settling is exempt on purpose: the liquid child and the rescheduled balance copy the parent's line of business, blank included, since refusing to collect money over a classification would block Liquidar on most of the book.
  - [Branch K] (Ago 2026) Una mutación **refresca en sitio**. Al eliminar, la fila deja su grupo de inmediato y el contador del grupo, el conteo de resultados y los totales de la cabecera (Total esperado / líquido / perdido) se recalculan solos, porque derivan del set filtrado. Dos cosas que hacían que eso *pareciera* una recarga se corrigieron con el mismo cambio, y valen para las seis vistas de contabilidad: las tablas pintan skeleton **sólo cuando todavía no hay nada en pantalla**, no encima de datos ya visibles, y la paginación vuelve a la página 1 cuando cambian los **filtros**, no cada vez que se reconstruyen las filas — borrar una fila desde la página 3 ya no deja al lector en la 1.
- **Coverage:** ✅ Covered — all four outcome classes, including the default and persisted Mes/Total ordering, the five-width indicator header, its filtering actions, the settlement's deduction, follow-up income, over-allocation block and backend rejection, y el borrado recalculando totales sin recargar ni mover la página.
- **E2E Spec:** `e2e/admin/admin-accounting-incomes.spec.js`

### FLOW: `admin-accounting-income-bulk-settle`
- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/accounting/incomes`, `/panel/accounting/pocket`
- **API:** `POST /api/accounting/incomes/bulk-settle/`, `GET /api/accounting/incomes/:id/detail/`, `GET /api/accounting/incomes/`, `GET /api/accounting/pocket/`
- **Description:** Un abono: un solo pago del cliente que cubre varios ingresos esperados con UN único movimiento del bolsillo. Desde la selección múltiple de Ingresos, el menú **[Acciones]** de la barra inferior ofrece "Registrar abono" (solo esperados de la empresa con saldo pendiente; sin elegibles el ítem queda apagado con la razón impresa en el propio ítem —un MenuItem deshabilitado de Headless UI no toma foco ni recibe puntero, así que un tooltip sería inalcanzable—, y una selección parcialmente elegible abre el modal anunciando cuántos quedaron fuera). El modal lista los ingresos del más antiguo al más reciente con su pendiente y el total, prellena el valor con la suma de pendientes, propone el reparto (cada pendiente completo hasta agotar el valor; el último queda parcial) y lo recalcula en vivo hasta la primera edición manual — desde ahí "Recalcular reparto" es el camino de vuelta. El excedente se acepta como saldo a favor del cliente (hijo liquid sin padre sobre el mismo movimiento; se aplica después re-apuntando su `expected_income`), por lo que un excedente con clientes mezclados bloquea. Al confirmar, el backend crea UN `PocketMovement` + un hijo liquid por imputación compartiéndolo — el hijo ES el valor imputado por par, así que la columna Cobro, el filtro `payment_status` y los KPIs siguen derivando igual. Borrar el movimiento revierte el abono completo; borrar o redimensionar un hijo compartido se rechaza. En el Bolsillo, el movimiento de un abono muestra "Abono · N ingresos" y abre el reparto read-only. Y desde el ingreso: el detalle nombra el movimiento detrás de cada liquidación — el nacido de un abono compartido se rotula "Abono" y ofrece "Abono · N ingresos", que abre ese mismo reparto (con las hermanas) apilado sobre el detalle, que mientras tanto deja de responder a Esc y al backdrop; un movimiento 1:1 se nombra como texto y una liquidación que nunca pasó por el bolsillo muestra una raya.
- **Steps:** seleccionar esperados → Registrar abono → revisar/ajustar el reparto → confirmar → filas Pagado/Parcial en la lista, un movimiento en el bolsillo.
- **Branches:** el reparto se consulta también desde el ingreso; valor menor deja el último parcial; valor exacto cubre todo sin tipear; excedente anuncia el saldo a favor; excedente con mezcla de clientes bloquea; 400 del backend deja el modal abierto; el reparto se consulta desde el movimiento del bolsillo.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-income-bulk-settle.spec.js`

### FLOW: `admin-accounting-filters`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/incomes` (same pattern across subviews)
- **Description:** Client-side dynamic filters via `useAccountingFilters`: period date range, amount min/max, kind segmented, collection on incomes ("Cobro": Todos/Sin pagos/Parcial/Pagado, matching the row's payment badge), partner segmented (Gustavo/Carlos/ProjectApp), ledger segmented ("Contabilidad": Todas/Empresa/Personal Gustavo/Personal Carlos), debounced free search, active-count badge, reset and saved filter tabs per view (incomes ships "Todos los esperados" among its seeded defaults; the uncollected cut and its hosting variant are builtin tabs instead, the first of them the view's landing tab). The revamped panel adds live-updating range dropdowns (debounced typing, no blur needed), removable applied-filter chips (one per value, plus a search chip), a filtered results counter visible even with the panel closed, `<mark>` highlighting of search occurrences in table text cells, and column sorting (asc/desc/off) on key columns of every list. Since Aug 2026 every saved tab (all five panel views with tabs) carries a `base_filters` restore point: filter edits under an active tab still auto-save into the tab, but once its live filters drift from the base the tab shows a '•' dot (semantic comparison — inactive keys ignored) and its context menu adds "Restaurar filtros" (PATCH filters back to the definition; reloads the panel when the tab is active) and "Fijar como base" (re-baseline to the current filters). Migration `accounts/0042` backfilled bases from the seed registry, so a drifted saved tab recovers its seeded definition on restore. Since Aug 2026 **every dimension takes several values at once** (`BaseSegmentedMulti`, a `role="group"` of `aria-pressed` toggles rather than a tablist): values inside one dimension are OR'd, dimensions are AND'd, a hint line in the panel says so, and "Todos" is the shortcut that CLEARS the dimension instead of being a value in it. The applied-filter chip carries one entry per dimension listing the values chosen in it ("Cobro: Sin pagos, Parcial"), each with its own ⨯ so one value can go without dismantling the cut — a dimension with a single value still reads exactly as before. The landing tab was the motivating bug: "Solo esperados" meant *expected + sin pagos*, so an expected income that had received an abono silently vanished from the one view that promises everything still uncollected; it is now **"Esperados por cobrar"** (`pending` + `partial`), keeping its `expected-pending` id so old links hold. Collections' "Por cobrar" had the same defect against `overdue` and got the same fix. Incomes also gained per-tab counts and puts its filters in the URL, so a multi-value cut can be shared as a link. Server-side, `payment_status` and `partner` accept comma-separated values like every other filter (one shared token parser, with `expected` AND-ed around the OR so liquid and lost rows cannot leak in), and a zero-total expected now reads as `paid` on both sides. Migration `accounts/0051` wrapped the scalars of existing saved tabs — `filters` and `base_filters` both, or the drift dot would light up on every seeded tab.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-filters.spec.js`

### FLOW: `admin-accounting-expenses-crud`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/expenses`
- **Description:** Expense records with category (Negocio/Personal) and ledger selector ("Contabilidad": Empresa / Personal Gustavo / Personal Carlos — personal expenses hide the split, use a single "Valor" field and are excluded from company totals) and partner split; same modal CRUD + filters pattern as incomes. Money inputs live-format es-CO thousands (BaseCurrencyInput). Since Jul 2026 the modal has a "Registrar egreso en bolsillo" toggle (on by default): when on, the new expense creates a linked pocket OUT movement (bidirectional sync via `accounting_service`) and edits/deletes mirror/cascade into it; when off (paper adjustments, personal expenses that never touched the company pocket) no movement is created. A personal-ledger expense with the toggle on is stored as a company draw (ledger company, full split to the owner — the modal shows a warning hint), since money out of the pocket must count against company utility. On edit the toggle prefills from the linkage and can link/unlink deliberately; a partial update without the flag preserves the current state, so historical expenses never gain a movement silently. Since Aug 2026 the period field (shared PeriodDateField) captures the exact date by default ("Fecha", prefilled with today) with a toggle down to month-only ("Mes"); edits always open in full-date mode showing the stored day (01 for month-only records; the toggle still downgrades to month) and the backend renders full dates as "17 Julio 2026".
- **Coverage:** ✅ Covered — display, success and error (backend 400 keeps the modal open with the Spanish toast).
- **E2E Spec:** `e2e/admin/admin-accounting-expenses-hostings.spec.js`

### FLOW: `admin-accounting-hostings`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`
- **Description:** Client hosting registry: monthly value, payment modality, validity and billing contact, with KPI cards and modal CRUD. New records offer exactly quarterly, semiannual and every-9-month modalities; `payment_per_cycle` is derived from the monthly value. Legacy monthly/annual rows remain readable as historical values but cannot be selected for new records. Estado is inline; ciclos/total pagado are read-only and computed from cycle history. Cliente and Proyecto remain separate linked columns.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-expenses-hostings.spec.js`

### FLOW: `admin-accounting-pocket`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/pocket`
- **Description:** ProjectApp pocket ledger with balance card and running-balance column (default view newest-first; the balance is computed chronologically). The pocket is the money entry point (Jul 2026): creating a movement also creates its linked income (IN → liquid/pocket) or expense (OUT). A new movement opens on Egreso, the common case, with every direction-dependent field already in its egreso variant; editing keeps the direction the record has. For IN the "Contabilidad" segmented is company-only; for OUT it is relabeled "Atribuir a" (Empresa/Gustavo/Carlos) because pocket money is company money: every OUT mirrors a company-ledger expense that counts against liquid utility — Empresa splits 50/50, a partner option registers a draw fully assigned to that partner (category personal). Linked movements open the edit modal with the direction locked and the attribution prefilled (derived from the split); edits mirror into the linked record and deleting either side cascades to the other (the delete confirm warns about the cascade). Unlinked historical movements keep plain CRUD and never gain a mirror.
  Desde ago-2026 el panel de filtros expone todos los campos que el formulario captura (el criterio de *insumo*): además de Fecha, Tipo y Valor trae **Atribuir a** (multi Empresa/Gustavo/Carlos sobre el `linked_ledger` derivado del espejo) y **Vínculo** (Todos/Vinculados/Sin vincular sobre `is_auto_managed`, que es la forma de encontrar los movimientos que quedaron sin su registro espejo); los campos de texto libre entran por el buscador, que ahora cubre `notes` además de `concept`. Los dos filtros nuevos existen también en el servidor (un knob `q_filters` en la capa compartida), así que el export CSV y la MCP `list_pocket` cortan las mismas filas que la tabla, y el export ganó las columnas *Atribución* y *Vinculado*. Como el saldo es una acumulación cronológica, se calcula **después** de filtrar: con filtros activos la columna se relabela **Acumulado** y suma sólo las filas visibles, el subtítulo lo aclara, y la tarjeta de saldo —que el servidor calcula siempre sobre todos los movimientos— se rotula "(total, no refleja los filtros)" y suma una línea "N movimientos filtrados · neto X". La tira de pestañas (`ProposalFilterTabs`, el estándar PA-44) trae seis sembradas: Entradas, Salidas, Gustavo, Carlos, Empresa y Sin vincular (la migración `accounts/0050` las backfillea para los usuarios existentes), cada una con su conteo entre paréntesis —el (0) honesto incluido— calculado en el browser con `countTabs`, ya que el dataset completo está en el store; lo que no cabe en la tira colapsa en el menú "+N".
  El contrato responsivo conserva el significado del libro: por debajo de 1024 px el saldo corrido se mueve debajo del valor de cada movimiento en vez de desaparecer; los tabs del módulo y los filtros guardados pasan a selectores. Desde 1024 px regresan las tiras y la columna independiente de saldo. La aceptación automática fija los cinco viewports de referencia (412, 835, 1195, 1440 y 2560 px), comprueba que no haya desborde horizontal y limita el shell general a 1400 px en monitor grande; la certificación física se registra por separado.
- **Coverage:** ⚠️ Partial — modal ledger selector, locked-direction edit, both filter cuts (attribution + link, with the Acumulado relabel), responsive navigation and running-balance representation across the five reference widths are covered; the create-POST payload (ledger included) and the cascade delete confirm are asserted at unit level only.
- **E2E Spec:** `e2e/admin/admin-accounting-pocket-recurring.spec.js`

### FLOW: `admin-accounting-recurring`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/recurring`
- **Description:** Recurring operational costs remain normalized to a monthly denominator, but management now happens from each row. **Vigentes** and **Archivados** are separate scopes. In the current scope an inactive payment remains visible for administration but contributes $0 to the monthly COP/USD KPIs, group subtotals, participation percentages and charts; archived rows also stay out of those budget surfaces and out of upcoming-charge notices. The page states that rule next to the scope switch. Both grouped and classic views place the row's leading three-dots action before drag/data columns: edit; duplicate; activate/deactivate; mute/reactivate reminders; and archive. Duplicate first GETs a non-persisted draft and opens the ordinary create form with name, price, currency, frequency, method, category and billing day inherited; reminder cadence, notes and archive state are cleared, and the reference date is recalculated from the next occurrence rather than copied. Archive deactivates without deleting and moves the row to Archivados; restore returns it as inactive; permanent deletion appears only there and requires typing `ELIMINAR`. Checkboxes enable atomic bulk activate, deactivate and archive; duplicate stays one-at-a-time. The editable category catalog, drag ordering, custom frequencies, currency conversion, classic view and category chart drill-down remain intact. Charts always use the active budget base and no longer offer an inactive-row toggle. Registering the real expense/pocket movement and a charge-history browser are explicitly deferred to the separate feature that makes a recurring definition an accounting origin.

#### Interaction matrix

| Interaction | Outcome | Start → action → observable end state |
|---|---|---|
| Inspect current budget | display | Open Recurrentes through the accounting subnav → current rows render → inactive rows show `Inactivo`, 0% participation and do not inflate KPIs/subtotals. |
| Open row actions | display | Click the leading three-dots button → one menu names the row and exposes every action valid for its lifecycle state. |
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

### FLOW: `admin-accounting-history`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/history`
- **Description:** Read-only audit of the module through two tabs (BaseSegmented). **Cambios:** audit trail (server-paginated 20/page) of every accounting change with entity/action/actor/record/date filters and expandable field-level old→new diffs. **Envíos** (Ago 2026): send log (`GET /api/accounting/email-log/`, 20/page) with one row per destination address — fecha, tipo de aviso, destinatario, asunto y estado — filterable by notice type, status, recipient, subject text, source record, client, project and date range; clicking a failed row expands the delivery error, the records the email was about and any retry link. This is the surface that answers "¿por qué no me llegó ese aviso?" and is scoped to the module's own `template_key`s, so proposal traffic sharing the `EmailLog` table stays out. Both subtabs carry the predefined tab strip and URL-persisted filters (`admin-accounting-history-filters`) and a send row can be read and retried (`admin-accounting-history-diagnosis`).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-ads-history-settings.spec.js`

### FLOW: `admin-accounting-history-filters`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/history`
- **Description:** Finding a send or a change takes one click on a predefined tab or a few filters, instead of scanning the list by eye. Each subtab runs its own `useAccountingFilters` instance (saved-tab views `accounting_history_sends` / `accounting_history_changes`) and, because Historial is the one accounting view that paginates server-side, the filter state is translated into query params by `buildExportParams` rather than filtering loaded rows. Under the filter row sits the strip (`ProposalFilterTabs`, the PA-44 standard): **Fallidos**, **Hoy** and **Últimos 7 días** are builtin — a stored date would freeze on the day it was seeded, and Fallidos has to sit second because it is where anyone goes when a notice did not arrive — while **Recordatorios de cobro**, **Cambios contables** and **Eliminaciones** are seeded rows that Configuración restores. Every tab carries its count, "Todas" and the honest (0) included, from `POST /api/accounting/history/tab-counts/`; the overflow collapses into a "+N" menu that hoists the selected tab back into view.
- **Steps:**
  1. Superuser opens `/panel/accounting/history`; the strip renders with a count per tab and the filter row collapsed behind its toggle.
  2. Clicking a predefined tab narrows the list and stamps both `?<subtab>Tab=` and the filter keys in the URL, so the query can be bookmarked and shared.
  3. Editing the controls under a builtin un-lights the tab; "Limpiar filtros" deselects it and clears the URL.
  4. "+" saves the active combination as an own tab (max 12 per view), which then behaves like any other tab and can be renamed, reordered, hidden or deleted.
  5. Arriving from a hosting, an income or a cuenta de cobro lands with `?tab=sends&entity_type=…&object_id=…` already applied.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-history-filters.spec.js`

### FLOW: `admin-accounting-history-diagnosis`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/history`
- **Description:** The history exists to diagnose, so a row shows what was sent and can send it again. **Ver el correo:** `GET /api/accounting/email-log/<id>/body/` returns the message as delivered (stored once per send in `EmailBody`, shared by the sibling recipient rows) and the panel renders it in a sandboxed `srcdoc` iframe, the same way the composer previews a branded email; sends predating the feature say so instead of opening an empty modal. **Reintentar:** `POST /api/accounting/email-log/<id>/retry/` re-sends to the address on that row and to no one else, only for the notices tied to a single record (`accounting_change`, `collection_account_sent`, `payment_status_team`). The three digests show the button disabled carrying its reason — re-running one would assemble today's summary, not the message that failed. That reason remains reachable through a focusable accessible proxy and one application tooltip, without a duplicate native `title`. The retry lands as a new row linked through `retry_of`, and a retry that fails again reports its cause.
- **Steps:**
  1. Superuser opens the Envíos subtab and clicks the eye on a row → the delivered message opens in a modal.
  2. On a failed row, the retry icon re-sends to that recipient; the list and its counts reload so the new attempt is visible.
  3. A failed digest shows the retry disabled; activating its focusable proxy reveals exactly one tooltip with the reason, and the button has no native `title`. A send that worked offers no retry at all.
  4. Expanding a row names the records the email was about and, when applicable, the send it was a retry of.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-history-filters.spec.js`

### FLOW: `admin-accounting-cards`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/cards`
- **Description:** Weekly credit-card balance snapshots (CardBalanceSnapshot): list with a latest-debt-per-card chip, filters (date range, debt range, card multi-select) and search; modal create (snapshot date defaults to today, card selected from a dropdown fed by the CreditCard catalog — see `admin-accounting-card-catalog`), edit prefill and ConfirmModal delete. Since Jul 2026 the Deuda input is gone: debt is server-computed as cupo − disponible for catalog cards (the form previews it and blocks disponible > cupo); legacy card names outside the catalog stay editable and keep their stored debt. Registering a snapshot dated on/after the cycle Friday silences the weekly card-debt reminder email. The card filter opens preselected with the active catalog cards (removable chips — clearing them surfaces historical card names again), and its options are the union of catalog names and names used by snapshots, so a registered card is filterable before its first snapshot. A saved tab in the URL wins over the preselection.
- **Steps:**
  1. Superuser opens `/panel/accounting/cards` (subnav "Tarjetas" or the dashboard "Ver historial de tarjetas" link). The card filter arrives preselected with the registered (active catalog) cards, shown as removable chips with the filter count at 1; the latest-debt chip covers only those cards.
  2. "Nuevo registro" opens the modal with today's date preselected; superuser picks the card from the catalog dropdown and fills the available amount — the computed debt (cupo − disponible) previews below the input.
  3. Submit POSTs `/api/accounting/card-snapshots/create/` without `debt_amount` (server computes it) → success toast + audit + email.
  4. Row edit prefills the modal (a legacy card name not in the catalog is injected as an extra option) and PATCHes `.../update/`; delete asks for confirmation.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-cards.spec.js`

### FLOW: `admin-accounting-export`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/*` (list views) and `/panel/accounting` (workbook)
- **Description:** Data export: every list view has an "Exportar" dropdown (CSV / Excel .xlsx) calling `GET /api/accounting/export/?section=&file_format=` with the active filters mapped to the server query params (`buildExportParams`), and the dashboard's "Exportar Excel" button downloads the full workbook (Resumen sheet + one sheet per section) from `GET /api/accounting/export/workbook/?year=`. Spanish headers, numeric money cells, filenames stamped with the Bogotá date.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-export.spec.js`

### FLOW: `admin-accounting-settings`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/settings`
- **Description:** (Ago 2026) Notification recipients are an administrable catalog of their own (`content.NotificationRecipient`, `GET/POST/PATCH/DELETE /api/accounting/notification-recipients/`, superuser-only, audited): each row shows the address, whether it is **Activo** or **Pausado** and its **fecha de alta**; adding validates the format and rejects duplicates case-insensitively (`Ese correo ya está en la lista.`) with the error inline under the field; a per-row switch pauses a recipient without deleting it (vacaciones, cambio de responsable); removing asks for confirmation naming the automations that stop arriving. Rows save individually — the page's "Guardar cambios" button governs only the toggles below. **Every automated email of the module** (cambios contables, recordatorio de deuda de tarjetas, recordatorio de extractos, calendario de cobros y pagos, cuentas de cobro y resultados de pago de hosting) resolves its destinations through `active_recipient_emails()` and reaches nobody else — no inbox is hardcoded. The global notifications toggle (`notifications_enabled`) is the master switch that pauses all of it at once without dismantling the list; with it off, or with zero active recipients, the panel says so explicitly in a warning (two distinct messages, so the fix is obvious). Changes are themselves audited, which means adding a recipient sends that address its own "creado" notice — a free delivery check. Also hosts the weekly card-debt reminder toggle (Fridays 9:00 Bogotá via Huey, re-alerts every 2 days until a snapshot dated on/after the cycle Friday exists; the global notifications toggle also gates it), the statement reminder toggle (`statement_reminder_enabled`, Jul 2026: emails every 8 days at 9:05 Bogotá while the previous month's statement of an active catalog card is missing, draft or lacks its PDF), the "Catálogo de tarjetas" section (see `admin-accounting-card-catalog`), the hosting expiry notices toggle (15/7 days before `valid_to`, then every 5 days until la cuenta de cobro is sent), the USD exchange rate (BaseCurrencyInput, min 1) used by the recurring USD KPI, and (Ago 2026) the "Vista de ingresos" segmented control — `income_default_view_mode`, default `grouped`: whether `/panel/accounting/incomes` lands agrupada por cliente or as the classic table on every visit; the in-page toggle is session-only. Cuentas de cobro adds a separate persisted pair: `collection_accounts_view_mode` (`grouped`/`classic`) and `collection_accounts_group_by` (`client`/`project`); saving here establishes the same global preference that the list updates immediately. Coverage note: the recipients catalog (list, alta, duplicado, pausa, baja con confirmación, ambas advertencias de "no le llega a nadie") + card toggle + overdue frequency + both view preference controls are tested; the statement reminder toggle, hosting toggle and USD rate field are not asserted yet (partial).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-ads-history-settings.spec.js`

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
  4. Trash icon asks for confirmation; DELETE `.../delete/` returns `credit_card_referenced` (400) when history references the name.
- **Coverage:** ✅ Covered (list, draft-row create, cupo patch, reference-blocked delete with Spanish error)
- **E2E Spec:** `e2e/admin/admin-accounting-statements-card-catalog.spec.js`

### FLOW: `admin-accounting-ads`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P3
- **Routes:** `/panel/accounting/ads`
- **Description:** Advertising spend log with a running accumulated column computed over the full history, platform/card filters and modal CRUD.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-ads-history-settings.spec.js`

### FLOW: `admin-accounting-hosting-client`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/hostings`, `/panel/clients`
- **Description:** Every hosting belongs to a client, so the form carries a searchable client picker with inline creation and **requires it on new records**. Records saved before the relation kept the client as free text following the house convention `Persona - Marca`: opening one searches that text and **offers the matching registered client** for confirmation (accent- and case-blind, both halves tried against name and company), while a still-unlinked record is flagged as **pending** and stays saveable — completing it is a separate step, never a blocker. The table shows the client with a "sin vincular" pill, the filter panel gains a **Cliente** filter with a "Sin cliente" sentinel, a builtin tab isolates the pending group, and a header card counts it. Rows are completed in bulk from the shared `ClientBulkAssignBar` — the same component `/panel/accounting/incomes` uses, so the two views cannot drift apart. The bulk bar holds only the selection count and one **[Acciones]** menu; **"Asignar cliente"** opens `BulkAssignModal` (picker + live plan + a confirm gated with the reason on the line beside it, while no client is picked — an empty picker no longer means unlink), and **"Desvincular cliente"** only appears in the menu when a selected row actually has a client. The menu opens upward (the bar is sticky at the bottom) and separates linking from collecting with a divider. Either way the scope is named *before* anything is written — how many rows gain a client, how many change one and **from which client**, the rows already on the target that will not move, and the full scrollable list of affected records. Only the rows that actually change travel in `POST /api/accounting/hostings/bulk-assign-client/` (one audit entry per hosting), and the toast afterwards reports how many the server really wrote. Selecting a client seeds the billing snapshot (name, email, contact, identification) without overwriting what the operator typed. The cuenta de cobro then **inherits the client**: the send action gates on the resolved recipient (hosting override, else the client's address) instead of a hosting-only email, issues on that client's `PA-{CODE}-{NNN}` series and links the document to the client user. A client holding hostings can no longer be deleted (`client_has_hostings`), and the client card lists their hostings with the monthly total alongside their incomes.
- **Steps:**
  1. Superuser creates a hosting and picks its client (or creates it inline); the billing snapshot fills itself.
  2. Opening a legacy hosting shows the suggested pairing; one click confirms it, or the record stays flagged as pending.
  3. The "Sin cliente" tab lists what is left. Selecting rows reveals the bulk bar: "Asignar cliente" stays off until a client is picked, with the reason on screen; "Desvincular cliente" only shows up when the selection has a client to lose.
  4. Either action confirms first: the modal breaks the selection into what gains a client, what changes one and from whom, and lists every affected hosting. Cancelling writes nothing. On confirm only the rows that change are sent, and the toast reports how many the server actually modified.
  5. With a client linked, "Enviar cuenta de cobro" becomes available even when the hosting has no email of its own.
- **Error cases:**
  - [No client picked] "Asignar cliente" is disabled and the bar reads "Elige un cliente para poder asignar." — no request leaves the page.
  - [Selection already on the target] "Asignar cliente" is disabled with "Todo lo seleccionado ya tiene a {cliente}."
  - [Nothing linked] "Desvincular cliente" is not rendered at all.
  - [Cancelled confirmation] No request fires and the selection survives untouched.
  - [Selected record deleted] (Ago 2026) Misma reconciliación que ingresos, desde el mismo composable: borrar un hosting seleccionado descarta ese id y sólo ése, la barra se va sola al quedar vacía la selección, y una asignación masiva que nombre un hosting inexistente se rechaza con **409 `records_not_found`** en vez de escribir la mitad sobreviviente del lote.
- **Coverage:** ✅ Covered (pending pill + Sin cliente tab, bulk assignment confirming the scope before the payload, the disabled-assign guard, the unlink action sending only the linked rows, la selección depurándose tras un borrado; the form picker and the suggestion are covered by unit tests)
- **E2E Spec:** `e2e/admin/admin-accounting-expenses-hostings.spec.js`

### FLOW: `admin-accounting-hosting-billing`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/hostings`
- **Description:** Send a client the cuenta de cobro from a hosting row. The paper-plane action (disabled without client email, tooltip explains) opens a ConfirmModal previewing amount and recipient; confirm POSTs `/api/accounting/hostings/:id/send-collection-account/`, which issues the Document (public number PA-YYYY-NNNN, one line item for the next modality period, issuer default payment methods), emails the client the branded message with the Spanish PDF attached and stamps `billing_requested_at` (pauses the expiry notices; a "Cobro enviado" badge appears on the row). If the email fails the document stays issued and a warning toast points to Cuentas de cobro for re-send. Since PA-25 the recipient and the numbering come from the linked client (see `admin-accounting-hosting-client`): the action gates on `billing_email` (hosting override, else the client's address), and a linked hosting issues on that client's series.
- **Steps:**
  1. Superuser opens `/panel/accounting/hostings` and clicks the paper-plane action on a row with client email.
  2. ConfirmModal previews `payment_per_cycle` and the recipient; confirm fires the POST.
  3. Success toast (with "Ver en Cuentas de cobro" action) and the row shows the "Cobro enviado" badge.
- **Coverage:** ✅ Covered (email gate, confirm + POST + badge, email-failure warning)
- **E2E Spec:** `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`

### FLOW: `admin-accounting-collections`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/collections`
- **Description:** Cuentas de cobro center (tab renamed from "Cobros", key `collections` intact): status counters (emitidas/pagadas/vencidas/anuladas with money totals from list meta), segmented status filter (Todas/Emitidas/Vencidas/Pagadas/Anuladas), search box + filter panel + saved tabs (`accounting_collections`) with multi filters for **Cliente** and **Proyecto** (each with its "Sin cliente" / "Sin proyecto" bucket), emisión and total ranges. Table with número/origen (badge)/**cliente**/**proyecto**/total/emisión/vence/estado (badge shows "Vencida" via `is_overdue`). Cliente and Proyecto are separate sortable columns since Aug 2026 — the single Cliente column showed `customer_name`, the frozen billing snapshot, which held a brand ("MIMITTOS") where the client is a person. Row actions: ver detalle (opens `admin-accounting-collection-detail`), descargar PDF (`GET .../pdf/` blob), reenviar al cliente (behind ConfirmModal naming the recipient), marcar pagada (expected-linked cuentas route through the Liquidar modal — see `admin-accounting-collection-create`) and anular (behind ConfirmModal; cancelling a hosting-linked account clears `billing_requested_at` so the expiry notices resume, and cancelling frees the linked income for a new cuenta). (Ago 2026) A cuenta issued with a **plazo de pago cero** carries no due date at all, so its "Vence" cell stays empty and it can never wear the "Vencida" badge nor be swept into that tab or counter: `is_overdue` derives from a date that no longer exists, instead of comparing the emisión date against itself and turning the cuenta overdue the day after it was sent.
 (Ago 2026) La fila ofrece además **eliminar**, que no es anular: anular deja el registro con su estado, porque el documento ya salió; eliminar borra físicamente la que nunca debió existir. El botón sólo aparece cuando el backend lo autoriza en `can_delete`: la cuenta ya está **anulada**, o **nunca llegó al cliente** (borrador, o emitida cuyo correo falló — el envío se consulta en `EmailLogTarget`, que no tiene FK y sobrevive al borrado). Una **pagada** no se puede ni anular ni eliminar. La confirmación es la única de la tabla con `requireTypeText`: muestra consecutivo, cliente y monto y exige teclear `ELIMINAR`, porque la acción es irreversible. El consecutivo **no se reutiliza** (la serie queda con un hueco explicable en vez de dos documentos con el mismo número), el ingreso vinculado vuelve a quedar facturable — la marca es derivada, así que se libera sola —, un hosting recupera sus avisos de vencimiento, y el borrado deja una fila `deleted` en el historial contable (`admin-accounting-history`) que nombra el consecutivo eliminado. (F7, 17-ago-2026) The **Proyecto column answers with the LIVE relation** — the same FK the project filter already matches on — and the frozen `customer_project_name` snapshot only fills FK-null legacy rows ("(histórico)" options intact), so the cell and the filter can never disagree: two cuentas of one client can honestly differ (one linked, one blank — the PA-DEIVISRI-001 evidence case) and a reload tells the same truth, while the PDF keeps printing the frozen snapshot untouched.
- **Coverage:** ✅ Covered (counters + meta, Vencidas filter/badge, mark-paid + cancel with confirm, resend behind its confirm + resend-failure toast, eliminar una anulada con la palabra tecleada + contadores al día, la ausencia del botón en una cuenta ya enviada y en una pagada, y el borrado rechazado — la carrera que el botón oculto no puede evitar: la cuenta sale al cliente desde otro lado y el DELETE responde 400 diciendo que se anule; PDF download not asserted)
- **E2E Spec:** `e2e/admin/admin-accounting-collections.spec.js`

### FLOW: `admin-accounting-collection-grouping`
- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/collections`, `/panel/accounting/settings`
- **API:** `GET /api/accounting/settings/`, `PATCH /api/accounting/settings/update/`, `GET /api/accounting/collection-accounts/`
- **Description:** Cuentas de cobro alterna entre la tabla clásica y una vista agrupada de un solo nivel. En **Cliente**, el encabezado responde a quién cobrarle; en **Proyecto**, separa proyectos vivos, snapshots huérfanos como “(histórico)” y el grupo real “Sin proyecto”. Cada encabezado reutiliza la banda de PA-60 (etiqueta arriba, valor abajo) para mostrar conteo, emitido, por cobrar, recaudado, anulado y el desglose Borradores/Emitidas/Vencidas/Pagadas/Anuladas; Vencidas es un subconjunto de Emitidas. Los grupos se ordenan por pendiente descendente, desempatan alfabéticamente y dejan el grupo sin asignar al final. El pie suma exactamente el conjunto filtrado.
- **Steps:** abrir Cuentas de cobro → alternar Agrupado/Clásico → elegir Cliente/Proyecto → contrastar encabezados, orden y pie → recargar y comprobar que el par persiste. La misma preferencia se puede editar en Configuración.
- **Branches:** un PATCH fallido revierte de inmediato al último par confirmado y muestra el error; no existe entrada libre que produzca un error de validación desde esta UI segmentada.
- **Coverage:** ✅ Covered (display de montos/estados, cambio de criterio y grupos históricos, persistencia tras recarga, rollback de fallo del servidor, edición desde Configuración)
- **E2E Spec:** `e2e/admin/admin-accounting-collections.spec.js`, `e2e/admin/admin-accounting-ads-history-settings.spec.js`

### FLOW: `admin-accounting-collection-detail`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/collections`
- **Description:** Inspecting one cuenta de cobro without leaving the tab. The row's "Ver detalle" opens a modal keyed on the **cuenta**, not on the income — a cuenta raised from a hosting has no income at all (`hosting_billing_service` sets `hosting_record` only), and those rows previously had no inspection action of any kind. **Resumen** shows cliente and proyecto as separate facts, the concept and its items, and the linked income with its amounts, status (`IncomePaymentStateCell`), partner split and **historial de liquidación** (liquid children + linked deductions, from `GET accounting/incomes/<id>/detail/` — before that endpoint the children were unreachable from the panel). When the frozen `customer_name` differs from the linked client the modal says so outright, naming both, since issued documents are never rewritten. **Documento** embeds the PDF via `?inline=1` so previewing never downloads. "Ver en Ingresos" is the optional exit and passes `accounting_incomeTab=all`, because Ingresos otherwise lands on its "Solo esperados" builtin and filters the focused row out of its own list. (Ago 2026) On a cuenta with a zero-day term the "Emisión / Vence" cell shrinks to **"Emisión"** over a single date: keeping the paired label would have hung it over `formatDate`'s em-dash fallback, which reads as a missing datum rather than an absent plazo. (Ago 2026) The Documento tab probes the inline PDF URL before embedding it — spinner, then the viewer, and when the document cannot render, a message in the app's own words pointing at "Descargar PDF" instead of the browser's refused-connection page.
- **Coverage:** ✅ Covered (columns separated, detail + settlement history, inline document embed, the exit landing on a non-filtering tab)
- **E2E Spec:** `e2e/admin/admin-accounting-collections.spec.js`

### FLOW: `admin-accounting-collection-create`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/collections`, `/panel/accounting/incomes`
- **Description:** Create a cuenta de cobro from the tab button ("Nueva cuenta de cobro" + empty-state CTA) or from an income row action (kind expected/liquid, never lost; rows with an active cuenta show "Ver cuenta de cobro" navigation instead, `?focus=` flashing both ways). The modal unifies with the clients module: `ClientAutocomplete` prefills the editable customer snapshot (razón social, NIT→`NIT`/cédula→`CC`, email, contacto) and supports inline client creation; the income link is MANDATORY via a searchable combobox over expected AND liquid incomes (never lost). The request carries NO `client` param — it asks for the whole eligible ledger once and narrows it on the page, because the endpoint does not paginate and the set is small: that makes every count exact and makes switching a filter cost zero requests, which is what lets the dropdown stay open and the cursor stay in the search box. Two chip groups sit between the label and the input, each option carrying its count: **Alcance** (`Del cliente`, the default once a client is picked and literally only their rows / `Todos`) and **Estado** (`Todos` / `Esperados` / `Líquidos`). Counts are faceted — each group is counted with the other group's filter already applied, so a chip's number is what clicking it shows. The chips narrow the set the concept search then runs over, and both snap back to their defaults whenever the client changes, so no recorte of the previous selection survives; `Del cliente` is disabled until there is one. `Todos` is how the still-unassigned incomes are reached (grouped as "Sin cliente", selectable on purpose since issuing adopts the client onto them — announced under the field before the send, never written early) along with the ones filed under someone else ("De otros clientes", each row naming its owner). Flagged incomes stay listed but blocked, each group declares how many rows it is holding back, an empty combination names itself («Acme Soluciones no tiene ingresos esperados.») and offers "Ver todos (N)" rather than rendering a blank panel that reads as a failed load, the list closes on click-outside or Esc, and picking an income of another client raises an inline warning that blocks the preview (offering to adopt the income's client or drop the income) instead of hitting the backend's 400. The client the income locks in can be released with "Cambiar" from this tab, where the client is a choice rather than the starting point. "Crear ingreso esperado" stacks the income form; the consecutivo is server-suggested per client (`PA-{CODE}-{NNN}`, continuous) and editable (sent only when edited, collision-checked) — the platform `issue` endpoint joins that same per-client series, falling back to the legacy `PA-{year}-{NNNN}` only for documents whose client has no profile. Step 2 previews the REAL email (subject + rendered body) and the attached PDF — produced by the same backend pipeline as the send inside a rolled-back transaction (no rows, no EmailLog, no consecutivo consumed) — before "Confirmar y enviar" issues, emails (PDF with valor en letras, NIT/C.C. types, formatted COP/dates, signature block) and links the document. Paid↔settlement stays synchronized: marking an expected-linked cuenta paid opens the Liquidar modal prefilled (409 on the direct endpoint while pending), and a fully-settled income auto-marks its issued cuenta paid. (Ago 2026) **Plazo de pago admite 0** — pago inmediato contra presentación — with a hint under the field explaining what the zero does, rendered only while the "Días tras emisión" mode is active since a 0 means nothing beside a fecha fija. A zero term issues the cuenta with **no due date**, so neither the PDF nor the client email prints a vencimiento: the whole labelled line goes, and because the PDF's date block is a flow of `field()` calls over a page measured to its content, the neighbours close ranks instead of leaving a gap. Reaching that state took undoing four separate guards that made the zero unexpressible — the input's `min="1"`, a `Number(...) || 8` in the payload builder, `min_value=1` in the panel serializer and a `payment_term_days or PAYMENT_TERM_DAYS` in the create service, the last two of which silently rebilled a legitimate 0 as the 8-day default. Negatives stay rejected (`min="0"` plus `min_value=0`, with typed out-of-range values clamped into 0–120 before the payload), and an emptied field still falls back to 8. (Ago 2026) The step-2 PDF pane probes the served URL before mounting the viewer — spinner while it resolves, the embed once it answers (the PDF endpoints ship `X-Frame-Options: SAMEORIGIN`; the middleware's site-wide DENY default was blanking the frame with the browser's connection-refused page) — and on failure a panel in the app's own words points at Descargar / Abrir PDF, which keep working: the review happens there and "Confirmar y enviar" stays available. Picking a hosting income that records its period pre-fills "Período facturado". (F7, 17-ago-2026) A cuenta raised from a project-linked income lands in the list already showing that project: the draft inherits the income's project — kept in sync by `_sync_project_to_draft_cuentas` when the income's project changes while a draft is open — and the Proyecto column reads the live FK, so no reload is needed for the new row to tell the truth. (Ago 2026) Si el selector marca **Sin correo**, la previsualización enumera de una vez todos los requisitos pendientes. El mismo modal permite guardar explícitamente el correo canónico del cliente por `PATCH` y continuar sin perder ningún campo ya diligenciado.
- **Steps:**
  1. Superuser clicks "Nueva cuenta de cobro" (or the income row action, which preselects and locks the income).
  2. Picks the client (snapshot + suggested consecutivo autofill; the selector warns before selection when it has no email); if needed, saves the canonical email inline without leaving or resetting the draft. Then narrows the income list by Alcance/Estado and picks the income from the modal-owned floating listbox, which cannot be clipped by the form panel and owns the only scrollbar while open; adjusts concept/value/terms.
  3. "Previsualizar" renders the real email and PDF; "Volver a editar" keeps state.
  4. "Confirmar y enviar" creates+issues+emails; the row appears and the income flags as linked.
- **Coverage:** ✅ Covered (create-through-preview with payload assertions; selector warning for a client without email; complete visible blocker list; invalid inline email; explicit canonical email save preserving the draft; floating income list outside the clipping panel; alcance/estado chips with their counts + focus retention + explicit empty state + "Ver todos" widening + click-outside close; Liquidar routing on mark-paid; generate icon opens locked modal; linked row navigates focused)
- **E2E Spec:** `e2e/admin/admin-accounting-collections.spec.js`, `e2e/admin/admin-accounting-incomes.spec.js`

### FLOW: `admin-accounting-hosting-cycles`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`
- **Description:** Cycle payment history per hosting (clock row action → `HostingCyclesModal`): historical modality/amount snapshots remain immutable, while the register form offers quarterly, semiannual and every-9-month cycles and prefills the current contract amount/modality. "Extender vigencia" advances one current modality period. `total_paid`/`cycles_count` recompute from history; deleting a cycle recalculates but never rolls back `valid_to`.
- **Coverage:** ✅ Covered (backfill badge history, register payment with advance_validity, delete with confirm)
- **E2E Spec:** `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js`

### FLOW: `admin-accounting-hosting-inline-edit`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P3
- **Routes:** `/panel/accounting/hostings`
- **Description:** Inline edits without opening the modal: double-click on cliente, dominio or valor/mes swaps the cell for an input (`AccountingInlineCell`; money cells use BaseCurrencyInput), Enter/blur PATCHes only when the value changed, Esc cancels; a failed PATCH leaves the row untouched so the cell falls back. The estado column is `AccountingStatusSelect` (badge-styled select, snap-back + spinner) PATCHing `is_active` directly.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-blog-publish-mode.spec.js` (mode reveal + overdue banner + hydration + publish-now payload; added 2026-07-22)

### FLOW: `admin-accounting-settings-reset-tabs`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P3
- **Routes:** `/panel/accounting/settings`
- **Description:** Restore the seeded default filter tabs per accounting view: the "Pestañas de filtros guardados" card lists the 6 views (Ingresos/Gastos/Hostings/Bolsillo/Recurrentes/Ads), each with a "Restablecer" button that, after a ConfirmModal warning that custom tabs will be deleted, POSTs `accounts/saved-filter-tabs/reset/` (atomic delete + re-seed from `DEFAULT_FILTER_TABS`) and toasts the result. New users get the defaults automatically on first GET.
- **Coverage:** ❌ Missing
- **E2E Spec:** —

### FLOW: `admin-accounting-list-error-retry`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P3
- **Routes:** `/panel/accounting/*` (all subviews)
- **Description:** When a `GET /api/accounting/<entity>/` (or `dashboard/`, `change-logs/`, `settings/`) fails, the page replaces the table/summary with `AccountingErrorState` (`data-testid=accounting-error-retry`): a Spanish danger alert plus a "Reintentar" button that re-fires the page's load function. CRUD errors keep using toasts and never hide the table. Mirrors `admin-diagnostic-list-error-retry`.
- **Coverage:** ❌ Missing
- **E2E Spec:** —

### FLOW: `admin-accounting-empty-state-cta`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P4
- **Routes:** `/panel/accounting/*` (list subviews)
- **Description:** With zero records, lists render `BaseEmptyState` with a primary "Nuevo <entidad>" action that opens the create modal; with active filters and zero matches, the action becomes "Limpiar filtros" and resets the filter panel.
- **Coverage:** ❌ Missing
- **E2E Spec:** —

### 23.1 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-accounting-dashboard` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-dashboard.spec.js` |
| `admin-accounting-receivables` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-dashboard.spec.js`, `e2e/admin/admin-accounting-incomes.spec.js` |
| `admin-accounting-stats-modals` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-dashboard.spec.js` |
| `admin-accounting-income-crud` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-incomes.spec.js` |
| `admin-accounting-income-client` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-incomes.spec.js` |
| `admin-accounting-filters` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-filters.spec.js` |
| `admin-accounting-expenses-crud` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-expenses-hostings.spec.js` |
| `admin-accounting-hostings` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-expenses-hostings.spec.js` |
| `admin-accounting-hosting-client` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-expenses-hostings.spec.js` |
| `admin-accounting-pocket` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-pocket-recurring.spec.js` |
| `admin-accounting-recurring` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-pocket-recurring.spec.js` |
| `admin-accounting-history` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-ads-history-settings.spec.js` |
| `admin-accounting-history-filters` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-history-filters.spec.js` |
| `admin-accounting-history-diagnosis` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-history-filters.spec.js` |
| `admin-accounting-cards` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-cards.spec.js` |
| `admin-accounting-export` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-export.spec.js` |
| `admin-accounting-settings` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-ads-history-settings.spec.js` |
| `admin-accounting-card-catalog` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-statements-card-catalog.spec.js` |
| `admin-accounting-ads` | admin | superuser | P3 | ✅ Covered | `e2e/admin/admin-accounting-ads-history-settings.spec.js` |
| `admin-accounting-hosting-billing` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js` |
| `admin-accounting-collections` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-collections.spec.js` |
| `admin-accounting-collection-detail` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-collections.spec.js` |
| `admin-accounting-collection-create` | admin | superuser | P1 | ✅ Covered | `e2e/admin/admin-accounting-collections.spec.js`, `e2e/admin/admin-accounting-incomes.spec.js` |
| `admin-accounting-hosting-cycles` | admin | superuser | P2 | ✅ Covered | `e2e/admin/admin-accounting-hosting-billing-cycles.spec.js` |
| `admin-accounting-hosting-inline-edit` | admin | superuser | P3 | ❌ Missing | — |
| `admin-accounting-settings-reset-tabs` | admin | superuser | P3 | ❌ Missing | — |
| `admin-accounting-list-error-retry` | admin | superuser | P3 | ✅ Covered | `e2e/admin/admin-accounting-error-retry.spec.js` |
| `admin-accounting-empty-state-cta` | admin | superuser | P4 | ✅ Covered | `e2e/admin/admin-accounting-empty-state.spec.js` |


## Section 24 — MCP Connectors Panel (superuser-only) (Jul 2, 2026)

Management UI for remote MCP connectors that expose panel modules to Claude (claude.ai custom connectors). Lives at `/panel/mcps` behind `admin-auth` + `superuser-only` middlewares; the backend enforces `IsSuperUser` on every `/api/mcp-connectors/*` endpoint. The MCP endpoint itself (`POST /api/mcp/blog/<token>/`) is machine-facing (capability-URL token auth, no browser UI) and is covered by backend tests (`backend/content/tests/views/test_mcp_blog.py`), not E2E.

### FLOW: `admin-mcps`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P2
- **Routes:** `/panel/mcps`
- **Description:** El superusuario administra los conectores MCP agrupados por área. Cada card muestra estado, riesgos, catálogo, credenciales limitadas y actividad atribuida; los secretos aparecen una sola vez. Puede activar un conector, crear o editar el alcance/vencimiento de una credencial, rotarla o revocarla. Los errores de validación quedan en el formulario y los fallos del servidor no cierran ni confirman la acción.
- **Steps:**
  1. El superusuario llega desde la navegación del Panel a Integraciones → MCPs.
  2. Expande una card y revisa riesgos, funciones, credenciales, actor técnico y actividad con request/objeto atribuido.
  3. Genera la principal o crea una limitada → recibe la URL una sola vez → la copia al cliente MCP.
  4. Edita alcance/vencimiento, rota o revoca una credencial individual; la revocación exige confirmación en el modal estándar del Panel.
  5. Activa o desactiva el conector con el toggle.
  - [Display] La card y sus acordeones presentan inventario real, no sólo un contenedor visible.
  - [Success] Crear, editar, rotar, revocar y activar producen el estado observable correspondiente.
  - [Error] Un staff no superusuario es redirigido; etiqueta vacía o alcance custom vacío permanecen bloqueados en cliente.
  - [Failure] Un 4xx/5xx conserva el formulario o estado anterior y muestra el detalle accionable.
  - [Security] El plaintext no puede recuperarse al recargar; sólo quedan prefijo y hash. Las escrituras —incluidos `created_by` y `linked_by` de hilos documentales, ingresos y extractos— se atribuyen a un principal técnico no interactivo del conector, nunca al superusuario humano del Panel.
  - [Contract] El servidor rechaza envelopes MCP incoherentes, alcances o vencimientos inválidos, confirmaciones vencidas/alteradas y assets temporales con tamaño, hash, MIME o firma incompatibles; un fallo de auditoría no interrumpe la respuesta del transporte.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-mcps.spec.js`

### 24.1 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-mcps` | admin | superuser | P2 | ✅ display · success · error · failure | `e2e/admin/admin-mcps.spec.js` |


## Section 25 — Flows Audit Gaps (Jul 4, 2026)

Registered by the `/e2e-user-flows-check` audit of the `feat/03072026-panel-modules-mcp-connectors` branch. Covers the new admin discount-offer action, backfills six flows that were already tested but undocumented here, and registers three system-triggered client-milestone notifications for traceability.

Also registered/updated in this audit and documented in their home sections:
- The three `platform-client-*` flows (§8.14) — now **✅ Covered** by `e2e/platform/platform-client-documents.spec.js`.
- `platform-password-reset` (§8.1) — added to `flow-definitions.json`; **✅ Covered** by `e2e/platform/platform-password-reset.spec.js`.

### FLOW: `admin-proposal-discount-offer-send`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit`
- **API:** `POST /api/proposals/:id/email-preview/` (template `proposal_urgency`), `POST /api/proposals/:id/discount-offer/send/`
- **Description:** From the proposal actions menu the seller picks "Enviar oferta de descuento" — only shown when `discount_percent > 0` and the client has an email. A modal renders the server-side email preview; confirming sends the offer (`ProposalEmailService.send_urgency_email(force=True)`) and shows a success toast. Never auto-sent.
- **Steps:**
  1. Admin opens `/panel/proposals/:id/edit` and clicks the actions menu.
  2. Picks "Enviar oferta de descuento" → discount modal opens and loads the email preview.
  3. Clicks "Enviar oferta" → offer is emailed to the client → success toast.
- **Branches:**
  - [Branch A — no discount] `discount_percent = 0` → the action is hidden.
  - [Branch B — no email] Client without an email → the action is hidden.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-discount-offer.spec.js`

### FLOW: `admin-styleguide`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/styleguide`
- **Description:** Admin browses the executable base-component/design-token catalog and verifies the canonical responsive behavior at compact, portrait, landscape, desktop and wide widths.
- **Interaction matrix:**
  - `display` — the admin reaches the catalog, sees the matching responsive profile, navigation mode, tabs/filters, priority table and capped content shell.
  - `success` — n/a: the page is a reference catalog and does not persist product data.
  - `error` — n/a: component validation belongs to unit tests; there is no user-submitted payload.
  - `failure` — n/a: the examples are local and make no product mutation request.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/visual/styleguide.spec.js`

### FLOW: `admin-layout-title-mapping`

- **Module:** admin
- **Role:** admin
- **Priority:** P3
- **Routes:** `/panel/*`
- **Description:** The browser tab `<title>` updates to the human-readable name of the active panel route (dynamic title mapping in the admin layout).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-layout-title-mapping.spec.js`

### FLOW: `platform-layout-title-mapping`

- **Module:** platform
- **Role:** platform-admin
- **Priority:** P3
- **Routes:** `/platform/*`
- **Description:** The browser tab `<title>` updates to the human-readable name of the active platform route (dynamic title mapping in the platform layout).
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/platform/platform-layout-title-mapping.spec.js`

### FLOW: `admin-proposal-json-import-client-picker`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/create`
- **Description:** When a pasted/imported proposal JSON does not resolve to an existing client, a client-picker prompts the admin to bind the imported proposal to a client before creating it.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-json-import-client-picker.spec.js`

### FLOW: `proposal-calculator-reopen-after-nav`

- **Module:** proposal
- **Role:** guest
- **Priority:** P1
- **Routes:** `/proposal/:uuid`
- **Description:** On the public proposal, reopening the investment calculator after navigating between sections preserves the previously selected modules and calculator state.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-calculator-reopen-after-nav.spec.js`

### FLOW: `proposal-slug-access`

- **Module:** proposal
- **Role:** guest
- **Priority:** P1
- **Routes:** `/proposal/:slug`
- **Description:** The public proposal is reachable via a human-readable slug URL (in addition to its UUID), resolving to the same proposal view.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-slug-access.spec.js`

### FLOW: `admin-client-first-login-notification`

- **Module:** admin
- **Role:** system
- **Priority:** P2
- **Trigger:** `POST /api/accounts/verify/` (first-time onboarding, `was_onboarded == False`)
- **Description:** On a client's first platform login (password set), `client_flow_notifications` fires a team milestone alert: an in-app notification to the project admins plus an email to the notification recipients. Best-effort; never blocks onboarding; fires only on the first login.
- **Coverage:** ⚠️ Backend-only
- **Evidence:** Backend service `accounts/services/client_flow_notifications.py` (out of browser-E2E scope; may be asserted as a branch of `platform-verify-onboarding`).

### FLOW: `admin-client-email-validated-notification`

- **Module:** admin
- **Role:** system
- **Priority:** P2
- **Trigger:** `POST /api/accounts/email/verify/confirm/`
- **Description:** When a client confirms their email OTP from the documents portal, `client_flow_notifications` fires a team milestone alert (in-app to project admins + email). Best-effort; already-verified confirmations do not re-notify.
- **Coverage:** ⚠️ Backend-only
- **Evidence:** Backend service `accounts/services/client_flow_notifications.py` (out of browser-E2E scope; may be asserted as a branch of `platform-client-email-validation`).

### FLOW: `admin-client-document-signed-notification`

- **Module:** admin
- **Role:** system
- **Priority:** P2
- **Trigger:** `POST /api/accounts/documents/:uuid/sign/`
- **Description:** When a client click-to-accept signs a document, `notify_team_document_signed_task` fires a team milestone alert (in-app to project admins + email) and the client receives a signature-confirmation email. Best-effort; idempotent re-signs do not re-notify.
- **Coverage:** ⚠️ Backend-only
- **Evidence:** Backend service `accounts/services/client_flow_notifications.py` + Huey task `notify_team_document_signed_task` (out of browser-E2E scope; may be asserted as a branch of `platform-client-document-sign`).

### 25.1 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-proposal-discount-offer-send` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-discount-offer.spec.js` |
| `admin-styleguide` | admin | admin | P3 | ✅ Covered | `e2e/visual/styleguide.spec.js` |
| `admin-layout-title-mapping` | admin | admin | P3 | ✅ Covered | `e2e/admin/admin-layout-title-mapping.spec.js` |
| `platform-layout-title-mapping` | platform | platform-admin | P3 | ✅ Covered | `e2e/platform/platform-layout-title-mapping.spec.js` |
| `admin-proposal-json-import-client-picker` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-proposal-json-import-client-picker.spec.js` |
| `proposal-calculator-reopen-after-nav` | proposal | guest | P1 | ✅ Covered | `e2e/proposal/proposal-calculator-reopen-after-nav.spec.js` |
| `proposal-slug-access` | proposal | guest | P1 | ✅ Covered | `e2e/proposal/proposal-slug-access.spec.js` |
| `admin-client-first-login-notification` | admin | system | P2 | ⚠️ Backend-only | `accounts/services/client_flow_notifications.py` |
| `admin-client-email-validated-notification` | admin | system | P2 | ⚠️ Backend-only | `accounts/services/client_flow_notifications.py` |
| `admin-client-document-signed-notification` | admin | system | P2 | ⚠️ Backend-only | `accounts/services/client_flow_notifications.py` |


## Section 27 — Panel Projects Module / Plataforma (Aug 13, 2026)

The Plataforma sidebar space (placed after Contabilidad on purpose: it doubles the superuser-only Hostings entry and the breadcrumb resolver walks sections in order) opens `/panel/projects`, the commercial face of `accounts.Project` — the entity hostings, incomes and cuentas de cobro already reference. Projects archive, they never delete (PA-29), the create form asks the PA-38 minimum, and every project selector now creates on the fly (PA-24/PA-25 mirror).

### FLOW: `admin-panel-projects`
- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects`
- **API:** `GET /api/projects/?scope=all`, `POST /api/projects/create/`, `PATCH /api/projects/<id>/update/`, `GET /api/project-states/`, `GET /api/proposals/client-profiles/?without_projects=true`
- **Description:** Listing of every project with client, administrable lifecycle state, created date and per-project hosting/income counts. It loads once and filters client-side by every active catalog state plus the manual-review bucket; search is accent/case-blind and columns remain sortable. On expanded widths, the non-zero cards under **Ciclo del proyecto** and **Pendientes operativos** share the same compact horizontal geometry and four/five-column grid: identity stays left, count/action stays right, an optional support line is clamped, and contextual help occupies a contained 48 px sibling column. Opening help never activates the card. **Clients without project** remains literal (no `Project` row) and opens a create path pre-seeded with that client. Create presents name, client, initial state and description as one full-width block; **En desarrollo** is visibly selected without redundant help. Name/client errors appear beneath their controls, the footer contains only Cancelar/Guardar, and Crear cliente remains visible in the selector even with matching results. Later state changes are intentionally absent from edit and use the consequence-preview flow. A same-name project warns without blocking. For superusers, counts link into accounting pre-filtered by project.
- **Responsive contract:** En 412 px y 835 px la cabecera muestra exactamente dos resúmenes accionables — **Estados** y **Pendientes** —; su ayuda queda anclada dentro de cada tarjeta y sus drawers conservan todos los estados, incluidos los que están en cero, y cada detalle operativo. La primera tarjeta del listado queda dentro de la pantalla inicial del teléfono. El scope es selector, el orden sigue explícito y el listado usa tarjetas en una o dos columnas. Desde 1195 px vuelven la tabla y ambos grupos de indicadores en tarjetas de 72–80 px con idéntico ancho/alto y ayuda contenida en una columna fija de 48 px. Crear, editar, asignar huérfanos y cambiar cliente usan pantalla completa en teléfono; la vista previa de impacto se apila antes de la decisión y conserva acciones sticky. En 2560 px la página se centra con máximo de 1400 px.
- **Steps:** open module → inspect or activate an indicator → search/sort/filter by catalog state → create from CTA or uncovered-client panel → edit descriptive data → open the dedicated lifecycle/history actions → jump into hostings/incomes by count.
- **Branches:** missing name/client marks each incomplete control without sending; duplicate name warns and still saves; backend 400 keeps the modal open and places the serializer message under its field; zero counts render as plain text; non-superusers see plain counts (no links).
- **Coverage:** ✅ Covered, incluidas validación local/API junto al campo, footer limpio, ancho uniforme, estado inicial coherente, creación de cliente visible, orden del ciclo, aislamiento entre ayuda y filtro, contención geométrica de la ayuda, estados en cero dentro del detalle compacto, acciones de filtro/navegación y display responsivo en los cinco anchos reales.
- **E2E Specs:** `e2e/admin/admin-panel-projects.spec.js`, `e2e/admin/admin-responsive-documents-clients-projects.spec.js`

### FLOW: `admin-project-fly-create`
- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`, `/panel/accounting/incomes`, `/panel/accounting/collections` (transitively, via the stacked income modal)
- **API:** `GET /api/accounting/projects/?client=<profile>`, `POST /api/projects/create/`
- **Description:** `ProjectSelect` is a combobox over the client's already-fetched projects (local filtering — a client has a handful, not a catalog) that mirrors the client selector so both are learned once. With no matches it offers "Crear proyecto «term»" (Enter included) opening an inline panel embedded in the component itself — ONE reusable selector, not a per-modal solution: hosting and income modals gained the flow without changes, and the cuenta de cobro inherits it through its stacked income modal. The panel pre-fills the typed name, shows the inherited client, warns without blocking on a same-name collision, stays open on a 400 with the backend message, and on success auto-selects the new project, appending it to the per-client picker cache (`projectsByClient`, `all` bucket dropped). Cancelling the outer form leaves the project standing — a record of its own, immediately visible in `/panel/projects`. The module store invalidates the whole picker cache after any create/update/archive/restore so renamed or archived projects never linger in forms.
- **Steps:** open hosting/income modal → pick client → type a project that does not exist → create it inline → the id travels in the outer form's payload.
- **Branches:** 400 keeps the inline panel open; cancelling the outer form afterwards preserves the project; re-opening the picker lists it without refetching.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-project-fly-create.spec.js`

### Section 27 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-panel-projects` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-panel-projects.spec.js` |
| `admin-project-fly-create` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-project-fly-create.spec.js` |

### FLOW: `admin-project-access-detail`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects` (modal)
- **API:** `GET /api/projects/:id/access/`
- **Interaction:** Open a project's detail icon from the list or card.
- **Display outcome:** The modal identifies the project and client, renders production and staging separately, and keeps passwords and sensitive notes masked.
- **Failure outcome:** A failed detail request renders a retry action in the modal; retry replaces the error with the project data.
- **Success / error:** n/a — opening the modal is a read/display action with no user input.
- **Coverage:** `e2e/admin/admin-project-access-detail.spec.js` plus the five responsive project profiles.

### FLOW: `admin-project-access-field-edit`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects` (project detail modal)
- **API:** `PATCH /api/projects/:id/access/`
- **Interaction:** Activate one field's edit icon, change its value, and explicitly save it.
- **Success outcome:** The API receives exactly one mutable field (plus environment when applicable) and the returned value replaces the read view.
- **Error outcome:** A serializer validation message remains beside the field and the draft stays editable.
- **Failure outcome:** A server failure remains inline and does not discard the draft.
- **Display:** n/a — the read-only values belong to `admin-project-access-detail`.
- **Coverage:** `e2e/admin/admin-project-access-detail.spec.js`.

### FLOW: `admin-project-access-secrets`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects` (project detail modal)
- **API:** dedicated password/note reveal endpoints under `/api/projects/:id/access/`
- **Interaction:** Reveal, hide, or copy a password or sensitive note through its icon control.
- **Display outcome:** Secret values are absent from the initial payload and appear as a mask.
- **Success outcome:** Reveal shows the requested secret until hidden or closed; copy writes it without first placing it in the modal.
- **Failure outcome:** A failed reveal reports the API error while the value remains masked.
- **Error:** n/a — there is no user-authored value to validate in reveal/copy.
- **Coverage:** `e2e/admin/admin-project-access-detail.spec.js`.

### FLOW: `admin-project-access-notes`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/projects` (project detail modal)
- **API:** note create/update/delete/reveal endpoints under `/api/projects/:id/access/notes/`
- **Interaction:** Inspect notes or open “Agregar nota”, enter title/content, choose sensitivity, and save.
- **Display outcome:** Existing titled notes render; sensitive content stays masked.
- **Success outcome:** A valid note is added to the project response and appears in the list.
- **Error outcome:** Missing title/content is rejected locally without a request.
- **Failure outcome:** A backend rejection preserves the entered content and shows an actionable error.
- **Coverage:** `e2e/admin/admin-project-access-detail.spec.js`.


## Section 28 — Client/Project Coherence (Aug 16, 2026)

The coherence ticket's rule made executable: cliente y proyecto se registran una sola vez y valen en todo el sistema. Relations are FKs everywhere (the frozen `customer_*` snapshots of ISSUED cuentas are the deliberate exception — an emitted document is a fact), every reassignment shows its exact scope before running, the mutation response rebuilds the open views, and every touched record leaves an `AccountingChangeLog` row queryable by client and project from Historial → Cambios.

### FLOW: `admin-accounting-project-bulk-assign`
- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/accounting/hostings`, `/panel/accounting/incomes`
- **API:** `POST /api/accounting/hostings/bulk-assign-project/`, `POST /api/accounting/incomes/bulk-assign-project/`, `GET /api/projects/?scope=all`
- **Description:** The bulk bar collapsed into one **[Acciones]** menu (count + a single control): **"Asignar proyecto"** opens `BulkAssignModal` and **"Quitar proyecto"** goes straight to the confirmation. Asignar proyecto uses a catalog-wide combobox (every project, searched by name or client, actives first) and confirms against the full plan: toAssign, toReassign (origins named), unchanged, and the blocked bucket — rows of ANOTHER client the ownership rule refuses to touch, listed apart and never in the payload (the backend answers 409 `client_mismatch`/`mismatched_ids` on a stale plan and the page drops exactly those ids). Quitar proyecto is its own destructive action; clearing works across clients. `results` carries the cascaded liquid children so the in-place rebuild misses nothing. The CLIENT preview now also announces which rows will lose their project when the client changes hands (`projectCleared`), matching the server rule that clears a now-foreign project on every client move — bulk included.
- **Steps:** select rows → Acciones → Asignar proyecto → search in the modal-owned floating listbox (never clipped by the panel and owning its own long-list scroll) → pick the project → read the live plan (blocked bucket included) → confirm → rows update in place.
- **Branches:** no project picked keeps the confirm off with the reason beside it, and a selection with no project to lose simply has no "Quitar proyecto" entry in the menu; every row already on target blocks with its own message; 409 drops the named ids and reloads.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-project-bulk-assign.spec.js`

### FLOW: `admin-accounting-project-coherence`
- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/accounting/hostings`, `/panel/projects`
- **API:** `POST /api/accounting/hostings/bulk-assign-client/`, `GET /api/accounting/hostings/`, `GET /api/projects/`
- **Description:** Requisito 14 of the ticket verified over a stateful mock: one client reassignment propagates to every module without a reload (row rebuilt from the response, project cleared and announced beforehand, per-project counters moved on /panel/projects) and a full `page.reload()` serves the same truth — the database is the source of coherence, the reload never was the fix.
- **Steps:** reassign a hosting's client → verify hostings in place → verify /panel/projects counters → reload → verify both again.
- **Branches:** none — the flow IS the invariant.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-accounting-project-coherence.spec.js`

### FLOW: `admin-project-inline-assign-offer`
- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/accounting/hostings`, `/panel/accounting/incomes`
- **API:** `POST /api/projects/create/`, `GET /api/projects/<id>/unlinked-records/`, `POST /api/projects/<id>/assign-unlinked/`
- **Description:** The Vástago gap closed: the inline create keeps the annotated row (unlinked_* counters travel with the `created` event) and, when the form closes — saved or cancelled — the PA-51 assign modal opens with the client's server-fresh backlog. Confirming assigns the checked ids; `assign-unlinked` now returns the updated rows (cascaded liquid children included) and the open accounting table rebuilds without a reload. (F7, 17-ago-2026) The offer also lists the client's **documents** without a project — cuentas de cobro of any commercial status included, shown by their public number: an issued cuenta's missing project has no HTTP write path by design (the generic document PATCH refuses non-drafts), so this confirmed-list flow and the `link_records_single_project` command are its only vehicles. `document_ids` travel with the confirmed plan, the same 409 staleness contract guards them, `unlinked_documents_count` joins the per-row counters (mirroring `documents_no_project_count` in the clients list), and the response document rows map-replace the open documents list.
- **Steps:** new hosting/income → pick client → create project inline → close the form → the offer opens → confirm → Proyecto cells fill.
- **Branches:** zero backlog never offers; dismissing the offer leaves the counters visible on /panel/projects; 409 reloads the preview.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-project-inline-assign-offer.spec.js`

### FLOW: `admin-project-change-client`
- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/projects`
- **API:** `GET /api/projects/<id>/change-client/preview/?client_profile_id=`, `POST /api/projects/<id>/change-client/`, `DELETE /api/accounts/projects/<id>/?force=1` (guarded)
- **Description:** A project changes owner through ONE guided path — the form field stays immutable (`client_immutable`) and a ghost "Cambiar cliente…" entry opens the cascade. The preview names everything: movable records, incomes an active (non-cancelled) cuenta blocks (they detach and keep their client; anular y reemitir is the path for a wrong cuenta), draft cuentas that follow the project (fresh provisional snapshot) or their blocked income, ISSUED documents nothing touches, clientless rows left to the completion tools, and other documents that ride along. The mode — Mover | Desvincular — is chosen EVERY time (no preselection). The apply carries the preview's hosting/income ids as a staleness token (409 `records_not_found`/`records_changed` reload the preview) and runs in one transaction with an audit row per touched record. Hard-deleting a project now refuses with 409 `project_has_records` while anything is linked.
- **Steps:** edit project → Cambiar cliente… → pick destination → read the impact → choose the mode → confirm → row and accounting lists refresh.
- **Branches:** same client / unknown client / archived project answer 400 with their codes; missing mode keeps confirm disabled; 409 reloads the preview and drops the chosen mode.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-project-change-client.spec.js`

### Section 28 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-accounting-project-bulk-assign` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-accounting-project-bulk-assign.spec.js` |
| `admin-accounting-project-coherence` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-accounting-project-coherence.spec.js` |
| `admin-project-inline-assign-offer` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-project-inline-assign-offer.spec.js` |
| `admin-project-change-client` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-project-change-client.spec.js` |


## Section 29 — Document State Episodes (Aug 25, 2026)

### FLOW: `admin-document-states-manage`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/documents/statuses`
- **API:** `/api/document-state-groups/`, `/api/document-states/`, `/api/document-states/:id/merge/`, `/api/document-states/:id/retire/`
- **Descripción:** El catálogo compartido separa grupos exclusivos —el ciclo— de grupos aditivos —las señales—. Muestra cuántos documentos tienen cada estado vigente y cuántos episodios históricos existen. El usuario puede crear grupos y estados, cambiar nombre, color, orden, grupo e incompatibilidades, fusionar duplicados y retirar valores que ya no se usan. Las semillas son editables, pero conservan su clave interna para presets e integraciones.
- **Recorrido:** entrar a Documentos → **Administrar estados** → revisar inventario → crear o editar un valor → confirmar nombres similares, fusiones o retiros dentro del panel → guardar → reutilizarlo desde cualquier documento.
- **Ramas:**
  - [Display] Ciclo y Señales muestran sus semillas y conteos.
  - [Success] Crear, editar y fusionar refresca el catálogo global.
  - [Error] Un estado con episodios abiertos no se puede retirar hasta cerrarlo o fusionarlo.
  - [Failure] Un fallo del servidor conserva el borrador de edición para reintentar.
- **Cobertura:** ✅ display/success/error/failure.
- **E2E:** `e2e/admin/admin-document-states-manage.spec.js`

### FLOW: `admin-document-state-workflow`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/documents/:id/edit`
- **API:** `/api/documents/:id/state-episodes/`, `/api/documents/:id/state-history/`, `/api/documents/:id/notes/`
- **Descripción:** Un documento conserva un episodio por cada período en que tuvo un estado. El ciclo admite uno vigente y puede avanzar o volver; las señales se suman. Abrir, cerrar, quitar, corregir la fecha efectiva y repetir un estado dejan movimientos con fecha/hora y autor. **Cerrar** registra que el trabajo terminó; **quitar** registra que la marca no aplicaba. El historial muestra fecha exacta, tiempo relativo, duración, nota de cierre, autor y observaciones enlazadas.
- **Recorrido:** abrir un documento → seleccionar o crear al vuelo un estado → resolver sugerencias de nombres parecidos → registrar fecha real si aplica → cerrar o quitar desde un modal propio con nota opcional → consultar la línea de tiempo.
- **Observaciones:** crear una observación ofrece abrir **Solucionar bug**. Resolver o descartar la última observación pendiente cierra o quita automáticamente la señal enlazada; eliminar y restaurar se cubren en `admin-document-observation-delete`.
- **Ramas:**
  - [Display] El encabezado y el historial muestran episodios vigentes e históricos con duración y atribución.
  - [Success] Cambiar el ciclo cierra el episodio anterior; las señales permanecen concurrentes.
  - [Success] Una sugerencia reutiliza el estado global existente en lugar de duplicarlo.
  - [Error] Una incompatibilidad rechaza la combinación sin alterar los episodios actuales.
  - [Failure] Un cierre fallido deja el episodio abierto y visible.
- **Cobertura:** ✅ display/success/error/failure.
- **E2E:** `e2e/admin/admin-document-state-workflow.spec.js`

### FLOW: `admin-document-state-filters`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/documents`
- **API:** `GET /api/documents/?states=&without_states=&preset=`
- **Descripción:** El listado muestra primero el episodio del ciclo y después las señales, cada uno con su antigüedad. **Solucionar bug** usa un tratamiento visual de atención. Seleccionar varios estados dentro de la dimensión usa OR; **Sin cerrado** consulta ausencia. Los presets resuelven las búsquedas repetidas: algo por solucionar, enviados sin cerrar, cerrados y por clasificar.
- **Ramas:**
  - [Display] El usuario identifica una acción pendiente y cuánto lleva abierta sin entrar al documento.
  - [Success] Estados múltiples, ausencia y presets generan consultas consistentes y reemplazan el preset al cambiar filtros manuales.
  - [Failure] Un fallo conserva un aviso persistente con opción de reintento.
- **Cobertura:** ✅ display/success/failure.
- **E2E:** `e2e/admin/admin-document-state-workflow.spec.js`

### FLOW: `admin-document-observation-delete`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/documents/:id/edit`
- **API:** `/api/documents/:id/notes/`, `/api/documents/:id/notes/bulk-delete/`, `/api/documents/:id/notes/:note_id/restore/`, `/api/documents/:id/notes/events/`
- **Descripción:** **Descartar** conserva una observación real y el motivo por el que no se atendió. **Eliminar** limpia una prueba, duplicado o error: la observación desaparece de la lista y de los conteos, pero queda recuperable en la papelera. La confirmación muestra el contenido completo y recuerda que una copia enviada por correo o mensaje no se borra fuera del sistema. La actividad conserva solamente quién eliminó o restauró y cuándo, sin duplicar el contenido.
- **Recorrido:** abrir un documento → abrir **Notas** → elegir una observación de cualquier estado → **Eliminar** → revisar contenido y advertencia → confirmar → revisar la papelera o restaurar. Para limpieza, seleccionar varias y confirmar una sola operación atómica.
- **Coherencia:** si la última observación pendiente de un episodio originado por observaciones se elimina, **Solucionar bug** deja de estar activo. Restaurarla reabre o reutiliza el estado compatible; un conflicto cancela toda la restauración.
- **Ramas:**
  - [Display] Cancelar conserva la observación; la confirmación explica eliminación, recuperación y copias externas.
  - [Display] La actividad identifica actor y fecha sin mostrar el contenido eliminado.
  - [Success] Eliminar la última pendiente limpia la señal originada por observaciones.
  - [Success] El borrado masivo envía una sola selección atómica y la restauración devuelve una observación desde la papelera.
  - [Failure] Un fallo mantiene la confirmación y el contenido visibles para reintentar o cancelar.
- **Cobertura:** ✅ display/success/failure.
- **E2E:** `e2e/admin/admin-document-observation-delete.spec.js`


## Section 30 — Responsive Compatibility Routes (Sep 1, 2026)

### FLOW: `platform-legacy-route-redirects`

- **Module:** platform
- **Role:** platform-admin / platform-client
- **Priority:** P2
- **Routes:** `/platform`, `/platform/dashboard`, `/platform/board`, `/platform/bugs`, `/platform/changes`, `/platform/deliverables`, `/platform/payments`, `/platform/access`, `/platform/collection-accounts`, `/platform/collection-accounts/:id`
- **Description:** Authenticated users opening a compatibility alias for a retired platform surface land on `/platform/projects` without returning to the legacy route or entering a redirect loop.
- **Outcome:** `success`
- **Coverage:** ✅ Covered in the five canonical responsive profiles.
- **E2E Spec:** `e2e/responsive/catalog-matrix.spec.js`


## Section 31 — Project Access Detail (Sep 5, 2026)

### FLOW: `platform-project-access-detail`

- **Module:** platform
- **Roles:** platform-admin, platform-client
- **Priority:** P1
- **Routes:** `/platform/projects/:id/access`
- **API:** project access endpoints under `/api/accounts/projects/:id/access/`
- **Interaction:** An admin reaches Accesos through project navigation and uses the shared editor over JWT transport.
- **Display outcome:** The scoped project detail renders both environments and masked credentials.
- **Success outcome:** An explicit field save updates the response through the platform endpoint.
- **Error outcome:** A client profile is redirected before the protected editor renders.
- **Failure outcome:** An API load failure appears with a retry control.
- **Coverage:** `e2e/platform/platform-project-access-detail.spec.js` and the five responsive platform profiles.


## Section 32 — Explainer Videos and Programa de Alianza (Sep 14, 2026)

### FLOW: `public-additional-modules-explainer`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Rutas:** `/:locale/additional-modules` y
  `/:locale/additional-modules/share/:uuid`
- **Interacción:** Encontrar la tarjeta del video explicativo debajo del título
  (primer bloque antes del primer módulo), reproducirlo en el mismo lugar con
  sonido y controles nativos, y usar el enlace directo al archivo si el
  navegador no puede reproducirlo. En inglés la tarjeta no aparece hasta tener
  el render en ese idioma. Si el interruptor del panel lo oculta (o, en un
  enlace compartido, el interruptor de ese enlace), la tarjeta no aparece y el
  encabezado se compacta.
- **Outcomes:** `display`, `success`, `failure`
- **Evidencia:** `ExplainerVideoCard.vue`, `useExplainerVideos.js`,
  `AdditionalModules/CatalogView.vue` (`showExplainer`), el flag
  `show_explainer_video` del payload público y
  `e2e/public/additional-modules.spec.js`.

- **Contenido audiovisual:** edición brag v2, 45 segundos en español con voz,
  música y subtítulos integrados. Fuentes originales conservadas.

### FLOW: `public-financing-explainer`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Ruta:** `/:locale/partnership-program` (la ruta vieja `/:locale/financing`
  responde 301 desde Django)
- **Interacción:** Reproducir el video explicativo del Programa de Alianza
  desde el hero (debajo del subtítulo y antes de los botones de WhatsApp y PDF)
  con sonido y controles nativos; si el navegador no puede reproducirlo, abrir
  el archivo desde el enlace de respaldo. En inglés la tarjeta no aparece hasta
  tener el render en ese idioma. Si el interruptor del panel lo oculta, la
  tarjeta no aparece y la guía empieza en "Dos formas de alianza".
- **Outcomes:** `display`, `success`, `failure`
- **Evidencia:** `ExplainerVideoCard.vue`, `useExplainerVideos.js`,
  `Financing/ProgramView.vue` (flag `show_explainer_video` del payload) y
  `e2e/public/financing.spec.js`.

- **Contenido audiovisual:** edición brag v2, 45 segundos en español con voz,
  música y subtítulos integrados. Fuentes originales conservadas.

### FLOW: `admin-additional-modules-explainer`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P3
- **Ruta:** `/:locale/panel/additional-modules`
- **Interacción:** Ver la tarjeta compacta del video explicativo junto al
  acceso rápido y reproducirlo para revisar lo que verá el cliente.
- **Outcomes:** `success`
- **Evidencia:** `pages/panel/additional-modules/index.vue`,
  `ExplainerVideoCard.vue` y `e2e/admin/admin-additional-modules.spec.js`.

- **Contenido audiovisual:** edición brag v2, 45 segundos en español con voz,
  música y subtítulos integrados. Fuentes originales conservadas.

### FLOW: `admin-additional-modules-explainer-visibility`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/:locale/panel/additional-modules`
- **Interacción:** Encender o apagar "Mostrar el video a los clientes" junto a
  la tarjeta compacta del video. El cambio se guarda al instante, se confirma
  con un aviso y agenda el rebuild de la página pública; si el guardado falla,
  el interruptor vuelve a su estado anterior y se avisa el error. El
  interruptor sigue visible con el panel en inglés.
- **Outcomes:** `success`, `failure`
- **Evidencia:** `ExplainerVisibilityToggle.vue`, `stores/explainer_videos.js`,
  `PATCH explainer-videos/admin/settings/update/` y
  `e2e/admin/admin-additional-modules.spec.js`.

### FLOW: `admin-additional-modules-share-video`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/:locale/panel/additional-modules` (modales de selección y de
  seguimiento)
- **Interacción:** Al preparar un enlace compartible, apagar "Mostrar el video
  explicativo en este enlace" (útil cuando se comparten pocos módulos y el
  video presenta el catálogo completo). Después, desde el seguimiento, volver
  a encender el video de un enlace puntual. Mientras el interruptor del
  catálogo está apagado, el seguimiento explica que ningún enlace lo muestra:
  el interruptor del catálogo manda sobre el del enlace.
- **Outcomes:** `success`, `display`
- **Evidencia:** `CatalogSelectionModal.vue`, `ShareHistoryModal.vue`,
  `stores/additional_modules.js` (`setShareLinkVideo`),
  `PATCH additional-modules/admin/shares/:uuid/` y
  `e2e/admin/admin-additional-modules.spec.js`.

### FLOW: `admin-financing-explainer`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P3
- **Ruta:** `/:locale/panel/partnership-program`
- **Interacción:** En la pestaña Programa, ver la tarjeta compacta del video
  explicativo bajo la distribución comercial y reproducirlo; la vista previa
  pública de más abajo no lo repite.
- **Outcomes:** `success`
- **Evidencia:** `pages/panel/partnership-program/index.vue`, `ExplainerVideoCard.vue`
  y `e2e/admin/admin-financing.spec.js`.

- **Contenido audiovisual:** edición brag v2, 45 segundos en español con voz,
  música y subtítulos integrados. Fuentes originales conservadas.

### FLOW: `admin-financing-explainer-visibility`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/:locale/panel/financing` (pestaña Programa)
- **Interacción:** Encender o apagar "Mostrar el video a los clientes" del
  Programa de Alianza, junto a la tarjeta compacta del video. El cambio se
  guarda al instante, se confirma con un aviso y agenda el rebuild de la
  página pública; si el guardado falla, el interruptor vuelve a su estado
  anterior y se avisa el error.
- **Outcomes:** `success`, `failure`
- **Evidencia:** `ExplainerVisibilityToggle.vue`, `stores/explainer_videos.js`,
  `PATCH explainer-videos/admin/settings/update/` y
  `e2e/admin/admin-financing.spec.js`.


## Unsectioned flows

### FLOW: `admin-accounting-income-reminder-mute`

- **Module:** admin
- **Role:** superuser admin
- **Priority:** P1
- **Routes:** `/panel/accounting/incomes`
- **API:** `POST /api/accounting/incomes/:id/mute/`
- **Description:** An uncollected expected income exposes **Silenciar avisos** in its row menu. The modal defaults to a dated silence with a future date prefilled, also offers an explicit indefinite mode, and refuses empty or non-future resume dates. A successful write updates the row in place: **Silenciado** or **Silenciado hasta {fecha}** appears beside its collection state. Opening the same menu then offers **Reactivar avisos**, which clears both mute fields without a confirmation. API failures leave the modal open and the row unchanged. The dedicated endpoint writes the accounting audit trail but deliberately sends no accounting-change email.
- **Steps:** navigate from the panel to Ingresos → open one pending expected income's actions → Silenciar avisos → choose a future date or Indefinidamente → save → verify the visible badge; reopen the row and reactivate when follow-up should resume.
- **Branches:** a date that is empty, today or earlier is blocked inline; a failed request preserves the prior state; paid, liquid and lost rows do not expose the action.
- **Coverage:** ✅ Covered — display, dated and indefinite success, manual reactivation, validation error and server failure.
- **E2E Spec:** `e2e/admin/admin-accounting-incomes.spec.js`

### FLOW: `admin-accounting-record-history`

- **Module:** admin
- **Role:** superuser
- **Priority:** P1
- **Routes:** `/panel/accounting`
- **Description:** Abre Detalle e historial o Ver historial de cambios desde ingresos, gastos, hosting, recurrentes, bolsillo, Ads, tarjetas, extractos, movimientos, alias, destinatarios, cuentas de cobro y configuración.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar el historial propio del registro contable y comparar los valores de dos versiones seleccionadas.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Display, success y failure validados en `admin/admin-entity-history.spec.js`; los trece tipos contables tienen cobertura de escritura en backend.

### FLOW: `admin-additional-modules-catalog`

- **Module:** admin / commercial
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/additional-modules`
- **Interaction:** Navigate from the panel sidebar, switch Spanish/English content, choose card/list/accordion presentation and retry a failed initial request. The chosen presentation is remembered for the panel surface.
- **Outcomes:** `success`, `display`, `failure`
- **Evidence:** `frontend/pages/panel/additional-modules/index.vue`, `GET /api/additional-modules/admin/`

### FLOW: `admin-additional-modules-manage`

- **Module:** admin / commercial
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/additional-modules`
- **Interaction:** Create or edit bilingual module content; a successful edit sends a `PATCH` and closes the form, while incomplete content and API failures remain visible inside it.
- **Outcomes:** `success`, `error`, `failure`
- **Evidence:** `ModuleFormModal.vue`, module create/update endpoints.

### FLOW: `admin-additional-modules-pdf`

- **Module:** admin / commercial
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/additional-modules`
- **Interaction:** Select catalog modules, document language and an optional client recipient, then download the personalized PDF without prices.
- **Outcomes:** `success`, `failure`
- **Evidence:** PDF selection modal and `POST /api/additional-modules/admin/pdf/`.

### FLOW: `admin-additional-modules-reorder`

- **Module:** admin / commercial
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/additional-modules`
- **Interaction:** Reorder categories/modules by controls or drag and save the complete optimistic-lock payload.
- **Outcomes:** `success`, `failure` (stale revision reloads the catalog)
- **Evidence:** `CatalogOrderModal.vue`, `POST /api/additional-modules/admin/reorder/`.

### FLOW: `admin-additional-modules-share`

- **Module:** admin / commercial
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/additional-modules`
- **Interaction:** Select modules and recipient, generate a fixed-selection link, then inspect openings or revoke it in Seguimiento.
- **Outcomes:** `success`, `error`, `failure`, `display`
- **Evidence:** `CatalogSelectionModal.vue`, `ShareHistoryModal.vue`, admin share endpoints.

### FLOW: `admin-client-change-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients`
- **Description:** Expande un cliente y abre Ver historial de cambios; consulta identidad, contacto y facturación con autor y fecha; pagina y compara versiones.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar contacto y facturación de una versión, comparar cambios e invertir la cronología.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Display, success y failure validados en `admin/admin-entity-history.spec.js`.

### FLOW: `admin-communication-folders`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/communications`
- **API:** `GET/POST /api/communications/folders/`, `PATCH/DELETE /api/communications/folders/:id/`, `PATCH /api/communications/threads/:id/`
- **Description:** El administrador organiza hilos completos en carpetas y subcarpetas propias del cliente o proyecto; conserva el histórico y encuentra su ubicación tras recargar.
- **Steps:** Seleccionar cliente/proyecto → crear carpeta y subcarpeta → abrir hilo → Mover a carpeta → guardar → seleccionar carpeta → recargar → verificar ubicación e ID. Retirar mediante Sin carpeta.
- **Branches:**
  - **display:** árbol, ruta, subcarpetas e IDs legibles al navegar desde el panel.
  - **success:** crear/renombrar/mover carpeta, clasificar hilo abierto o cerrado y restaurar el filtro desde la URL.
  - **error:** rechazo al eliminar una carpeta con contenido o mover fuera del contexto.
  - **failure:** error de carga/escritura muestra feedback y permite reintentar sin simular éxito.
- **Invariants:** las comunicaciones madre permanecen en la raíz; un hilo conserva mensajes y adjuntos; los archivados impiden eliminar su carpeta; una búsqueda recorre todas las carpetas del contexto seleccionado.
- **Specs:** `frontend/e2e/admin/admin-communication-filing.spec.js`.

### FLOW: `admin-document-change-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/documents/:id/edit`
- **Description:** Abre Historial desde el detalle del documento; consulta versiones completas y campos modificados, compara dos versiones o la anterior, invierte el orden y pagina.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar el contenido completo, comparar dos versiones o la anterior e invertir el orden o paginar la cronología.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Display, success y failure validados en `admin/admin-entity-history.spec.js`.

### FLOW: `admin-document-email-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/documents/:id/edit` → `/panel/emails?tab=history&email=:id`
- **Description:** El administrador ve los correos donde salió un documento y navega a la fila exacta del historial universal.
- **Interacciones y outcomes:**
  1. **display:** entrar al gestor, abrir un documento, leer **Este documento se envió en N correos** y comprobar asunto, destinatario, fecha y nombre archivado.
  2. **display:** pulsar una referencia y llegar al Historial con esa fila cargada y expandida.
  3. **success/error/failure:** n/a; es navegación de evidencia. La protección 409 al eliminar se cubre en integración backend.
- **E2E Spec:** `e2e/admin/admin-document-edit.spec.js`

### FLOW: `admin-document-gallery`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/documents`
- **Description:** El gestor cambia de Lista a Galería y ve una tarjeta por documento con vista previa Markdown saneada, cliente, fecha, episodios de estado activos y un resumen `+N` cuando hay desborde. El botón de tres puntos abre la misma hoja de acciones de la lista, conserva `Acciones de <título>` como nombre accesible, no emite `title` nativo y muestra un único aviso breve `Acciones`.
- **Steps:** entrar a Documentos → elegir Galería → leer una tarjeta real → enfocar o posar el cursor sobre el botón de acciones y ver un solo aviso `Acciones` → abrir la hoja de acciones.
- **Branches:** las subcarpetas aparecen primero y aceptan arrastre; la preferencia de vista persiste; en móvil la galería es obligatoria y el toque abre la hoja sin depender de hover.
- **Coverage:** ✅ Display y apertura de acciones cubiertos.
- **E2E Spec:** `e2e/admin/admin-document-gallery.spec.js`

### FLOW: `admin-document-list`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/documents`
- **Description:** El gestor usa el orden fijo acciones → título → estados → creado/fecha/archivado → cliente → proyecto. La fecha es la única columna ordenable: abre con los registros más nuevos, alterna ambos sentidos desde un icono accesible y serializa sólo el sentido no predeterminado como `?order=oldest`. Activos usan creación, Archivados usan fecha de archivado y Todos/búsqueda usan la fecha que muestra cada fila. Filtros, carpetas, scope, búsqueda y presentación conservan el sentido; una entrada nueva sin query vuelve a recientes. Galería y móvil exponen el mismo control en la barra porque no tienen encabezado. Los documentos manuales muestran episodios de workflow; las cuentas de cobro muestran en su lugar el estado comercial derivado (**Borrador, Emitida, Enviada, Envío fallido, Pagada o Anulada**). Una cuenta ya emitida sólo ofrece consulta, una descarga de su PDF contable y archivar/restaurar: no ofrece renombrar, mover, duplicar ni eliminar. El ciclo aparece primero y las señales después; **Solucionar bug** se distingue como acción pendiente y un desborde se resume en `+N`. En 412 px y 835 px el árbol de carpetas pasa a un drawer con foco contenido y la tarjeta conserva título/estados como información principal, seguida por fecha, cliente y proyecto. Desde 1195 px vuelve la estructura de dos zonas; Estados permanece como segunda columna, mientras Cliente/Proyecto se agrupan bajo Título hasta `panel-desktop` (1280 px). El botón de acciones conserva `Acciones de <título>` como nombre accesible, no emite `title` nativo y muestra un único aviso breve `Acciones`. En 2560 px el contenido completo queda centrado con un máximo de 1400 px.
- **Steps:** entrar desde la navegación del panel → confirmar nuevos primero → alternar el icono de Creado hacia antiguos y volver → cambiar carpeta/filtro sin perder el sentido → repetir desde Galería o móvil → leer un documento real → abrir el menú de la fila/tarjeta → cambiar entre activos, archivados y todos.
- **Branches:** un nombre largo de carpeta sigue legible dentro del drawer; el modo archivado ordena por `archived_at` y conserva su franja; Todos y búsqueda ordenan cada fila por la fecha visible; una falla al recargar conserva el orden y las filas anteriores; una cuenta emitida conserva el mismo estado comercial y las mismas acciones restringidas en tabla y tarjeta; por debajo de 1280 px sólo cliente y proyecto se agrupan dentro de la celda principal, mientras estado sigue visible; en táctil el control compacto reemplaza al encabezado sin duplicarlo; ningún ancho produce scroll horizontal de página.
- **Coverage:** ✅ Display responsivo cubierto en 412×915, 835×1194, 1195×835, 1440×900 y 2560×1440.
- **E2E Specs:** `e2e/admin/admin-document-list.spec.js`, `e2e/admin/admin-responsive-documents-clients-projects.spec.js`

### FLOW: `admin-document-navigation`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/documents`
- **API:** `GET /api/documents/navigation/`, `GET/PATCH /api/accounts/panel-preferences/documents/`, `GET /api/documents/`, `GET /api/document-folders/`
- **Description:** El administrador recorre el gestor por proyecto o por cliente con el mismo interruptor y en la misma posición que Comunicaciones. El catálogo muestra por defecto sólo proyectos operativos —incluido PRUEBA aunque tenga inventario cero— y «Ver proyectos no activos» es excluyente: encendido deja ver sólo el grupo donde aparece Candle y retira los activos del catálogo, sin archivar ningún documento. Este control local de la visita es independiente de «Ver documentos archivados», que cambia el ámbito de carpetas/documentos y se ubica justo antes de «Carpetas propias». Cada entrada muestra por separado cuántas carpetas y documentos tiene en el ámbito activo, archivado o combinado. «Sin proyecto» y «Sin cliente» permanecen visibles incluso con cero elementos. Al descender por las carpetas de una entidad, esa entidad sigue seleccionada y forma parte del origen al abrir un documento, de modo que «Volver» restaura el mismo recorrido. La preferencia se guarda por cuenta, mientras `?by=` permite compartir una visita sin cambiar esa memoria. «Carpetas propias» contiene exclusivamente raíces sin proyecto ni cliente; la conciliación es una tarea operativa interna y no genera avisos técnicos en esta navegación.
- **Steps:**
  1. El administrador entra al Gestor Documental y encuentra el interruptor Proyectos/Clientes encima de la navegación lateral.
  2. Recorre los proyectos operativos y activa «Ver proyectos no activos» cuando necesita consultar ese grupo; en cualquiera de los dos giros, un proyecto seleccionado que deje de listarse devuelve la selección a «Todos».
  3. Elige un proyecto o «Sin proyecto» y el listado consulta únicamente esa asociación.
  4. Dentro de un proyecto, abre una subcarpeta y luego un documento; al regresar desde el editor recupera la subcarpeta con el proyecto todavía seleccionado.
  5. Cambia a Clientes, elige una persona o «Sin cliente» y consulta su inventario.
  6. Sale del módulo y vuelve: el último modo elegido reaparece.
  7. Abre una carpeta propia; la navegación limpia cualquier proyecto o cliente previamente seleccionado.
- **Branches:**
  - [Branch A — Display] Cada entidad declara conteos separados de carpetas y documentos; los proyectos no operativos están ocultos al entrar y, mientras su control excluyente está encendido, son los únicos que se listan. Los clientes archivados tienen su propio grupo secundario, y desde el 31-ago-2026 el mismo interruptor excluyente lo gobierna: en modo cliente se rotula «Ver clientes archivados» y, apagado, los archivados no se listan.
  - [Branch B — Sin asignar] Las entradas «Sin proyecto»/«Sin cliente» existen permanentemente y filtran los registros sin esa asociación.
  - [Branch C — Memoria] Un cambio desde el interruptor hace `PATCH`; una visita posterior hidrata el modo mediante `GET`. Un `?by=` explícito sólo gobierna esa visita.
  - [Branch D — Carpetas propias] La sección manual no cambia al alternar el eje, excluye raíces que ya tengan proyecto o cliente y sigue navegable si falla la carga de facetas.
  - [Branch E — Contexto y ejes excluyentes] Elegir proyecto limpia cliente y elegir cliente limpia proyecto. Las carpetas descendientes de la entidad conservan el eje activo y ese origen sobrevive al ciclo documento→editor→volver; entrar a una carpeta propia o ajena limpia ambos ejes, sin enviar intersecciones accidentales.
  - [Branch F — Fallo recuperable] Un 5xx de `/documents/navigation/` muestra una explicación con «Reintentar» sin bloquear el resto del gestor.
  - [Branch G — Ámbitos independientes] «Ver proyectos no activos» no altera `scope`; «Ver documentos archivados» sigue filtrando contenido activo/archivado en cualquier proyecto, cliente o carpeta propia.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-navigation.spec.js`
- **Unit Tests:** `test/utils/documentNavigationFilters.test.js`, `test/components/FolderSidebar.spec.js`, `test/stores/document_navigation.test.js`, `test/composables/useDocumentFilterQuery.test.js`
- **Backend Tests:** `content/tests/views/test_document_navigation.py`, `accounts/tests/test_document_panel_preferences.py`

### FLOW: `admin-document-title-column-resize`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents`
- **Description:** Permite distinguir documentos con títulos extensos sin abrirlos. En tabla y tarjetas, el título queda contenido en una línea con puntos suspensivos; si se recorta, incluso después de cargar las fuentes web, un único aviso flotante de la aplicación muestra el nombre completo y **Ver completo** permite expandirlo por foco, toque o clic con corte seguro incluso cuando no contiene espacios. El aviso usa el mismo `BaseTooltip` de las acciones de fila, se mantiene dentro del viewport y no convive con un `title` nativo duplicado. Los avisos breves de acciones usan una sola línea horizontal y también permanecen contenidos en el viewport; los textos descriptivos largos conservan su ajuste multilínea. La carpeta y los demás distintivos quedan ordenados debajo del título, sin reservar una línea vacía en las filas de escritorio que no tienen carpeta. En la tabla, la manija visible y etiquetada del encabezado **Título** ajusta el ancho entre 240 y el máximo de inventario de 520 px, recuerda la preferencia del navegador y vuelve a 320 px con doble clic.
- **Steps:**
  1. Admin abre **Gestor Documental** y consulta el listado.
  2. Un título recortado —con espacios o con guiones bajos— muestra un solo aviso flotante y **Ver completo**; uno que cabe no agrega información repetida.
  3. Pulsa **Ver completo** en la tabla o tarjeta y el título se despliega sin abrir el documento.
  4. Comprueba que la carpeta aparece debajo del título y que títulos, carpeta y metadatos permanecen dentro de la fila o tarjeta.
  5. En la tabla, arrastra la manija de **Título** o la opera con teclado para elegir el ancho.
  6. Recarga la página y el ancho elegido se conserva.
  7. Hace doble clic en la manija para recuperar el ancho predeterminado.
- **Branches:**
  - [Display — contención] Los nombres reales largos, incluidos los escritos sin espacios, permanecen dentro de su celda o tarjeta en celular, tableta y escritorio; nunca invaden Cliente ni otro contenido.
  - [Display — recorte] El aviso flotante y el control de expansión sólo existen cuando la medición del texto confirma recorte, incluida la remedición tras cargar fuentes web; el control de acciones reutiliza el mismo aviso sin sumar un `title` nativo y su etiqueta breve se lee horizontalmente dentro del viewport.
  - [Display — metadatos] Carpeta aparece primero en el renglón inferior; Cliente, Proyecto y Estado siguen allí cuando el perfil compacto los oculta como columnas. Sin carpeta, la tabla de escritorio conserva altura natural.
  - [Success — consulta] **Ver completo** expande el nombre en el mismo contexto con `overflow-wrap:anywhere`, y **Contraer** recupera la línea truncada.
  - [Success — reparto] Proyecto, Cliente y Fecha ceden espacio en ese orden; Estados y Acciones conservan su ancho.
  - [Success — límite] El máximo de 520 px cubre el nombre más largo del inventario productivo vigente; tras alcanzar los mínimos de las columnas flexibles, la tabla habilita desplazamiento horizontal interno.
  - [Success — restablecer] El doble clic elimina la preferencia guardada y devuelve Título a 320 px.
- **Coverage:** ✅ Covered (aviso flotante único para título y acción, nombre corto sin ruido, carga tardía de fuentes, límite del inventario vigente, nombres reales sin espacios, contención geométrica en cinco viewports, expansión táctil en tabla y galería, orden de metadatos, arrastre persistente, columnas fijas y restablecimiento).
- **E2E Spec:** `e2e/admin/admin-document-title-column-resize.spec.js`

### FLOW: `admin-financing-settings`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/financing?tab=settings`
- **Interaction:** Consultar y publicar revisiones de la política comercial de financiación.

| Outcome | Inicio → acción → resultado observable |
|---|---|
| `display` | Abrir **Financiación → Configuración** → ver la revisión vigente, el rango elegible, el abono mínimo derivado, la tasa USD/COP y el historial. |
| `success` | Modificar una condición editable → pulsar **Publicar revisión** → confirmar → ver la nueva versión como vigente y conservar la anterior en el historial. |
| `error` | Ingresar un rango, porcentaje, plazo o ventana inválidos → intentar publicar → ver el error en el campo sin crear una revisión. |
| `failure` | Fallar la carga de la política → mostrar un estado de error explícito → reintentar → recuperar la configuración vigente. |

- **Reglas:** cada publicación crea una revisión inmutable; los nuevos borradores la adoptan automáticamente; los borradores anteriores sólo cambian por confirmación explícita; otrosíes listos, firmados, activos o completados nunca mutan; la tasa USD/COP se administra en Contabilidad y se congela por acuerdo.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-financing-settings.spec.js`
- **Backend Tests:** `content/tests/views/test_financing_agreements.py`, `content/tests/services/test_financing_policy_service.py`

# Personalizar la marca del Linktree

- **Rol:** admin. **Ruta:** `/panel/linktrees/:id/edit`.
- **Success:** editar colores/fuente, guardar y recargar conserva la apariencia;
  cargar una familia de Google Fonts la selecciona; subir/quitar logo actualiza la tarjeta.
- **Error:** una familia inexistente muestra error y conserva la selección.
- **Failure:** fallo de conexión a Google Fonts muestra aviso y permite reintentar.
- **Display:** entrar desde el listado muestra la apariencia y vista previa, también en móvil.
- **API:** PATCH de Linktree persiste colores y familia; POST/DELETE `logo/` guarda inmediatamente el logo independiente del avatar.
- **Cobertura:** `frontend/e2e/admin/admin-linktrees.spec.js` (API y Google Fonts simulados).
  Backend verifica persistencia real, serialización pública y rechazo de imágenes falsas.

# Plantillas HTML del Linktree

- **Flow:** `admin-linktree-templates`
- **Rol:** admin · **Prioridad:** P1
- **Ruta:** `/panel/linktrees/:id/edit` → Apariencia → Plantilla HTML.
- **Superficies:** `LinktreeTemplateEditor.vue`, store `linktree-templates.js`, API `linktree_template.py` y servicios `linktree_templates/`.

| Outcome | Interacciones que deben comprobarse |
| --- | --- |
| success | Seleccionar ZIP/archivos/carpeta, subir y esperar validación; publicar la candidata válida; aplicar plantilla compartida; reemplazar/restablecer un asset; restaurar una versión y publicar; volver al tema básico conservando historial. |
| error | Paquete inválido con archivo/línea; resultado visual inválido que bloquea publicación; perfil cambiado desde validación; imagen no editable o formato incompatible. |
| failure | Biblioteca/API no disponible con reintento; error recuperable de cola/Chromium; versión expirada; recursos o Google Fonts inaccesibles. |
| display | Entrar desde el listado, abrir editor y elegir ancho; comprobar iframe sandbox, las tres capturas, estado y versiones; bloqueo explicado si hay datos sin guardar o validación pendiente. |

El ámbito de compartición es el cliente del proyecto. Las pruebas backend comprueban el aislamiento entre clientes y los permisos de sesión/CSRF; los E2E comprueban el recorrido observable del editor y sus respuestas de API. Las mediciones reales de Chromium pertenecen a `test_linktree_template_browser.py`.

La ruta pública mantiene `public-linktree-view`: con `template_url` carga el HTML publicado; la ruta localizada de Django aplica CSP antes de entregar el documento. Los enlaces y acciones se verifican con una plantilla fixture controlada, sin depender de los identificadores internos `data-template-node`.

Selectores estables: `template-file-input`, `template-upload-validate`, `template-library-select`, `template-validating`, `template-valid`, `template-publish`, `template-revalidate`, `template-share`, `template-asset-<key>`, `template-issues`, `template-sandbox-preview`, `template-screenshots`, `template-version-select`, `template-restore`, `template-reset`.

### FLOW: `admin-monitoring-case-follow-up`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, modal desde el título de un caso.
- **Display:** evidencia, condición técnica y estado manual separados; historial paginado y enlace al reporte de origen cuando existe.
- **Success:** cambiar Pendiente / En revisión / Resuelto persiste el estado y la autoría.
- **Error:** una versión desactualizada devuelve conflicto y solicita actualizar.
- **Failure:** un fallo de guardado se anuncia sin perder la selección.
- **API:** detalle del caso y `POST /api/monitoring/cases/:id/state/`.
- **Cobertura:** `e2e/admin/admin-monitoring-case-follow-up.spec.js`.

### FLOW: `admin-monitoring-case-list`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring` desde Monitoreo en la navegación.
- **Display:** casos de proyectos, identidad del recurso y salud de las fuentes.
- **Success:** cambiar a Servidores o aplicar filtros muestra la lista correspondiente, con paginación de 25.
- **Failure:** una carga fallida muestra un aviso y permite actualizar, sin simular una lista saludable.
- **API:** `GET /api/monitoring/catalog/`, `GET /api/monitoring/cases/`.
- **Cobertura:** `e2e/admin/admin-monitoring-case-list.spec.js`.

### FLOW: `admin-monitoring-case-note`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, modal de caso.
- **Display:** historial con texto, autor y fecha de la nota.
- **Success:** escribir y agregar una nota la incorpora al historial compartido.
- **Error / failure:** un rechazo o fallo de API muestra el error y conserva el texto escrito.
- **API:** `POST /api/monitoring/cases/:id/notes/` y detalle del caso.
- **Cobertura:** `e2e/admin/admin-monitoring-case-follow-up.spec.js`.

### FLOW: `admin-monitoring-reports`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, pestaña Reportes.
- **Display:** reportes informativos y aviso de retención de 90 días.
- **Success:** abrir un reporte presenta texto plano, sin controles de seguimiento de casos.
- **Failure:** una carga fallida se comunica y permite volver a intentar.
- **API:** `GET /api/monitoring/reports/` y `GET /api/monitoring/reports/:id/`.
- **Cobertura:** `e2e/admin/admin-monitoring-case-list.spec.js`.

### FLOW: `admin-outbound-email-history-attachments`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/emails?tab=history`
- **Description:** El administrador reconoce y abre la evidencia exacta que acompañó cada correo, sin regenerarla desde el documento actual.
- **Interacciones y outcomes:**
  1. **display:** navegar a Emails, abrir Historial, expandir un envío y comprobar nombre, tipo documental, formato, tamaño individual, peso total, vínculo al documento y enlaces del contenido/plantilla.
  2. **display:** abrir **Previsualizar** y ver el PDF retenido en el visor compartido.
  3. **display:** un snapshot sin archivos afirma “Este correo no llevaba adjuntos”; un registro legado revela la brecha y no ofrece descarga.
  4. **success/error/failure:** n/a; esta interacción sólo consulta evidencia. Descarga/autorización y bytes exactos se verifican en integración backend.
- **E2E Spec:** `e2e/admin/admin-client-email-copy-settings.spec.js`

### FLOW: `admin-outbound-email-history-body`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/emails?tab=history`
- **Description:** El administrador expande un correo de Seguridad y acceso y abre **Ver contenido completo**. El cuerpo retenido —incluidos OTP, invitaciones o credenciales— se carga por un endpoint administrativo y se muestra dentro de un iframe sandboxed, tal como advierte Configuración.
- **Interacciones y outcomes:**
  1. **display:** navegar al Historial, expandir una fila de Seguridad, abrir el visor y comprobar contenido real devuelto por la API dentro del iframe.
  2. **success:** n/a; la consulta no muta datos.
  3. **error:** el permiso se prueba en integración backend; una sesión no administrativa no puede alcanzar el panel.
  4. **failure:** el error de carga se presenta dentro del modal y se cubre en unidad/store; el E2E focal valida el cuerpo exitoso.
- **E2E Spec:** `e2e/admin/admin-client-email-copy-settings.spec.js`

### FLOW: `admin-outbound-email-history-filter`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/emails?tab=history`
- **Description:** El administrador llega desde la navegación del panel al Historial universal y acota las salidas por destinatario, familia, estado, rango de fechas, presencia de adjuntos y tipo documental/formato; el servidor devuelve la fila principal coincidente sin limitar el resultado al compositor manual.
- **Interacciones y outcomes:**
  1. **display:** navegar a Emails, abrir Historial, completar los filtros —incluidos **Con adjuntos** y **Cuenta de cobro/PDF**— y comprobar tanto los parámetros enviados como los datos reales de la fila resultante.
  2. **success:** n/a; filtrar no muta datos.
  3. **error:** n/a; los valores pertenecen a catálogos o controles de fecha y no existe una validación editable independiente.
  4. **failure:** la falla de carga se cubre en la frontera del store; esta interacción sólo registra la consulta exitosa con datos.
- **E2E Spec:** `e2e/admin/admin-client-email-copy-settings.spec.js`

### FLOW: `admin-outbound-email-history-resend`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/emails?tab=history`
- **Description:** Reenvía desde el snapshot inmutable y permite cambiar sólo el destinatario; asunto, cuerpo y archivos permanecen bloqueados.
- **Interacciones y outcomes:**
  1. **success:** expandir un correo capturado, abrir **Reenviar exacto**, editar el destinatario y confirmar; el modal cierra y el panel confirma la nueva entrega.
  2. **failure:** si el SMTP rechaza el reenvío, el modal conserva el destinatario y muestra el error sin afirmar éxito.
  3. **error:** la validación de dirección inválida pertenece al contrato backend/input email y no amplía el cuerpo editable.
  4. **display:** el modal enumera el asunto y adjuntos bloqueados antes de confirmar.
- **E2E Spec:** `e2e/admin/admin-client-email-copy-settings.spec.js`

# Enlaces anteriores del Programa de Alianza

- **Rol:** administrador.
- **Success:** abrir `/panel/financing`, `/new` o `/:id` conduce a la ruta
  equivalente en `/panel/partnership-program`; conserva idioma y parámetros.
- **Error:** sin sesión, el destino exige autenticación administrativa.
- **Failure:** no aplica a la redirección local; los errores de datos pertenecen
  a los flujos existentes del programa y sus otrosíes.
- **Display:** no aplica: la ruta anterior no muestra una vista propia.

# Marca y recursos del proyecto

- **Ruta/rol:** `/panel/projects`, admin, Acciones → Marca y recursos.
- **Success:** vincular/desvincular un Linktree conserva su URL pública; subir un archivo con nombre y categoría, descargarlo y eliminarlo previa confirmación.
- **Error:** carga rechazada conserva los campos y no añade un recurso.
- **Failure:** carga de biblioteca fallida muestra aviso y reintento.
- **Display:** abrir el modal desde el listado muestra los recursos o estados vacíos, también en móvil.
- **Cobertura:** `frontend/e2e/admin/admin-project-brand.spec.js`, API simulada; `backend/content/tests/views/test_project_brand.py` verifica persistencia, aislamiento, permisos y archivos privados reales.

### FLOW: `admin-project-change-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects`
- **Description:** Abre el detalle de accesos y su pestaña Historial; consulta URLs, notas y credenciales enmascaradas, revela un secreto por acción explícita y lo oculta al cerrar.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar una versión histórica de accesos, revelar una credencial por acción explícita y ocultarla al terminar la consulta.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Display, success y failure validados en `admin/admin-entity-history.spec.js`.

### FLOW: `admin-project-lifecycle-states`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects`
- **API:** `POST /api/projects/<id>/state-transitions/preview/`, `POST /api/projects/<id>/state-transitions/`, `GET /api/projects/<id>/state-history/`
- **Description:** El cambio de estado es una operación de negocio en dos pasos: primero explica el significado y calcula las consecuencias, después aplica exactamente ese impacto mediante token. En evolución distingue un producto en producción con una siguiente versión en desarrollo y conserva el efecto operativo de Activo. Suspendido detiene nueva facturación y avisos sin borrar deuda causada; Completado exige cierre limpio; Dado de baja cancela futuro y obliga a decidir conservar o castigar cada saldo causado. Una baja directa requiere nota. Un cambio financiero entre preview y confirmación invalida el token y deja el modal abierto. El histórico conserva episodios, fechas efectivas, actores y notas.
- **Interaction matrix:**

| Interaction | Outcome | Start → end state |
|---|---|---|
| Abrir histórico desde la fila | display | Proyectos → Histórico → episodios reales con fecha, actor y nota |
| Suspender después de revisar consecuencias | success | Activo → preview → confirmación → fila Suspendido y nuevo episodio |
| Registrar trabajo evolutivo sin apagar la operación | success | Activo → ayuda En evolución → preview → fila En evolución con efecto operativo |
| Intentar baja directa incompleta | error | Preview de baja → falta decisión o nota → confirmar permanece bloqueado |
| Confirmar un preview financiero obsoleto | failure | Preview → cambian cobros → HTTP 409 visible y modal conserva el contexto |

- **Coverage:** ✅ Las cuatro clases están cubiertas.
- **E2E Specs:** `e2e/admin/admin-project-lifecycle-states.spec.js`

### FLOW: `admin-project-state-catalog`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/projects/statuses`
- **API:** `GET|POST /api/project-states/`, `PATCH /api/project-states/<id>/`, `POST /api/project-states/<id>/retire/`, `POST /api/project-states/<id>/merge/`
- **Description:** El catálogo compartido de PA-88 se reutiliza para proyectos con el mismo componente de administración. Los seis estados semilla son visibles: En desarrollo, Activo, En evolución, Suspendido, Completado y Dado de baja. Suspendido es la única detención reversible y conserva la deuda causada mientras detiene cobros y avisos nuevos. El usuario puede descubrir otros con el uso, crearlos, renombrarlos, describirlos, recolorearlos, fusionarlos y retirarlos. Los campos obligatorios se identifican en su etiqueta y los mensajes locales/API aparecen junto a su control después del intento; una selección de fusión faltante sigue ese patrón, mientras la restricción permanente de los estados semilla permanece como ayuda accesible. Todo proyecto permanece en Documentos y Comunicaciones; el efecto operativo sólo lo agrupa entre activos o archivados, sin archivar sus documentos. La ayuda contextual combina la descripción editable con una consecuencia del sistema derivada del efecto operativo protegido que gobierna cobros y cierres.
- **Interaction matrix:**

| Interaction | Outcome | Start → end state |
|---|---|---|
| Abrir el catálogo desde Proyectos | display | Proyectos → Administrar estados → seis semillas, ayuda, usos e histórico |
| Crear, renombrar o retirar un estado libre | success | Formulario/edición → catálogo refrescado sin perder histórico |
| Intentar crear sin requisitos | error | Acción disponible → mensajes junto a nombre, efecto y descripción; sin request |
| Intentar fusionar sin destino | error | Confirmar fusión → mensaje junto al selector; elegir destino lo limpia |
| Retirar un estado usado | error | Confirmar retiro → explicación de proyectos activos → estado permanece |
| Guardar durante una falla del servidor | failure | Editar nombre → HTTP 5xx visible → borrador permanece para reintentar |

- **Coverage:** ✅ Las cuatro clases están cubiertas.
- **E2E Specs:** `e2e/admin/admin-project-lifecycle-states.spec.js`

### FLOW: `admin-proposal-change-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** Abre Historial en una propuesta; consulta precio y alcance por versión, compara versiones o la última enviada correctamente y consulta su evidencia.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar precio y alcance históricos y comparar una versión con la última enviada correctamente.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Display, success y failure validados en `admin/admin-entity-history.spec.js`.

### FLOW: `admin-proposal-document-markdown`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/panel/proposals/:id/edit` → Documentos; disponible en `sent`, `viewed`, `negotiating`, `accepted` y `rejected`.
- **Display:** acciones de copia para contrato generado, comercial, técnico y adjuntos compatibles; PDF e imágenes conservan su visor; DOCX/XLSX presentan Markdown y tablas con advertencia. Todo adjunto conserva descarga del original.
- **Success:** Copiar Markdown solicita el documento elegido, escribe su contenido en el portapapeles y confirma Copiado. Contrato usa el snapshot guardado; comercial y técnico comparten los bloques curados del PDF.
- **Error:** DOC/XLS requieren conversión e imágenes requieren OCR. Archivo vacío, escaneado, protegido, corrupto o fuera de límites devuelve un error recuperable.
- **Failure:** errores de extracción, archivo ausente o portapapeles bloqueado permiten reintentar. Cerrar el visor aborta su solicitud pendiente.
- **Límites:** 15 MB, 100 páginas PDF, 20.000 celdas XLSX, 50 MB expandidos y un millón de caracteres; sin macros, consultas externas ni OCR.
- **E2E Spec:** `e2e/admin/admin-proposal-document-markdown.spec.js`.

### FLOW: `admin-proposal-first-view-retry`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit` (Analytics tab)
- **Description:** Recover a failed first-view email alert without fabricating another client view or resetting proposal analytics.
- **Steps:**
  1. Admin opens a proposal and navigates to the Analytics tab.
  2. The delivery card shows `Falló`, the attempt count, and the last sanitized error.
  3. Admin clicks `Reintentar alerta`.
  4. On success, the API resets the durable state to `Pendiente`, queues the task, and the card refreshes.
  5. On server failure, the card remains failed and the retry remains available.
- **Outcome classes:** success and failure covered; validation error is n/a because the retry action is hidden outside the failed state; delivery-state display is covered by `admin-proposal-analytics`.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-proposal-analytics.spec.js`

### FLOW: `admin-proposal-formalization-delivery`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/proposals/:id/edit` → Documentos
- **Recorrido:** abrir una propuesta desde el panel; entrar en Documentos; descargar o previsualizar anexos formales; abrir Formalización; elegir contrato final, anexos y adjuntos propios; editar Para/CC, asunto y secciones; preparar; revisar correo y archivos exactos; enviar.
- **Display:** contenido real de la propuesta, plantilla precargada, disponibilidad, destinatarios y manifiesto de archivos preparados.
- **Success:** preparar una selección válida, revisar sus bytes y enviarla; aparece confirmación y evidencia en Correos.
- **Error:** datos requeridos o adjuntos no disponibles impiden preparar; revisión obsoleta, vencida o consumida muestra un error accionable.
- **Failure:** falla de carga o preparación conserva el formulario; resultado incierto de envío consulta el estado y evita un segundo envío automático.
- **Límites:** preparación privada de 24 horas, hasta 20 secciones y 10 destinatarios; sin transición automática del estado comercial.

# admin-pwa-install — Instalación del panel interno

- **Rol:** administrador. **Prioridad:** P2.
- **Entrada:** barra lateral o menú móvil de cualquier vista del panel.
- **Success:** pulsar Instalar ProjectApp, aceptar el diálogo y ocultar la oferta.
  Cancelarlo permite intentarlo después; cerrar la invitación persiste durante
  la sesión del navegador. La invitación solo aparece en el dashboard y no
  desplaza los datos de los módulos operativos.
- **Display:** abrir el menú móvil y la ayuda; consultar instrucciones del
  navegador y el requisito de conexión.
- **Failure:** el navegador rechaza el diálogo; mostrar ayuda y mensaje de error.
- **Error:** no aplica; no hay formulario ni nuevos permisos.
- **Specs:** `frontend/e2e/admin/admin-pwa-install.spec.js`. El diálogo del
  sistema operativo se simula en esa frontera; las interacciones del panel son reales.
- **Límite manual:** verificar el ícono instalado y la apertura standalone en
  dispositivos Chrome/Edge y Safari iOS; Playwright no acredita esa instalación nativa.

# admin-pwa-offline — Apertura y recuperación sin conexión

- **Rol:** administrador. **Prioridad:** P2.
- **Entrada:** abrir o recargar la app instalada.
- **Success:** al volver internet, Reintentar recupera la URL original. Abrir
  el start_url sin sesión conduce al login real de Django con next al panel.
- **Failure:** sin conexión, Reintentar mantiene el aviso y la URL.
- **Display:** integrado en el resultado del fallo de navegación.
- **Error:** no agrega validaciones; los HTTP 4xx/5xx conservan su respuesta.
- **Specs:** `frontend/e2e/pwa/panel-offline.spec.js`, ejecutado contra un
  build servido por Django mediante `playwright.pwa.config.js`.
- **Privacidad:** solo falla a una pantalla autónoma; no escribe Cache Storage,
  no guarda respuestas privadas y no encola operaciones. Las exclusiones de
  rutas y métodos se verifican en los tests del worker.

### FLOW: `admin-secure-link-create`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links` → **Nuevo enlace**.
- **Success:** elegir tipo, título, campos, vigencia e idioma crea el enlace y muestra una única vez la URL con copiar enlace y copiar mensaje sugerido.
- **Error:** si falta un campo obligatorio (por ejemplo, la contraseña) el formulario muestra el error del servidor en ese campo y no crea nada.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/create/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`.

### FLOW: `admin-secure-link-manage`

- **Módulo / rol:** enlaces seguros / administrador del panel.
- **Ruta:** `/panel/secure-links`; `?link=<id>` abre el detalle (destino del correo de aviso).
- **Display:** pestañas por estado con conteos y **Recibidos** con los enlaces sin abrir que envían los clientes.
- **Success:** el detalle muestra historial, **Ver contenido** descifra sin gastar el enlace, **Revocar** lo desactiva y **Reactivar** lo vuelve a habilitar (opcionalmente con un enlace nuevo).
- **API:** `GET /api/secure-links/`, `GET /api/secure-links/<id>/`, `POST .../content/`, `POST .../revoke/`, `POST .../reactivate/`.
- **Cobertura:** `e2e/admin/admin-secure-links.spec.js`.

### FLOW: `proposal-closing-contact`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** El cliente llega al panel final “Gracias por tu tiempo” y encuentra allí el mensaje comercial, las acciones principales y los canales de contacto, separados de la nota de compromiso.
- **Steps:**
  1. El cliente recorre la propuesta hasta el panel de cierre.
  2. El panel muestra el llamado “¿Listo para comenzar?”.
  3. Se presentan las acciones comerciales configuradas.
  4. Se muestran Email, WhatsApp y Website con sus enlaces correspondientes.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-kickoff-closing-content.spec.js`

### FLOW: `proposal-kickoff-disclosure`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** El cliente revisa la nota de compromiso y el plan de kickoff en columnas con ancho cómodo cuando la pantalla lo permite. La información que condiciona la activación del cronograma permanece resumida en un desplegable para no desbalancear la sección.
- **Steps:**
  1. El cliente navega a la sección de nota final.
  2. A 1366 px, la nota/compromisos y el plan de kickoff aparecen en columnas de más de 520 px; en pantallas menores se apilan.
  3. El bloque “Información necesaria para activar el cronograma” inicia cerrado.
  4. El cliente expande el bloque.
  5. Se muestran la introducción y los pasos requeridos antes de iniciar.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-kickoff-closing-content.spec.js`

### FLOW: `proposal-payment-plan-closing`

- **Module:** proposal
- **Role:** guest (via shared UUID link)
- **Priority:** P2
- **Routes:** `/proposal/:uuid`
- **Description:** El cliente revisa cerca de las acciones de cierre los hitos del plan de pagos y el total de la propuesta, con moneda e IVA visibles.
- **Outcomes:**
  - `display` — el panel final muestra las cuotas configuradas y conserva el sufijo fiscal del total.
- **Steps:**
  1. El cliente recorre la propuesta hasta el panel de cierre.
  2. El panel presenta el plan de pagos configurado junto a las acciones de respuesta.
  3. El total mantiene la moneda y el texto `+ IVA` sin duplicarlos.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/proposal/proposal-payment-plan-closing.spec.js`

### FLOW: `public-additional-modules-catalog`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/additional-modules`
- **Interaction:** Follow the footer link, reach the catalog near the top without the panel/global header, read active modules in Spanish or English, choose card/list/accordion presentation, use the four catalog floating controls and retry a failed live request. The chosen presentation is remembered separately from the panel.
- **Outcomes:** `success`, `display`, `failure`
- **Evidence:** public catalog page/component and `GET /api/additional-modules/public/`.

### FLOW: `public-additional-modules-detail`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/additional-modules`
- **Interaction:** Open a module card, read what it is, purpose, problems, integrations and requirements in the active light/dark theme, then close back to the opener.
- **Outcomes:** `success`
- **Evidence:** `AdditionalModules/CatalogView.vue`.

### FLOW: `public-additional-modules-guide`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Rutas:** `/:locale/additional-modules` y
  `/:locale/additional-modules/share/:uuid`
- **Interacción:** En la primera visita, recorrer una guía específica del
  catálogo que empieza en la tarjeta del video explicativo y cerrarla; en
  visitas posteriores, reiniciarla desde el control flotante.
- **Outcomes:** `success`, `display`
- **Evidencia:** `AdditionalModules/Onboarding.vue` y
  `e2e/public/additional-modules.spec.js`.

### FLOW: `public-additional-modules-pdf`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Routes:** canonical catalog and shared selection
- **Interaction:** Download the full or selected no-price PDF in the active catalog language from the header or floating action; unavailable shares return 410.
- **Outcomes:** `success`, `failure`
- **Evidence:** public PDF endpoints and the shared/catalog download control.

### FLOW: `public-additional-modules-share`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/additional-modules/share/:uuid`
- **Interaction:** Open a prepared selection, record one first-party browser session, read only selected live modules, switch between Spanish and English and copy the unchanged current URL without creating a new token; revoked/empty selections show an unavailable state.
- **Outcomes:** `success`, `display`, `failure`
- **Evidence:** share page, public share and tracking endpoints.

### FLOW: `public-additional-modules-theme`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Rutas:** `/:locale/additional-modules` y
  `/:locale/additional-modules/share/:uuid`
- **Interacción:** Alternar entre modo claro y oscuro, leer el índice y el
  detalle con el mismo tema y recuperar esa preferencia en una visita posterior.
- **Presentación:** página, tarjetas e interiores se distinguen en ambos temas;
  las categorías se separan con espacio, sin líneas decorativas. La primera
  entrada de cada sección tiene una transición breve, desactivada con movimiento
  reducido. El nuevo observer no impone un estado oculto previo; su fallback
  ante API no disponible se verifica en pruebas unitarias.
- **Outcomes:** `success`, `display`, `failure`
- **Failure:** El mensaje de carga fallida y el catálogo recuperado con
  Reintentar conservan el tema elegido, también en selecciones compartidas.
- **Evidencia:** `useAdditionalModulesTheme.js`, `CatalogView.vue` y
  `e2e/public/additional-modules.spec.js`, `commercial-public-theme.spec.js`,
  `commercial-public-overlays.spec.js` y `commercial-public-motion.spec.js`.

### FLOW: `public-financing-guide`

- **Módulo:** public
- **Rol:** invitado
- **Prioridad:** P2
- **Ruta:** `/:locale/partnership-program`
- **Interacción:** En la primera visita, recorrer la guía del programa (empieza
  en la tarjeta del video explicativo y sigue por opciones, condiciones,
  calculadora, paquete, reglas y acciones flotantes) y cerrarla; en visitas
  posteriores, reiniciarla desde el control flotante. La vista previa del panel
  no la muestra.
- **Outcomes:** `success`, `display`
- **Evidencia:** `PublicGuidedTour.vue`, `Financing/Onboarding.vue`,
  `Financing/ProgramView.vue` y `e2e/public/financing.spec.js`.

### FLOW: `public-financing-language`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/partnership-program`
- **Interaction:** Use the language selector and continue on the reciprocal canonical route with localized commercial content.
- **Outcomes:** `success`
- **Evidence:** financing language control, Nuxt i18n routes and localized API payload.

### FLOW: `public-financing-load`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/partnership-program`
- **Interaction:** See an explicit unavailable state after the live request fails, then retry and recover the program content.
- **Outcomes:** `failure`, `success`
- **Evidence:** public financing page live-load and retry states.

### FLOW: `public-financing-overview`

- **Module:** public
- **Role:** guest
- **Priority:** P1
- **Route:** `/:locale/partnership-program`
- **Interaction:** Navegar desde el pie público y comparar las dos modalidades y ocho condiciones; la exclusividad conceptual de Project App. se ofrece sólo a cinco años para proyectos competidores del mismo sector y nicho. Consultar también calculadora, paquete mensual y contacto por WhatsApp.
- **Outcomes:** `display`
- **Evidence:** public financing page/component and `GET /api/financing/public/`.

### FLOW: `public-financing-pdf`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/partnership-program`
- **Interaction:** Download the complete localized booklet; if generation fails, remain on the page with a visible retryable error.
- **Outcomes:** `success`, `failure`
- **Evidence:** public PDF control and `GET /api/financing/public/pdf/`.

### FLOW: `public-financing-share`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/partnership-program`
- **Interaction:** Abrir el diálogo de Compartir; copiar la URL exacta (idioma, query y hash) o abrir el selector nativo. Escape devuelve el foco al control flotante.
- **Outcomes:** `success`, `failure`
- **Failure:** Si falla el portapapeles, mostrar un error recuperable dentro del diálogo. Cancelar el selector nativo no es un error.
- **Evidence:** `PublicDocumentShareButton.vue`, montado desde `Financing/ProgramView.vue`.

### FLOW: `public-financing-terms`

- **Module:** public
- **Role:** guest
- **Priority:** P2
- **Route:** `/:locale/partnership-program`
- **Interaction:** Expandir una regla para leer su detalle. La no competencia conceptual exige la modalidad de cinco años, coincidencia de sector, nicho y proyecto competidor, con alcance escrito; un segundo ciclo no extiende su vigencia.
- **Outcomes:** `success`
- **Evidence:** `Financing/ProgramView.vue` agreement-rule disclosures.

# Tema del Programa de Alianza

- **Rol:** visitante.
- **Success:** cambiar entre claro y oscuro conserva legibilidad de contenido,
  controles y diálogos en los cinco perfiles responsive. Recargar restaura la
  elección sin cambiar el tema del panel.
- **Presentación:** tarjetas elevadas sobre el fondo, interiores diferenciados
  y encabezado sin separador horizontal, tanto en claro como en oscuro. Las
  secciones entran una sola vez con transición breve; movimiento reducido
  desactiva esa entrada. El nuevo observer no impone un estado oculto previo.
- **Failure:** una carga fallida conserva el tema guardado en el mensaje de
  error y al recuperar el programa con Reintentar.
- **Error:** no hay entradas inválidas para este interruptor; almacenamiento
  no disponible no impide usar el tema durante la visita.
- **Display:** no se registra una interacción adicional; se valida como parte
  del cambio de tema.

### FLOW: `public-secure-link-create`

- **Módulo / rol:** enlaces seguros / cliente sin sesión.
- **Ruta:** `/{locale}/secure-link`, compartida desde el panel con **Enlace para clientes**.
- **Success:** tipo, campos, nombre, vigencia (1–7 días) y captcha generan una URL de un solo uso para copiar o enviar por correo; sólo el equipo puede abrirla y el equipo recibe un aviso sin el enlace ni el contenido.
- **Error:** los campos obligatorios faltantes o un captcha fallido se muestran en el formulario sin crear el enlace.
- **API:** `GET /api/secure-links/public/types/`, `POST /api/secure-links/public/create/`.
- **Cobertura:** `e2e/public/public-secure-links.spec.js`, `e2e/responsive/public.spec.js`.

### FLOW: `public-secure-link-reveal`

- **Módulo / rol:** enlaces seguros / destinatario sin sesión.
- **Ruta:** `/{locale}/secure-link/view#<token>` (el token viaja en el fragmento).
- **Display:** tipo, remitente, vencimiento y advertencia de un solo uso; cargar la página no gasta el enlace.
- **Success:** **Ver contenido** revela los campos una vez, con mostrar/ocultar y copiar.
- **Failure:** enlaces usados, vencidos, revocados o inválidos muestran su estado sin contenido; los creados por clientes piden iniciar sesión del equipo.
- **API:** `POST /api/secure-links/public/status/`, `POST /api/secure-links/public/reveal/`.
- **Cobertura:** `e2e/public/public-secure-links.spec.js`, `e2e/responsive/public.spec.js`.
