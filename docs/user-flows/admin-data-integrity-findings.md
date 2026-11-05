### FLOW: `admin-data-integrity-findings`

- **Módulo:** admin
- **Rol:** administrador del panel con sesión, incluida integridad financiera.
- **Prioridad:** P1
- **Ruta:** `/panel/data-integrity`, desde Sistema o Radar de atención.
- **Descripción:** Un administrador consulta resultados privados persistidos, inicia una revisión completa o acotada, filtra módulo/gravedad/estado y pagina. Una revisión fallida conserva el último resultado válido. El radar abre el fingerprint exacto y permite regresar a todos los hallazgos.
- **Éxito:** interacción completa con vista previa y confirmación cuando hay una decisión o corrección.
- **Error:** entrada inválida, bloqueo de negocio o impacto desactualizado muestra una alerta sin aplicar cambios.
- **Fallo:** errores de red o del servidor conservan el último resultado válido y permiten reintentar.
- **Visualización:** presenta resultados, fechas, motivo y estado observables; una consulta vacía explica su alcance.
- **E2E Specs:** `frontend/e2e/admin/admin-data-integrity.spec.js` y `frontend/e2e/responsive/data-integrity.spec.js`.
- **Backend:** pruebas de observaciones, alcance contable, organización documental, permisos y compatibilidad MCP.
