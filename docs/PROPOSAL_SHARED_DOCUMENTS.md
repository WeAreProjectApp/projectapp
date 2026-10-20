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
