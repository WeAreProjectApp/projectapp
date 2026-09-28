# Documentos REST y MCP 3.0.0

## Cambios de compatibilidad

- Las escrituras documentales REST/MCP devuelven `id`, `title`, `folder_id`,
  `folder_name`, `status`, `etag`, `updated_at`, `editable`, `movable` y
  `move_blockers`. Los resultados de archivado/restauración conservan sus
  indicadores. Para obtener texto en una escritura enviar `include_content: true`:
  se añade únicamente `markdown`, sin `content_json` ni una segunda copia.
- Las lecturas MCP usan `markdown`; se retira el alias de salida
  `content_markdown`. El alias de entrada de `update_document` se conserva. El
  GET de detalle del Panel mantiene `content_markdown`, sin duplicarlo.
- Crear, renombrar o mover carpetas rechaza campos desconocidos y nombres
  repetidos entre hermanos, incluso archivados. `parent_id` es el nombre
  recomendado y `parent` sigue siendo alias; valores contradictorios son error.
- `create_estimate_document` ya no crea carpetas. Requiere
  `REQUIREMENT_ESTIMATES_FOLDER_ID` o `--folder-id`; `--folder` sólo selecciona
  un nombre global único. La skill usa el mismo resolver para consultar y crear.

## Organización y auditoría

- El espejo del contrato admite cambiar exclusivamente `folder_id`. Conserva
  contenido, plantilla, cliente, proyecto y visibilidad; `editable=false` se
  refiere al contenido, `movable=true` a su organización.
- `move_documents({document_ids: [...], folder_id: int|null})` mueve de 1 a 100
  documentos activos en una transacción. Si uno falla, ninguno cambia. Cada ID
  recibe `moved`, `unchanged`, `failed` o `aborted` y los errores incluyen motivo.
  Endpoint REST: `POST /api/documents/move/`. Admite `include_content` explícito.
- `list_folders` incluye fechas, origen, autor y conteos de documentos/hijos
  archivados directos. El conteo histórico `document_count` del MCP sigue contando
  sólo Markdown activo; `archived_document_count` incluye todos los tipos.
- `parent_id` omitido lista todos los niveles; `null` lista raíces; un entero,
  hijos directos. `name` busca coincidencia exacta sin distinguir mayúsculas y
  elimina espacios exteriores. REST acepta `parent_id=null` en la query.
- La autoría nueva distingue usuario del Panel, `mcp` y `system`; el historial sin
  evidencia conserva `created_by=null` y `creation_source=unknown`. La migración
  no inventa autores ni modifica fechas históricas.
- El **slug permanece estable** al renombrar. La ubicación no define identidad.
- `describe_capabilities` permite `tools: [nombres]` y `summary: true`. El resumen
  contiene exclusivamente `name`, `title`, `risk`, `requires_confirmation` por
  herramienta. Los filtros respetan la credencial; nombres invisibles no revelan
  información. Sin argumentos se conserva el detalle completo.

## Despliegue

La migración añade autoría y un mutex de escrituras de carpetas. Las validaciones
se repiten dentro del bloqueo antes de guardar para cerrar carreras de duplicados
y ciclos. No hay eliminación, fusión ni renombrado de carpetas históricas.

Antes de habilitar la calculadora, verificar en el entorno de destino el ID de
`ProjectApp / Requirement Estimates` y configurar `REQUIREMENT_ESTIMATES_FOLDER_ID`.
El ID comunicado para ese entorno es **69**; no se usa como valor universal ni se
asigna `system_key`, porque este último bloquearía movimientos manuales.

Desplegar backend y frontend juntos: el store ya no reemplaza el editor con el
resumen de escritura. Las migraciones y configuración las aplica el despliegue,
nunca un worktree conectado a la base del servicio.
