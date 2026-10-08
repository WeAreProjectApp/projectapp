# Archivos confirmados como fuentes contractuales

El puente permite seleccionar explícitamente un `ProposalApprovalFile` ya
confirmado como fuente de `ProjectContract` o `ContractAmendment`. No ejecuta
aprobación comercial, envío, firma, publicación ni creación automática de contratos.

## Contrato de entrada y opciones

`approval_file_id` es excluyente con `document_id` y `proposal_document_id`.
Los mismos serializers y servicios validan REST y MCP. `GET delivery/documents/options/`
y `GET delivery/prompt/options/` agregan `approval_files` con ID, título, filename,
tipo, propuesta, tamaño, hash, fecha de confirmación y MIME; nunca ruta de storage.

El archivo debe pertenecer al proyecto y cliente vigentes, al entregable vinculado
de su propuesta y al manifiesto confirmado con el mismo ID, clave, tamaño y hash.
La lectura verifica los bytes privados completos (máximo 15 MB), sin truncarlos.
Los recursos retenidos sin proyecto operativo no son fuentes elegibles.

La creación o cambio a esta fuente empieza con `client_visible: false` y estado
de firma `unsigned`. Solicitar consulta pública durante esa selección se rechaza.
Un PATCH posterior permite habilitarla explícitamente mientras no haya contexto
publicado congelado. El nombre del archivo o su procedencia no acredita firma.

## Descargas, firmas y capturas

La ruta `GET delivery/{contracts|amendments}/<id>/source/` usa autorización JWT
del proyecto y visibilidad contractual. Devuelve los bytes exactos, nombre y MIME,
como adjunto con `private, no-store` y `nosniff`. Una cuenta ajena no accede al proyecto;
el propietario no descarga contratos privados.

El overview agrega `approval_file_id`, `source_download_url`, `source_filename`,
`source_content_type` y `source_sha256`. `pdf_url` queda vacío para originales no
PDF sin evidencia de firma; no se cambia su extensión ni se genera un PDF inventado.

`contract_source_file(project_id, actor, kind, node_id)` devuelve
`(bytes, filename, content_type)` para el transporte REST o MCP.
`approval_contract_source(node)` prioriza el PDF privado firmado, comprueba su hash
y nunca vuelve al original sin firma si la evidencia registrada está corrupta.
La firma externa conserva la relación `approval_file_id` en su snapshot.

El prompt conserva otra copia privada exacta, `origin: approval_file`, `source_id`,
hash, metadatos y fragmentos localizables. PDF y DOCX usan el extractor vigente;
formatos sin texto verificable quedan ilegibles con advertencia y descarga original.
El paquete sin firma no constituye contexto contractual completo. Ante una copia
no verificable se conserva la advertencia, sin usar datos de un documento vivo.

## Migración y validación

`accounts.0079_delivery_approval_source` depende de `accounts.0078` y
`content.0283`. Agrega dos FK `PROTECT` y extiende los constraints de fuente única;
no modifica ni reprovisiona contratos existentes. Sólo el despliegue aplica migraciones.

Las pruebas focales cubren fuente única, privacidad inicial, contexto de proyecto,
manifiesto, corrupción, reintentos, PDF firmado, descargas originales, capturas,
protección de borrado y selector UI. La QA conjunta revisa E2E y los adaptadores
adicionales del MCP sobre el contenido integrado.
