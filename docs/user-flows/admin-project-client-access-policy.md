### FLOW: `admin-project-client-access-policy`

- **Module:** admin
- **Roles:** admin, platform-admin
- **Priority:** P1
- **Route:** `/platform/projects/:id/access`
- **Interaction:** Admin explicitly enables each available project/access datum, saves a source-bound version and previews the limited client projection, handling stale values and load failures.
- **Coverage:** `frontend/e2e/project-collaboration/client-access.spec.js`; APIs reales JWT o sesión/CSRF en SQLite y almacenamiento temporales.
- **Success:** operación explícita persistida y resultado observado en UI.
- **Error:** permisos de objeto o versión/fuente obsoleta denegados sin escritura parcial.
- **Failure:** fallo del servicio informado conservando borrador/selección y sin datos anteriores.
- **Display:** navegación por el enlace de proyecto, texto real o dato habilitado de la fixture.
