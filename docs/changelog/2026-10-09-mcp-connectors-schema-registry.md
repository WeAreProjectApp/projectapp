# Conectores MCP: registro, esquemas e ingresos esperados

Esta entrega reúne los diez commits posteriores a `e8da7b83`, hasta
`eacc5206`, y el incremento de versiones y huellas de contrato. La medición
local con `projectapp.settings_test` encuentra 18 conectores y 991 herramientas
sumadas entre catálogos, contando las compartidas en cada uno donde aparecen.

## Versiones anunciadas

«Antes» corresponde a `e8da7b83`: `serverInfo` de `initialize` / versión de
`describe_capabilities`. El guion indica que capacidades aún no existía en ese
conector. Ahora `initialize`, `server/discover`, la metadata moderna y
`describe_capabilities` anuncian la misma versión del registro.

| Conector | Antes: serverInfo / capacidades | Ahora |
| --- | --- | --- |
| `accounting` | 1.0.0 / — | 1.1.0 |
| `accounting-billing` | 1.0.0 / 2.0.0 | 2.1.0 |
| `accounting-cards` | 1.0.0 / 2.0.0 | 2.1.0 |
| `accounting-ledger` | 1.0.0 / 2.0.0 | 2.1.0 |
| `additional-modules` | 1.0.0 / 2.0.0 | 2.1.0 |
| `blog` | 1.0.0 / — | 1.1.0 |
| `clients` | 1.0.0 / — | 1.1.0 |
| `commercial` | 1.0.0 / 2.0.0 | 2.1.0 |
| `communications` | 1.0.0 / 2.0.0 | 2.1.0 |
| `content` | 1.0.0 / 2.0.0 | 2.1.0 |
| `diagnostics` | 1.0.0 / — | 1.1.0 |
| `documents` | 3.1.0 / 3.1.0 | 3.2.0 |
| `linkedin-personal` | 1.0.0 / — | 1.1.0 |
| `operations` | 1.0.0 / 2.0.0 | 2.1.0 |
| `partnership-program` | 1.0.0 / 2.0.0 | 2.1.0 |
| `projects` | 2.1.0 / 2.1.0 | 2.2.0 |
| `proposals` | 2.1.0 / 2.1.0 | 2.2.0 |
| `tasks` | 1.0.0 / 2.0.0 | 2.1.0 |

Diez conectores anunciaban 1.0.0 en `serverInfo` y 2.0.0 en capacidades.
El detalle de la comparación se conserva en la
[auditoría de paridad](../audits/2026-10-09-mcp-schema-parity.md).

## Registro único y contrato público

`backend/content/mcp/connectors.py` es la fuente de verdad del inventario.
Cada `ConnectorSpec` declara slug, versión, fuentes de herramientas,
compatibilidad, uploads, confirmación sensible y notas; de allí se derivan
identidad e instrucciones. `registry.public_tool` alimenta tanto `tools/list`
como `describe_capabilities`, con el mismo alcance de credencial.
`initialize` también entrega las instrucciones propias del conector.

El payload de `/panel/mcps` incluye la versión. Sólo `blog`, `clients`,
`accounting`, `diagnostics` y `linkedin-personal` se marcan como compatibilidad
(`is_legacy`); Propuestas pertenece a los 13 conectores canónicos.

Cambiar el contrato público exige incrementar `ConnectorSpec.version`, escribir
un changelog y ejecutar `mcp_schema_report --write-fingerprints` con settings de
test. `backend/content/mcp/connector_contracts.json` conserva versión y SHA-256
de esquemas, descripciones, anotaciones, riesgos, confirmaciones e instrucciones.
La versión se almacena aparte: cambiar sólo la versión no cambia el SHA-256.

## Argumentos planos y sobres obsoletos

Las herramientas nativas de propuestas actualizadas, como formalización,
plantillas contractuales e historial, publican sus argumentos en la raíz.
Los sobres anteriores `data` para escrituras y `query` para
lecturas, y los aliases admitidos por sus handlers, siguen funcionando. El uso
de sobres se registra como `deprecated_envelope` sin registrar el contenido del payload.
Por ejemplo, se mantiene `query.variant` al leer una plantilla contractual y
`recipient_email` en los envíos que ya lo aceptaban. Los clientes nuevos deben
usar los campos publicados y evitar valores contradictorios entre ambas formas.

`accepted_arguments_schema` describe la forma privada aceptada en ejecución,
incluidos sobres y aliases de compatibilidad. Nunca se publica. El puente
Panel compartido todavía publica `data` en algunas herramientas con payload
explícito, como `update_proposal_settings` y `review_proposal_approval`; su
proyección plana depende del trabajo paralelo. Los adaptadores genéricos siguen
inventariados como deuda; esta entrega no presenta todo el puente como terminado.

## Política de esquemas y claves anidadas

`schema_policy.py` exige objetos cerrados, argumentos tipados y descritos, y
ausencia de `anyOf`, `oneOf` y `allOf` en la raíz. Los objetos libres requieren
una descripción y un motivo documentado; por ejemplo, el contenido de una
sección cuyo formato depende de su tipo. La metadata privada de esa política
se retira al publicar. Las restricciones como «exactamente uno de markdown o
patches» quedan descritas y sus handlers siguen comprobándolas.

`schema_backlog.py` contiene excepciones que sólo pueden reducirse: adaptadores
genéricos, argumentos sin descripción y esquemas diferidos. Fuera de esas
excepciones, las pruebas exigen la política. El barrido de descripciones de
Documentos y Proyectos continúa en `feat/09102026-mcp-folder-migration`.

Los objetos de propuestas con campos definidos rechazan claves desconocidas
también dentro de listas y objetos anidados, antes de ejecutar o crear un intent.
El contenido variable declarado como libre mantiene la validación del Panel.

Los esquemas publicados son el contrato, pero esta rama **no añade un validador
central de argumentos**. Los argumentos desconocidos o faltantes se rechazan
en el handler o serializer de cada herramienta; los de ingresos esperados
devuelven `unknown_field` para claves desconocidas. La rama paralela incorpora
en `protocol.py` un validador opt-in para `documents`, `projects` o herramientas
con `strict_arguments`; usa `accepted_arguments_schema` cuando está presente.
Ese trabajo no forma parte de esta entrega local.

## Compatibilidad, confirmación y extractos

Los cinco conectores de compatibilidad conservan URLs y ejecución directa de
sus herramientas existentes. Añaden `describe_capabilities`, `confirm_action`
y `cancel_action`. Las instrucciones sólo prometen una vista previa cuando la
herramienta exige confirmación; las otras acciones existentes de compatibilidad
siguen siendo directas y el agente debe revisar con el usuario las operaciones
sensibles. Disponer de `confirm_action` no convierte cada herramienta en dos pasos.

`accounting-cards` incorpora `get_statement`: la selección anterior por prefijo
`get_statement_` lo dejaba fuera. La separación contable se declara ahora por
área de herramienta, sin depender de ese prefijo.

## Gestor Contable (accounting 1.1.0, accounting-ledger 2.1.0): ingresos esperados

Ambos conectores incorporan cinco herramientas con los servicios y serializers
del Panel. En claude.ai, «Gestor Contable» corresponde al slug `accounting`.

| Herramienta | Regla de ejecución |
| --- | --- |
| `list_expected_incomes` | Lectura paginada por cliente, proyecto, origen, fechas de cobro, estado de pago o texto; `origin: ["none"]` encuentra ingresos sin clasificar. |
| `get_expected_income` | Lectura de ingreso, pagos, deducciones, cuenta de cobro, bloqueos y ETag. |
| `update_expected_income` | Vista previa y `confirm_action` si cambia dinero, IVA, reparto, contabilidad, cliente o proyecto; los cambios descriptivos sin esos cambios se aplican directamente. |
| `create_expected_income` | Siempre vista previa y `confirm_action`. Exige clasificación de origen e IVA explícito (`null` significa sin registrar), más total o base. |
| `duplicate_expected_income` | Siempre vista previa y `confirm_action`; admite `overrides`, conserva el desfase de cobro y no copia pagos ni cuentas. |

El reparto automático usa `split_half` del Panel; un reparto personalizado se
conserva con aviso y la empresa recibe el residual. Base, IVA y total deben
coincidir. Pagos, deducciones, liquidación completa o cuentas emitidas bloquean
los cambios financieros y de cliente/proyecto con `INCOME_LOCKED`; los datos
conservados bloquean toda edición. El ETag incluye las dependencias del ingreso:
`if_match` obsoleto o cambios posteriores a la vista previa producen
`STALE_VERSION`. La confirmación revalida antes de escribir y deja el historial
contable habitual.

El [runbook de validación](../MCP_VALIDATION_RUNBOOK.md#libro-contable-ingresos-esperados)
reproduce el ingreso #172: leer, previsualizar Semestre 1, confirmar, verificar
y duplicar Semestre 2. También recoge los rechazos de reparto, IVA, claves
desconocidas y registros que no son ingresos esperados.

## Mes de cobro propio en hosting

La ventana `period_start` / `period_end` describe el servicio cubierto;
`period_date` describe cuándo se espera cobrar. Una fecha explícita prevalece.
Si se omite al crear, toma el inicio; al editar sigue un inicio movido sólo si
la fecha guardada ya coincidía con él. Completar una ventana histórica conserva
una fecha independiente de cobro. Duplicar mantiene el desfase entre ambos.

El formulario del Panel muestra «Mes de cobro esperado» con su opción de día
exacto; sigue el inicio hasta que se edita y conserva fechas independientes en
ediciones y duplicados. Orden, filtros y avisos usan la fecha de cobro.
Los cambios de inicio, fin y periodicidad quedan auditados en `TRACKED_FIELDS`.

## Documentos 3.2.0

Se corrige la afirmación anterior de que el espejo contractual «admite cambiar
exclusivamente folder_id»: desde Documentos 3.1.0 (#479) el espejo
`is_contract_mirror=true` es de sólo lectura, **no es editable ni movible**.
Revisar `editable`, `movable` y `move_blockers`; su contenido se administra
desde las plantillas de Propuestas. No se habilita una excepción de movimiento.
El barrido de descripciones y contratos explícitos de Documentos/Proyectos
continúa en la rama paralela citada arriba.

Nota retroactiva: Documentos 3.1.0 (#479), Propuestas 2.1.0 y Proyectos 2.1.0
se entregaron sin changelog propio. La columna «Antes» reconoce esas versiones;
esta nota no atribuye sus cambios al incremento actual.

## Cómo refrescar el cliente

Tras desplegar, ejecutar el informe remoto como cliente limpio y comparar
`tools/list` con `describe_capabilities`. Abrir una conversación nueva en
claude.ai. Si ambas vías coinciden pero el agente sigue mostrando definiciones
antiguas, quitar y volver a agregar el conector en **Settings → Connectors**
con la misma URL. Si hace falta otra credencial, crearla en `/panel/mcps` sin
rotar `Default`, para conservar las conexiones que la usan.

Reiniciar las sesiones de Claude Code y Codex. Las apps de escritorio o móvil
también pueden conservar caché; el servidor anuncia `ttlMs: 300000` (cinco
minutos). El prefijo **Input constraint** lo añade el cliente al reescribir
combinadores de raíz; verlo en una definición antigua no prueba deriva del
servidor. Procedimiento completo:
[verificación post-deploy y caché](../MCP_VALIDATION_RUNBOOK.md#verificación-post-deploy-y-caché-de-clientes).
