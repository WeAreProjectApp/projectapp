### FLOW: `admin-service-contract-settings`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/panel/proposals` → Configuraciones
- **Recorrido:** abrir Configuraciones, editar catálogos de duración y preavisos, elegir las tres preselecciones y guardar.
- **Display:** muestra duración en meses, lista compartida de preavisos en días y tres preselecciones independientes; explica la conservación de contratos existentes.
- **Success:** guarda mediante PATCH de company-settings y las siguientes aperturas del modal reciben la configuración.
- **Error:** impide listas vacías, duplicados, números fuera de 1–999 o preselecciones fuera de las opciones; muestra errores junto al control.
- **Failure:** la carga ofrece Reintentar; un guardado rechazado conserva los valores editados y permite otro intento.
