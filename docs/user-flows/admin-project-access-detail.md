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

- **PA-225:** El detalle ofrece Abrir espacio en la plataforma por ID en nueva pestaña.
