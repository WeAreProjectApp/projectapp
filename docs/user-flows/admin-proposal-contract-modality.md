### FLOW: `admin-proposal-contract-modality`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/proposals/:id/edit` → Documentos
- **Recorrido:** abrir una propuesta en negociación; en Documentos, elegir la modalidad de cierre (`Contrato único` o `Producto y servicio`); con la separación aparecen el contrato de producto y el de servicio; generar el de servicio con su duración inicial y sus dos preavisos; volver al contrato único cuando haga falta.
- **Display:** interruptor editable sólo en negociación y bloqueado con su motivo en aceptada o rechazada; oculto en enviada o vista. Cada contrato de la modalidad muestra copia, vista previa, descarga, borrador y parámetros propios.
- **Success:** el cambio se guarda al instante, confirma la modalidad y muestra sus documentos; generar el contrato de servicio envía sus tres datos y el documento queda disponible.
- **Error:** un rechazo del backend (fuera de negociación, plantilla sin texto de servicio) deja la modalidad anterior y explica el motivo; sin los tres datos del servicio el formulario no se envía.
- **Límites:** cambiar de modalidad no borra documentos; los de la otra modalidad no se sirven ni se sincronizan a la plataforma. La vista pública "Contrato y condiciones" sigue mostrando el contrato único.
