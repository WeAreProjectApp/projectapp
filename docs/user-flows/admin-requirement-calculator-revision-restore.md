### FLOW: `admin-requirement-calculator-revision-restore`

- **Module:** commercial
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/requirement-calculator`
- **Description:** El administrador consulta revisiones paginadas, carga una anterior en el editor y la publica como una nueva revisión inmutable. Si falla la carga o publicación, no sustituye silenciosamente la definición vigente.
- **Steps:** Abrir Versiones → consultar motivo y fecha → restaurar → comprobar el editor → confirmar Guardar.
- **Branches:** Una falla al cargar conserva la definición actual y muestra el error; el pasado no se sobrescribe.
- **Coverage:** ✅ Covered — `display`, `success`, `failure`; ejecución de navegador aprobada en `frontend/e2e/admin/admin-requirement-calculator.spec.js`, incluida la publicación confirmada como nueva revisión.
