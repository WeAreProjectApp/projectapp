### FLOW: `admin-data-integrity-fix`

- **Módulo:** admin
- **Rol:** administrador del panel con sesión, incluida integridad financiera.
- **Prioridad:** P1
- **Ruta:** `/panel/data-integrity`, desde Sistema o Radar de atención.
- **Descripción:** El administrador selecciona hasta veinte hallazgos corregibles, elige parámetros y revisa los cambios y bloqueos. Al corregir el nombre de un proyecto identifica cada registro y campo y compara sus valores exactos. La aplicación requiere motivo y confirmación del impacto vigente. Un lote bloqueado o vencido no modifica registros.
- **Éxito:** interacción completa con vista previa y confirmación cuando hay una decisión o corrección.
- **Error:** entrada inválida, bloqueo de negocio o impacto desactualizado muestra una alerta sin aplicar cambios.
- **Fallo:** errores de red o del servidor conservan el último resultado válido y permiten reintentar.
- **Visualización:** la vista previa de NM1 identifica cada registro del proyecto y distingue los espacios del valor original, el nombre propuesto y los cambios de relación que correspondan.
- **E2E Specs:** `frontend/e2e/admin/admin-data-integrity.spec.js` y `frontend/e2e/responsive/data-integrity.spec.js`.
- **Backend:** pruebas de observaciones, alcance contable, organización documental, permisos y compatibilidad MCP.
