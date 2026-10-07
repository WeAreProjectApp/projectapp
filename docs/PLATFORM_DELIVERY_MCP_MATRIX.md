# Platform: paridad administrativa de entregas por MCP

La interfaz se abre en `/platform/projects/{id}/delivery`, con controles
administrativos de contratos, alcances, importación, firma y publicación.
El conector **Gestor de la plataforma** (`projects`) incluye la autoría y administración de la jerarquía
proyecto → contrato/otrosí → alcance → fase de ejecución → etapa → requerimiento.
Las operaciones invocan `accounts.services.delivery_workflow` y
`accounts.services.delivery_authoring`, igual que las vistas JWT de Platform.
Las fases de ejecución son distintas de las fases
comerciales de hosting; su vínculo es de trazabilidad y no emite cargos.

## Matriz acción de interfaz → herramienta

Los nombres entre llaves indican seis herramientas concretas, una por entidad:
`contract`, `amendment`, `scope`, `phase`, `stage` y `requirement`.

| Acción administrativa en Platform | Herramienta de Proyectos | Regla compartida / evidencia |
| --- | --- | --- |
| Consultar el seguimiento y la versión del espacio | `get_delivery_overview` | Incluye contratos y otrosíes, alcances y su jerarquía, conformidades y respuestas autorizadas. |
| Abrir un elemento del seguimiento | `get_delivery_{entidad}` | Solo obtiene el elemento dentro de la jerarquía del proyecto indicado. |
| Crear contrato, otrosí, alcance, fase, etapa o requerimiento | `create_delivery_{entidad}` | Borrador; valida propiedad, vínculo contractual y claves estables. |
| Editar un elemento | `update_delivery_{entidad}` | Requiere `expected_version`; rechaza contenido aprobado o evidencia contractual congelada. |
| Eliminar un elemento permitido | `delete_delivery_{entidad}` | Confirmación MCP; nunca elimina evidencia publicada/aprobada. |
| Consultar fuentes disponibles y esquemas JSON | `get_delivery_authoring_contract` | Opciones sin textos y sin selección automática de contrato; esquemas de guías v1/v2 y respuesta v2. |
| Preparar el prompt para crear guías | `create_delivery_guide_prompt` | Contrato explícito, otrosíes y fuentes elegidas; captura inmutable con fragmentos, localizadores, hashes y plantilla v2 citada. |
| Preparar una respuesta de etapa | `create_delivery_reply_prompt` | Etapa publicada; deriva su contrato/alcance y captura las fuentes elegidas y conversación pública, sin notas internas. |
| Consultar las preparaciones anteriores | `list_delivery_prompt_contexts` | Hasta cincuenta capturas del proyecto, sin cargar el texto de las fuentes. |
| Reabrir una preparación retenida | `get_delivery_prompt_context` | Contexto del proyecto indicado; conserva prompt, fuentes y conversación capturados aunque el origen cambie. |
| Descargar la copia usada al preparar un prompt | `download_delivery_prompt_source` | `context_id` y `source_key`; bytes exactos y formato original como artefacto privado temporal de la credencial. |
| Previsualizar JSON de una respuesta | `preview_delivery_reply` | Lectura sin compartir: valida citas/localizadores, clasificación e integridad del contexto. Fuentes incompletas exigen alcance indeterminado. |
| Previsualizar una importación JSON | `preview_delivery_import` | Valida v1 manual o v2 con contexto y citas, y su impacto sin guardar. |
| Aplicar una importación JSON revisada | `apply_delivery_import` | Confirmación, versión vigente, transacción completa e idempotencia; no importa firmas ni decisiones. |
| Publicar una etapa o abrir otra ronda de pendientes | `publish_delivery_stage` | Confirmación; exige contrato/otrosí firmado y guía completa. Conserva requerimientos aprobados. |
| Constatar un PDF firmado fuera de Platform | `attest_external_delivery_signature` | Confirmación; `asset_id` PDF completo de la misma credencial, máximo 10 MB, firmante, fecha y declaración administrativa. |
| Registrar una aprobación previa explícita del cliente | `record_external_delivery_approval` | Confirmación; requiere `client_statement: true`, transcripción entrante y decisión `approved`. Usa un mensaje entrante recibido del mismo cliente/proyecto, o evidencia documental con revisor original, fecha, canal y referencia externa. Registra actor administrativo y `is_external`, sin atribuirle una revisión nueva al cliente. |
| Preparar la constancia por correo de una etapa aprobada | `prepare_delivery_stage_closure_email` | Etapa publicada y completamente aprobada; conserva destinatario, cuerpo, historia pública hasta el cierre y adjuntos opcionales. No envía. |
| Consultar el historial de constancias | `list_delivery_stage_closure_emails` | Preparaciones e intentos del administrador y su credencial; documentos públicos seleccionables con su ronda y hash. |
| Revisar una copia preparada | `get_delivery_stage_closure_email` | Vista exacta, estado e historia conservados; no publica ni envía. |
| Descargar un adjunto de la constancia | `download_delivery_stage_closure_email_attachment` | Bytes privados exactos por `preparation_id` y `file_id`; artefacto temporal limitado a esa credencial. |
| Enviar manualmente la constancia revisada | `send_delivery_stage_closure_email` | Confirmación sensible del contenido exacto y `human_reviewed: true`; captura duradera antes de SMTP y un solo intento por preparación. |
| Preparar un reenvío explícito | `prepare_delivery_stage_closure_email_resend` | Nueva copia ligada a la anterior, con el mismo cuerpo y archivos; requiere otra revisión y confirmación para enviar. |
| Elegir la comunicación entrante que respalda una conformidad | `list_delivery_approval_evidence` | Solo mensajes recibidos, no anulados y del mismo cliente/proyecto; el servicio comprueba la cita al guardar. |
| Responder un reporte o una revisión | `add_delivery_message` | Mensaje manual, autoría real y documentos opcionales. Una respuesta citada exige `context_id`, `source_references`, `classifications` y `human_reviewed: true`; rechaza observaciones cambiadas desde la captura. |
| Elegir un documento del proyecto | `list_delivery_document_options` | Propiedad del cliente/proyecto; no admite una fuente ajena. |
| Consultar documentos de un nivel | `list_delivery_documents` | Niveles: proyecto, contrato, otrosí, alcance, fase, etapa y requerimiento. |
| Abrir una referencia documental | `get_delivery_document` | Solo documentos asociados al proyecto indicado, con referencia de publicación y descarga autorizada. |
| Asociar o retirar un documento | `link_delivery_document` / `unlink_delivery_document` | Versión vigente y mismas reglas de congelación y publicación heredada. |
| Descargar el PDF documental | `download_delivery_document_pdf` | `link_id`; usa la autorización y evidencia congelada de Platform y genera un artefacto temporal de la credencial MCP. |
| Descargar el respaldo de una conformidad registrada | `download_delivery_document_pdf` | `review_id` y `evidence_id`, excluyendo `link_id`; descarga la copia privada exacta del respaldo, aunque su documento editorial cambie después. |
| Consultar el contrato/otrosí antes de publicar etapas | `download_delivery_contract_pdf` | Independiente de la publicación de etapas; su lectura no acredita firma. |
| Adjuntar el PDF externo | `begin_upload` → `upload_asset_chunk` → `complete_upload` | Infraestructura existente: MIME, integridad SHA-256, tamaño, expiración y aislamiento por conector/credencial. |
| Revisar/confirmar/cancelar una acción sensible | `confirm_action` / `cancel_action` | Intención ligada a la credencial; la versión del espacio se vuelve a comprobar antes de ejecutar. |

Las acciones de aprobación, objeción o rechazo de una revisión **actual del
cliente** pertenecen al API autenticado del cliente. No existe una herramienta
administrativa que suplante ese actor. El registro histórico exige evidencia
explícita y mantiene su procedencia externa.

## Autoría con fuentes elegidas y respuesta revisada

El catálogo implementado contiene **52 herramientas de entrega y la descarga de fuente contractual**. Los contextos
se crean y se consultan; no tienen CRUD editorial ni permiten sustituir las
copias retenidas. Crear un contexto exige `expected_version` y `request_id`,
pero no incrementa la versión del espacio ni publica etapas. Repetir la misma
selección con el mismo identificador devuelve la captura anterior.

Cada fuente adicional indica exactamente `document_id` o `proposal_document_id`,
su rol `contractual_annex`/`reference` y una nota de aplicabilidad. Una referencia
de otro contrato del mismo proyecto debe elegirse expresamente como material no
normativo. Asociar un anexo, conocer su versión o comprobar una cita **no acredita
su incorporación jurídica ni una interpretación contractual**.

Guías v2 usan `schema_version: 2`, `context_id` y `source_references` en cada
requerimiento. Las citas contienen `source_key`, `locator` y `quote` y se
comprueban contra la copia retenida, no contra el documento actual. V1 permanece
disponible para guías manuales y no permite reemplazar guías ya trazadas. El CRUD
de requerimientos conserva la procedencia; cambiar contenido trazado exige
reenviar el contexto y las citas válidas. Las conformidades siguen congeladas.
El fundamento debe citar el contrato o un otrosí seleccionado; un anexo puede
complementar esas citas y nunca sustituirlas por sí solo.

La respuesta v2 contiene `response_text` y solicitudes clasificadas como
`inside_scope`, `outside_scope` o `indeterminate`, con fundamento y citas.
Fuentes faltantes, lectura parcial o incertidumbre impiden conclusiones
definitivas dentro o fuera del alcance. Previsualizar no comparte el texto. El administrador
debe revisarlo y ejecutar `add_delivery_message` de forma explícita; Platform no
ejecuta un modelo ni envía correo desde este flujo.

## Contrato de escritura y documentos

- `project_id` identifica siempre el proyecto; las referencias ajenas fallan.
- Leer `version` mediante `get_delivery_overview` y reenviarla como
  `expected_version`. Un espacio cambiado se rechaza con `CONFLICT`; una
  confirmación contra una vista previa anterior falla con `STALE_VERSION`.
- Usar un `request_id` estable para importación, publicación, respuestas,
  constancias y aprobaciones externas. Reintentar una confirmación ejecutada
  devuelve su resultado y no repite la operación.
- Los CRUD reciben `data` con los campos editoriales publicados por su esquema.
  No admiten estados, versión interna, firma ni decisión arbitraria.
- En requerimientos, `data.context_id` y `data.source_references` deben conservar
  la procedencia validada. En mensajes, `classifications` corresponde al campo
  persistido `reply_classifications`; el actor siempre procede de la credencial.
- Los documentos de etapas/requerimientos heredan su publicación en **lista,
  detalle, PDF y enlace directo** del cliente. Las notas internas permanecen
  administrativas. Consultar un contrato habilitado para firma no publica etapas.
- Las descargas MCP usan los servicios autorizados de PDF y artefactos temporales.
  Los campos de almacenamiento privado no se exponen. La publicación preserva
  el documento utilizado aunque la fuente editorial cambie después.
- La revisión conserva `evidence_document_ids` y entrega `evidence_documents`
  con títulos, hashes y rutas autorizadas. La misma herramienta de PDF acepta
  **solo** `link_id` o el par `review_id`/`evidence_id`; nunca ambos. El respaldo
  de la aprobación se conserva en una copia privada independiente.
- La metadata de firma distingue `portal` y `external` y conserva los hashes de
  origen y evidencia. MCP no expone las capturas de IP ni navegador de la firma;
  esos datos permanecen en la evidencia privada de Platform.
- Eliminar un documento o PDF de propuesta usado como fuente devuelve
  `document_used_in_delivery` con conflicto 409 y conserva su original.
  La protección se resuelve antes de borrar un archivo. Las fuentes retenidas
  no pueden retirarse para evadir la inmutabilidad de la captura.
- Los contextos y sus fuentes están excluidos de la creación automática de
  ejemplos. Solo una selección administrativa explícita los crea; su retirada
  en datos de prueba pertenece al reset autorizado de desarrollo.

## Evidencia de implementación y verificación

- Catálogo y adaptadores: `backend/content/mcp/delivery_tools.py`; incorporación
  al conector: `backend/content/mcp/operation_catalogs.py`.
- Revisión explícita de todos los campos: `DELIVERY_CONTRACTS` en
  `backend/content/mcp/contracts.py`, incluidas exclusiones de rutas privadas y
  recibos internos de idempotencia.
- Pruebas reales del transporte y servicios: `test_mcp_delivery.py`, con datos
  aislados, creación de las seis entidades, edición, importación,
  confirmaciones, firma, respuestas y errores de propiedad/versión/congelación.
- Validaciones documentales, permisos, metadata y cobertura de herramientas:
  `test_mcp_delivery_contracts.py` y el contrato existente `test_mcp_contracts.py`
  para el conector `projects`.
- Guardas de firma y datos privados: `test_mcp_delivery_guards.py` verifica que
  un contrato firmado no cambia de título, que una constancia externa no puede
  presentarse como firma de Portal y que la metadata omite la captura privada.
  También comprueba el PDF exacto del respaldo de revisión después de editar la
  fuente, su pertenencia al proyecto y el selector inequívoco del origen del PDF.
- Autoría seleccionada y respuestas revisadas: `test_mcp_delivery_authoring.py`
  prueba el transporte de los seis nuevos controles, la retención de fuentes,
  citas verificables, faltantes, lectura parcial, aislamiento por proyecto y
  revisión humana obligatoria antes de compartir un borrador.
- Retención del original en el panel: `test_delivery_source_deletion.py` cubre
  referencias/anexos de `Document` y `ProposalDocument` y la eliminación válida
  de archivos que no sustentan una captura.
- Constancias manuales de cierre: `test_mcp_delivery_closure_email.py` verifica
  preparación y descarga privada, propiedad del actor/credencial, confirmación
  sensible, hash/versión/revisión humana, captura anterior al transporte,
  idempotencia y reenvío explícito. Las pruebas usan correo en memoria.

La existencia de esta matriz describe la cobertura del incremento. Los resultados
ejecutados se registran en `MCP_VALIDATION_RUNBOOK.md`; no se validan conectores ni
se modifican datos reales de producción durante las pruebas.

## Evidencia privada de correo

Las preparaciones usan `DeliveryEvidenceEmail`, `DeliveryEvidenceEmailFile` y
`DeliveryEvidenceEmailAttempt`; quedan excluidas de CRUD y generación automática.
Los adjuntos del gateway optan por almacenamiento privado sin cambiar los
correos históricos ni introducir un transportador adicional. Captura fallida
impide SMTP y limpia los archivos nuevos. El estado desconocido o enviando no
provoca un reintento automático. La operación explícita de reenvío conserva el
vínculo con la copia y el snapshot anteriores.

## Recursos y modelo de datos

El mismo conector conserva proyectos, estados, fases comerciales, historial,
entregas, ideas, permisos de consulta, cobros y tickets. Clientes y Propuestas
conservan sus conectores propios. La etiqueta no cambia el slug, las credenciales,
la activación ni los permisos existentes. La versión compatible es 2.1.0.

| Acción | Herramientas |
| --- | --- |
| Consultar recursos | `list_project_resources`, `get_project_resource` |
| Crear o editar | `create_project_resource`, `update_project_resource` |
| Archivar o restaurar | `archive_project_resource`, `restore_project_resource` |
| Incorporar una versión | `upload_project_resource_version` |
| Consultar o adjuntar archivos | `list_project_resource_attachments`, `upload_project_resource_attachment` |
| Administrar carpetas | `list_project_resource_folders`, `create_project_resource_folder`, `update_project_resource_folder`, `delete_project_resource_folder` |
| Archivos del cliente | `list_project_resource_client_files`, `upload_project_resource_client_file` |
| Descargar bytes exactos | `download_project_resource_file` |
| Consultar el modelo y su plantilla | `get_project_data_model`, `get_project_data_model_template` |
| Revisar e importar entidades | `preview_project_data_model`, `import_project_data_model` |

Los recursos conservan el modelo existente `Deliverable`; archivar no elimina
sus archivos ni versiones. Eliminar una carpeta conserva la operación vigente de
Platform: elimina esa carpeta y sus registros dependientes. Los adaptadores no
atribuyen una carga administrativa al cliente. REST y MCP usan
`accounts.services.platform_resources` y `platform_data_model`.

Las escrituras MCP requieren `expected_version` y `request_id`, y pasan por
confirmación antes de cambiar contenido compartido. La vista previa conserva la
selección, el propietario y la metadata del archivo. Al ejecutar se revalida el
propietario dentro del bloqueo del proyecto. Los recibos reutilizan
`DeliveryWorkspace` y `DeliveryOperation`, con dominio de operación y huella que
incluye actor, credencial y propietario; no existe otro contador o tabla de
reintentos. Las consultas devuelven `version`, `project_id` y `result`.

Los archivos se cargan mediante assets propios. PDF conserva las reglas de
categoría y los archivos del cliente tienen máximo 15 MB. Diseños admite ZIP
solamente en `projects`, sin extracción: se comprueba estructura, cantidad,
rutas, ausencia de cifrado y tamaño descomprimido. Los demás conectores no
adquieren ese formato. La respuesta conversacional omite `file_url`; descargar
requiere el recurso y, para versiones/adjuntos/archivos del cliente, el tipo y su
`file_id`. El resultado es un artefacto temporal ligado a la credencial.

Esta adaptación no certifica que el servidor haya retirado las URLs históricas
públicas. Su cierre pertenece a la ronda de privacidad y al deploy verificado.

## Avisos operativos de entrega

`list_delivery_notification_events` y `get_delivery_notification_event` consultan
el estado y sus intentos. `preview_delivery_notification_retry` retorna la copia
y `preview_sha256` sin SMTP. `retry_delivery_notification_event` requiere esa
huella, versión y `request_id`; la confirmación es sensible y duradera.

Los cuatro adaptadores llaman a `accounts.services.delivery_notifications`.
El servicio administra el bloqueo, destinatario vigente, claim anterior al envío
y reintentos; el adaptador no implementa otro gateway. Solo un fallo confirmado
permite reintento. `sending` y `unknown` no se reintentan automáticamente.
Las respuestas omiten HTML, secretos y rutas privadas. La integración de ese
servicio y sus migraciones precede a la validación combinada de los avisos.

## Fuente del paquete aprobado y verificación focal

`create_delivery_contract` y `create_delivery_amendment` aceptan
`data.approval_file_id`, exclusivamente frente a `document_id` o
`proposal_document_id`. El servicio compartido exige pertenencia al proyecto y
cliente y coincidencia con el manifest confirmado. El registro empieza privado
y sin firma. El conector no transforma ese cierre administrativo en aceptación,
firma o revisión del cliente.

`download_delivery_contract_source` recibe `project_id`, `kind` y `node_id`.
Conserva el formato original del archivo confirmado; cuando consta evidencia
firmada, devuelve ese PDF exacto. Usa la autorización y comprobación de hash del
servicio compartido y produce un artefacto temporal de la credencial.

El reintento de un aviso usa **la versión del evento**, obtenida en su detalle,
no la versión general del espacio de entrega. La confirmación conserva la huella
del DTO del aviso y el servicio vuelve a comprobar el manifest bajo bloqueo.
Un UUID malformado se rechaza antes de consultar o crear una intención.

Verificación local de esta entrega: 18 casos de recursos MCP y 10 regresiones
REST con migraciones reales de test; cuatro comprobaciones del contrato MCP;
13 casos de integración de fuente, avisos, archivo y campos con schema de test
creado por ORM (`--nomigrations`). El gate focal de los tres archivos nuevos
terminó en 100/100, sin errores ni advertencias. La revisión combinada, MySQL y
el CI remoto pertenecen al cierre del PR y no se presumen por esos resultados.

La compatibilidad de carpetas conserva también la edición/eliminación
administrativa dentro de un recurso archivado; el cliente sigue sin poder
consultarlo. Crear carpetas o subir archivos a un recurso archivado mantiene el
rechazo existente. Una prueba MCP y cinco regresiones REST verificaron este
límite en el schema de test aislado.

## Límite de rol entre REST y MCP

El acceso REST de recursos y modelo de datos conserva el rol administrativo de
Platform y la propiedad del proyecto. Marcar una cuenta de cliente como staff
no habilita lecturas de otro proyecto, archivos archivados ni escrituras
administrativas. El servicio compartido recibe el Request real desde las vistas;
ese contexto no es un campo del payload. MCP conserva su principal técnico sin
perfil simulado y exige contexto del conector `projects`, actor y credencial
coincidentes y una credencial utilizable. No se modifican los permisos globales
de entrega ni los roles del proyecto.

Doce escenarios negativos de REST/servicio y comprobaciones positivas del
principal MCP verifican este límite. El archivo de pruebas es
`accounts/tests/test_platform_resource_role_boundary.py`.

## Confirmación de efectos públicos (S2)

`add_delivery_message`, crear/editar contrato u otrosí, asociar/retirar un
documento y evaluar/comentar/evaluar en lote tickets requieren una confirmación
cuando cambian lo que ve el cliente. Notas internas y borradores privados se
ejecutan directamente. Un estado público de ticket sigue requiriendo revisión
aunque su nota sea interna; ocultar contenido ya visible también es público.

La vista previa identifica al cliente por id y correo, muestra la selección
exacta y conserva las versiones del espacio y los tickets. Incluye las fuentes
canónicas y sus hashes. La ejecución vuelve a verificar la huella bajo bloqueo
del proyecto, destinatario y documentos antes de llamar al servicio existente;
un cambio de dueño, correo, cuerpo, fuente o versión exige una vista previa nueva.
No se crean permisos, firmas, decisiones del cliente ni un contador alternativo.

Para contratos firmados, manda la copia privada C1 y no el borrador editable.
En documentos se respeta la precedencia del portal: copia publicada, archivo
generado y finalmente contenido que se renderiza al descargar. Sin PDF guardado,
la vista previa muestra contenido y procedencia del renderer con sus hashes,
`file=null` y `source_mode=render_on_read`; no promete un hash binario ni genera
archivos. Esa revisión permite completar la asociación. Preparar posteriormente
una copia binaria cambia la fuente y requiere revisar una vista previa nueva.
Los flags staff del destinatario no cambian esta proyección de cliente.
