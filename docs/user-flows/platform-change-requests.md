### Platform: solicitudes de cambio contextualizadas

El cliente crea una solicitud sobre un requerimiento publicado. El origen conserva
contrato, otrosí, alcance, fase, etapa, publicación, ronda y versión. Las respuestas
y documentos del equipo se guardan separados de las guías y sus aprobaciones.

Entrada después de iniciar sesión: `/es-co/platform/projects`; abrir el proyecto,
la pestaña Solicitudes y el ticket mediante la interfaz.

| Resultado | Interacción | Evidencia esperada |
|---|---|---|
| display | Abrir Solicitudes de cambio desde el proyecto. | Estado, prioridad, origen congelado, comentarios, respuestas y adjuntos. |
| success | Seleccionar una guía publicada y enviar título/descripción. | Solicitud pendiente con el contexto original. |
| success | Evaluar o responder con documentos opcionales. | Historia y evidencia privada conservadas; no cambia la guía fuente. |
| success | Convertir una solicitud aprobada. | Requerimiento nuevo y pendiente, vinculado a una etapa editable explícita del contrato aplicable. |
| error | Crear sin título/requerimiento o convertir una solicitud ya vinculada. | Validación; no se duplica ninguna guía. |
| error | Seleccionar etapa de otro contrato o documento de otro contexto. | Rechazo sin cambiar el ticket ni la entrega. |
| failure | API, descarga o conflicto de versión. | Error visible y estado anterior conservado; recargar antes de continuar. |

El cliente sólo consulta solicitudes de sus proyectos. Los comentarios no amplían
el alcance. La aprobación de una solicitud no constituye aceptación de una guía;
la conversión no publica ni aprueba el nuevo requerimiento. La revisión contractual
por fuentes/prompts depende de P3 y permanece indeterminada mientras falte ese
adaptador. `/platform/changes` redirige a proyectos.

Código: `frontend/pages/platform/projects/[id]/changes.vue`, componentes
`frontend/components/platform/issues/`, servicios `backend/accounts/services/issue_*.py`.
