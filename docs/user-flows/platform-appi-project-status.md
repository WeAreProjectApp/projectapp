### FLOW: `platform-appi-project-status`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-appi.spec.js`

Cliente autenticado abre Appi, elige uno de sus proyectos o Todos mis proyectos y consulta estado, salud, fase, entregables, bugs o cláusula contractual. La respuesta muestra sólo hechos autorizados, fuentes internas y fecha de verificación; una respuesta histórica puede aparecer como desactualizada, una reconsulta crea una nueva consulta y una respuesta revocada queda no disponible.

| Resultado | Interacción y evidencia |
|---|---|
| display | Abrir Appi desde el lanzador, navegar por el selector de proyecto y comprobar texto de respuesta, fuente interna y fecha de verificación; comprobar las marcas desactualizada y no disponible con datos reales del fixture. |
| success | Enviar una consulta válida sobre el proyecto propio, esperar su resultado y usar Consultar de nuevo; la nueva fila conserva el historial anterior y actualiza el marcador de cuota. |
| error | Intentar consultar con una conversación o proyecto que ya no está disponible; la interfaz conserva los demás mensajes y no muestra datos ajenos. |
| failure | Simular el fallo del procesamiento o de la lectura durante el sondeo; se muestra el estado de fallo y Reintentar, sin presentar una respuesta inventada. |
