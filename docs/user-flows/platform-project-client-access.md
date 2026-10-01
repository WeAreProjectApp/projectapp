### FLOW: `platform-project-client-access`

- **Module:** platform
- **Roles:** platform-client
- **Priority:** P1
- **Route:** `/platform/projects/:id/access`
- **Interaction:** A client sees only approved project/environment fields, explicitly reveals a granted credential and loses that action when revoked. Default hidden access preserves other modules.
- **Coverage:** `frontend/e2e/project-collaboration/client-access.spec.js`; APIs reales JWT o sesión/CSRF en SQLite y almacenamiento temporales.
- **Success:** operación explícita persistida y resultado observado en UI.
- **Error:** permisos de objeto o versión/fuente obsoleta denegados sin escritura parcial.
- **Failure:** fallo del servicio informado conservando borrador/selección y sin datos anteriores.
- **Display:** navegación por el enlace de proyecto, texto real o dato habilitado de la fixture.
