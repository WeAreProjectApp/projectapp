### FLOW: `admin-project-change-client`
- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/projects`
- **API:** `GET /api/projects/<id>/change-client/preview/?client_profile_id=`, `POST /api/projects/<id>/change-client/`, `DELETE /api/accounts/projects/<id>/?force=1` (guarded)
- **Description:** El campo de cliente del formulario conserva su valor (`client_immutable`); Cambiar cliente… abre el cambio guiado. Elegir el destino carga una vista previa con `can_apply`, `blockers`, `blocker_counts`, los planes `planned.move` y `planned.detach`, y un `impact_hash` común a ambos modos. Si la historia financiera, las entregas o los tickets impiden el cambio, el modal muestra sus motivos y orienta a crear un proyecto nuevo para el cliente destino; oculta los modos y deshabilita la confirmación. Si el cambio está permitido, presenta los registros afectados, conserva los documentos emitidos y exige elegir Mover o Desvincular cada vez. La confirmación envía `expected_impact_hash` y las listas de IDs de hosting, ingresos e hilos de la vista previa. El cambio se aplica en una transacción con auditoría por registro; la fila muestra el nuevo cliente. El borrado definitivo sigue respondiendo 409 `project_has_records` mientras haya registros vinculados.
- **Steps:** editar proyecto → Cambiar cliente… → elegir destino → revisar impacto y motivos → si está permitido, elegir modo y confirmar → la fila y los listados contables se actualizan; si está bloqueado, cancelar y crear un proyecto nuevo para el cliente destino.
- **Branches:** `display`: un cambio permitido muestra el impacto y mantiene la confirmación deshabilitada hasta elegir modo; `success`: Mover envía el hash revisado y actualiza el cliente visible; `error`: `can_apply: false` muestra los bloqueos y la guía de crear un proyecto nuevo, oculta los modos y mantiene la confirmación deshabilitada sin enviar ningún POST a `change-client/`, incluso al cancelar. Mismo cliente, cliente inexistente o proyecto terminal siguen respondiendo 400; 409 `records_not_found`/`records_changed` recarga la vista previa y descarta el modo elegido.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-project-change-client.spec.js`

### Section 28 Coverage Index

| Flow ID | Module | Role | Priority | Status | Spec |
|---------|--------|------|----------|--------|------|
| `admin-accounting-project-bulk-assign` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-accounting-project-bulk-assign.spec.js` |
| `admin-accounting-project-coherence` | admin | admin | P1 | ✅ Covered | `e2e/admin/admin-accounting-project-coherence.spec.js` |
| `admin-project-inline-assign-offer` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-project-inline-assign-offer.spec.js` |
| `admin-project-change-client` | admin | admin | P2 | ✅ Covered | `e2e/admin/admin-project-change-client.spec.js` |
