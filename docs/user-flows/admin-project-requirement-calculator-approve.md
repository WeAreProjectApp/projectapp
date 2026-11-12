### FLOW: `admin-project-requirement-calculator-approve`

- **Module:** projects
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/requirement-calculator?project=<id>`
- **Description:** El administrador confirma la aprobación de un borrador limpio. La aprobación genera el PDF, lo asigna al proyecto, guarda el evento en el historial y deja la versión congelada. Un conflicto, PDF no generado o falla de servidor conserva el borrador.
- **Steps:** Abrir borrador limpio → escribir motivo → Aprobar → confirmar → comprobar estado, historial y tarjetas de sólo lectura.
- **Branches:** Cambios pendientes deshabilitan Aprobar. Conflicto, PDF no generado o 5xx conserva el borrador.
- **Coverage:** ✅ Covered — `display`, `success`, `error`, `failure`; ejecución de navegador aprobada en `frontend/e2e/admin/admin-project-requirement-calculator.spec.js`.
