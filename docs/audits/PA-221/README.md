# PA-221 · Integridad y cobertura MCP

Estado del ticket: **TO DO por indicación de Carlos**. Este expediente no cambia
su acceso, no sustituye evidencias históricas y no acredita un dictamen nuevo.

## Corte y alcance

- Base de implementación: `295b65efb77af8303ec28b269ae1935a995a6f0e`.
- Implementación, SHA y resultados CI por corte: [PR #584](https://github.com/WeAreProjectApp/projectapp/pull/584).
- Se conserva el módulo de integridad, programación y Radar incorporado por #553;
  no se desarrollan nuevas ampliaciones de esos frentes.
- Corrección NM1, nombres/capacidades del catálogo, inventario Panel/Plataforma,
  cierre de huecos delegables y retiro condicionado a pruebas y consumidores.
- No se modifican datos reales ni se ejecuta retiro desde el worktree.

## Hallazgos y correcciones

| Hallazgo | Cambio | Evidencia de código |
|---|---|---|
| NM1 contaba cuatro registros y anunciaba tres cambios | Planifica las raíces documental, de conversación y de Enlaces seguros con los mismos valores que sus escritores; muestra antes/después y cambios laterales | `content/services/data_integrity/rules/naming.py`, servicios de raíces |
| Una raíz segura ausente podía crearse fuera de la vista previa | Bloqueo `managed_root_missing`; no se provisiona durante la corrección | plan de NM1 |
| Deshacer podía partir de otra composición de raíces | Guarda `project_roots`; el cambio posterior bloquea deshacer | fixer NM1 |
| Nombres dispares y capacidades sin lista clara | Presentación centralizada, migración de nombres y `capabilities` derivadas de herramientas publicadas | `content/mcp/presentation.py`, API y acordeón MCP |
| Monitoring no tenía gestión MCP de sus operaciones del Panel | Ocho herramientas administrativas en Operations 3.1.1, compartiendo las FBV, serializers, versiones y autoría del Panel | `content/mcp/monitoring_tools.py`, `monitoring/urls.py` |
| El retiro sólo comprobaba reemplazos registrados, uso y consumidores | Matriz de funciones y evidencia QA revisable, obligatoria además de las guardas existentes | `content/mcp/coverage.py`, `mcp_retirement` |
| Un conector retirado seguía en la lista del Panel | Se excluye de la lista operativa, se desactiva y deja de ofrecer herramientas; conserva rechazo 410 | listado, `tools_for_credential`, comando de retiro |

Las operaciones 1 y 3 y el cotejo QA-NOC-004 / `36-preview-vs-recorded-changes.json`
son antecedentes descritos en el ticket. No se reescribieron ni se reutilizaron
como una nueva prueba. La reproducción futura utiliza un proyecto ficticio nuevo.

## Inventario y matriz

- [Superficies y funciones del Mapa de vistas](surfaces.json): 111 vistas de Panel
  y Plataforma; 81 requieren cotejo funcional y 30 son excepciones explícitas,
  incluidos redirects. Conserva los textos de cada función para la revisión.
- [Inventario de conectores y reemplazos](inventory.json): 12 gestores principales
  y 12 compatibilidades pendientes; uso y consumidores no observados.
- [Matriz de operaciones](matrix.csv): 831 herramientas de negocio del registro
  actual, incluidos los ocho puentes nuevos de Monitoring. Las columnas distinguen
  `mapped_unverified` de una comprobación funcional.

Estos archivos son inventario estático del diff. **No certifican 831 herramientas
funcionando ni una cobertura completa de las 111 vistas.** Las vistas de cada
gestor son candidatas de asignación; QA concreta la relación entre cada función,
la operación ejercitada, el rol y el resultado. No se da por cubierta una acción
por compartir endpoint, servicio, nombre o conector con otra.

Regeneración desde el worktree, con settings aislados y sin lecturas de negocio:

```bash
node frontend/scripts/export-mcp-surfaces.mjs > docs/audits/PA-221/surfaces.json
DJANGO_SETTINGS_MODULE=projectapp.settings_test .venv/bin/python backend/manage.py mcp_surface_matrix --check --output /ruta/nueva/matriz.json
DJANGO_SETTINGS_MODULE=projectapp.settings_test .venv/bin/python backend/manage.py mcp_surface_matrix --format csv --output /ruta/nueva/matriz.csv
```

El CI genera JSON y CSV con el SHA de la corrida en el artefacto
`mcp-surface-matrix`. Un inventario con `tracked_tree_clean=false` es un corte del
trabajo local, no una revisión desplegable certificada.

## Excepciones y límites

Autenticación, recuperación y perfil propio pertenecen a la identidad interactiva.
La bandeja de notificaciones filtra por `Notification.user=request.user`; no se
añade un `user_id` que permita leer una bandeja ajena. Administrar operadores y
crear/rotar accesos MCP conserva la frontera de sesión, CSRF y superusuario.
Mapa de vistas, styleguide y redirects son referencia o navegación. La ingestión
de Monitoring sigue usando la credencial propia de la fuente; Operations sólo
administra el seguimiento. Las referencias están en `surface_catalog.py`, las
vistas de cuentas, `mcp_blog.py` y `monitoring/views.py`.

## Revisión funcional y evidencia del retiro

QA y DevQA completan un reporte generado **en el SHA servido**, sobre datos
ficticios. Cada fila de herramienta requiere:

- `result=mapped_verified`, `tested_role` y `view_ids` realmente comprobados,
  dentro de las vistas candidatas del gestor.
- `evidence` de acción/resultado y `permission_evidence` de su autorización.
- `confirmation_evidence` para herramientas que exigen confirmación.

Cada superficie no exenta requiere evidencia y `checks` hacia sus filas de
herramienta. Cada entrada de `feature_checks` conserva su ID/texto y requiere su
propia evidencia, resultado y checks vinculados a esa vista. No basta un caso
genérico del módulo. Los campos de metadatos y las excepciones no se cambian para
hacer pasar el reporte. Una función realmente ausente vuelve a Implementación.

Las referencias admiten artefactos de Actions del repositorio o archivos bajo
`docs/audits/`; nunca URLs MCP autenticadas, tokens o enlaces con credenciales.
El comando comprueba estructura, completitud y vigencia. **La veracidad de los
casos es responsabilidad de QA y de la revisión del operador**: no autentica CI
ni firma una prueba por el mero hecho de aceptar un JSON.

La verificación read-only es `mcp_surface_matrix --verify <reporte-qa.json>`.
El operador ejecuta `mcp_retirement --slug <origen> --retire
--coverage-report <reporte-qa.json>` para previsualizar; sólo `--apply` retira.
Además se exigen los 30 días de transición, 14 días continuos sin uso antiguo,
observación válida, consumidores migrados/revocados y ausencia de confirmaciones.
Un reporte estático o desactualizado deja `replacement_coverage_unverified`.

Sólo un retiro exitoso anexa SHA-256, referencia del reporte, revisión, huellas,
conteos y fecha en `retirement_evidence[catalog]`. Un dry run o un bloqueo no
guarda evidencia ni altera acceso. Se conservan entradas anteriores y del otro
catálogo. Una huella posterior diferente invalida su uso para otro retiro.
El retiro de un catálogo compatible de un gestor canónico no lo desactiva.

## Guion del nuevo QA

1. Preparar un proyecto ficticio con nombre que tenga espacios repetidos y sus
   tres raíces. Guardar IDs, SHA, rol y valores iniciales; no reutilizar proyecto 42.
2. Desde la skill y el MCP canónico de Integridad, consultar reglas y hallazgos;
   repetir revisión general y por cliente, proyecto, propuesta, documento y hilo.
3. Comparar el detalle NM1 con los cuatro valores iniciales y finales. La vista
   previa no cambia datos; confirmar exige motivo y hash vigentes. Cotejar
   persistencia, historial y resolución del hallazgo.
4. Deshacer y verificar restauración exacta; repetir con otro caso y edición
   posterior para comprobar bloqueo sin pisar cambios.
5. Con clientes/carpetas ficticios, probar fusión y reasignación admitidas.
   Conservar el duplicado archivado, originales emitidos e historial. Reglas sin
   corrección segura deben informar o dirigir a la herramienta correspondiente.
6. En el catálogo, cotejar nombres, alcance y capacidades; probar acceso autorizado
   y denegado, credenciales y recuperación de errores. Mantener visibles los
   pendientes de retiro y excluir los retirados, sin alterar datos históricos.
7. Por Monitoring MCP, consultar catálogo/casos/reportes, añadir nota, cambiar
   estado con versión y confirmar vínculo de recurso. Cotejar actor técnico,
   rechazo de versión antigua y denegación no administrativa.
8. Completar las funciones de la matriz, consumidores y doble chequeo del reemplazo:
   equivalencia de operación/permisos y ejecución desde el consumidor real.

Las pruebas automatizadas se ejecutan exclusivamente en CI. El recorrido DEV/Chrome
y el acceso desde la skill se acreditan por separado; un CI verde no los reemplaza.
No se diseñan casos nuevos dedicados a teclado. No se cambia el estado del ticket.

## Pendientes operativos

- Ronda DEV/Chrome y cotejo de datos, fusiones, reasignaciones y skill.
- Completar evidencia funcional de toda la matriz y comprobar consumidores externos.
- Aplicación de la migración aditiva 0308 por el deploy y evaluación del retiro en
  el entorno correspondiente. No ejecutar migraciones ni comandos mutantes de
  producción desde el worktree.
