# Aprobación y documentos compartidos

La aprobación interna requiere confirmar cliente, proyecto y contrato real. Se reutiliza el modal existente; cancelar no modifica el estado. Se retiró la aceptación pública, incluida su condición opcional; siguen rechazo y solicitud de negociación. Las rutas genéricas y MCP de estado no pueden aprobar.

## Fuente y versiones

`Document` es la identidad del gestor. `ProposalDocumentBinding` vincula esa identidad con la propuesta y su fuente estructurada o binaria. No hay una segunda copia editable de texto. El gestor abre el editor de origen para contratos/detalles; los adjuntos habilitados admiten sustitución privada mediante `POST documents/:id/proposal-source/` con archivo y `source_hash`.

`ProposalApprovalPackage` numera los cierres y `ProposalApprovalFile` conserva los bytes privados por revisión. Cada módulo descarga la misma revisión. Confirmar una revisión cambia los punteros vigentes y conserva el historial, también al cambiar modalidad contractual. Contratos propios se identifican por función contractual; los anexos personalizados utilizan UUID estables. Los archivos firmados y las fuentes de entregas conservan sus identificadores exactos.

Las escrituras estructuradas compartidas exigen la huella capturada al editar. El primer guardado válido gana; un guardado antiguo devuelve 409 y no modifica datos. La confirmación del paquete revalida la fuente bajo bloqueo y es idempotente por `request_id`. Crear proyecto, carpetas, documentos y aceptar ocurre en una transacción, con limpieza de archivos nuevos ante fallos.

## Carpetas y API

Bajo la raíz gestionada del proyecto se crean Contratos y Anexos mediante claves estables. Se hereda proyecto/cliente. Los detalles comercial y técnico provienen de la generación curada de PA-143; entran todos los anexos activos. Una raíz histórica sin conciliar bloquea la operación e indica completar PA-108. No se convierten raíces por coincidencia de nombre.

- `GET/POST proposals/:id/approval/`: revisar y confirmar el cierre inicial.
- `POST proposals/:id/approval/revisions/`: confirmar otro paquete con la misma identidad documental.
- `GET/POST documents/:id/proposal-source/`: consultar revisiones o sustituir el adjunto en borrador.
- Las descargas de archivos de cierre conservan sus rutas e identificadores. Una cuenta o entrega firmada nunca cambia de revisión por reconfirmar.

Los conectores Comercial y Documentos utilizan esos servicios. La lectura devuelve identidad, revisión, capacidades y versión; las escrituras sensibles requieren la confirmación MCP existente. Los editores genéricos de Markdown rechazan documentos con fuente estructurada. Se actualizan también los adaptadores anteriores de propuestas.

## Históricos y despliegue

Migraciones aditivas `content.0296` y `0297`, aplicadas por el deploy. Ninguna migración de esquema empareja datos reales.

`reconcile_proposal_documents` sin `--apply` produce un inventario JSON y una huella. Para aplicar una propuesta revisada se requieren `--proposal`, `--actor`, `--expected-hash` y `--apply`. Reutiliza los archivos exactos del cierre confirmado, verificando sus huellas; si faltan proyecto, contrato o archivos, exige completar la revisión. No reconstruye contratos históricos desde una propuesta modificada ni envía correos.

Las pruebas nuevas usan SQLite y almacenamiento temporal con `settings_test`; las pruebas del navegador simulan la frontera HTTP y no acreditan por sí solas la consistencia de base de datos.

## Aprobación explícita del servicio

Elegir contratos separados no acredita que el cliente haya aprobado el servicio.
`BusinessProposal.service_contract_approved` empieza en `false`, también para
propuestas existentes. En Documentos, el switch «Servicio aprobado» sólo aparece
con contratos separados: apagado exige producto; encendido exige producto y
servicio. El contrato único conserva su comportamiento. La generación y edición
de ambos borradores sigue disponible durante la negociación.

Guardar el switch cambia la fuente y marca el borrador pendiente; sólo confirmar
una nueva revisión modifica los documentos vigentes. Los contratos retirados
conservan su identidad, revisiones, descargas y referencias de firma. El valor
queda guardado en cada manifiesto nuevo; las evidencias previas no se modifican.
Las herramientas de creación/edición JSON y `update_proposal_settings` admiten el
booleano; omitirlo en una actualización conserva el valor guardado. El detalle
público no expone esta decisión administrativa.

## Reparar vínculos faltantes

`GET/POST proposals/:id/approval/reconciliation/` consulta y recupera vínculos de
archivos ya confirmados. POST exige `expected_hash` de la consulta vigente y staff.
El MCP de Documentos ofrece `preview_proposal_document_reconciliation` y
`reconcile_proposal_documents`; la escritura usa la confirmación MCP existente.
La CLI `reconcile_proposal_documents` comparte ese mismo servicio.

La consulta no escribe. Se comprueban bytes, huellas, cliente, proyecto y carpeta
raíz; se bloquean identidades ambiguas o archivos corruptos. Si falta un vínculo,
se reutiliza el archivo exacto del paquete actual, conservando los documentos ya
vinculados. Los cierres anteriores al sistema de paquetes se incorporan con sus
archivos conservados. No se reconstruyen anexos que nunca fueron confirmados:
`requires_new_revision` indica cuáles requieren revisar y confirmar otro paquete.
No se envían correos ni se cambia el estado de la propuesta al reparar.
