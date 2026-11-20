### FLOW: `admin-requirement-calculator-revision-restore`

- **Module:** commercial
- **Role:** admin
- **Priority:** P2
- **Route:** `/panel/requirement-calculator`
- **Description:** El administrador consulta revisiones paginadas, carga una anterior en el editor y la publica como una nueva revisión inmutable. Si falla la carga o publicación, no sustituye silenciosamente la definición vigente.
- **Steps:** Abrir Versiones → consultar motivo y fecha → restaurar → comprobar el editor → confirmar Guardar.
- **Branches:** Versiones muestra un aviso si todavía no hay publicaciones. Con más de 20 revisiones aparecen los controles de paginación. Una falla al cargar muestra el error y conserva la definición actual y las revisiones históricas.
- **Coverage:** ✅ Covered — `display`, `success`, `failure`; ejecución de navegador aprobada en `frontend/e2e/admin/admin-requirement-calculator.spec.js`, incluida la publicación confirmada como nueva revisión.
