### FLOW: `platform-appi-private-history`

- **Módulo:** platform
- **Prioridad:** P1
- **Rol:** platform-client
- **E2E:** `frontend/e2e/platform/platform-appi.spec.js`

Cliente abre sus conversaciones privadas de Appi, cambia entre ellas, carga mensajes anteriores y puede borrar una conversación tras confirmarlo. El historial conserva sólo sus consultas durante 90 días, no aparece después de vencer y nunca revela conversaciones, preguntas ni respuestas de otra cuenta o de un proyecto que dejó de pertenecerle.

| Resultado | Interacción y evidencia |
|---|---|
| display | Abrir el selector de historial desde Appi y comprobar títulos propios, mensajes paginados y la ausencia de conversaciones vencidas, ajenas o revocadas. |
| success | Elegir una conversación propia, cargar mensajes anteriores y borrar otra mediante la confirmación; la conversación desaparece y el cupo consumido no se restablece. |
| error | Solicitar una conversación inexistente o que dejó de ser accesible; la interfaz muestra el error y conserva el historial que sí pertenece al cliente. |
| failure | Fallar la carga o el borrado; la conversación no desaparece localmente y aparece el aviso de error sin afirmar que fue eliminada. |
