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
| success | Preparar respuesta contractual y revisar el texto final y fuentes antes de guardar. | Citas verificadas por el core y conclusión de alcance pública, sin procedencia privada para el cliente. |
| success | Convertir una solicitud aprobada. | Requerimiento nuevo y pendiente, vinculado a una etapa editable explícita del contrato aplicable. |
| error | Crear sin título/requerimiento o convertir una solicitud ya vinculada. | Validación; no se duplica ninguna guía. |
| error | Seleccionar etapa de otro contrato o documento de otro contexto. | Rechazo sin cambiar el ticket ni la entrega. |
| error | Reutilizar preparación ajena o con conversación/versiones antiguas. | No se crea respuesta ni modifica el ticket; preparar evidencia actualizada. |
| failure | API, descarga o conflicto de versión. | Error visible y estado anterior conservado; recargar antes de continuar. |

El cliente sólo consulta solicitudes de sus proyectos. Los comentarios no amplían
el alcance. La aprobación de una solicitud no constituye aceptación de una guía;
la conversión no publica ni aprueba el nuevo requerimiento. El motor de P3 exige
contrato, fuentes suficientes y revisión humana para concluir dentro/fuera del
alcance; los demás casos permanecen indeterminados. `/platform/changes` redirige a proyectos.

Código: `frontend/pages/platform/projects/[id]/changes.vue`, componentes
`frontend/components/platform/issues/`, servicios `backend/accounts/services/issue_*.py`.
