# PA-248 · Estados y eliminación de proyectos

Los cambios de estado conservan sus reglas financieras. Suspender, completar o
dar de baja pueden dejar ingresos futuros sin cobrar fuera de los esperados,
con estado Cancelado, y archivar cobros futuros de hosting. No se borran los
registros ni se confunden con ingresos perdidos. En desarrollo y Operando no
anuncian esas modificaciones. La API y MCP también devuelven vacías las listas
de cancelaciones futuras para esas transiciones, usando el mismo efecto operativo. La baja conserva las decisiones explícitas sobre
saldo por cobrar o saldo perdido; completar exige resolver deuda causada.

## Eliminación selectiva

Eliminar proyecto muestra Forzar eliminación junto al nombre desde la apertura,
sólo para superusuarios. Cambiar estado sigue siendo una acción independiente.
Las categorías empiezan apagadas; apagado conserva, encendido elimina. La
selección exige sus dependencias de forma explícita. Confirmar requiere DELETE
exacto y la huella del alcance vigente. Cancelar o cerrar no escribe datos.

El historial de decisiones de facturación siempre se conserva. accounts.0091
agrega contexto de retención y admite proyecto vacío únicamente cuando existe
ese contexto; la relación sigue usando PROTECT. La eliminación transaccional
registra cliente, nombre e ID original en ProjectRetentionContext y traslada
la pertenencia de esos eventos sin cambiar actor, fecha, motivo o antes/después.
Las fuentes legales elegidas para borrar mantienen sus bloqueos. No se permite
seleccionar billing_context_events mediante payload manual.

La migración se aplica mediante deploy, nunca contra producción desde el worktree.
Los registros conservados se consultan desde Datos sin proyecto del cliente;
el historial no se ofrece como categoría trasladable ni eliminable.

## MCP de Proyectos 4.5.0

preview_project_force_delete recibe project_id y delete_keys (lista explícita,
[] conserva todo). force_delete_project requiere además confirmation=DELETE e
impact_token de esa revisión; crea una confirmación MCP y sólo confirm_action
ejecuta la operación. Ambas herramientas necesitan grant nominal y la ejecución
requiere force_delete_project explícito. Los permisos generales no lo conceden.
Se usa el principal técnico del conector para auditoría, sin impersonar un SU.
El borrado normal por delete_project conserva su límite de proyectos vacíos.
Las credenciales anteriores no reciben grants automáticamente.

## Validación pendiente de CI y DEV

Regresiones: selección permitida con historia protegida, selección prohibida,
confirmación exacta, permisos Panel/MCP, token obsoleto, cancelar, doble envío y
consulta posterior del historial. Comparar antes/después de ingresos y cobros
para suspensión, operación, cierre y baja; conservar importes pagados y relaciones
ajenas. DEV usa casos ficticios propios, cinco perfiles y ambos temas. Teclado
dedicado fuera del alcance manual. Registrar SHA servido, rol, IDs y resultados.
