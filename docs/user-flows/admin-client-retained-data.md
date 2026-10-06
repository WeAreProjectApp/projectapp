### FLOW: `admin-client-retained-data`

- **Módulo:** admin
- **Rol:** administrador del panel con sesión
- **Prioridad:** P1
- **Ruta:** `/panel/clients`
- **API:** `GET /api/proposals/client-profiles/<id>/retained-project-data/`; consulta por contexto, categoría y página; descarga de archivo; `POST .../reveal/` sólo para revelar un secreto admitido, con CSRF.
- **Descripción:** La ficha expandida ofrece Datos sin proyecto. La consulta muestra el proyecto de origen y las cantidades de datos conservados, carga registros al elegir una categoría y permite volver, paginar y cerrar. Los archivos se descargan con autorización. Las credenciales no se precargan; se revelan mediante una acción explícita y se ocultan al cambiar de contexto o cerrar.
- **Éxito:** No hay formulario de edición, reasignación ni mutación de los registros. La consulta completada se valida como visualización con navegación real y datos concretos.
- **Error:** Un rechazo de acceso al consultar una categoría muestra el error y no expone registros ni realiza escrituras. El backend rechaza un contexto de otro cliente, una fila fuera del inventario y una revelación no admitida.
- **Fallo:** Si el servicio no responde correctamente, el modal muestra el error; cerrar y abrir permite reintentar. Una respuesta tardía de otro cliente se descarta.
- **Visualización:** Llegar desde el menú Clientes, expandir la ficha y abrir Datos sin proyecto muestra el nombre anterior del proyecto y cantidades reales. Elegir una categoría muestra los registros conservados; un resultado vacío se explica.
- **Cobertura:** `frontend/e2e/admin/admin-client-retained-data.spec.js`; autorización, paginación, lectura segura, archivos y CSRF en `backend/content/tests/views/test_project_retention.py`; aislamiento de respuestas y revelado explícito en `frontend/test/components/clients/ClientRetainedProjectDataModal.spec.js`.
