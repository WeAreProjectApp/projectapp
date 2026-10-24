### FLOW: `platform-appi-guidance-boundary`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-appi.spec.js`

Cliente usa Appi para pedir pasos de la plataforma, como reportar un bug, y recibe una guía editable con enlace interno permitido. Las guías globales funcionan sin proyecto; las guías de un proyecto piden seleccionarlo. Preguntas fuera del universo de proyecto y uso de la plataforma reciben la respuesta respetuosa de alcance, sin ofrecer información general ni enlaces externos.

| Resultado | Interacción y evidencia |
|---|---|
| display | Abrir Appi sin proyecto y comprobar sugerencias y propósito finito; al elegir un proyecto, comprobar las sugerencias adicionales relacionadas con estado, salud y bugs. |
| success | Preguntar cómo reportar un bug, verificar el paso a paso y abrir el enlace interno de Reporte de bugs desde la respuesta. |
| error | Pedir una guía que necesita proyecto cuando está seleccionado Todos mis proyectos; Appi explica que debe elegirse un proyecto y no entrega un enlace ambiguo. |
| failure | Fallar la petición de la guía o de sus capacidades; se conserva la pregunta y se muestra el error de la interfaz, sin sustituirla por una guía de otro proyecto. |
