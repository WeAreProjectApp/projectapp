### FLOW: `platform-appi-shared-quota-audio`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-appi.spec.js`

Cliente ve el marcador del cupo compartido de IA, su ventana móvil y el próximo restablecimiento. Una pregunta escrita, una respuesta reutilizada o una consulta fuera de alcance consume una unidad; una pregunta dictada reserva una unidad al transcribir y la canjea una sola vez al enviarla. Al agotar el límite, la interfaz bloquea nuevas consultas y muestra cuándo podrá continuar, sin duplicar el cobro al reintentar.

| Resultado | Interacción y evidencia |
|---|---|
| display | Abrir Appi y comprobar límite, usado, restante y hora de restablecimiento del cupo compartido para ese cliente. |
| success | Dictar una pregunta, revisar la transcripción en el campo y enviarla; la respuesta se crea con el mismo recibo y el marcador baja sólo una unidad. |
| error | Alcanzar el cupo de la ventana móvil e intentar enviar o empezar una grabación; los controles permanecen bloqueados y se informa cuándo vuelve a haber cupo. |
| failure | Fallar transcripción, envío o sondeo; se conserva la posibilidad de editar o descartar la grabación y un reintento con el mismo identificador no consume una segunda unidad. |
