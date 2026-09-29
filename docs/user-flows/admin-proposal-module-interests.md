### FLOW: `admin-proposal-module-interests`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/proposals/:id/edit`
- **Description:** El vendedor consulta los intereses del cliente como información comercial. Su posterior acuerdo se incorpora manualmente al alcance y a la inversión.
- **Steps:**
  1. Abrir la propuesta en el panel y consultar General.
  2. Leer la lista de módulos de interés y la fecha de su última actualización.
  3. Abrir Actividad y consultar el registro automático de la selección o su retiro.
- **Branches:**
  - Sin selecciones previas no se muestra una fecha inventada.
  - El retiro de todos los intereses queda registrado con fecha y actividad.
  - Los nombres registrados se conservan aunque se edite o desactive el catálogo.
- **E2E Spec:** `e2e/admin/admin-proposal-module-interests.spec.js`
- **Components:** `ProposalGeneralTab.vue`, `ProposalActivityTab.vue`
