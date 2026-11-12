## Administración de carpetas de documentos

**Rol:** administrador. Entrada: Panel → Gestor Documental.

### PA-206 — creación contextual

**Nueva carpeta** en el encabezado abre el formulario directo con destino visible: carpeta abierta o raíz definida del proyecto seleccionado. Guardar mantiene la ubicación del listado y muestra la nueva carpeta; cancelar no escribe. Sin raíz definida se conserva el proyecto y se propone una carpeta sin padre.

### PA-207 — destinos buscables y jerarquía

En **Gestionar carpetas**, **Dentro de** busca por fragmento de nombre y conserva la ruta de cada coincidencia. Admite **Ninguna (carpeta raíz)** y teclado; escribir sin elegir no cambia el destino confirmado. El árbol muestra los ancestros de cada subcarpeta. La edición y eliminación usan sus formularios compartidos; archivar y reordenar entre hermanas conservan su contrato.

### Resultados y cobertura

- Éxito: crear desde raíz/subcarpeta y elegir una subcarpeta entre nombres coincidentes; cancelar sin crear.
- Error: nombre rechazado conserva formulario y destino.
- Fallo del servidor: se conserva el manejo de errores de creación/reordenamiento existente.
- Presentación: destino y rama visibles antes de confirmar.
- Regresión CI: `admin-document-folder-create.spec.js`, `admin-document-folder-manage.spec.js` y `admin-document-folders.spec.js`. La aprobación manual Chrome sobre datos aislados se registra por separado.

- **Integración 2026-11-11:** El cierre del formulario secundario devuelve el foco al botón que abrió la edición.
