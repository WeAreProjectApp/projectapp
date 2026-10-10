# Plantillas contractuales y documentos espejo

Las plantillas **combined**, **product** y **service** son textos independientes.
El contrato de producto se importa una vez desde la separación histórica; ya no
se deriva por recortes al leerlo. Sólo el servicio transaccional
`content.services.contract_template_service` actualiza los textos, registra sus
versiones y sincroniza los documentos del gestor. Django admin y el panel muestran
las plantillas en solo lectura.

## MCP de propuestas

`describe_capabilities` expone los esquemas, riesgos y confirmaciones de todas
las herramientas. `get_proposal_contract_template` acepta `variant`, predeterminado
`combined`, y conserva `id`, `name` y `content_markdown`. Añade `markdown`,
`placeholders` (campos con llaves), `version`, `version_id`, `updated_at` y `etag`.

`preview_proposal_contract_template_update` recibe `variant` y exactamente uno
entre `markdown` o `patches`. Devuelve el texto candidato, diff unificado,
validaciones, coherencia y `documents_to_sync` con variante, ID y disponibilidad
del espejo. No escribe contratos ni versiones.

El campo `{service_conditions}` está reservado al contrato de servicio separado;
las otras variantes lo rechazan porque sus generadores no lo resuelven.

Los parches admiten `replace`, `insert_before` e `insert_after`. Seleccionan un
bloque completo por `heading`, un parágrafo con `heading` + `clause_heading`,
o un fragmento por `text` exacto. El resultado se indica en `markdown`. Cada
objetivo debe aparecer una sola vez; no se admiten expresiones regulares.

```json
{
  "variant": "combined",
  "patches": [{
    "operation": "insert_after",
    "heading": "Parágrafo Primero — Plazo para Subsanar",
    "clause_heading": "CLÁUSULA DÉCIMA SÉPTIMA — INCUMPLIMIENTO",
    "markdown": "Texto adicional aprobado.\n\n"
  }]
}
```

`update_proposal_contract_template` exige además `if_match` y `change_note`.
La llamada inicial sólo crea una confirmación con diff e impacto; `confirm_action`
ejecuta el lote previsualizado. Se vuelve a comprobar bajo bloqueo la versión de
las tres plantillas y la identidad de los espejos. Las confirmaciones tienen el
vencimiento, alcance de credencial y protección contra repetición comunes del MCP.

`related_updates` admite hasta otras dos variantes, cada una con su `variant`,
`if_match` y `markdown` o `patches`. La coherencia se valida sobre el resultado
completo. Una variante repetida, un campo desconocido o un objetivo ambiguo se
rechazan antes de cualquier escritura contractual.

`list_proposal_contract_template_versions` recibe `variant`, `limit` (1–50,
default 20) y `offset` (default 0). Devuelve Markdown, autor, fecha, motivo y origen
de restauración. `restore_proposal_contract_template_version` exige `variant`,
`version_id`, `if_match` y `change_note`; también permite `related_updates` con
versiones o cambios coordinados. Restaurar crea una versión nueva: conserva las
anteriores y aplica las mismas validaciones. Una versión histórica que omita
campos hoy obligatorios o deje variantes incoherentes no se puede restaurar sin
preparar un texto corregido mediante update.

`check_proposal_contract_templates_consistency` compara las cláusulas por ámbito
(producto, servicio o común), muestra faltantes y diferencias y conserva cifras,
monedas, unidades, obligaciones y plazos. Normaliza formato, numeración y
referencias. Sólo reconoce las adaptaciones explícitas de modalidad: contrato de
desarrollo independiente, ubicación de condiciones económicas y reglas que se
aplican exclusivamente al producto. No usa evaluación de IA externa. Toda
incoherencia bloquea update y restore.

## Gestor documental y transacción

`list_contract_mirrors` devuelve `document_id`, título, `variant`, `folder_id`,
`folder_path`, `folder_movable`, `version`, `last_synced_at` y `synchronized`
para cada variante, además del bloque `pinned_folder`. Una vinculación
pendiente o un PDF no disponible aparece explícitamente como no sincronizado.
Los tres documentos se consultan como las cuentas de cobro: PDF, Markdown,
versión y fecha. No ofrecen editar, guardar, renombrar, mover, arrastrar,
duplicar, archivar ni eliminar individualmente. Las observaciones privadas usan
el gestor de notas existente.

### Carpeta Contratos fijada por ID (2026-10-09)

`ContractTemplate.mirror_folder` fija la ubicación por ID, con FK nullable y
`PROTECT`; el nombre «Contratos» deja de ser la identidad de la carpeta. La
migración `content.0286_contracttemplate_mirror_folder` hace backfill desde las
vinculaciones existentes, incluido `mirror_document` legacy, cuando identifican
una sola carpeta. Una ubicación ambigua queda sin pin persistido. El resolver
usa el campo, luego una carpeta derivada única de los vínculos actuales y, si
no puede resolverla, informa `unpinned`.

`pinned_folder` expone `pinned_folder_id`, `pin_source` (`field`, `derived` o
`unpinned`), `folder_path`, `folder_movable`, `archive_blocked` y
`archive_block_reason`. Son lecturas: ninguna herramienta MCP cambia el pin.
La sincronización compara el ID y el estado activo de la carpeta, junto con la
revisión y el PDF del espejo. Sin pin resoluble, una actualización contractual
falla con `MIRROR_SYNC_FAILED`, `stage: folder_pin` y `applied: false`.

Contratos y sus ancestros manuales pueden renombrarse, moverse y reordenarse;
los espejos siguen dentro de la misma carpeta y mantienen `synchronized: true`.
Se conservan las restricciones propias de carpetas administradas automáticamente.
Archivar la carpeta o un ancestro que contiene espejos devuelve HTTP 409
`contract_mirror_folder_archive_blocked` (MCP:
`CONTRACT_MIRROR_FOLDER_ARCHIVE_BLOCKED`), con `contracts_folder_id`,
`contracts_folder_path` y `mirror_document_ids`. Para liberar un ancestro hay
que mover primero la carpeta de los espejos fuera de él.

La carpeta fijada permanece sin cliente ni proyecto. Intentar cambiar esas
asociaciones devuelve HTTP 409 `contract_mirror_folder_pinned` (MCP:
`CONTRACT_MIRROR_FOLDER_PINNED`). El cambio de cliente de una carpeta superior
omite la rama fijada y sus espejos, y los informa en `folders_pinned`,
`documents_pinned` y sus totales. El borrado forzado de un proyecto que contiene
esa carpeta también exige moverla fuera del proyecto antes de continuar.
Guion de comprobación: [Migración de carpetas por MCP — parte 1](MCP_VALIDATION_RUNBOOK.md#migración-de-carpetas-por-mcp--parte-1-2026-10).

Los PDFs se conservan en `ContractTemplateMirror.pdf_content`, separados de los
archivos inmutables de propuestas. Una confirmación guarda textos, versiones,
PDFs y notas privadas en la misma transacción. Si falla un PDF o una nota,
`MIRROR_SYNC_FAILED` identifica variante, documento y etapa, con `applied=false`;
no se conserva ningún cambio parcial. Cada nota contiene versión, fecha,
`change_note` y resumen del diff.

Los espejos enmascaran los datos personales y dejan las condiciones particulares
por completar. No toman un cliente, importes ni datos de una propuesta real.
Las nuevas generaciones de combinado y servicio toman los términos explícitos de
`contract_params` y, cuando faltan, los valores de `service_contract_settings`.
Editar una plantilla no actualiza parámetros, PDFs, firmas ni Markdown ya
guardados en propuestas. La regeneración requiere una acción explícita sobre la
propuesta.

## Migraciones y primer uso

Las migraciones añaden el texto independiente de producto, el historial y los
espejos transaccionales. Importan los textos previos como versión 1 sin tocar
propuestas. La vinculación operativa se hace tras el despliegue, desde su entorno
canónico, nunca desde un worktree apuntando a la base real.

En ProjectApp ya existen **ProjectApp / Contratos** (carpeta 121), el combinado
(documento 104) y la copia de servicio sin firma (205). Inicialización idempotente:

```bash
DJANGO_SETTINGS_MODULE=projectapp.settings_prod venv/bin/python manage.py initialize_contract_template_mirrors --apply --folder-id 121 --service-document-id 205
```

Conserva los IDs 104 y 205, crea el producto y respalda el texto manual anterior en
`imported_markdown`. Los títulos son «Contrato unificado de producto y servicio»,
«Contrato de producto — desarrollo e implementación de software» y «Contrato de
servicio — hosting, mantenimiento y soporte». Todos permanecen en Contratos.

El inicializador busca `--folder-id` por pk y exige una carpeta activa sin
cliente ni proyecto, aunque haya sido renombrada. Con `--apply` persiste el pin
si todavía no existe; repetir con el mismo ID es idempotente. Si la plantilla
ya tiene otro `mirror_folder_id`, rechaza re-fijarla y revierte el lote. Sin
`--apply` sólo informa y no fija ninguna carpeta.

`apply_contract_template_adjustments` relee el documento 237, comprueba sus
instrucciones y produce un lote con los nuevos parágrafos de duración/renovación
y terminación de la cláusula XXI y los ajustes de XVII, XIX y XXIV. Incluye la
instrucción adicional del operador: confidencialidad y no circunvención de tres
años en las tres variantes, confidencialidad ampliada del servicio y garantía del
producto de tres años desde la aceptación final, conservando sus demás condiciones.
La instrucción adicional prevalece sobre la excepción de confidencialidad que
el documento 237 originalmente proponía conservar.

Sin `--apply`, el comando devuelve únicamente preview. Con `--apply` y una
`--credential-id` activa del conector proposals, usa la confirmación real del MCP;
no genera tokens ni evita su control de alcance. La segunda ejecución es un no-op.
Tras confirmar, comprobar coherencia, los tres espejos y sus PDFs. Reportar los
IDs y versiones reales; el ID del espejo de producto no se asume.
