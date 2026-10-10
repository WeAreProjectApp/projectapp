# Gestor Documental MCP 4.0.0

## Contratos explícitos y ruptura de compatibilidad

Las herramientas de Documentos incluidas en este barrido publican argumentos
planos, tipados, descritos en español y cerrados con
`additionalProperties: false`. Los 36 adaptadores del Panel declaran sus
filtros y campos de escritura reales; también se cierran las 16 raíces nativas
de documentos e hilos que aún admitían argumentos desconocidos. Los objetos
anidados tienen campos cerrados o valores de mapa tipados, y los obligatorios
pertenecen a las propiedades declaradas.

**Se retiran los envelopes `data` y `query`**, incluidos los alias internos de
los adaptadores. Una llamada que los conserve falla con `unknown_field`. Cada
campo del cuerpo o filtro pasa directamente a `arguments`, junto con los IDs
de ruta y el `if_match` opcional de la herramienta que lo admite.

El objetivo es que la vista previa evalúe los mismos argumentos y reglas que
la ejecución, y que el contrato publicado pueda auditarse contra la vista,
serializer y servicio. Un campo superior desconocido se rechaza antes de
ejecutar un handler, preparar una confirmación o escribir. El tipado del schema
no reemplaza las validaciones del dominio ni amplía permisos.

El inventario se mantiene en **73 herramientas**. `describe_capabilities`,
`confirm_action` y `cancel_action` son contratos compartidos de PR #503 y están
fuera del barrido, al igual que las herramientas de historial `*_history` de
esa entrega. El historial excluido conserva su contrato y los demás conectores
conservan sus alias por ahora; esta ruptura se limita a los contratos de negocio
convertidos de **documents 4.0.0** y **projects 3.0.0**.

## Migración de llamadas MCP

Los ejemplos muestran `params` de `tools/call`; los IDs son ilustrativos y
deben sustituirse por referencias autorizadas. Consultar de nuevo `tools/list`
antes de construir llamadas; no copiar campos de otro serializer del Panel.

### Escritura mediante el puente del Panel

Antes, `update_folder` recibía los campos dentro de `data`:

```json
{"name":"update_folder","arguments":{"folder_id":12,"data":{"name":"Documentos revisados","parent_id":34}}}
```

Ahora:

```json
{"name":"update_folder","arguments":{"folder_id":12,"name":"Documentos revisados","parent_id":34}}
```

`parent_id` y su alias de campo `parent` siguen disponibles; si se envían ambos,
deben coincidir. Las políticas y el hash admitidos por este movimiento también
van al nivel superior, conservando sus defaults seguros.

### Lista con filtros

Antes, `browse_documents` recibía un envelope `query`:

```json
{"name":"browse_documents","arguments":{"query":{"client":29,"scope":"all","tags":[2,3],"page":1}}}
```

Ahora:

```json
{"name":"browse_documents","arguments":{"client":29,"scope":"all","tags":[2,3],"page":1}}
```

El puente conserva la codificación de filtros: booleanos como `true`/`false`,
listas CSV salvo `x-query-encoding: repeat`, y omisión de null cuando el filtro
es nullable. Los nombres de filtro son los de cada herramienta; no sustituir
`client` por `client_profile_id` si su schema no lo declara.

### Escritura de entrega en el conector Proyectos

El cambio coordinado de Proyectos 3.0.0 afecta a `create_delivery_contract`.
Esta herramienta pertenece a `projects`, no a `documents`.

Antes:

```json
{"name":"create_delivery_contract","arguments":{"project_id":7,"expected_version":0,"request_id":"contract-initial","data":{"key":"main","title":"Contrato principal"}}}
```

Ahora:

```json
{"name":"create_delivery_contract","arguments":{"project_id":7,"expected_version":0,"request_id":"contract-initial","key":"main","title":"Contrato principal"}}
```

### Escritura de recurso en el conector Proyectos

Antes:

```json
{"name":"update_project_resource","arguments":{"project_id":7,"resource_id":5,"expected_version":0,"request_id":"resource-title","data":{"title":"Manual revisado"}}}
```

Ahora:

```json
{"name":"update_project_resource","arguments":{"project_id":7,"resource_id":5,"expected_version":0,"request_id":"resource-title","title":"Manual revisado"}}
```

La escritura sigue pasando por confirmación. Los detalles de entregas,
recursos, importaciones y campos exclusivos del Panel están en la
[guía de Proyectos 3.0.0](2026-10-10-projects-mcp-3.0.0.md#migración-de-llamadas-mcp).
Los objetos de dominio tipados, como `payload` de importación o de tickets,
permanecen; sólo se eliminan las envolturas genéricas `data`/`query`.

## Errores con campo identificable

Enviar `data` a `update_folder`, aun con un `folder_id` válido, produce este
`structuredContent`; el texto MCP conserva el mismo error:

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

La falta de un obligatorio conserva `required`. Un campo del serializer que se
llama literalmente `message` mantiene `field: "message"` en
`details.errors[*]`, o su ruta anidada; ya no se atribuye a `non_field_errors`.
El mensaje principal del error sigue siendo texto. `blockers`, `planned`,
`can_apply`, `impact_hash` y `plan_hash` conservan su estructura.

## Qué se conserva y cómo validar

Se mantienen IDs, URLs de conectores, alcance de credenciales, ETags,
confirmaciones, assets temporales, Markdown, papelera, notas, hilos, políticas
de propiedad/portal, pin de espejos y migración/deshacer de
[Documentos 3.2.0](2026-10-10-documents-mcp-3.2.0.md). No hay nuevas tools ni
una migración de datos en este barrido. Las llamadas que ya eran planas y usan
campos declarados conservan sus reglas; las llamadas envueltas deben migrarse.

Después del deploy, reconectar el conector para refrescar los schemas y
comprobar **4.0.0 / 73 tools** en discovery/capacidades. El cierre exige los
guards de explicitud, la sonda de desconocidos y las regresiones bridge/nativas
del [runbook de esquemas explícitos](../MCP_VALIDATION_RUNBOOK.md#esquemas-explícitos--documents-400-y-projects-300-2026-10-10).
Esta nota describe el contrato de PR 2; no acredita merge, CI ni ejecución en
producción.
