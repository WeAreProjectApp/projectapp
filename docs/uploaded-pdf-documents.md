# Documentos PDF subidos

El gestor admite Markdown y PDF como modalidades de contenido bajo la misma identidad documental. Un PDF manual se conserva en almacenamiento privado, sin portadas añadidas ni conversión; mantiene las asociaciones, estados, notas y publicación explícita habituales. La descarga y el visor entregan sus bytes originales.

## Contrato

- Creación: POST `/api/documents/create-from-pdf/`, multipart `file` y metadatos del serializer de documentos. Reemplazo: POST `/api/documents/<id>/replace-pdf/`, `file` y `expected_version` vigente.
- Máximo 25 MiB (26.214.400 bytes), extensión PDF y estructura legible sin cifrado. La validación y la extracción se ejecutan en procesos separados, cada uno limitado a 128 MiB, 3 segundos CPU y 5 segundos de espera. Un fallo de validación rechaza la carga; un fallo de extracción conserva el PDF validado sin texto indexado. Sin OCR; hasta 200 páginas y 500.000 caracteres para búsqueda.
- Las lecturas exponen `content_format` y `pdf` (nombre, tamaño, SHA-256, versión y estado del texto), sin ruta de almacenamiento. La identificación sigue siendo editable; el contenido cambia únicamente mediante reemplazo. El índice contiene sólo el texto vigente.
- Cada reemplazo conserva ID/UUID, aumenta la versión y mantiene el archivo anterior en el historial interno. El borrado del documento vivo no borra los archivos históricos. Un duplicado empieza con identidad nueva, sin publicación, y referencia los mismos bytes inmutables hasta su siguiente reemplazo.
- Se rechaza reemplazar fuentes generadas por el sistema, archivadas, destinadas a firma o ya firmadas, fuentes compartidas de propuestas y PDF con evidencia contractual firmada o snapshots de entrega. Un contrato en borrador sin evidencia no bloquea. Las guardas se revalidan bajo locks de proyectos antes del documento y versión optimista.
- Los nuevos archivos se registran en la compensación del historial exterior y del savepoint MCP. Un fallo de persistencia, historial o consumo elimina sólo los archivos nuevos, conserva los anteriores y deja el asset reintentable. Una caída abrupta del proceso puede dejar objetos privados no referenciados; esta entrega no incorpora un recolector que pueda borrar evidencias.
- El portal conserva sus permisos y prioriza firma/snapshot sobre fuente vigente. Los límites de entrega/firma (10 MiB) y captura de fuentes (15 MiB) se mantienen.

## MCP

`create_document_from_pdf` y `replace_document_pdf` reciben un `source_asset_id` completo de la misma credencial. Se reutiliza la carga por partes existente. Metadatos por `update_pdf_document`; movimientos, etiquetas, estados, notas, archivo y publicación conservan las operaciones compartidas. `render_document_pdf` entrega el original como asset firmado temporal; las cuatro operaciones de historial permiten leer, comparar y descargar versiones internas. Los nuevos temporales/artefactos PDF del conector documents usan almacenamiento privado. Contrato efectivo: documents 8.2.0; huella generada con `mcp_schema_report`.

## Despliegue posterior

La migración aditiva `content.0304_uploaded_pdf_documents` depende de `0303_merge_editorial_requirement_packages`. No se aplica desde el worktree. El deploy debe aplicar y validar además la excepción Nginx versionada para las dos rutas de carga (26M con margen multipart). El límite de archivo sigue siendo 25 MiB y el resto de las rutas conserva sus límites. Sin aplicar esa plantilla, la carga del panel desplegado sigue limitada por el transporte anterior de 10M. Esta sesión no modifica Nginx vivo ni despliega.

PA-125 y la incorporación automática de contratos firmados son tareas separadas. El selector de contratos sigue buscando por título y muestra identidades, nunca revisiones internas como fuentes distintas.
