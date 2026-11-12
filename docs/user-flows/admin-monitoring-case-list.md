### FLOW: `admin-monitoring-case-list`

- **Módulo / rol:** monitoreo / administrador del panel.
- **Ruta:** `/panel/monitoring` desde Monitoreo en la navegación.
- **Display:** indicadores del conjunto filtrado completo, atención prioritaria, salud de fuentes y tarjetas compactas con identidad y fechas.
- **Success:** elegir proyecto/servidor, fuente, estado, gravedad, condición, seguimiento, texto o fechas; abrir filtros desde indicadores y detalle de salud de una fuente; Limpiar filtros; navegar una consulta estable de 25 registros y conservar selección en URL.
- **Error:** fechas invertidas o consulta vencida muestran explicación y permiten recuperar la consulta sin perder filtros.
- **Failure:** fallos de lista, catálogo o chequeo de estado quedan visibles; no se simula una lista saludable.
- **API:** catalog, cases y status de `/api/monitoring/`.
- **Pruebas:** `e2e/admin/admin-monitoring-case-list.spec.js`; ejecución y SHA se acreditan en CI.
