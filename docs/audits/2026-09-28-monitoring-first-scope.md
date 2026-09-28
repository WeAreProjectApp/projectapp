# Verificación del primer alcance de Monitoreo

Fecha: 2026-09-28. Base revisada: `main`, commit `2212a758`.

## Resultado

El módulo y los dos cambios de iconos solicitados ya están integrados.
La revisión confirma sus contratos mediante pruebas aisladas y corrige la guía
operativa. **La integración no está operativa en producción**: la inspección
autenticada del 2026-09-28 a las 13:43–13:45 UTC confirmó que faltan configuración,
colector e inventario. Las tablas existen, pero no hay recursos, fuentes,
credenciales ni entregas registradas.

No se debe cerrar el punto 7 como funcionamiento correcto. La verificación ya
identificó el pendiente concreto: instalar y configurar la integración existente,
y luego comprobar la recepción por recurso. No se trata de un error de acceso ni
de una entrega rechazada por un colector activo.

## Correspondencia con el requerimiento

| Puntos | Evidencia en la base revisada |
| --- | --- |
| 1–3. Módulo, niveles y separación | `backend/monitoring/` y `/panel/monitoring`; recursos de tipo proyecto o servidor y filtros por recurso/fuente. Integrado por [PR #393](https://github.com/WeAreProjectApp/projectapp/pull/393), commit `122bf1fc`. |
| 4. Base de datos y N+1 | Exportador `backend/projectapp/monitoring_export.py` para django-silk: agrupa duración/conteos por ruta parametrizada y omite SQL y secretos. El toolkit contempla el reporte semanal/MySQL y otros productores; la activación real se verifica por fuente. |
| 5–6. Seguimiento mínimo | Estados Pendiente/En revisión/Resuelto, notas, autor/fecha, historial, versiones contra conflictos y reportes separados. Sin asignaciones ni avisos nuevos; el correo coexiste. |
| 7. Verificar los proyectos monitoreados | Alcance registrado: ProjectApp, Mimittos, Tenndalux y su servidor `vps-projectapp-prod`. Inspección real completada: inventario y entregas vacíos, colector/cola sin instalar y Silk apagado en la configuración de los tres proyectos. Falta activar y validar la integración. |
| 8. Icono comercial | Propuestas usa `money-bag`: bolsa con monedas sin símbolo monetario, dentro del componente SVG existente `SidebarIcon`. No hay emoji con alas en esta implementación. |
| 9. Distinguir Monitoreo y Hosting | Monitoreo usa `search` (lupa); Hosting usa `database`. Ambos cambios de iconos llegaron por [PR #407](https://github.com/WeAreProjectApp/projectapp/pull/407), commit `87d160e9`. La navegación de escritorio y móvil comparte `panelNav.js`. |

Las nueve preguntas pendientes se responden según el comportamiento existente en
[la guía de monitoreo](../monitoring.md#decisiones-que-ya-representa-la-implementación).

También se confirmó que los exportadores de
[Mimittos, PR #66](https://github.com/WeAreProjectApp/mimittos_project/pull/66) y
[Tenndalux, PR #57](https://github.com/WeAreProjectApp/tenndalux_project/pull/57)
fueron integrados el 2026-09-19. Sus commits están presentes en los clones de
producción; no hay archivos exportados ni activación declarada de Silk.

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

Tras la verificación adicional de Tailscale se consultó `srv1681495`
(`vps-projectapp-prod`) mediante SSH. La lectura de MySQL se realizó en una
transacción `READ ONLY`, cerrada con rollback, sin iniciar Django ni ejecutar
comandos de provisión. Sólo se consultaron migraciones, inventario y conteos;
no se imprimieron credenciales ni contenido de reportes.

| Comprobación remota | Resultado a las 13:43–13:45 UTC |
| --- | --- |
| ProjectApp desplegado | `2212a758d8054dba6eb39da58e37bc2b22b470d3`, rama `main`, clon limpio. |
| Mimittos desplegado | `0740d0214307f908a2f21bd78c2ecb98ed7d3159`, rama `main`, clon limpio. |
| Tenndalux desplegado | `e6854810a4ef01880c1b78823c3bdd6c50bf1ddc`, rama `master`, clon limpio. |
| Toolkit instalado | `b1ed6ee5bdd5b31b0af1352b04a49da9555fd0d5`, rama `master`, clon limpio. |
| Aplicaciones | Los tres servicios web están `active`. |
| Esquema de monitoreo | Ocho tablas presentes; migraciones `0001_initial` y `0002_case_monitoring__last_se_4418a8_idx_and_more` aplicadas el 2026-09-20 a las 15:42 UTC. |
| Inventario y credenciales | Cero recursos, cero fuentes y cero credenciales. |
| Historial recibido | Cero entregas, casos, reportes y actividades de seguimiento. |
| Colector y programación | `projectapp-monitoring.service` y `.timer`: `LoadState=not-found`, `ActiveState=inactive`. |
| Configuración y cola | No existen `/etc/projectapp-monitoring/`, su `config.json`, `/var/lib/projectapp-monitoring/` ni `outbox.sqlite3` en las rutas del runbook. |
| Exportaciones Silk | Ningún `backend/logs/monitoring/silk-*.json` en los tres proyectos. |

Los `.env` declaran `ENABLE_SILK=False` en los tres proyectos; ninguna unit
declara una sobreescritura de ese toggle. Tenndalux carga ese mismo `.env` como
`EnvironmentFile`. El entorno de los procesos en `/proc` no fue legible para el
usuario SSH: el resultado acredita la configuración declarada, no una lectura
directa del toggle en memoria de los workers.

La petición anónima al catálogo de producción
(`https://www.projectapp.co/api/monitoring/catalog/`) recibió HTTP 403. Esto
registra el rechazo de esa petición; no demuestra inventario, permisos de una
sesión staff ni entrega del colector.

| Recurso | Inventario/fuentes en vivo | Última recepción | Silk |
| --- | --- | --- | --- |
| `vps-projectapp-prod` | Recurso y fuentes no provisionados | Ninguna registrada | No aplica al recurso servidor |
| `projectapp` | Recurso y fuentes no provisionados | Ninguna registrada | Configuración deshabilitada; sin export |
| `mimittos_project` | Recurso y fuentes no provisionados | Ninguna registrada | Configuración deshabilitada; sin export |
| `tenndalux_project` | Recurso y fuentes no provisionados | Ninguna registrada | Configuración deshabilitada; sin export |

La ausencia de credenciales e inventario impide aceptar entregas autenticadas de
estos recursos. No hay observaciones reales con las cuales demostrar asociación,
idempotencia o seguimiento en producción; esos contratos sí están cubiertos por
las pruebas aisladas. Una base vacía no acredita funcionamiento sin errores.

Para completar el punto 7, la operación debe seguir
`vps-ops-toolkit/docs/projectapp-monitoring.md`:

1. Preparar la configuración con las cuatro identidades y generar el manifiesto.
   Provisionar recursos/fuentes y una credencial limitada, guardando el token
   exclusivamente en el archivo protegido indicado por el runbook.
2. Instalar directorio de cola y units; verificar permisos y compatibilidad de
   los productores con el sandbox del colector. Necesita 1.
3. Ejecutar la entrega controlada y contrastar respuesta 200/201, asociación,
   fechas y cola sin rechazos. Habilitar el timer tras esa validación. Necesita 2.
4. Comprobar reintentos, recuperación y seguimiento con una fuente de validación
   aislada, sin generar incidentes reales. Necesita 3.
5. Decidir el rollout de Silk: ProjectApp con muestra del 5 %, observación de
   24 horas y luego cada proyecto restante por separado. Hasta entonces, declarar
   esas fuentes deshabilitadas, sin prometer recepción de N+1/consultas lentas.

No se ejecutaron migraciones productivas, provisión de inventario, cambios de
credenciales, activación de Silk, cambios de correo, reinicios ni despliegues.
