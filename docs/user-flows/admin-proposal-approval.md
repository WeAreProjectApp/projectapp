# Revisar la aprobación y vincular una propuesta

- Rol: administrador del Panel.
- Prioridad: P1.
- Origen: listado, cambio de estado, menú de acciones, editor de Propuestas o propuesta dentro de la ficha de Clientes.
- Superficies: modal compartido de aprobación y revisión de cliente/proyecto.

| Clase | Interacción | Resultado observable |
|---|---|---|
| success | Aprobar desde una propuesta expandida en Clientes | Modal compartido antes de guardar; al completar se refresca la ficha correspondiente |
| success | Confirmar cliente y proyecto existentes | Propuesta vinculada al proyecto elegido, sin crear otro |
| success | Crear cliente y proyecto al confirmar | El vínculo conserva ambos registros y el paquete documental |
| success | Desactivar contratos de la propuesta y adjuntar varios archivos | El nuevo paquete usa los personalizados y conserva detalle comercial/técnico |
| success | Aprobar y revisar después | Estado aceptado pendiente, sin cliente/proyecto/archivos nuevos |
| error | Confirmar personalizados sin archivo o con datos inválidos | Error correspondiente; modal y valores conservados |
| failure | Fallo del servidor durante confirmación | Mensaje visible; formulario conservado para reintentar |
| display | Abrir aprobación desde el listado | Resumen real de cliente, proyecto, condiciones y documentos |
| display | Reabrir propuesta vinculada | Cliente/proyecto y archivos confirmados del mismo vínculo |
| success | Cancelar o pulsar Escape | Se conserva el estado previo y vuelve el foco al disparador |

La aceptación pública sigue su recorrido existente y se verifica además en
backend: aceptar no aprovisiona recursos. Este flujo comienza con la revisión
interna. Los permisos, atomicidad, duplicados y archivos privados se verifican
también en pruebas API/servicios/MCP; no se sustituyen por mocks del navegador.

Especificación: `frontend/e2e/admin/admin-proposal-approval.spec.js`.
Ejecución focal: los ocho casos de este archivo pasaron con un worker, API
simulada en el límite externo y sin servicios reales; incluyen 412 y 835 px.
Las siete regresiones de estados en línea pasaron en el mismo lote.
El delta final verifica Clientes (1/1) y las cuatro regresiones de handoff,
incluido el siguiente paso y las transiciones actualizadas sin recargar (4/4).
Los resultados finales de integración se registran en el PR.
