### FLOW: `admin-project-idea-collection`

- **Module:** admin
- **Roles:** admin
- **Priority:** P1
- **Route:** `/panel/projects/:id/ideas`
- **Interaction:** Admin opens the idea workspace from the selected project three-point menu, selects exact idea versions from one project and client, preserves internal snapshots for future evaluation and resolves stale or failed requests without changing contracts.
- **Coverage:** `frontend/e2e/project-collaboration/ideas.spec.js`; APIs reales JWT o sesión/CSRF en SQLite y almacenamiento temporales.
- **Success:** operación explícita persistida y resultado observado en UI.
- **Error:** permisos de objeto o versión/fuente obsoleta denegados sin escritura parcial.
- **Failure:** fallo del servicio informado conservando borrador/selección y sin datos anteriores.
- **Display:** navegación desde el menú de tres puntos del proyecto seleccionado, texto real o dato habilitado de la fixture.
