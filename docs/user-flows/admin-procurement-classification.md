### FLOW: `admin-procurement-classification`

- **Module:** procurement
- **Role:** staff admin
- **Priority:** P1
- **Routes:** `/panel/procurement`
- **Description:** Staff opens official detail, records personal analysis, discards with a required reason and restores the previous state. Team notes and decision history remain visible. Al recargar, el formulario recupera el estado y la nota del staff de la sesión. Otro staff ve el formulario inicial y puede consultar el seguimiento del equipo.
- **Coverage:** ✅ Covered
- **E2E Spec:** `frontend/e2e/admin/admin-procurement.spec.js` (validado en navegador)
