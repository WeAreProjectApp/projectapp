# Platform: paridad administrativa de entregas por MCP

La interfaz se abre en `/platform/projects/{id}/delivery`, con controles
administrativos de contratos, alcances, importación, firma y publicación.
El conector **Proyectos** incluye la autoría y administración de la jerarquía
proyecto → contrato/otrosí → alcance → fase de ejecución → etapa → requerimiento.
Las operaciones invocan `accounts.services.delivery_workflow`, igual que las
vistas JWT de Platform. Las fases de ejecución son distintas de las fases
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
| Copiar el prompt y consultar el esquema JSON | `get_delivery_authoring_contract` | Formato vigente y contexto del proyecto, sin ejecutar IA dentro de Platform. |
| Previsualizar una importación JSON | `preview_delivery_import` | Valida la carga y el impacto sin guardar. |
| Aplicar una importación JSON revisada | `apply_delivery_import` | Confirmación, versión vigente, transacción completa e idempotencia; no importa firmas ni decisiones. |
| Publicar una etapa o abrir otra ronda de pendientes | `publish_delivery_stage` | Confirmación; exige contrato/otrosí firmado y guía completa. Conserva requerimientos aprobados. |
| Constatar un PDF firmado fuera de Platform | `attest_external_delivery_signature` | Confirmación; `asset_id` PDF completo de la misma credencial, máximo 10 MB, firmante, fecha y declaración administrativa. |
| Registrar una aprobación previa explícita del cliente | `record_external_delivery_approval` | Confirmación; requiere `client_statement: true`, transcripción entrante y decisión `approved`. Usa un mensaje entrante recibido del mismo cliente/proyecto, o evidencia documental con revisor original, fecha, canal y referencia externa. Registra actor administrativo y `is_external`, sin atribuirle una revisión nueva al cliente. |
| Elegir la comunicación entrante que respalda una conformidad | `list_delivery_approval_evidence` | Solo mensajes recibidos, no anulados y del mismo cliente/proyecto; el servicio comprueba la cita al guardar. |
| Responder un reporte o una revisión | `add_delivery_message` | Mensaje al nivel elegido, requerimientos tratados y documentos opcionales; autoría real, opción de nota interna. |
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

La existencia de esta matriz describe la cobertura del incremento. Los resultados
ejecutados se registran en `MCP_VALIDATION_RUNBOOK.md`; no se validan conectores ni
se modifican datos reales de producción durante las pruebas.
