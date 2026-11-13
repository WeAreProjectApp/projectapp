# Monitoreo: prioridades, tendencias y capacidad — PA-249

## Qué se muestra

Monitoreo mantiene Proyectos, Servidores y Reportes. Los selectores del proyecto aplican cambios al elegir; el texto espera 300 ms. Limpiar restablece filtros, fechas y página. La URL conserva la selección. Las fechas son inclusivas en la zona horaria de Django; una fecha inicial posterior a la final devuelve 400.

Los KPIs cuentan **casos**, no detecciones: total del conjunto filtrado, condición técnica activa por gravedad y seguimiento Pendiente/En revisión. Un caso recuperado puede seguir pendiente; uno cerrado manualmente puede seguir técnicamente activo. El detalle y las transiciones mantienen esa separación. Reportes cuenta reportes informativos, nunca incidencias.

La salud de fuentes conserva Sin datos, Actualizada, Atrasada y Deshabilitada. Se aplica el ámbito de tipo/recurso/fuente, no fechas, búsqueda de eventos, gravedad ni estado humano. La presión actual sólo se muestra con muestras de hasta dos minutos: RAM/disco >=85 % de su capacidad y carga de un minuto >=3 por vCPU. Son las referencias actuales de server-alerts; no cambian sus correos, cooldown o automatismos. Sin cobertura no se declara un servidor sano.

## Consulta estable y detalle

Los listados mantienen páginas de 25. `snapshot=new` en cases/reports crea una consulta estable de 15 minutos vinculada al actor y a los filtros. Devuelve `snapshot`, `captured_at`, `revision`, `summary`, `attention`, `sources` y el sobre paginado habitual. Se guardan proyecciones livianas por página en la caché; no se copia evidencia extensa. Las páginas siguientes envían el token y los mismos filtros. Token vencido, ajeno o incompatible devuelve 409 y exige actualizar explícitamente; no se mezclan resultados. Una página fuera de rango vuelve a la última disponible. Sin snapshot se conserva el contrato anterior.

El chequeo cada minuto consulta `/api/monitoring/status/`: avisa cambios sin reemplazar la consulta ni cerrar un detalle. Actualizar conserva filtros y crea otra consulta desde página 1. La capacidad y las gráficas indican su fecha y disponibilidad de forma independiente del listado congelado.

Los indicadores de gravedad abren el listado con `condition=active` y la gravedad elegida. Seguimientos pendientes usa `followup=true` (pending/reviewing), sin cambiar el significado de los estados existentes. Ambos filtros quedan visibles y se limpian con los demás. Los indicadores de fuentes abren sus detalles, con recurso, última observación, intervalo esperado y error. Actualizar recarga también la asignación del proyecto seleccionado.

El detalle permite `activities_page` y `deliveries_page`, con sus totales independientes; `page` sigue siendo compatible. `history_snapshot=true` devuelve `history_bounds.activities/deliveries`; reenviarlos como `activities_before/deliveries_before` conserva el límite superior durante la navegación. Los nuevos recibos no desplazan páginas anteriores. Las notas en preparación sobreviven a cambios de página. Tras guardar o actualizar se abre un corte nuevo del historial.

La vista principal de observaciones omite null y cadenas vacías; mantiene cero y false. El desplegable Datos técnicos muestra el objeto original como texto, sin HTML ejecutable ni filtrado destructivo. Las reglas de retención preexistentes siguen vigentes: PA-249 no reconstruye observaciones podadas.

## Mediciones reales

La nueva fuente `telemetry` pertenece exclusivamente a un recurso de servidor. Ingestión v1 admite de forma aditiva `kind=metric` y `metrics`: `cpu_percent` (0–100 o null), `cpu_count`, `load_1m`, `ram_total_bytes`, `ram_used_bytes`, `disk_total_bytes`, `disk_used_bytes`. Rechaza valores no finitos, capacidades cero, uso mayor que capacidad, campos desconocidos, recursos fuera de credencial y mediciones de proyectos. La recepción crea una muestra y un recibo idempotentes; no crea un caso ni aumenta detecciones. Cambiar el contenido de la misma identidad devuelve 409.

El toolkit lee `/proc/meminfo` (usado = MemTotal − MemAvailable), diferencias de `/proc/stat` (idle incluye iowait), `/proc/loadavg` y `statvfs` del filesystem raíz (usado = bloques − bloques libres). Capacidad en bytes, CPU en porcentaje del conjunto de procesadores y carga en procesos; la carga no es un porcentaje. Primera muestra, reinicio o discontinuidad de contadores dejan CPU null. La cola y los reintentos existentes conservan la misma identidad.

`GET /api/monitoring/servers/<server_id>/series/?period=24h|7d|30d|90d` devuelve intervalos de 5 min/30 min/2 h/6 h, promedio, máximo y cantidad real de muestras por intervalo. Los huecos son null, sin interpolación; la captura conserva cada minuto y la vista agrupa hasta 361 intervalos para mantener una respuesta acotada, con sus máximos y cantidades visibles. Un intervalo parcial promedia sólo las muestras recibidas. La capacidad usa las muestras del periodo, no una extrapolación del presente. El gráfico indica periodo, unidades, leyenda y última actualización. Sin muestras indica Sin histórico. Se conservan 90 días; limpieza acotada por lotes, manteniendo el horizonte de reintentos para entregas tardías.

## Capacidad por proyecto

`GET|PUT /api/monitoring/resources/<resource_id>/capacity/` consulta o registra una asignación informativa de un recurso técnico de proyecto. Cada dimensión tiene modalidad unknown/shared/assigned. Asignada requiere cantidad positiva; las otras requieren null. CPU se expresa en vCPU; RAM y almacenamiento se persisten en bytes y se editan en GiB. Version 0 crea el registro; las siguientes ediciones envían la versión leída y una versión antigua devuelve 409 sin sobrescribir. Actor y valores anteriores/posteriores quedan en el historial paginado `/capacity/history/`.

La primera página del historial devuelve `history_bounds.changes`. Reenviarlo como `changes_before` mantiene el total y las filas del mismo corte aunque otro operador registre una asignación; el límite 0 conserva un corte vacío. Omitirlo inicia una consulta nueva. El Panel conserva ese límite al paginar y lo renueva al recargar o guardar capacidad, sin cambiar el registro de auditoría.

Guardar **no cambia** systemd, cgroups, planes comerciales ni cuotas. La relación con servidor es la ya configurada en el inventario. Consumo por proyecto permanece no disponible: ni repartir la RAM del servidor ni presentar un límite de Gunicorn como todo el proyecto representa una medición atribuible.

## Permisos y MCP

Las API conservan SessionAuthentication, CSRF e IsAdminUser. Staff tiene el ámbito administrativo global existente; no se añade acceso para clientes JWT. Un ID de servidor no sirve para editar capacidad de proyecto. Las credenciales de ingestión conservan su alcance por recurso.

MCP Proyectos incorpora `get_monitoring_catalog`, `get_monitoring_status`, `list_monitoring_cases`, `get_monitoring_case`, `set_monitoring_case_state`, `add_monitoring_case_note`, `list_monitoring_reports`, `get_monitoring_report`, `get_monitoring_server_series`, `get_monitoring_capacity`, `update_monitoring_capacity`, `list_monitoring_capacity_history` y `link_monitoring_project`. Usa case_id/report_id/server_id/resource_id explícitos y los mismos serializers/servicios del Panel. Los campos observados y de auditoría son read-only; sólo se gestionan estado, notas, vínculo comercial y capacidad. No expone tokens de ingestión. Las restricciones allowed_tools siguen vigentes; un catálogo nuevo no agrega herramientas a una lista explícita anterior.

DevQA debe verificar tools/list y ejecutar las operaciones permitidas/denegadas en el MCP realmente servido en el mismo SHA: la presencia de REST o pruebas del adaptador no acredita por sí sola esa disponibilidad.

## Activación y validación

1. Integrar y desplegar ProjectApp aplicando monitoring.0006 por el deploy normal. Nunca ejecutar migrate desde el worktree.
2. Instalar el corte compatible del toolkit conforme al protocolo de generación del host. No propagar automáticamente ni modificar units del motor de integridad.
3. Después de que la API esté disponible, registrar la fuente telemetry y activar `telemetry_enabled: true` en el archivo operativo existente, desde el flujo del operador. No se requieren credenciales nuevas ni se imprimen las existentes.
4. Verificar acuse, identidad repetida, hora observada, capacidades y aparición de las primeras muestras. No reconstruir historia anterior ni provocar incidentes para probar.
5. Para desactivar la captura, retirar el flag; conservar cola e histórico. La transición emite un heartbeat deshabilitado cuando la captura ya había estado activa.

CI cubre filtros, paginación, agregados, permisos, métricas, capacidad y MCP. DEV LISTO y QA manual son evidencias independientes sobre un SHA servido: roles, IDs ficticios, fechas, temas, cinco anchos (incluida tableta vertical), foco con mouse, recuperación y tiempos observables. No se agregan casos dedicados de teclado. Sin asignación de dupla o acceso a DEV se registra el pendiente; no se declara aprobación.

El generador `create_fake_monitoring` admite count/seed/fecha ancla del generador canónico y sólo desarrollo aislado. Incluye varias páginas, notas/entregas extensas, observaciones vacías y con cero/false, fuentes con estados distintos, capacidad y series ficticias con huecos. Nunca se ejecuta desde esta sesión contra la base del servicio.
