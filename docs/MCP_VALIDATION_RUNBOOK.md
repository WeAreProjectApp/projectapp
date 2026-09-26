# Guion de validación y mantenimiento de MCP

Las carpetas del conector de Documentos declaran `folder_kind`, proyecto y
estado. `create_folder` hereda la asociación de su padre y `rename_folder`
rechaza raíces automáticas de proyecto; estas protecciones se validan junto
con los contratos de modelo antes de publicar cambios del gestor.

Última revisión integral: 2026-09-04.

Este documento es el procedimiento repetible para validar la plataforma MCP de
ProjectApp: transporte moderno y compatible, credenciales con alcance,
confirmación de operaciones sensibles, uploads temporales y paridad operativa
con las áreas del Panel. La fuente ejecutable del inventario está en
`backend/content/views/mcp_blog.py`; los adaptadores de paridad viven en
`backend/content/mcp/operation_catalogs.py` y la clasificación de campos en
`backend/content/mcp/contracts.py`.

## Plataforma operativa común

- El endpoint canónico acepta `Authorization: Bearer <credencial>` en
  `/api/mcp/<slug>/`. La URL histórica `/api/mcp/<slug>/<token>/` permanece
  disponible para no romper conectores instalados.
- El contrato stateless MCP `2026-07-28` usa `server/discover`, metadata por
  request, `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` para `tools/call`,
  `resultType` y hints de caché privada. Los handshakes 2025 y 2024 siguen
  admitidos por compatibilidad.
- Cada credencial tiene etiqueta, alcance de herramientas, vencimiento y
  revocación propios. El secreto sólo se muestra al crear o rotar; la base
  conserva únicamente SHA-256 y un prefijo enmascarado.
- Cada conector ejecuta como un principal técnico no interactivo
  `mcp_<slug>`, con contraseña inutilizable. No toma prestada la identidad del
  primer superusuario humano.
- Las lecturas y ediciones reversibles se ejecutan directamente. Toda acción
  externa, financiera o irreversible responde primero con
  `confirmation_id`, impacto y vencimiento; `confirm_action` ejecuta una sola
  vez los mismos argumentos y `cancel_action` descarta el intent.
- Los módulos con archivos exponen `begin_upload`, PUT firmado o
  `upload_asset_chunk`, `complete_upload` y `abort_upload`. Tamaño, MIME y
  SHA-256 se verifican antes de que un `asset_id` pueda consumirse; descargas y
  exports se entregan como artefactos firmados temporales.
- La auditoría conserva las 200 entradas más recientes por conector con
  request ID, credencial, herramienta, riesgo, resultado/error, duración e IDs
  de objetos afectados. No persiste cuerpos completos ni secretos.

## Invariantes

- Todos los conectores comparten control de Origin, throttle por conector,
  principal técnico, registro de actividad y los dos transportes de credencial.
- Un conector nuevo nace inactivo y sin token. Activarlo y emitir la URL es una
  decisión explícita del superusuario en `/panel/mcps`.
- Los handlers MCP reutilizan serializers y servicios del panel. Una regla que
  impide una acción en la interfaz también la impide por conversación.
- En propuestas, `_meta.optional_metadata.email_intro` del template/artifact se
  persiste como `BusinessProposal.email_intro`. Debe ser texto plano específico
  del cliente y conectar problema, solución y resultado. `send_proposal`,
  `resend_proposal` y el envío múltiple rechazan el mensaje vacío antes de
  snapshots o transiciones; `resend_proposal` acepta un `email_intro` opcional
  para editarlo y enviarlo en la misma operación.
- Las carpetas con `system_key` pertenecen al archivado automático. El MCP puede
  listarlas para orientar al operador, pero no crearlas debajo, renombrarlas ni
  usarlas como destino de un documento markdown.
- Ninguna descripción puede prometer un dato que el handler descarte o una
  acción que el servidor no realiza.
- `DocumentState.description` es una lectura clasificada del contrato MCP. Para
  estados de proyecto, la descripción administrable no sustituye el
  `operational_effect` ni la ayuda de consecuencias derivada por el sistema.
- `UserProfile.document_navigation_mode` es una preferencia de presentación del
  panel y permanece clasificada como perfil/plataforma: no altera ni se expone
  en las herramientas MCP de clientes o Documentos.
- Todo `Project` pertenece a los catálogos de Documentos y Comunicaciones; no
  existe un opt-out por módulo. `DocumentFolder.managed_project` identifica su
  única raíz documental canónica. El MCP puede seguir referenciando proyectos
  existentes, pero no adopta carpetas históricas ni provisiona raíces por esa
  vía.
- `ProjectAdminAccess`, `ProjectAccessNote` y los campos legacy
  `Project.admin_url/admin_username/admin_password_encrypted` quedan excluidos
  con motivo explícito. Ninguna tool MCP lista, revela, crea o modifica
  URLs, credenciales o notas del detalle seguro; las operaciones MCP de proyecto
  conservan únicamente identidad, ciclo y metadatos no operativos.
- `DocumentFolder.managed_client` es el equivalente para clientes y se comporta
  igual desde el MCP: read-only, sin adopción ni provisión por esa vía. Con él
  `folder_kind` tiene **tres** valores (`project` / `client` / `manual`), que es
  lo que declara la descripción de `list_folders`. Dos asimetrías respecto de
  proyectos, deliberadas: la raíz de cliente **no** se crea sola con el cliente
  (se adopta), y **sí** se puede renombrar —el nombre lo pone el operador, no un
  módulo externo—, así que `rename_folder` la acepta.
- **Archivado de clientes.** `UserProfile.archived_at` (antes `deactivated_at`)
  es el eje de ciclo de vida del cliente, con el mismo vocabulario que el bucket
  no activo de proyectos. `list_clients` devuelve **sólo activos** salvo que se
  pida `archived=true`: devolverlos mezclados es como el conector termina
  proponiendo trabajo sobre un cliente que se archivó a propósito. `archived_at`
  es read-only y `archived_by` está excluido como auditoría interna, junto a
  `created_by` — archivar **no** es una operación del MCP, porque suspende los
  proyectos del cliente y cancela su facturación futura, y eso exige la vista
  previa del panel. El archivado de un hilo de comunicaciones sólo cambia su
  visibilidad y sí está expuesto mediante una acción de dominio específica.
- `update_message` edita sólo un borrador saliente activo;
  `delete_draft` aplica la misma condición; `mark_message_sent` registra un
  hecho externo y no contacta proveedores. El envío real pertenece a las
  herramientas separadas `send_email`/`resend_email`, clasificadas como
  sensibles y ejecutables únicamente después de vista previa y confirmación.
  Sus payloads de destino usan `recipient_emails` (Para) y `cc_emails` (copia
  visible): admiten hasta 10 direcciones únicas entre ambas listas. El campo
  legado singular `recipient_email`/`recipient` sigue aceptándose para clientes
  MCP anteriores, pero no permite expresar varios destinatarios.
- `CommunicationThread.managed_project` / `managed_client` identifican la
  **comunicación madre** de un proyecto o un cliente, en paralelo con
  `DocumentFolder.managed_project` / `managed_client`. Son read-only para el MCP:
  la madre de proyecto se provisiona sola al crearse el proyecto, la de cliente
  sólo por adopción revisada, y ninguna se marca desde una herramienta.
  `thread_kind` toma tres valores (`project` / `client` / `manual`).
- El **archivado** de hilos (`is_archived`/`archived_at`) es un eje de visibilidad
  ortogonal a `status` (`open`/`closed`): cerrar bloquea la escritura, archivar
  saca de la vista. Esos campos son read-only: el MCP sólo puede cambiarlos con
  `archive_thread`/`unarchive_thread`, que reutilizan el servicio del panel; una
  comunicación madre no se puede archivar. `list_threads` expone
  `scope=active|archived|all` y conserva `active` como valor por defecto.
- Los hilos entre documentos (`DocumentThread` / `DocumentThreadItem`) sí forman
  parte del conector `documents`. Tres reglas los gobiernan y ninguna se puede
  relajar desde una herramienta:
  - **La edición de miembros es incremental.** El PATCH del panel reemplaza la
    lista completa y disuelve el hilo cuando queda un solo miembro; un conector
    que reconstruyera esa lista destruiría la historia al olvidar una entrada.
    Por eso `update_document_thread` expone `link` / `unlink_document_ids`, se
    rechaza antes de bajar de dos documentos, y disolver es una herramienta
    aparte.
  - **Enlazar acepta sólo documentos markdown activos**, la misma regla del
    resto del conector. Leer y desenlazar aceptan cualquier miembro, porque un
    hilo armado desde el panel puede contener una cuenta de cobro o un
    documento archivado.
  - **Las cuentas de cobro emitidas siguen excluidas del contrato documental
    MCP.** Su `generated_file`, hash/procedencia y datos contables son artefactos
    comerciales de sólo lectura en el panel; `list_documents`/`read_document`
    continúan operando únicamente Markdown y no prometen vista previa, descarga
    ni reemplazo del PDF. Esta exclusión no impide leer una cuenta que ya sea
    miembro de un hilo creado desde el panel.
  - **`position` es derivada** de la cronología: el conector envía fechas y el
    servidor mantiene el orden estable. Es la única exclusión del contrato.
  - **La fila del listado es una sola.** `list_document_threads` y el índice de
    hilos del panel (`GET /api/document-threads/`) comparten
    `DocumentThreadListSerializer` sobre `thread_list_queryset`, igual que ya
    compartían la consulta. Al tocar esa fila hay que verificar ambas
    superficies: las fechas se serializan con `isoformat()` (`+00:00`), no con
    los campos de fecha de DRF, que emitirían `Z` y romperían al conector.
  `dissolve_document_thread` es irreversible —se pierde `linked_by`/`linked_at`—
  y por eso devuelve el hilo completo previo más `released_document_ids`, con lo
  que se puede recrear con `create_document_thread`.
- Nunca copiar tokens reales en tickets, fixtures, logs, commits o este guion.

## Inventario vigente

| Slug | Herramientas | Alcance |
|---|---:|---|
| `operations` | 4 | Dashboard, indicadores, alertas y conteos globales de sólo lectura |
| `commercial` | 135 | Clientes, propuestas, diagnósticos, módulos adicionales, horas, Programa de Alianza (financiación), visibilidad de videos explicativos, archivos y correos comerciales |
| `projects` | 21 | Proyectos, asignaciones, estados, transiciones, documentos asociados e historial |
| `documents` | 64 | Documentos Markdown editables, carpetas, estados, tags, observaciones, hilos, correo, imports y exports |
| `communications` | 33 | Hilos, mensajes, compositor, previews, envío/reenvío, adjuntos, historial, templates y entregabilidad |
| `content` | 43 | Blog, portafolio, QR, Linktrees, LinkedIn y activos relacionados |
| `tasks` | 20 | Tareas, archivo, comentarios, alertas, orden y controles comunes |
| `accounting-ledger` | 56 | Ingresos, gastos, bolsillo, recurrentes, Ads, categorías, previsión de cobro, liquidaciones y exports |
| `accounting-billing` | 35 | Cuentas de cobro, hosting, ciclos, ajustes, destinatarios y correo contable |
| `accounting-cards` | 38 | Tarjetas, snapshots, extractos, transacciones, alias, imports y recordatorios |
| `blog` | 7 | Conector de compatibilidad: plantilla, CRUD y calendario editorial |
| `clients` | 6 | Conector de compatibilidad: búsqueda, detalle y CRUD de clientes |
| `accounting` | 70 | Conector de compatibilidad: catálogo contable monolítico anterior |
| `diagnostics` | 13 | Conector de compatibilidad: diagnósticos y secciones |
| `proposals` | 11 | Conector de compatibilidad: propuestas y enlaces |
| `linkedin-personal` | 7 | Conector de compatibilidad: LinkedIn personal |

Los conectores canónicos nuevos nacen inactivos. Los seis slugs marcados como
compatibilidad no se eliminan ni cambian de URL; permiten una transición gradual
hacia los conectores agrupados por área.

## Preparación segura

1. Ejecutar en una base de test o staging. Producción sólo admite consultas
   read-only hasta que el operador autorice una mutación concreta.
2. Crear una credencial temporal, preferentemente Bearer y limitada a las
   herramientas del caso. Verificar que se le asignó el principal técnico del
   conector y que el secreto no reaparece al recargar.
3. Activar el conector bajo prueba. No reutilizar credenciales reales en
   capturas, comandos compartidos ni fixtures.
4. En contrato moderno, empezar con `server/discover`; en compatibilidad,
   inicializar con `initialize`. Consultar `tools/list` y comparar nombres,
   riesgos, schemas y alcance con el inventario esperado.
5. Para una acción sensible, validar primero el preview, luego confirmar una
   sola vez y repetir `confirm_action` para comprobar respuesta replay-safe.
6. Al terminar, desactivar el conector y revocar la credencial temporal.

Petición base compatible para una llamada manual (sustituir los marcadores
localmente y no guardarlos en el historial del shell):

```bash
curl -sS -X POST 'https://<host>/api/mcp/<slug>/<token>/' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://claude.ai' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Descubrimiento stateless `2026-07-28` por Bearer:

```bash
curl -sS -X POST 'https://<host>/api/mcp/<slug>/' \
  -H 'Authorization: Bearer <credencial>' \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: server/discover' \
  --data '{"jsonrpc":"2.0","id":"discover-1","method":"server/discover","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{},"io.modelcontextprotocol/clientInfo":{"name":"manual-validation","version":"1.0.0"}}}}'
```

Para invocar una herramienta:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": {}
  }
}
```

Una llamada de negocio válida responde HTTP 200. Un rechazo de negocio también
usa HTTP 200, con `result.isError=true`, `structuredContent.error.code` y texto
accionable. Un envelope moderno inválido responde HTTP 400; token, slug inválido
o inactividad responden 404 para no revelar conectores.

Toda herramienta marcada `requires_confirmation=true` usa dos llamadas. La
primera invocación devuelve un `confirmation_id` sin ejecutar; la segunda llama
`confirm_action` con ese ID. El intent vence a los diez minutos, queda ligado a
conector y credencial, conserva la huella exacta de argumentos y no vuelve a
ejecutarse ante un replay.

## Caso crítico: editar un documento en borrador

1. Invocar `list_documents` y luego `read_document` con el ID elegido.
2. Exigir `editable=true`, guardar `etag` y leer `edit_blockers`. Un documento
   archivado o un artefacto generado no se fuerza: responde `NOT_EDITABLE`.
   El contrato vigente (`is_contract_mirror=true`, blocker `contract_mirror`)
   tampoco: `read_document` devuelve el borrador completo en vivo, y
   `update_document`, `append_document` y `delete_document` responden
   `NOT_EDITABLE`. El contrato sólo cambia por migración de su plantilla.
3. Editar con el nombre canónico `markdown` y el ETag leído:

```json
{
  "document_id": 40,
  "markdown": "# Borrador actualizado\n\nContenido revisado.",
  "if_match": "<etag-de-read_document>"
}
```

4. Volver a leer y comprobar `markdown`, `content_markdown`, `content_json` y
   un ETag nuevo. `content_markdown` se acepta como alias de compatibilidad,
   pero no puede enviarse con un valor distinto a `markdown`.
5. Repetir la edición con el ETag anterior: debe fallar con `STALE_VERSION` sin
   sobrescribir el cambio vigente.

Esta operación es una escritura reversible y no requiere confirmación. Borrar,
disolver o reemplazar evidencia sí conserva el flujo preview + confirm.

## Barrido de paridad por área

Para cada conector canónico, ejecutar `describe_capabilities` con una credencial
sin alcance y con otra limitada. La primera debe coincidir con `tools/list`; la
segunda sólo muestra herramientas autorizadas más `describe_capabilities`,
`confirm_action` y `cancel_action`.

| Área | Lectura mínima | Mutación mínima | Acción sensible a previsualizar |
|---|---|---|---|
| Operaciones | dashboard global | no aplica | no aplica |
| Comercial | cliente/propuesta/diagnóstico | actualizar una entidad reversible | envío o eliminación disponible en el catálogo |
| Proyectos | detalle e historial | actualizar datos o transición reversible | eliminación disponible en el catálogo |
| Documentos | leer Markdown y ETag | actualizar borrador con `if_match` | eliminar/disolver |
| Comunicaciones | hilo, cuerpo y adjuntos | actualizar borrador/default/template | enviar, reenviar o eliminar |
| Contenido | abrir blog/portafolio/QR/Linktree | editar borrador o metadata | publicar/eliminar |
| Tareas | detalle, comentarios y alertas | crear/editar/reordenar | eliminar |
| Libro contable | dashboard, previsión de cobro y movimientos | crear/editar movimiento o semáforo | liquidar/eliminar/export sensible cuando aplique |
| Cobros | cuenta, hosting y ciclos | actualizar configuración o registro | emitir/reintentar/eliminar |
| Tarjetas | extracto y transacciones | resolver alias o editar snapshot | finalizar/reabrir/eliminar |

Los adaptadores resuelven la misma ruta DRF del Panel mediante
`APIRequestFactory`, autentican el principal técnico y dejan que la vista,
serializer y servicio existentes decidan permisos, validación y transacción.
No se implementa un segundo CRUD con escrituras ORM paralelas.

### Libro contable: previsión manual de cobro

1. Invocar `get_receivables` sin argumentos. Debe listar únicamente ingresos
   esperados abiertos de la contabilidad de empresa, sin limitarse al año del
   dashboard, y devolver `summary.by_confidence` para verde (`high`), naranja
   (`medium`), rojo (`low`) y seleccionados sin clasificar.
2. Elegir un resultado abierto e invocar `update_income` con
   `collection_confidence: "high"`. Verificar que la respuesta conserva el
   valor anterior de `is_receivable_candidate` —no lo activa—, que sólo el nivel
   aparece como cambio en el historial y que se genera el aviso habitual.
3. Invocar `update_income` de forma explícita con
   `is_receivable_candidate: true` y volver a consultar `get_receivables`:
   `summary.high_total` debe sumar el `total_amount` original del registro, no
   sólo su saldo restante. Luego se puede retirar de la selección con
   `is_receivable_candidate: false`; el color se conserva como contexto
   histórico.
4. Casos negativos: intentar seleccionar un ingreso personal, líquido,
   perdido o completamente pagado debe fallar sin modificarlo. Al liquidar por
   completo un candidato, debe salir automáticamente de la selección activa.

### Comercial: visibilidad de los videos explicativos

1. Invocar `get_explainer_video_settings`: sin configuración previa devuelve
   `show_additional_modules_video` y `show_financing_video` en `true`.
2. Invocar `update_explainer_video_settings` con
   `{"show_additional_modules_video": false}`. La respuesta refleja el cambio,
   `GET /api/additional-modules/public/` pasa a `show_explainer_video: false`
   y el panel agenda el rebuild de la página pre-generada; repetir el mismo
   valor no agenda otro rebuild.
3. Crear un enlace con `create_additional_module_share` incluyendo
   `show_explainer_video: false` y luego invocar
   `update_additional_module_share` con su `share_uuid` y
   `{"show_explainer_video": true}`: la respuesta de administración refleja el
   valor, y el payload público del enlace sólo lo muestra si el interruptor del
   catálogo también está encendido. Idioma y selección siguen inmutables.
4. Casos negativos: `update_additional_module_share` sin el campo responde 400
   y no modifica el enlace; un valor no booleano en
   `update_explainer_video_settings` responde 400.

## Comunicaciones: guion por herramienta

Usar dos clientes, un proyecto de cada cliente, un documento markdown de cada
cliente y un superusuario. Conservar los IDs que devuelve cada paso.

`list_threads` y el endpoint del panel comparten
`communication_query_service.py`. Los argumentos escalares del conector se
normalizan como una selección de un valor y conservan su contrato; el REST puede
enviar valores repetidos o separados por coma para la selección múltiple del
panel. En ambos caminos, canal, dirección, estado del mensaje y fechas deben
coincidir en un mismo mensaje, no en mensajes distintos del mismo hilo. El
argumento `q` busca por título del hilo, cliente, nombre de proyecto, asunto o
contenido del mensaje en ambos caminos.

`CommunicationPanelPreference` queda excluido deliberadamente del conector:
sus campos personalizan la interfaz de una cuenta y no forman parte del registro
conversacional que MCP consulta o modifica.

### 1. `list_threads`

Lectura exitosa:

```json
{
  "client_id": 10,
  "project_id": 20,
  "status": "open",
  "channel": "email",
  "direction": "outgoing",
  "message_status": "draft",
  "reply_status": "unanswered",
  "date_from": "2026-08-01",
  "date_to": "2026-08-31",
  "q": "Portal Boreal",
  "order": "recent",
  "scope": "active",
  "page": 1,
  "page_size": 20
}
```

Verificar `results`, `count`, `page` y `num_pages`; cada fila debe incluir
cliente/proyecto, actividad, conteos y preview vigente. `reply_status` acepta
`answered` o `unanswered` y evalúa mensajes salientes enviados no anulados
mediante su relación explícita de respuesta. Repetir por separado con
`client_id`, con `project_id` y con `q` igual a una parte del nombre del proyecto
para probar los cortes estructurados y la búsqueda legible.

Errores: filtros, `order` o `scope` fuera de catálogo, fecha no ISO, página cero
e IDs no enteros deben producir `isError=true`. Una página
posterior al final puede normalizarse a la última página, como `Paginator`.

### 2. `get_thread`

```json
{"thread_id": 30}
```

Verificar mensajes cronológicos completos, estados, `reply_to`, documentos y
correcciones de fecha. Un ID inexistente, vacío, cero o no entero debe fallar sin
crear ni modificar registros.

### 3. `create_thread`

```json
{"client_id": 10, "project_id": 20, "title": "Aprobación de entrega"}
```

Verificar que nace `open`, vacío y atribuido al actor MCP. Casos de error:
cliente omitido/inexistente, título vacío, perfil no cliente y proyecto de otro
cliente. Ningún rechazo puede dejar un hilo parcial.

### 4. `update_thread`

```json
{"thread_id": 30, "title": "Aprobación final", "project_id": null}
```

Verificar que corrige sólo los campos enviados, conserva cliente e historial y
permite asociar o desasociar un proyecto del mismo cliente. Deben fallar: hilo
cerrado, proyecto ajeno, título vacío, ausencia de campos editables y cualquier
campo no declarado. Ningún rechazo puede producir una actualización parcial.

### 5–6. `close_thread` / `reopen_thread`

```json
{"thread_id": 30}
```

`close_thread` debe registrar estado, fecha y actor. Mientras el hilo está
cerrado, crear mensajes, editar su cabecera o confirmar un borrador enviado debe
fallar. `reopen_thread` revierte esa condición sin tocar archivo ni historial.
Cerrar uno ya cerrado o reabrir uno abierto debe ser un error explícito.

### 7–8. `archive_thread` / `unarchive_thread`

```json
{"thread_id": 30}
```

Archivar retira el hilo del `scope=active`, lo incorpora a `archived` y lo
mantiene en `all`; restaurar hace el movimiento inverso sin alterar `status`.
Una comunicación madre de proyecto o cliente no se puede archivar. Repetir la
misma transición debe fallar sin modificar fechas ni actor.

### 9. `create_message`

Saliente de correo con referencia documental:

```json
{
  "thread_id": 30,
  "channel": "email",
  "direction": "outgoing",
  "subject": "Acta de entrega",
  "content": "Adjunto el acta para aprobación.",
  "occurred_at": "2026-09-02T15:00:00Z",
  "document_ids": [40]
}
```

Debe quedar como `draft`: crear no equivale a enviar. Un mensaje entrante de
WhatsApp queda `received`, sin asunto. `reply_to_id` sólo acepta un mensaje
previo del mismo hilo y dirección opuesta. Deben fallar: hilo cerrado, email sin
asunto, WhatsApp con asunto, contenido vacío, documento de otro cliente,
documento inexistente, respuesta de otro hilo o de igual dirección. Cada fallo
debe dejar iguales los conteos de mensajes y referencias.

### 10. `update_message`

```json
{
  "message_id": 50,
  "subject": "Acta de entrega corregida",
  "content": "Texto corregido.",
  "document_ids": [40],
  "reply_to_id": null
}
```

Verificar que se conserva ID, hilo, canal y dirección, se reemplazan —no se
acumulan— documentos y queda una revisión append-only con el diff suministrado.
Sólo un borrador saliente activo es editable. Mensajes enviados, recibidos,
fallidos o anulados, documentos ajenos y respuestas de otro hilo deben fallar
sin cambiar el registro.

### 11. `delete_draft`

```json
{"message_id": 50}
```

Verificar eliminación física del borrador y retorno de `deleted`, `id` y
`thread_id`. Sólo aplica a borradores salientes activos; la evidencia enviada,
recibida, fallida o anulada debe preservarse y producir `isError=true`.

### 12. `mark_message_sent`

```json
{"message_id": 50, "occurred_at": "2026-09-02T15:05:00Z"}
```

Verificar transición `draft → sent`, fecha efectiva y actor. Repetir sin
`occurred_at` para conservar la fecha registrada. Deben fallar un mensaje
entrante, uno ya enviado, uno anulado, un hilo cerrado, un ID inexistente y una
fecha no ISO. Confirmar que no se creó `EmailLog` ni se invocó ningún proveedor:
la herramienta sólo registra el envío realizado por fuera.

### 13. `void_message`

```json
{"message_id": 51, "reason": "Registro duplicado"}
```

Verificar que el mensaje histórico permanece visible con fecha, motivo y actor
de anulación. Sólo se anulan mensajes enviados, recibidos o fallidos; un
borrador, una segunda anulación o un motivo vacío deben rechazarse.

### 14. `correct_message_date`

```json
{
  "message_id": 51,
  "occurred_at": "2026-09-01T18:30:00Z",
  "reason": "Corrección contra evidencia externa"
}
```

Verificar la nueva fecha y una corrección append-only con valor anterior, valor
nuevo, motivo y actor. Sólo aplica a mensajes históricos no anulados; borradores,
fecha idéntica, formato inválido o motivo vacío deben fallar sin crear auditoría.

## Documentos: eliminación recuperable de observaciones

Usar un documento markdown con dos observaciones, una pendiente enlazada a un
episodio **Solucionar bug** con `origin=note` y otra resuelta o descartada. Las
herramientas reutilizan el mismo servicio transaccional que el panel.

### 1. `delete_document_notes`

```json
{"document_id": 40, "note_ids": [70, 71]}
```

Verificar que una sola llamada elimina lógicamente toda la selección, devuelve
`deleted_note_ids` y no deja resultados parciales. Las observaciones salen de
`read_document`, de la lista activa y de los conteos. Si la selección contenía
la última pendiente de un episodio originado por observaciones, ese episodio se
cierra como `removed`; un estado manual nunca se cierra por esta regla.

Deben fallar sin modificar nada: selección vacía, IDs repetidos, observación de
otro documento, ID inexistente y observación ya eliminada. Se puede eliminar
una observación pendiente, resuelta o descartada; una copia enviada antes por
correo o mensaje permanece fuera del sistema.

### 2. `list_deleted_document_notes`

```json
{"document_id": 40}
```

Verificar que sólo devuelve la papelera recuperable con contenido, estado,
`deleted_at` y actor. La lectura normal del documento debe seguir ocultando esas
filas. El historial técnico de eliminación es distinto: registra actor y fecha,
pero no crea una copia del título o contenido.

### 3. `restore_document_note`

```json
{"document_id": 40, "note_id": 70}
```

Verificar que la observación vuelve al alcance activo. Si era pendiente y su
eliminación había cerrado el episodio enlazado, la restauración reabre o
reutiliza **Solucionar bug** y vuelve a enlazarla. Una incompatibilidad de
estados o un estado retirado debe revertir toda la operación y conservar la
observación en la papelera. Restaurar una fila activa o de otro documento debe
fallar de forma explícita.

## Documentos: hilos entre documentos

Usar tres documentos markdown activos en carpetas distintas —el punto del hilo
es que la historia cruza carpetas, clientes y proyectos— y un cuarto que ya
pertenezca a otro hilo. Las herramientas reutilizan `document_thread_service`,
el mismo servicio transaccional que el modal del panel.

### 1. `create_document_thread`

```json
{"title": "Etapa 2 · Conteo Diario",
 "items": [{"document_id": 138, "occurred_on": "2026-08-16"},
           {"document_id": 146, "occurred_on": "2026-08-24"}]}
```

Verificar que el hilo nace con los documentos ordenados **por fecha**, no por el
orden en que se enviaron, y que `occurred_on` omitido cae en `issue_date` o en
el día Bogotá de `created_at`. Sin `title`, el nombre es el del primer documento.

Deben fallar sin crear nada: un solo documento, un documento repetido, uno que
ya pertenece a otro hilo (el mensaje nombra el hilo dueño), una cuenta de cobro,
un documento archivado y una fecha que no sea `YYYY-MM-DD`.

### 2. `get_document_thread` y `list_document_threads`

```json
{"document_id": 146}
```

Verificar que un documento suelto responde `thread: null` —no un error— y que
`thread_id` abre el mismo hilo. En el listado, comprobar `document_count`,
`first_occurred_on`, `last_occurred_on`, `latest_item` y que `search` encuentra
el hilo tanto por su nombre como por el título de cualquiera de sus documentos.

### 3. `update_document_thread`

```json
{"thread_id": 4, "link": [{"document_id": 162, "occurred_on": "2026-08-27"}]}
```

**La verificación que importa**: los miembros no mencionados siguen ahí. Un
`link` agrega o re-fecha; `unlink_document_ids` retira sin borrar el documento.
La operación que dejaría el hilo con menos de dos documentos debe rechazarse y
el hilo quedar intacto — ésa es la diferencia con el PATCH del panel, que ahí sí
disuelve. Renombrar y mover miembros en la misma llamada es atómico: si el
nombre falla, la membresía tampoco cambia.

### 4. `dissolve_document_thread`

```json
{"thread_id": 4}
```

Verificar que los documentos sobreviven y quedan disponibles para otro hilo, que
la respuesta trae el hilo completo previo y `released_document_ids`, y que un
documento antes enlazado ya se puede eliminar (el `PROTECT` lo bloqueaba).

## Revalidación de conectores existentes

| Conector | Lectura que debe comprobarse | Escritura/acción que debe comprobarse | Error representativo |
|---|---|---|---|
| Blog | `get_blog_post` devuelve JSON bilingüe, fuentes, SEO, portada y LinkedIn | crear/editar conserva esos campos | post inexistente o payload incompleto |
| Documents | resumen/detalle y filtros muestran cliente, proyecto, estados, tags y sólo observaciones activas | crear/editar mantiene asociaciones; eliminar/restaurar observaciones reconcilia estados y papelera en una transacción | proyecto ajeno, archivado, selección de observaciones mezclada o restauración incompatible |
| Clients | métricas incluyen documentos, ingresos, hostings y comunicaciones | CRUD usa `proposal_client_service` | un hilo impide tratar/eliminar el cliente como huérfano |
| Communications | hilo completo incluye ciclo de vida, mensajes, documentos, correcciones y revisiones; listado separa activos/archivados | cabecera y ciclo del hilo más crear/editar/eliminar borrador, confirmar envío, anular y corregir fecha convergen en `communication_service` sin enviar por el canal | transición repetida, comunicación madre, mensaje no editable, proyecto/documento ajeno o respuesta de otro hilo |
| Tasks | detalle, comentarios y alertas reflejan el modelo actual | CRUD, archivo, orden y duplicación | comentario/alerta de otra tarea |
| Accounting | detalle incluye pagos, deducciones, cuenta de cobro, período de hosting y ciclo de vida de recurrentes | `settle_income`/`bulk_settle_incomes` crean pagos; las seis tools de recurrentes preparan duplicado, cambian estado, archivan/restauran, silencian avisos y aplican lote por el mismo servicio del panel | no esperado, repetido, excedido, ID perdido o intento de activar/silenciar un recurrente archivado |
| Diagnostics | detalle expone slug, expiración y cliente | update permite esos campos y usa el serializer actual | slug duplicado o cliente inválido |
| Proposals | detalle/template exponen metadata comercial completa, incluido `email_intro` | importación persiste el mensaje personalizado; reenvío permite editarlo; `update_proposal` con `technicalDocument` exige que cada ítem funcional quede referenciado en algún `linked_item_ids` | JSON incompleto, mensaje vacío al enviar/reenviar, transición inválida o detalle técnico sin trazar (`technical_item_coverage_incomplete`) |
| LinkedIn | estado de token/post y errores de publicación | borrador, programación, edición, borrado y publicación de texto | token ausente/expirado o post no publicable |

## Verificación automatizada

Desde `backend/`, con el virtualenv del clon principal y nunca con la suite
completa. Cada comando respeta el máximo de 20 tests; iniciar otro ciclo después
de tres comandos.

```bash
/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_operational_platform.py -q \
  -k 'default_token or panel_ or bearer_ or rotating_ or revoked_ or tools_list_exposes or sensitive_call'

/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_operational_platform.py -q \
  -k 'confirm_action or confirmation_cannot or signed_upload or temporary_output or operations_connector or tool_audit or modern_ or scoped_discovery'

/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_contracts.py -q -k 'all_registered or every_panel'
```

En el ciclo siguiente, ejecutar el resto de `test_mcp_contracts.py` en lotes,
`test_mcp_protocol.py`, las regresiones focales de Documentos, Comunicaciones,
Tareas y Contabilidad y los servicios afectados. No agrupar archivos si la
selección supera 20 casos.

Para cambios en observaciones de Documentos, agregar el archivo focal sin
superar 20 tests por ejecución:

```bash
/home/ryzepeck/webapps/projectapp/backend/venv/bin/python -m pytest \
  content/tests/views/test_mcp_documents.py::TestDocumentsMcpToolList \
  content/tests/views/test_mcp_documents.py::TestDocumentsMcpWorkflow -q
```

Luego ejecutar una regresión mínima de los handlers compartidos modificados y:

```bash
/home/ryzepeck/webapps/projectapp/backend/venv/bin/python manage.py check
/home/ryzepeck/webapps/projectapp/backend/venv/bin/python manage.py makemigrations --check --dry-run
python3 scripts/test_quality_gate.py --repo-root . \
  --report-path test-results/test-quality-audit-report.json
```

No ejecutar `manage.py migrate` desde un worktree: su `.env` enlazado apunta a
producción. La migración `content.0240_mcp_operational_platform` se valida con
el grafo y se aplica únicamente durante deploy. Crea credenciales, intents,
uploads y trazas ampliadas; copia cada token histórico a la credencial
`Default`, preserva la URL actual y siembra los conectores canónicos inactivos.
Su reverse es deliberadamente no destructivo.

Para la UI, ejecutar el unit test del store y el único spec E2E del flujo:

```bash
npm --prefix frontend test -- test/stores/mcps.test.js
E2E_PORT=3001 E2E_WORKERS=1 npm --prefix frontend run e2e -- \
  e2e/admin/admin-mcps.spec.js
```

## Contrato anti-deriva

Todo cambio futuro de modelo/serializer/servicio en un módulo expuesto debe, en
la misma entrega:

1. Revisar `MCP_MODEL_CONTRACTS` y clasificar cada campo agregado o cambiado.
2. Comparar handlers con la vista, serializer y servicio vigentes del panel.
3. Actualizar descripción, schema, filtros y payload real de cada tool afectada.
4. Agregar una prueba observable de éxito y otra de error cuando cambie una
   regla; actualizar este guion si cambia la operación manual.
5. Ejecutar los archivos MCP anteriores y la regresión compartida mínima.

`test_mcp_contracts.py` falla ante campos sin clasificar, nombres duplicados,
descripciones demasiado vagas o schemas que dejan de ser objetos. Esa falla es
una solicitud de revisión: nunca se resuelve ocultando el campo sin explicar por
qué queda fuera del MCP.

## Criterio de cierre

- Los 16 conectores aparecen en el registro y `tools/list` coincide con este
  inventario; los diez canónicos cubren las áreas operativas y los seis
  históricos permanecen compatibles.
- Comunicaciones expone 33 operaciones, incluidos preview, envío confirmado,
  adjuntos, templates y entregabilidad; sus rechazos dejan la base consistente.
- Los MCP existentes devuelven y aceptan los campos descritos en su contrato;
  Documentos expone 64 herramientas y conserva edición Markdown con ETag,
  papelera, observaciones, hilos, uploads y artefactos.
- Toda acción sensible exige intent ligado a credencial, confirma una sola vez
  y deja evidencia; toda credencial respeta alcance, expiración y revocación.
- No se alteraron tokens, prefijos, estados activos ni `last_used_at` de
  conectores existentes durante la migración; los nuevos quedan inactivos.
- Tests focales, regresión, Django check, migraciones sin drift y quality gate
  quedan verdes y anotados; el flujo `/panel/mcps` cubre inventario, riesgo,
  creación, edición, rotación, revocación, error y gate de superusuario.

## Ejecución de referencia — 2026-08-26

| Verificación | Resultado |
|---|---|
| Communications MCP | 15/15 tests verdes |
| Contrato de nueve conectores | 19/19 tests verdes |
| Paridad de módulos existentes | 17/17 tests verdes |
| Regresión compartida Propuestas/Contable + catálogos | 31/31 tests verdes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate de los tres archivos MCP nuevos | 91/100, 0 errores, 0 warnings |

El gate global local puntuó 97/100, pero no pudo ejecutar sus dos puentes AST de
frontend porque este worktree backend-only no instala `frontend/node_modules`
(`@babel/parser` ausente). No fue un hallazgo de los cambios MCP; el workflow de
CI, que instala las dependencias frontend, conserva la validación global final.

## Ejecución focal — 2026-08-31

| Verificación | Resultado |
|---|---|
| Edición MCP de borradores | 19/19 tests verdes |
| Servicio y auditoría de revisiones | 14/14 tests verdes |
| Regresión `tools/list` / creación / envío | 3/3 tests verdes |
| Contratos MCP | 20/20 tests verdes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate focal | 0 errores; warnings históricos no bloqueantes |

## Ejecución focal — 2026-09-02

| Verificación | Resultado |
|---|---|
| Acciones administrativas MCP | 20/20 tests verdes |
| Edición MCP de borradores | 19/19 tests verdes |
| Catálogo, creación, consulta y envío confirmado | 19/19 tests verdes |
| Contratos de campos y metadata (dos lotes) | 23/23 tests verdes |
| Paridad transversal de conectores | 17/17 tests verdes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate focal | 93/100, 0 errores, 0 junk; 1 warning de infraestructura (`ruff` ausente) |

El cambio es backend/MCP y no altera modelos, relaciones, reglas de fake data ni
un flujo humano del frontend; por eso no requiere refresh de datos ni cambios en
USER_FLOW_MAP/E2E. El CI, que instala su toolchain de lint, conserva la última
validación del warning local.

## Ejecución focal — 2026-09-02 (plataforma operativa)

| Verificación | Resultado |
|---|---|
| Fundamento de credenciales, confirmación, uploads, actor y auditoría | 25 casos verdes |
| Protocolo MCP moderno + compatibilidad heredada | 14/14 tests verdes |
| Resolución de rutas y métodos de adaptadores | 12/12 tests verdes |
| Edición documental y validación de contenido binario | 3 regresiones nuevas verdes |
| Store de administración MCP | 8/8 tests verdes |
| Flujo `/panel/mcps` | 10/10 E2E verdes en servidor local aislado |
| Build Nuxt | aprobado; warnings preexistentes no bloqueantes |
| Django system check | 0 issues |
| `makemigrations --check --dry-run` | sin cambios detectados |
| Quality gate del lote QA | 0 errores; `ruff` ausente como warning ambiental conocido |

El mapa global quedó en 304 flows cubiertos, 34 parciales, 0 faltantes y 33
exentos; `admin-mcps` cubre `display`, `success`, `error` y `failure`. El único
`junk-only`, `platform-hosting-subscription`, es un draft preexistente ajeno a
esta entrega y requiere validación live antes de retirar su marcador. El
Arquitecto, el Verificador y el Auditor aprobaron el corpus MCP; el Auditor no
dejó candidatos `DELETE`, `MERGE` ni `REWRITE`.

La migración conserva tokens, prefijos, activación y `last_used_at` de los
conectores existentes. Los conectores canónicos nuevos nacen inactivos. La
rotación de las credenciales compartidas entregadas al inicio se realiza sólo
después de merge, migración y verificación del corte; nunca dentro de esta
corrida de desarrollo.

## Ejecución focal — 2026-09-05 (detalle seguro de proyectos)

| Verificación | Resultado |
|---|---|
| Contrato de campos del conector Proyectos | 1/1 verde |
| Modelos `ProjectAdminAccess` / `ProjectAccessNote` | todos los campos excluidos con motivo explícito |
| URLs y campos legacy de acceso en `Project` | excluidos del contrato MCP con motivo explícito |
| Rotación o uso de credenciales MCP | no ejecutado; fuera del alcance de la entrega |

La superficie humana nueva usa APIs staff/JWT dedicadas y no añade tools MCP.

## Ejecución focal — 2026-09-14 (videos explicativos y Programa de Alianza)

| Verificación | Resultado |
|---|---|
| Contrato de campos del conector Comercial (`ExplainerVideoSettings`, `show_explainer_video` del enlace) | verde |
| Adaptadores `get/update_explainer_video_settings` y `update_additional_module_share` resuelven a vistas con el método declarado | verde |
| Descripciones de `get_financing_program` / `render_financing_program_pdf` | nombran el Programa de Alianza; comparten las ocho condiciones, incluida la exclusividad conceptual de Project App. sólo a cinco años. Los nombres de las tools no cambian |
| Invocación en vivo contra producción | no ejecutada; fuera del alcance de la entrega |

El conector Comercial pasa de 132 a 135 herramientas. La descripción del
conector sembrada en BD por la migración 0240 se conserva sin migración de
datos.

## Revisión de formalización — 2026-09-19

`ProposalFormalization` y `ProposalFormalizationFile` clasifican todos sus
campos como excluidos del MCP: son preparaciones privadas de 24 horas,
revisadas y enviadas por el administrador que las creó desde Documentos.
El conector Comercial conserva sus herramientas actuales; no expone el HTML,
destinatarios, rutas privadas ni el envío de estas preparaciones. La regresión
focal verifica los contratos de campos de `proposals` y `commercial` y sus
adaptadores, sin invocar conectores contra producción.

## Agregados de proyectos anidados — 2026-09-22

`get_client` y `retrieve-proposal-client` reutilizan `ProjectListSerializer`
con instancias sin las anotaciones privadas de los listados de Plataforma.
Los getters conservan sus fallbacks: propuesta de la primera fase (o vínculo
legacy por entregable), bugs abiertos, cambios pendientes, inversión total y
próximo pago del hosting activo. La ausencia de propuesta o suscripción sigue
siendo `null`; los conteos vacíos permanecen en cero.

La optimización no añade campos de modelo, herramientas ni cambios de schema
MCP; las clasificaciones de `content/mcp/contracts.py` permanecen vigentes.
La regresión focal lee un proyecto real anidado por ambos consumidores y
comprueba valores concretos, además de los contratos y las operaciones MCP de
crear, actualizar y consultar un cliente inexistente. Se ejecuta sólo con
`projectapp.settings_test`, sin conectores ni datos del servicio en producción.

### Linktrees — marca personalizada (2026-09-21)

`create_linktree` y `update_linktree` aceptan `background_color`, `accent_color`,
`text_color`, `muted_color`, `button_text_color` (hexadecimal de seis dígitos) y
`font_family` (nombre de Google Fonts, sin URL ni CSS). Los serializers compartidos
validan los datos del panel y MCP. `upload_linktree_logo` usa `asset_id` para un
JPG/PNG/WebP real de hasta 5 MB; `remove_linktree_logo` lo elimina. El logo es
independiente del avatar. Comprobar lectura pública tras actualizar y rechazo de
color/CSS inválidos o archivo falso; no modificar tarjetas reales al validar.

### Linktrees asociados a proyectos

`create_linktree`/`update_linktree` aceptan `data.project` (ID de Project) o null.
Verificar lectura de la relación, desvinculación y rechazo de IDs inexistentes.
Las mismas reglas corren en el serializer del panel. `ProjectBrandAsset` queda
excluido explícitamente del conector: documentos privados disponibles sólo en
el panel, sin URLs públicas ni descargas vía MCP. Prueba focal:
`content/tests/views/test_mcp_linktree_branding.py::test_mcp_links_and_unlinks_project`.

### Linktrees — plantillas HTML Nivel 2 (2026-09-23)

Las plantillas HTML se administran desde el panel con sesión y CSRF. Ninguna
actualización genérica de Linktree (`update_linktree`) puede cargar, validar ni
activar HTML: `Linktree.active_template_version` es de sólo lectura y cambia
únicamente con las herramientas de Nivel 3 descritas a continuación.

El contrato de branding existente sigue disponible. La página pública sólo
anuncia `template_url` cuando la versión pertenece al perfil, fue publicada y
tiene validación válida. Al cambiar datos de una tarjeta con plantilla hay que
validar una nueva instantánea y publicarla (panel o MCP).

Comprobaciones focalizadas: contrato de clasificación de campos en
`content/tests/views/test_mcp_contracts.py` y aislamiento/publicación en
`content/tests/views/test_linktree_template_views.py`. Operación y despliegue:
[Plantillas HTML de Linktree](LINKTREE_HTML_TEMPLATES.md).

### Linktrees — plantillas HTML Nivel 3 por MCP (2026-09-23)

El conector `content` expone en `backend/content/mcp/linktree_template_tools.py`
el ciclo completo de una plantilla, reutilizando el lector de paquetes, la
creación de instantáneas, la validación en Chromium (Huey) y la guarda de
publicación del panel. Una conversación nunca salta la validación ni activa una
instantánea sin `status=valid` y perfil vigente.

| Herramienta | Riesgo | Qué hace |
| --- | --- | --- |
| `get_linktree_template_contract` | read | Contrato de autoría (archivos, manifest, variables Mustache, enlaces, acciones, iconos, reglas HTML/CSS, ejemplo). Con `linktree_id` devuelve las variables reales de la tarjeta: nombre, rol, bio, iniciales, foto/logo disponibles, enlaces con etiqueta/URL/icono/tipo, botones sin destino, acciones disponibles, contacto, colores y fuente. `icon_query` busca nombres Lucide. |
| `list_linktree_templates` | read | Biblioteca (propias + compartidas por cliente) y versiones con estado, errores, capturas y versión activa. |
| `get_linktree_template` | read | Fuente del paquete (manifest, html, css, avisos, metadatos de imágenes) para iterar un diseño. |
| `get_linktree_template_version` | read | Estado `pending/valid/invalid`, reporte completo, overrides, `profile_current` y `next_step`. |
| `upload_linktree_template` | write | `files[]` con `path` y `content` (texto; manifest.json admite objeto), `base64` o `asset_id`. Crea la plantilla y una candidata `pending`. |
| `validate_linktree_template` | write | Nueva candidata con datos actuales desde `template_id` o restaurando `version_id`. |
| `preview_linktree_template` | read | Documento HTML de vista previa (firmado por una hora) y capturas 320/375/430 como artefactos temporales descargables. |
| `override_linktree_template_asset` | write | Reemplaza (`asset_id`/`base64`) o restablece (`reset`) una imagen de `editable_assets`; crea candidata nueva. |
| `publish_linktree_template` | sensitive | Publica una versión válida; responde con `confirmation_id` y se ejecuta con `confirm_action`. |
| `reset_linktree_template` | write | Vuelve al tema básico conservando el historial. |
| `share_linktree_template` | write | Comparte una plantilla propia con el cliente del proyecto vinculado. |
| `get_linktree_template_clicks` | read | Clics agregados por enlace y día de una versión publicada (sin IPs ni visitantes). |
| `list_linktree_assets` | read | Biblioteca de imágenes propia del Linktree: clave, alt, URL, dimensiones y marcado de uso. |
| `upload_linktree_asset` | write | Sube o reemplaza una imagen por clave (`base64` + `filename` o `asset_id`) y devuelve la URL para usarla en el HTML/CSS. |
| `delete_linktree_asset` | sensitive | Elimina una imagen de la biblioteca tras `confirm_action`; las versiones publicadas conservan su copia. |

Biblioteca de imágenes (`content.LinktreeAsset`): las plantillas pueden pegar la URL
devuelta (`src="…"`, `url(…)`) o usar `data-asset="clave"`/`asset(clave)`; al subir
el paquete la URL se normaliza a la clave y `manifest.library_assets` (administrado
por el servidor) registra las claves usadas. Cada candidata copia la imagen vigente
de la biblioteca; una clave faltante bloquea la candidata con
`missing_library_asset` y una clave repetida entre paquete y biblioteca se rechaza
con `library_key_clash`. Los archivos se conservan mientras alguna versión los
referencie. El tema básico (colores y fuente del editor) sigue existiendo para las
tarjetas sin plantilla publicada; el contrato lo indica como no aplicable al HTML.

Reglas verificadas: una sola validación en curso por tarjeta (código
`validation_pending`); paquetes rechazados informan archivo, línea y código sin
dejar plantilla ni versión; `template_id` ajeno responde `NOT_FOUND`;
`confirm_action` sobre una versión `invalid` responde `not_validated`; los
`asset_id` consumidos quedan marcados como usados. Contratos: `LinktreeTemplate`
y `LinktreeTemplateVersion` pasan a lectura (más `is_shared` escribible) y
`assets`/`profile_digest` siguen excluidos con motivo.

Prueba focal: `content/tests/views/test_mcp_linktree_templates.py` (17 casos,
Chromium sustituido por `queue_validation` neutralizado),
`content/tests/views/test_mcp_linktree_assets.py`,
`content/tests/services/test_linktree_asset_library.py`,
`content/tests/views/test_linktree_asset_views.py` más
`test_mcp_contracts.py`, `test_mcp_linktree_branding.py` y
`test_mcp_parity_refresh.py`. En producción la validación real corre en Huey; el
worker debe tener Chromium instalado (ver guía de plantillas).


### Documentos de propuestas — copia Markdown

`ProposalDocument` y su snapshot `content_markdown` quedan explícitamente
excluidos del contrato MCP: son archivos administrados por sesión del panel.
La exportación no agrega herramientas MCP ni permite editar la evidencia del
contrato a través de `contract_params`. Revisar el contrato de campos al añadir
cualquier campo nuevo a este modelo.

### Carpetas de Comunicaciones

Validar `list_folders`, `create_folder`, `update_folder`, `delete_folder` con un perfil de cliente y proyecto opcional. Rechazar ciclos, cambio de contexto y eliminación con hilos archivados. `create_thread`/`update_thread` reciben `folder_id`; null retira la ubicación, una comunicación madre lo rechaza. `list_threads` admite `folder=<id>|none`; con `q`, busca todas las carpetas del contexto. Una actualización exclusivamente organizativa funciona con hilo cerrado. Los contratos incluyen `CommunicationFolder` y `CommunicationThread.folder`; los servicios son los mismos del panel.
