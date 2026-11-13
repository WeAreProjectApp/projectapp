### FLOW: `admin-monitoring-server-trends`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring`, pestaña Servidores.
- **Display:** capacidad y última muestra por servidor; gráficas de RAM, disco, CPU y carga con unidades, leyenda y huecos reales. Ausencia explícita de histórico.
- **Success:** elegir servidor y periodos 24 h/7 d/30 d/90 d solicita las muestras correspondientes.
- **Error:** no aplica al selector cerrado de periodos; su validación del servidor pertenece a backend.
- **Failure:** una serie fallida muestra aviso y reintento.
- **API:** GET status y servers/:id/series de `/api/monitoring/`.
- **Pruebas:** `e2e/admin/admin-monitoring-server-trends.spec.js`; ejecución y SHA se acreditan en CI.
