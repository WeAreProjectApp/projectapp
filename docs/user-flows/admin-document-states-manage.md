### FLOW: `admin-document-states-manage`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/documents/statuses`
- **API:** `/api/document-state-groups/`, `/api/document-states/`, `/api/document-states/:id/merge/`, `/api/document-states/:id/retire/`
- **Descripción:** El catálogo compartido separa grupos exclusivos —el ciclo— de grupos aditivos —las señales—. Muestra cuántos documentos tienen cada estado vigente y cuántos episodios históricos existen. El usuario puede crear grupos y estados, cambiar nombre, color, orden, grupo e incompatibilidades, fusionar duplicados y retirar valores que ya no se usan. Las semillas son editables, pero conservan su clave interna para presets e integraciones.
- **Recorrido:** entrar a Documentos → **Administrar estados** → revisar inventario → crear o editar un valor → confirmar nombres similares, fusiones o retiros dentro del panel → guardar → reutilizarlo desde cualquier documento.
- **Ramas:**
  - [Display] Ciclo y Señales muestran sus semillas y conteos.
  - [Success] Crear, editar y fusionar refresca el catálogo global.
  - [Error] Un estado con episodios abiertos no se puede retirar hasta cerrarlo o fusionarlo.
  - [Error — validación] **Crear estado**, **Crear grupo**, **Guardar** y **Fusionar** siguen disponibles. Al intentarlos sin nombre o sin destino, el aviso aparece bajo su campo y lo marca inválido, sin llamar al servidor; un rechazo del API por nombre o grupo se muestra en el mismo lugar. Que una semilla no se pueda fusionar es una restricción permanente y queda como ayuda del botón deshabilitado.
  - [Failure] Un fallo del servidor conserva el borrador de edición para reintentar.
- **Cobertura:** ✅ display/success/error/failure.
- **E2E:** `e2e/admin/admin-document-states-manage.spec.js`
