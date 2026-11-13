### FLOW: `admin-monitoring-reports`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, pestaña Reportes.
- **Display:** total filtrado, última observación, reportes paginados y retención; detalle original como texto sin controles de casos.
- **Success:** filtrar por recurso/fuente/texto/fechas, limpiar y navegar páginas de una consulta estable; abrir un reporte.
- **Error:** fechas invertidas o snapshot vencido tienen recuperación explícita.
- **Failure:** fallo de carga visible sin simular éxito.
- **API:** GET reports y reports/:id de `/api/monitoring/`.
- **Pruebas:** `e2e/admin/admin-monitoring-case-follow-up.spec.js`; ejecución y SHA se acreditan en CI.
