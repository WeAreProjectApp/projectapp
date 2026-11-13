### Panel: configuración de IA de Plataforma

Entrada: iniciar sesión como staff, abrir **Plataforma → Configuración de IA**.
IA y audio parten apagados. Su disponibilidad se configura en Feature flags y la excepción del cliente prevalece sobre el global.

| Resultado | Interacción | Evidencia esperada |
|---|---|---|
| success | Abrir la gestión central de disponibilidad. | El enlace lleva a Feature flags; no existen controles de activación duplicados. |
| success | Guardar una clave, elegir el redactor o un cupo global/cliente. | Sólo se informa presencia/versión de la clave; los dos canales comparten la política. |
| success | Editar, previsualizar o restaurar una plantilla. | Vista previa sin proveedor; guardar/restaurar crea una versión. |
| error | Previsualizar una plantilla con marcadores no permitidos. | Error visible, sin revisión nueva ni llamada al modelo. |
| failure | Guardar con error del servidor o versión antigua. | Error visible y formulario conservado para corregir o recargar. |
| display | Navegar desde Plataforma a la configuración y consultar valores. | Modelos por función, claves sin contenido, cupo 20/300 inicial y consumo. |

Código: `frontend/pages/panel/platform/ai.vue`, `frontend/stores/platform_ai_admin.js`,
`backend/accounts/views_ai.py`, `backend/content/mcp/platform_ai_tools.py`.
Los tests E2E sustituyen únicamente las respuestas de API; cifrado, versiones y
permisos se comprueban en integración backend.
