### Panel: configuración de IA de Plataforma

Entrada: iniciar sesión como staff, abrir **Plataforma → Configuración de IA**.
Las dos funciones empiezan apagadas y el global apagado prevalece sobre el cliente.

| Resultado | Interacción | Evidencia esperada |
|---|---|---|
| success | Cambiar activación y guardar. | Se conserva la configuración confirmada y se muestra confirmación. |
| success | Guardar una clave, elegir el redactor o un cupo global/cliente. | Sólo se informa presencia/versión de la clave; los dos canales comparten la política. |
| success | Editar, previsualizar o restaurar una plantilla. | Vista previa sin proveedor; guardar/restaurar crea una versión. |
| error | Previsualizar una plantilla con marcadores no permitidos. | Error visible, sin revisión nueva ni llamada al modelo. |
| failure | Guardar con error del servidor o versión antigua. | Error visible y formulario conservado para corregir o recargar. |
| display | Navegar desde Plataforma a la configuración y consultar valores. | Modelos por función, claves sin contenido, cupo 20/300 inicial y consumo. |

Código: `frontend/pages/panel/platform/ai.vue`, `frontend/stores/platform_ai_admin.js`,
`backend/accounts/views_ai.py`, `backend/content/mcp/platform_ai_tools.py`.
Los tests E2E sustituyen únicamente las respuestas de API; cifrado, versiones y
permisos se comprueban en integración backend.
