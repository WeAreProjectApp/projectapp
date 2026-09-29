### FLOW: `admin-proposal-document-markdown`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P2
- **Ruta:** `/panel/proposals/:id/edit` → Documentos; disponible en `sent`, `viewed`, `negotiating`, `accepted` y `rejected`.
- **Display:** acciones de copia para contrato generado, comercial, técnico y adjuntos compatibles; PDF e imágenes conservan su visor; DOCX/XLSX presentan Markdown y tablas con advertencia. Todo adjunto conserva descarga del original.
- **Success:** Copiar Markdown solicita el documento elegido, escribe su contenido en el portapapeles y confirma Copiado. Contrato usa el snapshot guardado; comercial y técnico extraen el texto de sus PDF originales; el comercial sólo omite las seis secciones acordadas, sin reescribir las demás.
- **Error:** DOC/XLS requieren conversión e imágenes requieren OCR. Archivo vacío, escaneado, protegido, corrupto o fuera de límites devuelve un error recuperable.
- **Failure:** errores de extracción, archivo ausente o portapapeles bloqueado permiten reintentar. Cerrar el visor aborta su solicitud pendiente.
- **Límites:** 15 MB, 100 páginas PDF, 20.000 celdas XLSX, 50 MB expandidos y un millón de caracteres; sin macros, consultas externas ni OCR.
- **E2E Spec:** `e2e/admin/admin-proposal-document-markdown.spec.js`.
