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

#### Datos del servicio configurables

Duración y ambos preavisos ofrecen opciones globales y **Personalizar**, que
muestra debajo un campo de texto libre. Las preselecciones iniciales son
9 meses / 60 / 60 días. Sólo las opciones frecuentes se envían como números;
el servidor guarda el texto personalizado literalmente. La duración incluye
su unidad; la plantilla añade días calendario a los preavisos.
Los contratos previos mantienen sus valores y los textos diferentes de las
opciones se abren editables. Alternar una opción conserva el borrador durante
esa apertura. La duración permite 100 caracteres y cada preaviso 60; vacíos,
espacios y textos demasiado largos muestran errores por campo.

- **Success:** personalizar los tres valores, guardar, recargar y reabrir
  recupera lo escrito; teclado y móvil permiten completar el mismo recorrido.
- **Error:** una validación rechazada mantiene el modal abierto con el borrador
  y el error junto al campo; corregir permite guardar.
- **Failure:** un fallo del servidor conserva el borrador y permite reintentar.
  Carga fallida o configuración inválida bloquea la generación por plantilla
  y ofrece Reintentar.
- **Guardado pendiente:** se bloquean envíos repetidos y cierre por Cancelar,
  Escape o backdrop hasta conocer el resultado.
