# PA-249 · Traspaso de implementación

Rama `feat/12112026-pa249-monitoring-dashboard`, [PR #582](https://github.com/WeAreProjectApp/projectapp/pull/582), base `main`. Rol de esta sesión: Implementación. El SHA final y los resultados de sus corridas se publican en el PR y en el [hilo del ticket](https://projectapp-zone.slack.com/archives/C0CF8GLU6RL/p1794491162065679). Este documento prepara el recorrido; no acredita despliegue ni resultado manual.

## Preparación de DevQA

Backlog debe identificar una dupla y un entorno aislado para el PR completo. La solicitud está en el hilo. DevQA publica DEV LISTO con turno, URL, SHA realmente servido de frontend y backend, servicios, roles, IDs, fechas y límites. La rama no se mergea ni se despliega desde la sesión de implementación.

- Aplicar `monitoring.0006` mediante el procedimiento de despliegue del entorno aislado. El archivo de entorno enlazado del worktree no es una base de QA.
- Preparar un administrador staff ficticio, un usuario autenticado sin permisos administrativos y registros ficticios de proyectos/servidores distintos. Staff conserva su alcance administrativo global; la prueba de ID ajeno no debe inventar una restricción por cliente para ese rol.
- Usar el generador canónico `create_fake_monitoring`, con semilla y fecha ancla registradas, volumen de al menos 75 casos por tipo. Proporciona reportes, más de una página de notas/observaciones, estados variados, evidencia vacía/extensa, cero/false, fuentes sin datos/atrasadas/deshabilitadas, asignación informativa e histórico con huecos. Los IDs se obtienen del catálogo del entorno; no se reutilizan IDs de otra ronda.
- El generador fecha los datos al mediodía de su ancla. Registrar esa hora y elegir un periodo que la contenga. Para presión actual y recepción idempotente, DevQA debe preparar una muestra reciente válida en el entorno aislado: un histórico ficticio por sí solo no acredita medición actual.
- Preparar historial de capacidad con más de 25 cambios y un segundo operador para conflicto de versión. Registrar los efectos esperados antes de escribir. Guardar capacidad sólo cambia el registro informativo y su auditoría.
- Instalar el recolector compatible del toolkit y registrar la fuente `telemetry` antes de activar su flag. La captura es cada minuto durante 90 días. La activación usa el archivo operativo existente, conserva las credenciales en su ruta y se hace después del backend; [contrato y activación](../monitoring-dashboard.md).

## Recorrido compartido

| Caso | Acción de QA frontend | Cotejo de DevQA |
|---|---|---|
| Filtros y contexto | Combinar proyecto/servidor, fuente, estado, gravedad, condición, seguimiento y texto; escribir varias letras; aplicar fechas; Limpiar; Actualizar; navegar atrás/adelante. | Selecciones compatibles, espera de texto de 300 ms, límites de fechas inclusivos, 400 al invertirlas; página 1 al filtrar/limpiar y selección conservada al actualizar. |
| Páginas estables | Recorrer al menos tres páginas de eventos y reportes; recibir datos nuevos; continuar y luego Actualizar. | IDs sin omisiones/duplicados dentro del corte, totales y KPIs del conjunto filtrado completo, aviso de novedades, nueva consulta explícita. Probar token vencido y recuperación conservando filtros. |
| Atención | Abrir gravedad activa y seguimientos desde KPIs; abrir fuente sin datos/atrasada y servidor bajo presión. | Activo técnico independiente del cierre humano; pendientes incluye revisión y recuperados. Salud/medición ausente no equivale a cero incidencias. RAM/disco ≥85 %, carga ≥3×vCPU, muestras de hasta dos minutos. |
| Tendencias | Cambiar entre 24h/7d/30d/90d; revisar RAM, disco, CPU y carga; repetir sin datos y tras una falla recuperable. | Valores y unidades contra muestras reales; promedios/máximos/cantidades, capacidad total, última actualización, huecos sin interpolación. La vista agrupa en 5 min/30 min/2 h/6 h; conserva la captura por minuto. |
| Capacidad | Seleccionar proyecto, editar CPU/RAM/almacenamiento asignado o compartido; guardar; recargar; abrir y paginar historial. | vCPU/GiB convertidos a bytes, servidor relacionado, versión/autor/antes/después. Consumo por proyecto permanece no disponible. No se alteran cuotas, servicios o límites del host. |
| Conflictos y errores | Dos operadores sobre la misma asignación/caso, doble clic, entrada inválida, carga fallida y recuperación. | 409 conserva borrador y dato persistido; validación denegada sin escrituras parciales; operación única y auditoría coherente. No repetir escrituras ya selladas para obtener otra evidencia. |
| Detalle | Abrir observaciones vacías/completas/extensas, desplegar originales, cambiar páginas independientes y guardar nota/estado. | Cero/false visibles; claves vacías omitidas sólo en la presentación. Evidencia original y relaciones con reportes conservadas; notas en preparación sobreviven a paginar. |
| Autorización y MCP | Comprobar pantallas permitidas/denegadas y navegación coherente con los roles acordados. | Denegación real al sustituir IDs y escribir con rol no administrativo; servidor no admite capacidad de proyecto. Verificar `tools/list` y consulta/gestión de las 13 operaciones nuevas del MCP Proyectos sobre el mismo SHA, incluidas validaciones y conflictos. REST o un mock no acredita exposición real. |

## Presentación y evidencia

Recorrer claro y oscuro en 412×915, 835×1194 (tableta vertical), 1195×835, 1440×900 y 2560×1440 CSS. Revisar dropdowns buscables, etiquetas largas, gráficas, modales, paginación, foco con mouse y retorno al flujo. Registrar tiempos observables, consola y red con la operación y el volumen identificados. No hay casos dedicados de teclado.

CI ejecuta las automatizadas; no se ejecutaron tests ni builds locales. Los specs nuevos conservan la marca de no validados hasta su ejecución efectiva en CI. La revisión estática del catálogo, contrato responsive y registro de flujos no acredita una revisión visual manual.

El recolector compatible está publicado en el toolkit, SHA `4a7f5da620b036dc2e75672d8e43f29a98a2e4db`, con sus controles de [CI aprobados](https://github.com/ProjectAppSunset/vps-ops-toolkit/actions/runs/43232950513). La captura permanece desactivada hasta que DevQA o el despliegue la habiliten después del backend.

La evidencia de cierre distingue resultados de CI por SHA, DEV LISTO por SHA servido y dictamen de QA por caso. Una aprobación de esta rama no sustituye la futura validación de `main` integrado. El [runbook MCP](../MCP_VALIDATION_RUNBOOK.md) y el [contrato de Monitoreo](../monitoring-dashboard.md) detallan operaciones y límites.
