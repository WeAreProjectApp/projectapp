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
| success | Volver a aprobar después de una corrección administrativa de estado | Revisar condiciones del borrador y confirmar otro paquete sin alterar los archivos previos |
| success | Cancelar antes de confirmar | Estado previo conservado sin crear proyecto ni documentos |
| error | Confirmar personalizados sin archivo o con datos inválidos | Error correspondiente; modal y valores conservados |
| failure | Fallo del servidor durante confirmación | Mensaje visible; formulario conservado para reintentar |
| display | Abrir aprobación desde el listado | Resumen real de cliente, proyecto, condiciones y documentos |
| display | Reabrir propuesta vinculada | Cliente/proyecto y archivos confirmados del mismo vínculo |
| success | Cancelar o pulsar Escape | Se conserva el estado previo y vuelve el foco al disparador |

La aprobación pública se retiró. El cierre interno exige cliente, proyecto y contrato; incorpora todos los anexos activos. Un conflicto conserva el formulario. Los permisos, atomicidad, identidades y archivos privados también se verifican en API/servicios/MCP.

Especificación: `frontend/e2e/admin/admin-proposal-approval.spec.js` y regresión desde Clientes.
