### FLOW: `admin-project-delete`

- **Módulo:** admin
- **Rol:** administrador; eliminación forzada exclusiva de superusuarios
- **Prioridad:** P1
- **Ruta:** `/panel/projects`
- **API:** `GET /api/projects/<id>/delete-preview/`, `GET /api/projects/<id>/delete-preview/?force=true`, `DELETE /api/projects/<id>/delete/`
- **Descripción:** El menú de acciones abre Eliminar proyecto en un modal amplio. Cambiar estado muestra su texto completo en los cinco tamaños del panel. Un proyecto vacío admite la confirmación normal; uno con información muestra sus dependencias. Desde Cambiar estado, un superusuario puede activar Forzar eliminación, revisar los registros propios afectados y escribir exactamente `DELETE`. Esta acción elimina el proyecto y sus dependencias propias, incluidos datos contables y contratos, sin asignar otro estado. Conserva cliente, propuestas comerciales, catálogos y auditoría independiente. Los archivos exclusivos se limpian después de confirmar la transacción; los archivos aún referenciados se conservan.
- **Éxito:** La confirmación válida retira el proyecto de la lista y muestra Proyecto eliminado. Cancelar conserva el proyecto y no envía una petición de borrado. Desactivar Forzar eliminación vuelve al formulario de estado y descarta la confirmación previa.
- **Error:** `delete`, espacios u otro texto no habilitan la confirmación. La opción no aparece para un administrador ordinario ni al abrir Cambiar estado directamente. Un abono, hilo o dependencia compartida, o evidencia legal protegida, impide todo el borrado. Si cambian las dependencias después de revisarlas, el modal muestra el alcance actualizado, limpia `DELETE` y exige confirmar de nuevo.
- **Fallo:** Una vista previa fallida muestra el error y permite reintentar. Un fallo al eliminar conserva el proyecto y el modal abierto. La transacción evita borrados parciales.
- **Visualización:** La revisión muestra proyecto, advertencia, tipos de registros y cantidades. Se verifica como parte del recorrido de eliminación; no declara una prueba de visualización independiente.
- **Cobertura:** `frontend/e2e/admin/admin-project-delete.spec.js` conserva el recorrido normal; `frontend/e2e/admin/admin-project-force-delete.spec.js` cubre el recorrido forzado, permisos, confirmación exacta, vista previa obsoleta, reintento y cancelación. Borrado transaccional, datos compartidos, CSRF/JWT, auditoría y archivos se verifican en backend.
