# Verificación del primer alcance de Monitoreo

Fecha: 2026-09-28. Base revisada: `main`, commit `2212a758`.

## Resultado

El módulo y los dos cambios de iconos solicitados ya están integrados.
La revisión actual confirma sus contratos mediante pruebas aisladas y corrige
la guía operativa. **La recepción de eventos reales en producción sigue sin
verificarse**: el acceso a `vps-projectapp-prod` solicitó autenticación adicional
de Tailscale y no se obtuvo una sesión del servidor durante esta revisión.

No se debe cerrar el punto 7 del requerimiento con esta evidencia local.
Tampoco se debe interpretar la ausencia de acceso como una falla del colector.

## Correspondencia con el requerimiento

| Puntos | Evidencia en la base revisada |
| --- | --- |
| 1–3. Módulo, niveles y separación | `backend/monitoring/` y `/panel/monitoring`; recursos de tipo proyecto o servidor y filtros por recurso/fuente. Integrado por [PR #393](https://github.com/WeAreProjectApp/projectapp/pull/393), commit `122bf1fc`. |
| 4. Base de datos y N+1 | Exportador `backend/projectapp/monitoring_export.py` para django-silk: agrupa duración/conteos por ruta parametrizada y omite SQL y secretos. El toolkit contempla el reporte semanal/MySQL y otros productores; la activación real se verifica por fuente. |
| 5–6. Seguimiento mínimo | Estados Pendiente/En revisión/Resuelto, notas, autor/fecha, historial, versiones contra conflictos y reportes separados. Sin asignaciones ni avisos nuevos; el correo coexiste. |
| 7. Verificar los proyectos monitoreados | Alcance registrado: ProjectApp, Mimittos, Tenndalux y su servidor `vps-projectapp-prod`. Pruebas locales detalladas abajo; falta comprobar inventario, recepción, cola y Silk desplegados. |
| 8. Icono comercial | Propuestas usa `money-bag`: bolsa con monedas sin símbolo monetario, dentro del componente SVG existente `SidebarIcon`. No hay emoji con alas en esta implementación. |
| 9. Distinguir Monitoreo y Hosting | Monitoreo usa `search` (lupa); Hosting usa `database`. Ambos cambios de iconos llegaron por [PR #407](https://github.com/WeAreProjectApp/projectapp/pull/407), commit `87d160e9`. La navegación de escritorio y móvil comparte `panelNav.js`. |

Las nueve preguntas pendientes se responden según el comportamiento existente en
[la guía de monitoreo](../monitoring.md#decisiones-que-ya-representa-la-implementación).

También se confirmó que los exportadores de
[Mimittos, PR #66](https://github.com/WeAreProjectApp/mimittos_project/pull/66) y
[Tenndalux, PR #57](https://github.com/WeAreProjectApp/tenndalux_project/pull/57)
fueron integrados el 2026-09-19. El merge de esos exportadores no acredita su
activación en las instalaciones de producción.

## Verificación local

Las pruebas corren desde un worktree propio, con `projectapp.settings_test`,
SQLite aislado, almacenamiento temporal y sin leer el `.env` de producción.
El frontend usa respuestas HTTP simuladas: verifica la interacción real del
navegador, pero no demuestra recepción desde los servidores.

| Comprobación | Resultado |
| --- | --- |
| Recepción (`test_ingest.py`) | 12/12 aprobadas, con creación de la base de test mediante migraciones. |
| Seguimiento y exportador (`test_followup_api.py`, `test_silk_export.py`) | 13/13 aprobadas. |
| Asociación, inventario y salud (`test_contract_edges.py`) | 16/16 aprobadas. |
| Store del panel (`monitoring.test.js`) | 17/17 aprobadas. |
| Página, filtros y fechas (`PanelMonitoringIndex.test.js`) | 6/6 aprobadas. |
| Navegador (`admin-monitoring-case-list.spec.js`, `admin-monitoring-case-follow-up.spec.js`) | 14 escenarios verificados: 13 aprobados en el lote inicial y el escenario de arranque aprobado en una ejecución focal posterior. |
| Iconos renderizados | Bolsa con monedas en Propuestas, lupa en Monitoreo y base de datos en Hosting comprobadas visualmente en el navegador local. |

Los lotes backend posteriores al primero usan `--nomigrations`: verifican el
comportamiento con el esquema de modelos en SQLite y evitan repetir la preparación
de todas las migraciones. No hay cambios de esquema en esta entrega. Ningún lote
excede 20 pruebas y no se ejecuta la suite completa.

Comandos usados desde `backend/`, con el Python del entorno virtual disponible:

```bash
python -m pytest monitoring/tests/test_ingest.py -v --no-cov
python -m pytest monitoring/tests/test_followup_api.py monitoring/tests/test_silk_export.py -v --no-cov --nomigrations
python -m pytest monitoring/tests/test_contract_edges.py -v --no-cov --nomigrations
```

Desde `frontend/`:

```bash
npm test -- --runInBand test/stores/monitoring.test.js
npm test -- --runInBand test/components/PanelMonitoringIndex.test.js
E2E_PORT=3078 E2E_WORKERS=1 npm run e2e -- --config=/tmp/projectapp-monitoring-first-scope.config.mjs e2e/admin/admin-monitoring-case-list.spec.js e2e/admin/admin-monitoring-case-follow-up.spec.js
E2E_PORT=3078 E2E_WORKERS=1 npm run e2e -- --config=/tmp/projectapp-monitoring-first-scope-recheck.config.mjs e2e/admin/admin-monitoring-case-follow-up.spec.js --grep='opens a case detail with its current pending state'
```

Las configuraciones temporales heredan `frontend/playwright.config.js`, usan un
worker, cero retries automáticos y un máximo de 300 segundos para arrancar Nuxt.
La primera omite el calentamiento general; la segunda prepara únicamente
`/panel` con las mismas respuestas HTTP simuladas antes del escenario pendiente.
No se modifican los specs ni sus aserciones. Los archivos temporales quedan fuera
del repositorio.

El intento con la configuración estándar se interrumpió durante la preparación
de páginas de Proyectos/Contabilidad, antes de ejecutar los escenarios de
Monitoreo. La preparación focal inicial también superó el límite de 120 segundos.
En la ejecución de 14 escenarios, el primero agotó 60 segundos esperando la
navegación mientras había módulos JavaScript sin terminar de cargar; los otros
13 pasaron. Un primer reintento coincidió con el apagado del servidor del lote
anterior y devolvió `ERR_CONNECTION_REFUSED`. La repetición con servidor propio
y preparación focal pasó: 1/1 en 49,4 segundos. Resultado combinado: 41 pruebas
backend, 23 unitarias frontend y 14 escenarios E2E verificados; no se presenta
el primer lote de navegador como una ejecución completamente verde.

## Correcciones de documentación

- La guía indicaba `PATCH /api/monitoring/resources/:id/link/`; la ruta registrada
  y cubierta por pruebas es `PATCH /api/monitoring/resources/:id/`.
- El contexto y el plan todavía marcaban pendiente la integración del PR #393.
  Se actualizan a integrado, manteniendo pendiente la comprobación operativa.
- Se explicitan criterios de recepción, asociación, duplicados, seguimiento,
  recuperación, salud, Silk e interfaz; se distingue el resultado del código del
  estado de su instalación.

Esta entrega sólo modifica documentación. No agrega capacidades visibles ni
cambia flujos, catálogos, modelos, exportadores, iconos o configuración de los
monitores. Por ello no requiere actualización del Mapa de vistas ni del registro
E2E; los flujos existentes se ejercitan con sus specs actuales.

## Evidencia remota y pendiente operativo

La petición anónima al catálogo de producción
(`https://www.projectapp.co/api/monitoring/catalog/`) recibió HTTP 403. Esto
registra el rechazo de esa petición; no demuestra inventario, permisos de una
sesión staff ni entrega del colector.

| Recurso | Inventario/fuentes en vivo | Última recepción | Silk |
| --- | --- | --- | --- |
| `vps-projectapp-prod` | Sin verificar | Sin verificar | No aplica al recurso servidor |
| `projectapp` | Sin verificar | Sin verificar | Activación y export sin verificar |
| `mimittos_project` | Sin verificar | Sin verificar | Activación y export sin verificar |
| `tenndalux_project` | Sin verificar | Sin verificar | Activación y export sin verificar |

Para completar el punto 7 se necesita acceso autenticado de lectura al servidor:

1. Registrar la versión desplegada, las migraciones aplicadas y el inventario
   real de los cuatro recursos, sin mostrar credenciales.
2. Contrastar estado del colector/timer, pendientes y rechazos de la cola con
   las últimas recepciones y errores de cada fuente del panel.
3. Comprobar asociación de observaciones reales por recurso y el estado de Silk
   por proyecto. Si está deshabilitado, declararlo explícitamente; no activarlo
   como efecto lateral de esta revisión.
4. Registrar las discrepancias y seguir el runbook de instalación para cualquier
   activación o prueba controlada que haga falta. No generar incidentes reales.

No se ejecutaron migraciones productivas, provisión de inventario, cambios de
credenciales, activación de Silk, cambios de correo, reinicios ni despliegues.
