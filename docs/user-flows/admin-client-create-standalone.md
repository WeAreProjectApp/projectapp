### FLOW: `admin-client-create-standalone`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/clients/`
- **Description:** Create a new client profile standalone (without a proposal) from the clients page via the "+ Nuevo cliente" modal. Email is optional — if omitted the backend generates a placeholder `cliente_<id>@temp.example.com` and the client shows a placeholder badge.
- **Steps:**
  1. Admin clicks "+ Nuevo cliente" button (data-testid: `clients-new-button`).
  2. Modal opens with name, email, phone, company, identification type (NIT / C.C.), identification number, address and billing code. Short fields share rows when space permits.
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

La ficha guarda por separado NIT y cédula: una cédula no se convierte en NIT.
La cuenta nueva toma nombre legal, identificación y tipo, contacto, correo y
dirección de esa misma ficha. La edición de estos datos está disponible en
Clientes y desde «Editar ficha del cliente» dentro de una cuenta nueva.
