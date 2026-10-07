### FLOW: `admin-proposal-project-reassignment`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/proposals/:id/edit?tab=project&section=project-data`
- **Description:** Corregir el proyecto de una propuesta vinculada conservando su identidad, fases y evidencia aprobada.
- **Steps:**
  1. Abrir Proyecto → Datos desde la navegación de la propuesta.
  2. Seleccionar otro proyecto activo del mismo cliente y explicar el motivo.
  3. Revisar el origen, destino y las relaciones incluidas en el traslado.
  4. Confirmar sólo cuando la revisión no tiene dependencias pendientes.
  5. Ver el proyecto actualizado en Datos.
- **Outcomes:**
  - `success`: La confirmación cambia el vínculo sin recrear la propuesta ni el paquete aprobado.
  - `error`: Una revisión obsoleta o una dependencia pendiente exige revisar nuevamente antes de confirmar.
  - `failure`: Un error de transporte conserva la revisión y permite reintentar la misma operación; la idempotencia evita duplicar el traslado.
  - `display`: La consulta de cliente, contactos y proyecto en todos los estados forma parte de `admin-proposal-edit`.
- **E2E Spec:** `e2e/admin/admin-proposal-navigation.spec.js`
