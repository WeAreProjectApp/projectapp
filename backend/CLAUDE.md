# Backend Rules — ProjectApp

## Stack And Scope
- Django 6.1 + DRF backend.
- Project apps are `content`, `accounts`, `monitoring`, and `secure_links`.
- Production settings module: `projectapp.settings_prod`.

## Project Conventions
- DRF views are function-based views with `@api_view`.
- Keep view functions focused on request/response wiring.
- Put business rules in services, serializers, helpers, or model methods.
- Prefer Django ORM queries. Use raw SQL only when strictly necessary and parameterized.
- Preserve the bilingual field pattern (`*_en`, `*_es`) where it already exists.
- Proposal and email flows rely heavily on service-layer behavior; read the relevant service before changing view logic.
- Large files such as `backend/content/views/proposal.py` should receive minimal, deliberate edits.

## MCP Parity Gate
- Every change to a model, serializer, service, status transition, or relation exposed by an MCP connector must review that connector in the same delivery.
- Classify every current model field in `content/mcp/contracts.py` as read-only, read/write, or intentionally excluded with a reason; the contract test must remain green.
- Keep tool descriptions and JSON schemas aligned with actual handlers, and route MCP writes through the same serializer/service guardrails as the panel.
- Update `docs/MCP_VALIDATION_RUNBOOK.md` and run the focused MCP create/read/update/error slice whenever the exposed contract changes.

## Auth And Security
- `/panel/` admin flows use session auth + CSRF.
- `/platform/` API flows use JWT via SimpleJWT in the `accounts` app.
- Validate input in serializers or dedicated validators.
- Never hardcode secrets or bypass CSRF/security middleware for convenience.

## Commands
- Activate venv from repo root: `source .venv/bin/activate`
- Run backend tests: `cd backend && pytest path/to/test_file.py -v`
- Run a focused backend check: `cd backend && python manage.py check`
- Run dev server: `cd backend && python manage.py runserver`

## Testing Rules
- Run only the changed test file or a tight regression slice.
- Never run the full backend suite.
- Keep test names focused on one observable behavior.
- Prefer deterministic tests: freeze time, seed data explicitly, and avoid hidden global state.
