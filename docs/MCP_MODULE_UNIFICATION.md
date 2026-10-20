# MCP por módulo: contrato y migración

Esta entrega consolida el registro en ocho conectores: `operations`,
`commercial`, `projects`, `documents`, `communications`, `content`, `accounting`
y `tasks`. Los otros doce slugs son adaptadores en retirada, no módulos nuevos.
La revalidación de PA-91 queda incorporada en los contratos de modelos y en los
recorridos de regresión existentes; no se construye otro módulo de Comunicaciones.

## Inventario y evidencia

`manage.py mcp_inventory --check --format json` genera el catálogo reproducible
sin acceder a datos de negocio. `--usage` incorpora el estado de la base configurada,
consumidores y evidencia diaria; sin ese flag no se infiere uso ni despliegue.
`mcp_schema_report` contrasta descubrimiento, esquemas y versiones. El CI ejecuta
ambos controles. `scripts/audit_mcp_consumers.py` inspecciona la configuración local
de Codex y Claude Code sin mostrar tokens; `--check` falla si el mismo cliente
configura varios conectores del mismo módulo. Claude web y otros hosts necesitan
su propia verificación: la ausencia en archivos locales no acredita su migración.

Los informes previos y posteriores viven en `docs/audits/2026-10-19-mcp-*`.
No califican una herramienta de obsoleta por falta de llamadas: sólo por un
reemplazo equivalente validado o porque se retiró su capacidad del producto.
Las herramientas en transición conservan su implementación hasta completar el retiro.

## Propiedad y estándar

Contable concentra registros financieros, hosting, suscripciones, conciliación,
contexto de cuentas y contratos de facturación. Proyectos conserva su ciclo y
sus procesos transversales, incluidos efectos financieros de sus transiciones;
no publica otra copia de las herramientas financieras detalladas.
Contenido reúne blog, LinkedIn, portafolio, QR y Linktrees. Comercial reúne
clientes, propuestas, diagnósticos, programas y sus contratos.

`list_incomes`, `get_income`, `create_income`, `update_income` y `duplicate_income`
reemplazan las dos familias de ingresos. La lectura y escritura de esperados
conserva el servicio de IVA, reparto, bloqueos y concurrencia. Duplicar abre el
siguiente ingreso esperado; no copia pagos, cuentas ni selecciones de previsión.
Las listas son paginadas. Las operaciones específicas de abono/liquidación siguen
siendo acciones de dominio independientes.

Los nombres distinguen el recurso: `list_hostings`, `list_pocket_movements`,
`create_document_folder` y `create_communication_folder`. El índice completo
con rutas/conteos de carpetas documentales es `get_document_folder_index`;
`list_document_folders` conserva el listado filtrado del panel.
Los pares antiguos de configuración y auditoría contable se consolidan en
`get_accounting_settings`, `update_accounting_settings` y `list_accounting_change_logs`.
El resumen anual (`get_accounting_dashboard`) y las estadísticas descriptivas
(`get_accounting_stats`) se conservan porque devuelven análisis distintos.
Las listas de destinatarios contables y de copias de correo se conservan porque
son entidades distintas y cumplen propósitos diferentes.

Esquemas, catálogo y capacidades usan la misma fuente. Toda acción sensible,
incluidas creación/edición de contenido que puede publicarse o programarse,
requiere vista previa y `confirm_action` en su propio conector; `cancel_action`
la descarta. La confirmación mantiene credencial, actor, argumentos, recursos,
vencimiento y protecciones de reintento. La publicación consume la confirmación
antes de llamar al proveedor y conserva su resultado aunque el proveedor falle.
Los archivos no se transfieren entre
conectores ni credenciales. Los errores conservan código de máquina y mensaje humano.

## Consumidores y credenciales

La migración `content.0293` congela el catálogo anterior de cada credencial
existente y sus permisos efectivos. Un alcance antes vacío se convierte en la
lista de acciones que realmente permitía: no adquiere lecturas secretas. Los
permisos explícitos se conservan, incluidos permisos secretos ya concedidos.
No se copian tokens entre conectores ni se amplían los antiguos al módulo unificado.

Las credenciales nuevas usan el catálogo canónico. Para preparar un reemplazo
limitado, el administrador usa el endpoint habitual del destino:

```json
{"label": "Consumidor migrado", "migrate_from_credential_id": 42}
```

La API traduce sólo las funciones del origen que pertenecen a ese destino,
conserva actor y vencimiento y limita `income_kinds` cuando el origen sólo podía
operar esperados. El secreto se muestra una sola vez. Cuando Proyectos se reparte
entre Proyectos y Contable, crear un reemplazo por destino y configurar ambos
conectores antes de dar por migrado al consumidor.

El botón «Rotar acceso anterior» conserva el principal compatible: no lo convierte
en una credencial de acceso completo al catálogo nuevo. Los nombres antiguos
aceptados por credenciales canónicas no aparecen en descubrimiento. Las respuestas
compatibles incluyen `_meta.deprecation` con el destino y el aviso.

Después del despliegue y de probar cada cliente, `mcp_retirement --slug <origen>`
muestra las condiciones pendientes sin escribir. Desde el clon de servicio,
con los settings de producción explícitos, el operador puede registrar cada
consumidor mediante `--migrated-credential <id> --replacement-credential <id>`
(repetir el segundo flag si hay varios destinos) y `--apply`. Se comprueban
permisos, actor, vencimiento y cobertura de todos los destinos. `--verify-consumers
--apply` registra que se completó el inventario de consumidores, incluidos los
externos. No ejecutar estos comandos mutantes desde un worktree.

## Retiro y recuperación

El retiro requiere al menos 30 días desde la publicación, consumidores
verificados y migrados o revocados, 14 días continuos sin llamadas antiguas y
ninguna confirmación pendiente. El contador se escribe antes del despacho; si
falla, la llamada se rechaza con `MCP_AUDIT_UNAVAILABLE` sin ejecutar su acción
y se reinicia la ventana de observación cuando la base permite registrarlo.
Los intentos autenticados con protocolo inválido también cuentan como actividad.
La tarea Huey de cinco minutos mantiene la observación; un hueco de más de diez
minutos reinicia los 14 días. La evidencia diaria se conserva 90 días y no depende
de los últimos 200 eventos del panel.

`mcp_retirement --slug <origen> --retire --apply` aplica sólo un retiro elegible;
no hay retiro automático por calendario. En un slug canónico retira el catálogo
y los nombres anteriores; en uno reemplazado retira todas sus herramientas.
Las filas de credenciales y auditoría permanecen. Un acceso autenticado retirado
responde `410 CONNECTOR_RETIRED`, y no permite rotar un token que ya no serviría.
La revocación sigue disponible. Credenciales inválidas siguen sin revelar datos.

No se borran datos de negocio, no se fusionan destinatarios ni se reescriben
migraciones previas. Antes del retiro, los consumidores pueden seguir con el
catálogo compatible. Ante un problema, se conserva esa vía y se corrige el
catálogo nuevo; la seguridad de confirmación no se desactiva para hacer rollback.
El retiro definitivo y la configuración de clientes externos no se acreditan
por abrir el PR: necesitan despliegue y evidencia real.
