### Platform: reportar y seguir bugs de proyecto

El cliente puede reportar un bug general aunque no existan guías publicadas. Si
elige una entrega, el ticket conserva contrato, otrosí, alcance, fase, etapa,
publicación, ronda y versión del requerimiento originales. Los datos, pasos,
resultado esperado/real, entorno, pantallazo y comentarios permanecen en el ticket.

Entrada después de iniciar sesión: `/es-co/platform/projects`; abrir el proyecto,
la pestaña Bugs y el ticket mediante la interfaz.

| Resultado | Interacción | Evidencia esperada |
|---|---|---|
| display | Abrir Bugs desde un proyecto y consultar el detalle. | Origen general, publicado o legado; respuestas, PDFs e historia visibles según el rol. |
| success | Reportar con título, sin guía seleccionada. | Bug general reportado; no se exige contrato ni etapa. |
| success | Reportar desde una entrega publicada. | La guía autocompleta los datos vacíos; queda congelada la publicación seleccionada. |
| success | El equipo responde y marca «Resuelto por equipo». | Respuesta y documentos opcionales quedan en la historia; no cambia ninguna aprobación. |
| success | Seleccionar fuentes, preparar y verificar borrador, revisar texto final y guardar. | Citas verificadas por el motor compartido; conclusión de alcance pública y procedencia privada conservada. |
| success | El cliente explica «Sigue fallando». | Comentario público y reapertura a Reportado; se conservan respuestas anteriores. |
| error | Enviar sin título o reabrir sin explicación. | Validación visible; el estado no cambia. |
| error | Usar un documento, contrato o requerimiento de otro contexto. | Rechazo sin guardar respuesta, adjunto ni cambio de estado. |
| error | Guardar sin revisión humana o con conversación/versiones antiguas. | No se crea respuesta ni cambia el estado; preparar un contexto actualizado. |
| failure | Responder con una versión antigua o fallar la API/descarga. | Error visible y datos anteriores conservados; el cliente puede recargar y reintentar. |

El administrador puede evaluar, comentar y archivar. El cliente sólo opera sus
proyectos y no recibe notas ni adjuntos internos. Un PDF se descarga mediante JWT
y conserva los bytes adjuntos aunque el documento fuente cambie después.

La revisión contractual usa el motor de P3. Sin contrato o fuentes suficientes,
el resultado sigue indeterminado; preparar no modifica estados. El cliente no
recibe fuentes, citas ni contexto privado de autoría. La ruta global
`/platform/bugs` redirige a proyectos.

Código: `frontend/pages/platform/projects/[id]/bugs.vue`, componentes
`frontend/components/platform/issues/`, servicios `backend/accounts/services/issue_*.py`.
