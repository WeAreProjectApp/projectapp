### FLOW: `admin-document-change-history`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/documents/:id/edit`
- **Description:** Abre Historial desde el detalle del documento; consulta versiones completas y campos modificados, compara dos versiones o la anterior, invierte el orden y pagina.
- **Display outcome:** Navegar desde la interfaz hasta un registro real y verificar sus cambios, autor y fecha. Evidencia incompleta se identifica sin inventar versiones; el estado vacío explica la ausencia de datos anteriores.
- **Success outcome:** Consultar y ver inmediatamente el diff renderizado anterior → seleccionada, con fechas y signos −/+; comparar versiones de páginas distintas; cambiar el orden por dropdown; leer la versión completa y volver al mismo par. Cambios de formato, tablas, listas y documentos extensos conservan su lectura. Una sola paginación y selección conservada al navegar.
- **Error outcome:** n/a — los controles emiten sólo identificadores y opciones válidas. Permisos, pertenencia y validación del contrato se prueban en backend.
- **Failure outcome:** Fallos de API muestran una recuperación explícita y no revelan valores protegidos ni comparaciones obsoletas.
- **Coverage:** Specs de display, success y failure en `admin/admin-entity-history.spec.js` y `admin/admin-document-history-reader.spec.js`. Los casos nuevos se validan exclusivamente por CI; QA visual manual pendiente y pausado. Permisos y conservación de contenido tienen controles de backend.
