# Monitoreo: rendimiento y QA del primer alcance

Fecha: 2026-09-28. Worktree: `monitoring-first-scope`.
PR: https://github.com/WeAreProjectApp/projectapp/pull/437.

## Resultado

Las correcciones de pruebas pasan el control de calidad y los diez casos
afectados. El código funcional, la API y los iconos mantienen el comportamiento
ya integrado. La auditoría independiente conserva las 54 definiciones revisadas:
los tres controles que permitían regresiones ahora tienen un techo explícito.

El resultado de rendimiento es **con observaciones**, no cumplimiento completo.
El GET de detalle usa siete consultas HTTP con sesión staff real, frente al
presupuesto canónico de cuatro. Detección, recuperación y cambio de estado usan
15, 14 y 9 consultas, frente al presupuesto de ocho para mutaciones. Sus nuevos
límites históricos impiden empeorar esos resultados; no elevan el estándar ni
certifican cumplimiento.

## Cambios

- Retención: fixture local que conserva la jerarquía servidor → proyecto →
  fuente Silk, sin importar fixtures desde otro archivo de pruebas. Se corrigen
  imports y documentación; las tres pruebas y sus aserciones se conservan.
- Ingestión y seguimiento: techo del total de consultas junto con las
  comprobaciones existentes de respuesta, estado e historial. Se conserva el
  límite de ocho para la petición que no cambia el estado.
- Ambos archivos de presupuestos se incluyen en `performance_budget_tests`
  para que las próximas revisiones los descubran.

## Evidencia y límites

Desde el backend del worktree, con Python del entorno virtual disponible:

```bash
python -m pytest monitoring/tests/test_retention.py monitoring/tests/test_observe_case_query_budget.py monitoring/tests/test_case_state_query_budget.py -q --no-cov --nomigrations --junitxml=/tmp/projectapp-monitoring-budget-qa.xml
```

Resultado: **10 passed**, en SQLite aislado con `projectapp.settings_test`, sin
cargar `.env`. El XML registra detección=15, recuperación=14, cambio=9,
referencia sin cambio=7 y delta=2.

`qa-agent.sh --verify projectapp --projdir=<worktree> --files=<los tres archivos>`
escaneó los tres archivos con reglas estrictas, severidad de junk `error`, Ruff
y lint externo: **cero errores y cero advertencias**. El helper retiró su marcador
de verificación pendiente. Ruff estaba disponible en el PATH; la pasada previa
sin Ruff no se usa como evidencia de aprobación.

La sonda temporal del detalle usó sesión real y SQLite de test. Creó 10.000
actividades y 10.000 entregas; las páginas 1 y 400 devolvieron 25 elementos por
colección con siete consultas cada una: sesión, usuario, caso con relaciones,
conteo/página de actividades y conteo/página de entregas. Esto verifica constancia
del conteo; no mide latencia, CPU, memoria ni el plan de ejecución de MySQL.
No se añade un test rojo ni se acepta un presupuesto local de siete como estándar.

La reproducción completa y el diagnóstico del candidato viven en el toolkit:
`docs/audits/2026-09-28-projectapp-perf-monitoring-first-scope.md`.
El candidato de detalle queda diagnosticado; la ausencia de retención de exports
JSON queda como candidato separado, sin borrar archivos que podrían no haberse
entregado.

Se reutiliza la evidencia de frontend de la revisión inicial: 23 pruebas
unitarias y 14 escenarios E2E verificados, con los reintentos de preparación
descritos en ese informe. Esos archivos y el código que ejercitan no cambiaron.
El mapa de flujos está vigente; el borrador de Hosting detectado por el preflight
queda fuera del alcance de Monitoreo. No hay cambios visibles que exijan alterar
el Mapa de vistas ni el registro E2E.

La activación productiva y la recepción real de eventos siguen pendientes según
el informe inicial. Esta revisión no provisiona inventario, activa Silk, instala
el colector, migra bases de datos ni despliega servicios.
