# ProjectApp

Custom Software Development Company — full-stack web application with a dynamic business proposal system, portfolio showcase, and client-facing marketing pages.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Django 6.1, Django REST Framework, MySQL |
| **Frontend** | Nuxt 4, Pinia (Options API), TailwindCSS, GSAP |
| **Task Queue** | Huey + Redis |
| **Email** | SMTP via GoDaddy (`team@projectapp.co`) |
| **Auth** | Django session + CSRF (`/panel/`), JWT via SimpleJWT (`/platform/`) |
| **Deployment** | Gunicorn + Nginx, systemd services |

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/gustavop-dev/projectapp.git
cd projectapp
```

### 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py create_fake_data 5
```

### 3. Start the backend server

```bash
source .venv/bin/activate
python3 manage.py runserver
```

### 4. Frontend setup (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

### 5. Useful commands

```bash
# Create fake business proposals with sections and requirements
python3 manage.py create_fake_proposals

# Delete all fake data
python3 manage.py delete_fake_data
```

---

## Codex Ecosystem

ProjectApp uses a Codex-first methodology and automation stack:

- Always-on runtime instructions:
  - `AGENTS.md`
  - `backend/AGENTS.md`
  - `frontend/AGENTS.md`
- Native repo skills: `.agents/skills/*`
- Project config: `.codex/config.toml`
- Compatibility surfaces: `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`, `.claude/`

Main references:

- Methodology guide: `docs/CODEX_METHODOLOGY_GUIDE.md`
- Setup & activation: `docs/CODEX_SETUP.md`
- Migration history: `docs/CODEX_MIGRATION_MAP.md`

Workflow naming policy:

- Canonical debug workflow: `$debug`
- Legacy alias kept for compatibility: `debugme`

Sensitive operational skills are manual-only (`deploy-and-check`, `git-commit`, `git-sync`, `blog-ai-weekly`) and use dual safeguards:

- `disable-model-invocation: true` in `SKILL.md`
- `policy.allow_implicit_invocation: false` in `agents/openai.yaml`

---

## Project Structure

```
projectapp/
├── backend/
│   ├── content/
│   │   ├── models/          # Django models (Contact, Design, Product, BusinessProposal, ...)
│   │   ├── serializers/     # DRF serializers
│   │   ├── views/           # @api_view function-based views
│   │   ├── services/        # Business logic (ProposalService, ProposalEmailService)
│   │   ├── tasks.py         # Huey async tasks (reminders, expiration)
│   │   ├── templates/       # Email HTML/text templates
│   │   └── management/      # Custom management commands
│   └── projectapp/          # Django project settings, URLs, WSGI
├── frontend/
│   ├── pages/               # Nuxt file-based routing
│   ├── components/          # Vue components (BusinessProposal/, animations/, layouts/)
│   ├── stores/              # Pinia stores (products.js, proposals.js)
│   ├── composables/         # Vue composables (useExpirationTimer, useProposalNavigation)
│   ├── middleware/           # Nuxt route middleware (admin-auth.js)
│   └── layouts/             # Nuxt layouts (default.vue, admin.vue)
└── docs/                    # Architecture standards, testing guides
```

---

## Business Proposal System

A complete feature for creating, sending, and tracking personalized business proposals for prospective clients. Proposals are presented as a beautiful fullscreen horizontal-scroll experience, with automated email reminders and expiration tracking.

### How It Works

**For the Admin (you):**

1. **Create a proposal** — Go to `/panel/proposals/create` or Django Admin. Fill in client name, email, investment amount, currency, and expiration date.
2. **12 sections auto-generated** — Each proposal starts with pre-filled default content for all 12 sections (Greeting, Executive Summary, Timeline, Investment, etc.).
3. **Edit sections** — Open `/panel/proposals/{id}/edit`, switch to the "Sections" tab, expand any section, and edit its JSON content. Enable/disable sections as needed.
4. **Send to client** — Click "Send to Client". The system sets the status to SENT, records the timestamp, and schedules an automatic email reminder for day 5.
5. **Track engagement** — See view count, first viewed date, and status changes (SENT → VIEWED → ACCEPTED/REJECTED) in real-time.

**For the Client (your prospect):**

1. **Receives a unique link** — e.g., `https://projectapp.co/proposal/d5d2d7f7-b7b8-419b-a423-90ad795ba2b3`
2. **Fullscreen presentation** — A horizontal-scroll experience with GSAP animations. No header, no footer — just the proposal.
3. **Navigation** — Floating index panel on the left to jump between sections, section counter (3/12) in the top-right corner.
4. **Expiration countdown** — Badge showing "Expires in 5 days" with color-coded urgency (green → yellow → red).
5. **If expired** — Shows a branded "This proposal has expired" page with WhatsApp and email contact buttons.
6. **Day-5 reminder** — Automatic branded HTML email: "Your proposal is waiting — view it before it expires."

### Admin Panel Screenshots Flow

```
/panel/                        → Dashboard: total proposals, status counts, recent list
/panel/proposals/              → Table: title, client, status badge, investment, expiry, views, actions
/panel/proposals/create        → Form: title, client name, email, investment, currency, expiry, reminder days
/panel/proposals/{id}/edit     → Tab 1: General (metadata + send button) | Tab 2: Sections (expand/edit JSON)
```

### Client View Sections

Each proposal contains up to 12 sections, rendered as fullscreen panels with horizontal scroll:

| # | Section | Description |
|---|---------|-------------|
| 1 | **Greeting** | Personalized welcome with client name and inspirational quote |
| 2 | **Executive Summary** | Project overview, key highlights |
| 3 | **Context & Diagnostic** | Client's current situation, challenges, opportunities |
| 4 | **Conversion Strategy** | Step-by-step approach to achieve results |
| 5 | **Design & UX** | Visual design philosophy and focus areas |
| 6 | **Creative Support** | Collaborative design process details |
| 7 | **Development Stages** | Visual timeline from proposal to delivery (wide panel) |
| 8 | **Functional Requirements** | Grouped requirements with items, options, fields (wide panel) |
| 9 | **Timeline** | Phase-by-phase project schedule with milestones (wide panel) |
| 10 | **Investment** | Total cost, payment options, hosting plan, value proposition |
| 11 | **Final Note** | Personal message and commitment badges |
| 12 | **Next Steps** | How to proceed, CTAs, contact methods |

### Technical Architecture

**Backend (Django):**
- **4 models**: `BusinessProposal`, `ProposalSection`, `ProposalRequirementGroup`, `ProposalRequirementItem`
- **8 serializers**: List, Detail, CreateUpdate variants for proposals and sections
- **10 API endpoints**: Public (retrieve by UUID, PDF placeholder), Admin (CRUD, send, reorder sections), Auth check
- **2 Huey tasks**: `send_proposal_reminder` (scheduled per-proposal), `expire_stale_proposals` (daily cron)
- **Email service**: HTML + text templates via `EmailMultiAlternatives`

**Frontend (Nuxt 3):**
- **Pinia store**: `proposals.js` — 11 actions covering public fetch, admin CRUD, auth check
- **2 composables**: `useProposalNavigation` (section tracking), `useExpirationTimer` (countdown)
- **Client view**: `pages/proposal/[uuid].vue` — GSAP horizontal scroll with `ScrollTrigger` + `ScrollToPlugin`
- **5 UX overlay components**: `ProposalIndex`, `SectionCounter`, `ExpirationBadge`, `PdfDownloadButton`, `ProposalExpired`
- **Admin pages**: Dashboard, proposals list, create, edit (with section JSON editor)
- **Auth middleware**: `admin-auth.js` — checks Django session via `/api/auth/check/`

**Key API Endpoints:**

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/proposals/{uuid}/` | Public | Client views proposal (tracks views) |
| GET | `/api/proposals/` | Admin | List all proposals |
| POST | `/api/proposals/create/` | Admin | Create with 12 auto-generated sections |
| PATCH | `/api/proposals/{id}/update/` | Admin | Update metadata |
| POST | `/api/proposals/{id}/send/` | Admin | Mark as SENT + schedule reminder |
| PATCH | `/api/proposals/sections/{id}/update/` | Admin | Edit section content |
| DELETE | `/api/proposals/{id}/delete/` | Admin | Delete proposal (cascade) |
| GET | `/api/auth/check/` | Auth | Verify staff session for Nuxt admin |

### Proposal Lifecycle

```
DRAFT → SENT → VIEWED → ACCEPTED
                      → REJECTED
                      → EXPIRED (auto, daily cron)
```

- **DRAFT**: Created, not yet sent to client
- **SENT**: Email scheduled, `sent_at` recorded, reminder queued for day N
- **VIEWED**: Client opened the link (first view tracked)
- **ACCEPTED/REJECTED**: Manual status update by admin
- **EXPIRED**: Auto-set by daily Huey task when `expires_at < now()`

---

## Deployment

See [docs/deployment-guide.md](docs/deployment-guide.md) for initial setup and full documentation.

Producción usa `/deploy-and-check` del toolkit `vps-ops-toolkit`: una
transacción de Integrity con preparación aparte, publicación de artefactos y
recuperación. `scripts/deploy.sh` está retirado y rechaza cualquier ejecución.
El éxito depende del cierre de Integrity, después del control de salud.

La identidad del backend se consulta en `/api/version/`; la del frontend, en
`/version.json`. El SHA se fija durante el build. El registrador de GitHub
Deployments pertenece al toolkit y se implementa por separado.

Contrato y traspaso de controles: [Interfaz de versión de despliegue](docs/DEPLOYMENT_VERSION_INTERFACE.md).

---

## Reference Implementations

- [Candle Project](https://github.com/carlos18bp/candle_project)
- [Jewel Project](https://github.com/carlos18bp/jewel_project)
- [Dress Rental Project](https://github.com/carlos18bp/dress_rental_project)
- [Sign In/Sign On Feature](https://github.com/carlos18bp/signin_signon_feature)
