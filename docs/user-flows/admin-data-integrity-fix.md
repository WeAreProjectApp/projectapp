### FLOW: `admin-data-integrity-fix`

- **Módulo:** admin
- **Rol:** administrador del panel con sesión, incluida integridad financiera.
- **Prioridad:** P1
- **Ruta:** `/panel/data-integrity`, desde Sistema o Radar de atención.
- **Descripción:** El administrador selecciona hasta veinte hallazgos corregibles, elige parámetros y revisa antes/después y bloqueos. La aplicación requiere motivo y confirmación del impacto vigente. Un lote bloqueado o vencido no modifica registros.
- **Éxito:** interacción completa con vista previa y confirmación cuando hay una decisión o corrección.
- **Error:** entrada inválida, bloqueo de negocio o impacto desactualizado muestra una alerta sin aplicar cambios.
- **Fallo:** errores de red o del servidor conservan el último resultado válido y permiten reintentar.
- **Visualización:** presenta resultados, fechas, motivo y estado observables; una consulta vacía explica su alcance.
- **E2E Specs:** `frontend/e2e/admin/admin-data-integrity.spec.js` y `frontend/e2e/responsive/data-integrity.spec.js`.
- **Backend:** pruebas de observaciones, alcance contable, organización documental, permisos y compatibilidad MCP.
