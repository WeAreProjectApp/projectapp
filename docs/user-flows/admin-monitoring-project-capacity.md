### FLOW: `admin-monitoring-project-capacity`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, Proyectos al elegir un proyecto.
- **Display:** servidor relacionado, asignación/compartido/sin configurar y unidades; consumo por proyecto no disponible e historial de cambios.
- **Success:** registrar cantidades informativas y consultar el historial con autor y antes/después. Guardar no cambia cuotas reales.
- **Error:** cantidades inválidas o versión en conflicto se explican, conservando la edición.
- **Failure:** carga o guardado fallido permite reintentar sin inventar consumo.
- **API:** GET/PUT resources/:id/capacity y GET resources/:id/capacity/history de `/api/monitoring/`.
- **Pruebas:** `e2e/admin/admin-monitoring-project-capacity.spec.js`; ejecución y SHA se acreditan en CI.
