### FLOW: `platform-project-ideas`

- **Module:** platform
- **Roles:** platform-client, platform-admin
- **Priority:** P1
- **Route:** `/platform/projects/:id/ideas`
- **Interaction:** The current client writes or corrects suggestions with preserved authorship and revision history, with object isolation and recoverable failed submissions.
- **Coverage:** `frontend/e2e/project-collaboration/ideas.spec.js`; APIs reales JWT o sesión/CSRF en SQLite y almacenamiento temporales.
- **Success:** operación explícita persistida y resultado observado en UI.
- **Error:** permisos de objeto o versión/fuente obsoleta denegados sin escritura parcial.
- **Failure:** fallo del servicio informado conservando borrador/selección y sin datos anteriores.
- **Display:** navegación por el enlace de proyecto, texto real o dato habilitado de la fixture.
