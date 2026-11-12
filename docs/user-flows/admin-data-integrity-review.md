### FLOW: `admin-data-integrity-review`

- **Módulo:** admin
- **Rol:** administrador del panel con sesión, incluida integridad financiera.
- **Prioridad:** P1
- **Ruta:** `/panel/data-integrity`, desde Sistema o Radar de atención.
- **Descripción:** El administrador acepta como intencional o reabre un hallazgo presente con motivo y confirmación. La decisión conserva actor y fecha. Evidencia nueva vuelve a pendientes y un conflicto no cambia la decisión.
- **Éxito:** interacción completa con vista previa y confirmación cuando hay una decisión o corrección.
- **Error:** entrada inválida, bloqueo de negocio o impacto desactualizado muestra una alerta sin aplicar cambios.
- **Fallo:** errores de red o del servidor conservan el último resultado válido y permiten reintentar.
- **Visualización:** presenta resultados, fechas, motivo y estado observables; una consulta vacía explica su alcance.
- **E2E Specs:** `frontend/e2e/admin/admin-data-integrity.spec.js`.
- **Backend:** pruebas de observaciones, alcance contable, organización documental, permisos y compatibilidad MCP.
