### FLOW: `admin-monitoring-case-follow-up`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, detalle desde evento o atención prioritaria.
- **Display:** condición técnica y estado humano separados, observaciones etiquetadas que conservan cero/false, JSON original desplegable y notas/entregas con páginas independientes.
- **Success:** guardar estado con versión vigente y consultar el reporte relacionado conservando el regreso al caso.
- **Error:** un conflicto de versión exige actualizar, sin sobrescribir el seguimiento vigente.
- **Failure:** un fallo de carga o guardado mantiene abierto el detalle y permite reintentar.
- **API:** GET cases/:id y POST cases/:id/state de `/api/monitoring/`.
- **Pruebas:** `e2e/admin/admin-monitoring-case-follow-up.spec.js`; ejecución y SHA se acreditan en CI.
