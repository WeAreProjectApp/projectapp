# PA-215 — correos de liquidación y remanente

Rol: Implementación, confirmado por el operador. Alcance aprobado: correo y
remanente visible con Participaciones contraída. Automatizadas exclusivamente
en CI. La validación manual corresponde a DevQA y Backlog ProjectApp en Chrome.

## Diagnóstico y cambio

`EmailDeliveryGateway.send` copiaba el mensaje completo antes del transporte,
incluida la conexión SMTP con su `RLock`. Fallaba antes de crear el snapshot y
antes del envío. La segunda copia, destinada al destinatario interno, tenía el
mismo riesgo. La clonación ahora conserva la conexión por referencia con el
memo de `deepcopy`; copia el contenido sin cambiar el mensaje original ni su
timeout. La preparación queda dentro del bloque que limpia el contexto si
falla; la preparación de cada copia queda dentro de su manejo independiente.

El resumen de Participaciones añade el remanente positivo de ProjectApp,
redondeado a centavos. No cambia importes, destinos ni payloads de liquidación.
No hay migraciones ni modificaciones en contratos REST o MCP.

## Regresiones para CI

- Backend SMTP real con red interceptada: envío principal y BCC, timeout de
  20 segundos, texto/HTML, adjuntos archivados, copias independientes, contenido
  previo a cambios del transporte y limpieza del contexto ante fallo al clonar.
- Aviso de ingreso completo sin cuenta: falla de SMTP y reintento desde
  Historial; un pago, un movimiento y un aviso de negocio.
- Confirmaciones individuales y múltiples: una por ingreso elegible, falla
  de SMTP y reintentos relacionados sin duplicar pagos ni movimientos.
- Componente: 119 y 119,03, eliminación del remanente al recibir importe par,
  y reparto manual 50,25 + 60,50 que deja 8,25 de 119.
- E2E: selección de uno o varios ingresos por un total de 119; Participaciones
  permanece contraída y muestra 59 + 59 + 1; editar a 118 elimina el remanente.

## Flujos y Mapa de vistas

Se revisó el recorrido `/panel/accounting/incomes` y sus entradas desde fila y
selección; ambos montan `IncomeLiquidateModal`. La modificación visible
pertenece al resultado `display` del flujo existente
`admin-accounting-income-bulk-settle`. Se amplían su descripción, dos casos E2E
y el relato canónico; el mapa agregado se regenera desde los shards.
Los casos existentes de éxito, validación y rechazo del servidor conservan sus
entradas y etiquetas. Esta revisión estática no acredita ejecución de navegador.

El catálogo y el Explorador describen el resumen ampliado. No cambian URLs,
audiencias, nodos, tipos de vista ni conteos responsivos; los controles
estructurales y las pruebas de catálogo corresponden a CI.

## Traspaso manual

Acceso: superusuario financiero. DevQA verifica SHA servido, aislamiento de
datos y capturador de correo sin salida externa antes de publicar DEV LISTO.

1. Cotejar si permanecen ingresos QA 37, 38 y 39, aviso 8 y correos 14, 16 y
   17. Registrar sus pagos, movimientos y avisos antes de reintentar. Si la
   base fue regenerada, preparar equivalentes y publicar sus IDs.
2. Reintentar los tres correos desde Historial sin volver a liquidar. Verificar
   un aviso interno y dos confirmaciones en el capturador, destinatarios de
   cuentas emitidas e intentos enviados enlazados a los fallidos. Conservar
   pagos, movimientos y aviso originales; no modificar el fallo histórico.
3. Con datos nuevos, completar un ingreso sin cuenta y liquidar dos ingresos
   con cuentas emitidas y ambas confirmaciones marcadas. Los mensajes deben
   salir en el primer intento. Corroborar saldos y relaciones persistidos.
4. Abrir con recibido 119: sin expandir Participaciones, ver Carlos 59,
   Gustavo 59 y ProjectApp 1. Repetir selección múltiple. Comprobar 118,
   centavos, reparto manual y ambos destinos sin variar el recibido.
5. Regresión acordada: 100 + 100 con 180 recibidos y comisión 20 produce
   90 recibidos y deducción 10 por ingreso; abono sin deducción cubre los
   más antiguos primero. Conservar reprogramación e IVA ya aceptados.
6. Revisar 412×915, 835×1195, 1195×835, 1440×900 y 2560×1440, temas claro y
   oscuro, Tab/Enter, cierre y devolución de foco. Registrar evidencia real.

Solicitud y respuestas: buzón de DevQA, clave `pa215-settlement-email`, y
`projectapp-qa/devqa-mensajes/PA215-implementacion-a-devqa.md`. No hay turno
asignado ni dictamen manual acreditado por este documento. SHA, PR, corrida de
CI y acuse se publican en la ficha de la solicitud una vez disponibles.
