### FLOW: `admin-proposal-formalization-delivery`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/proposals/:id/edit` → Documentos
- **Recorrido:** abrir una propuesta desde el panel; entrar en Documentos; descargar o previsualizar anexos que conservan el contenido original (comercial sin seis secciones de presentación y cierre; técnico completo); abrir Formalización; elegir contrato final, anexos y adjuntos propios; editar Para/CC, asunto y secciones; preparar; revisar correo y archivos exactos; enviar.
- **Display:** contenido real de la propuesta, plantilla precargada, disponibilidad, destinatarios y manifiesto de archivos preparados.
- **Success:** preparar una selección válida, revisar sus bytes y enviarla; aparece confirmación y evidencia en Correos.
- **Error:** datos requeridos o adjuntos no disponibles impiden preparar; revisión obsoleta, del formato anterior de anexos, vencida o consumida muestra un error accionable.
- **Failure:** falla de carga o preparación conserva el formulario; resultado incierto de envío consulta el estado y evita un segundo envío automático.
- **Límites:** preparación privada de 24 horas, hasta 20 secciones y 10 destinatarios; sin transición automática del estado comercial.
