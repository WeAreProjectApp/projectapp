# Gestor Documental MCP 3.0.1

## Errores y movimientos

Todos los errores de herramientas contienen `ok: false` y `error` con `code`,
`message` y `details`. El JSON de `content[0].text` coincide con
`structuredContent`: los clientes que sólo leen texto reciben el mismo detalle.
Los errores de campos incluyen `details.errors`, con `field`, `code` y `message`.
Se preservan los detalles anteriores y los códigos ya publicados. Campos
inesperados y ciclos de carpetas usan `unknown_field` y `folder_cycle`.
Los fallos internos no revelan la excepción del servidor.
Los rechazos HTTP anteriores al despacho (token, origen, formato, método o
límite de solicitudes) también devuelven `error.code` y `error.message`,
conservando su estado HTTP y las cabeceras de reintento.

`move_documents` conserva la atomicidad y el orden de IDs. Los resultados
`failed` y `aborted` añaden código y mensaje; `reason` se conserva por compatibilidad.
Los bloqueos documentales incluyen `move_blockers`. Los resultados se publican en
la raíz (`results`) y, en errores, también en `error.details.results` por
compatibilidad. Ningún resultado abortado declara un movimiento completado.

Códigos por elemento: `not_found`, `archived`, `not_movable`, `folder_not_found`,
`folder_archived`, `folder_not_movable`, `permission_denied`, `batch_aborted`,
`write_failed`. La autorización de la credencial sigue devolviendo `FORBIDDEN`
antes de consultar recursos que no puede utilizar.

## Descubrimiento

`tools/list` y `describe_capabilities` comparten la proyección de esquemas del
registro definitivo. Capacidades incluye su propia herramienta, conserva los
filtros `tools`/`summary` y respeta la credencial. Descubrimiento y capacidades
anuncian `documents` 3.0.1 desde una constante común.

Se publican `list_folders.parent_id/name`, `describe_capabilities.tools/summary`,
los campos superiores de `create_folder`/`update_folder` (`name`, `parent_id`,
`parent`, `order`, `client`, `project`) e `include_content` en escrituras.

Tras desplegar, comparar una consulta nueva `tools/list` con capacidades. Si el
servidor coincide y el agente ve argumentos antiguos, refrescar/reconectar el
conector en ese cliente. No regenerar tokens ni renombrar herramientas.

## Procedencia

`creation_operation` identifica el creador: `create_folder`,
`django_admin.create_folder`, `ensure_project_folder`, su plantilla,
`ensure_generated_folder_path` o `create_fake_documents`. `creation_source`
admite además `migration`; las migraciones futuras que creen carpetas deben
pasar explícitamente ese origen y su identificador. No se modifican migraciones
históricas ni se deducen autores de carpetas anteriores.

El Panel y Django admin conservan el usuario; MCP conserva su principal técnico.
El admin usa las mismas validaciones de duplicados y ciclos que el Panel.
Las sincronizaciones no reescriben la procedencia de carpetas existentes.
Las skills heredan el canal de ejecución: MCP o comando del servidor.

La migración aditiva 0272 añade el identificador de operación. La aplica el
despliegue; no correr migraciones ni reparaciones desde un worktree.

## Littigio

La investigación confirmó movimientos MCP anteriores al despliegue de 3.0.0.
El comando `repair_document_folder` previsualiza un manifiesto de IDs y huellas;
la aplicación exige hash, administrador y respaldo. Rechaza cambios posteriores,
conserva asociaciones y contenido, registra el historial y archiva sólo el origen
vacío. La repetición con recibo durable no genera nuevos movimientos.
La reparación de producción se completó el 28-09-2026 a las 23:56 UTC: cinco
documentos restaurados a 80, carpeta 124 archivada y autoría MCP recuperada.

Evidencia y procedimiento: [reparación de Littigio](../runbooks/littigio-folder-repair.md).
