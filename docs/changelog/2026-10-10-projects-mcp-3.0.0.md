# Gestor de la Plataforma MCP 3.0.0

## Contratos explícitos y ruptura de compatibilidad

Las herramientas de Proyectos incluidas en el barrido publican un schema de
entrada plano, cerrado, tipado y descrito en español. Los 48 adaptadores del
Panel declaran los campos y filtros que sus vistas y servicios usan. Las
nativas de entregas, recursos, tickets, facturación, hosting y alta de proyectos
describen también objetos anidados y argumentos obligatorios.

**Se retiran `data` y `query`**, tanto publicados como aceptados mediante alias
internos. Los campos de escritura y filtros se envían directamente en
`arguments`. Una clave superior desconocida devuelve `unknown_field` antes de
ejecutar el handler, preparar una confirmación o escribir. El contrato cerrado
permite auditar el recorrido y comprobar que el preview y la ejecución evalúan
los mismos argumentos, sin alterar las reglas del servicio compartido.

El inventario continúa en **164 herramientas**. Los contratos compartidos
`describe_capabilities`, `confirm_action` y `cancel_action`, y los tools de
historial `*_history`, pertenecen a PR #503 y quedan fuera del barrido. El
historial excluido conserva su contrato y los conectores restantes conservan
sus alias por ahora. Las herramientas de tickets conservan su objeto tipado **`payload`**;
no es un alias de `data`.

## Migración de llamadas MCP

Los ejemplos muestran `params` de `tools/call`, con IDs ilustrativos. Obtener
referencias autorizadas y la versión vigente antes de escribir; actualizar las
plantillas de llamadas y reconectar el conector después del deploy.

### Escritura mediante el puente del Panel

Antes:

```json
{"name":"update_project","arguments":{"project_id":7,"data":{"name":"Proyecto revisado","description":"Alcance actualizado"}}}
```

Ahora:

```json
{"name":"update_project","arguments":{"project_id":7,"name":"Proyecto revisado","description":"Alcance actualizado"}}
```

El cambio de cliente y el de estado siguen usando sus operaciones específicas;
no se habilitan como campos de `update_project`.

### Lista con filtros

Antes:

```json
{"name":"list_projects","arguments":{"query":{"client_profile_id":29,"scope":"all"}}}
```

Ahora:

```json
{"name":"list_projects","arguments":{"client_profile_id":29,"scope":"all"}}
```

Lo mismo aplica a `list_project_retention_contexts`: enviar `client_profile_id`,
`page` e `integrity` planos cuando se necesiten, sin prefijo `query`.
El transporte conserva booleanos `true`/`false`, listas CSV o repetidas según
el schema y omisión de null en filtros nullable.

### Escritura de entrega

Antes:

```json
{"name":"create_delivery_contract","arguments":{"project_id":7,"expected_version":0,"request_id":"contract-initial","data":{"key":"main","title":"Contrato principal"}}}
```

Ahora:

```json
{"name":"create_delivery_contract","arguments":{"project_id":7,"expected_version":0,"request_id":"contract-initial","key":"main","title":"Contrato principal"}}
```

Los seis CRUD editoriales sólo aceptan campos declarados para su entidad.
`context_id`, `source_references` y `approval_file_id` también van planos donde
se admiten. Preparación, instantánea y revalidación de efectos públicos usan
esos mismos argumentos; compartir contenido sigue exigiendo la confirmación
correspondiente. `expected_version` procede de `get_delivery_overview`.

### Escritura de recurso

Antes:

```json
{"name":"create_project_resource","arguments":{"project_id":7,"asset_id":"10000000-0000-4000-8000-000000000001","expected_version":0,"request_id":"resource-initial","data":{"title":"Manual","description":"Guía revisada","category":"documents"}}}
```

Ahora:

```json
{"name":"create_project_resource","arguments":{"project_id":7,"asset_id":"10000000-0000-4000-8000-000000000001","expected_version":0,"request_id":"resource-initial","title":"Manual","description":"Guía revisada","category":"documents"}}
```

`asset_id` debe ser el UUID de un upload completado por la misma credencial,
nunca una ruta de storage; el UUID de ejemplo no es utilizable. Releer la
versión mediante las consultas de recursos y revisar/confirmar antes de aplicar.
Carpetas usan `name`/`order` planos; el modelo de datos usa `entities` plano,
con cada entidad tipada. El upload de adjuntos conserva `title` y `category`,
pero **deja de aceptar `description`**, que su serializer ignoraba. La
descripción del recurso sí se conserva.

## Importaciones con contratos v1/v2

`preview_delivery_import` y `apply_delivery_import` conservan **`payload`**,
descrito mediante la unión de los contratos existentes de autoría, elegida por
`payload.schema_version`:

- **1:** guías manuales, con `scopes` y su jerarquía tipada.
- **2:** añade UUID de `context_id` y citas `source_references` por requerimiento,
  verificadas contra las fuentes capturadas.

No envolver `payload`, `expected_version` ni `request_id` en `data`. El preview
no guarda; aplicar conserva confirmación, transacción e idempotencia. El schema
no reemplaza las validaciones de citas, versiones, propiedad ni congelación.
Consultar `get_delivery_authoring_contract` y la
[matriz de entrega](../PLATFORM_DELIVERY_MCP_MATRIX.md#contrato-de-escritura-y-documentos).

## Eliminación y campos exclusivos del Panel

`preview_project_delete` y `delete_project` aceptan **sólo `project_id` y el
`if_match` opcional**. `if_match` conserva concurrencia optimista; no autoriza
un borrado forzado. `force`, `delete_keys`, `confirmation` e `impact_token`
quedan fuera del contrato MCP y fallan como `unknown_field`. La eliminación
sensible sigue limitada a proyectos vacíos y no crea una intención si llegan
controles de purga.

`PANEL_ONLY_FIELDS`, en `content/mcp/schemas/projects_bridge.py`, registra con
motivo explícito las entradas excluidas del MCP: las listas legacy
`hosting_ids`, `income_ids` y `communication_thread_ids` de
`change_project_client`, los campos que `update_project` rechaza siempre y los
controles de eliminación forzada. MCP cambia cliente mediante `mode` y
`expected_impact_hash`, sobre el plan calculado por el servidor. No trasladar
las listas del Panel a esa llamada. La exclusión es por herramienta:
`assign_project_unlinked_records` conserva sus listas declaradas.

## Errores con campo identificable

Enviar el envelope `data` a `update_project`, con un `project_id` presente,
devuelve este `structuredContent`; el texto MCP devuelve el mismo error:

```json
{
  "ok": false,
  "error": {
    "code": "unknown_field",
    "message": "data: Campo desconocido o de solo lectura.",
    "details": {
      "data": ["Campo desconocido o de solo lectura."],
      "errors": [{"field":"data","code":"unknown_field","message":"Campo desconocido o de solo lectura."}]
    }
  }
}
```

Al omitir `message` de `add_delivery_message` con los demás obligatorios
presentes, el error de validación identifica el campo original:

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "message es obligatorio.",
    "details": {
      "message": ["message es obligatorio."],
      "detail": "message es obligatorio.",
      "errors": [{"field":"message","code":"required","message":"message es obligatorio."}]
    }
  }
}
```

Un campo del serializer llamado `message`, incluso anidado, conserva su ruta
en `details.errors[*].field` en lugar de `non_field_errors`. El mensaje del
envelope sigue siendo texto. Se mantienen `blockers`, `planned`, `can_apply`,
`impact_hash` y `plan_hash` sin aplanar sus estructuras.

## Qué se conserva y cómo validar

Se mantienen URLs, credenciales y permisos, IDs, assets y límites de upload,
versiones, huellas de impacto, confirmaciones y reintentos. Entregas no
importan firmas ni decisiones; tickets conservan `payload`; hosting y pagos
mantienen el ciclo de vida de
[Proyectos 2.2.0](2026-10-10-projects-mcp-2.2.0.md). `create_project` conserva
su contrato estricto sin políticas, con `name`/`client_profile_id` y las
opciones `description`, `state_id`, `root_folder_id`. Este barrido no añade
herramientas ni migraciones de datos.

Después del deploy, comprobar **3.0.0 / 164 tools**, refrescar `tools/list` y
cotejar schemas con `describe_capabilities`. El
[runbook de esquemas explícitos](../MCP_VALIDATION_RUNBOOK.md#esquemas-explícitos--documents-400-y-projects-300-2026-10-10)
incluye guards, sonda sin escrituras, contratos bridge, nativas de entrega y
el slice nativo de Proyectos de 22 casos. Esta nota describe PR 2 y no acredita
su CI, merge ni operaciones ya ejecutadas en producción.
