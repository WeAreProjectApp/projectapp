# Detalle informativo de movimientos del bolsillo

`accounting` pasa de 1.3.0 a 1.4.0 y `accounting-ledger` de 2.3.0 a 2.4.0.
La herramienta `get_pocket` añade datos de consulta a su respuesta y conserva
sus argumentos, campos existentes, permisos y reglas de escritura.

El detalle incluye el saldo real después del movimiento (`running_balance`),
el registro relacionado (`linked_record_detail`) y el reparto de un abono
(`allocation_details`). Cada imputación identifica el ingreso, su importe,
el pendiente actual y si corresponde a saldo a favor. La descripción pública
explica estos datos; las huellas de ambos conectores se actualizan con ella.

La consulta comparte el servicio del Panel. El pendiente considera los demás
pagos y deducciones; representa el estado actual, no una fotografía histórica.
El listado `list_pocket` conserva su respuesta y no carga estos cálculos.
