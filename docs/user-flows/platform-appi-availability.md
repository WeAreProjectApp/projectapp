### FLOW: `platform-appi-availability`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-appi.spec.js`

Cliente ve el lanzador de Appi sólo cuando chatbot está habilitado globalmente y para su cuenta. Si faltan las claves o el proveedor necesario, el lanzador explica que no está disponible y no abre un chat; al recuperar disponibilidad, puede abrir Appi sin mezclar el estado privado de otra sesión.

| Resultado | Interacción y evidencia |
|---|---|
| display | Entrar por la navegación normal como cliente y comprobar que el lanzador se oculta cuando el global o el cliente están apagados, y queda deshabilitado cuando falta preparación del proveedor. |
| success | Con chatbot activo y disponible, abrir Appi desde el lanzador y comprobar que aparece el panel con su propósito y el campo de consulta. |
| error | Cambiar a una cuenta sin capacidad de chatbot y comprobar que no conserva conversaciones, borrador ni cuota de la cuenta anterior. |
| failure | Fallar la lectura de capacidades; no se abre un chat con estado incierto y el lanzador no permite una consulta facturable. |
