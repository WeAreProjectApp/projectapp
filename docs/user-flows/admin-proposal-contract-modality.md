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

#### Formularios compactos y listas flotantes

Crear y editar contrato único, producto o servicio comparten un ancho máximo de
42 rem. Nombre/email, identificaciones, banco/tipo y ciudad/fecha se agrupan;
los dos preavisos comparten fila. Bajo 640 px los campos se apilan en orden de
lectura. Markdown conserva su editor y la vista previa amplia.

Los tres datos del servicio usan listas visuales sin buscador, con opción
seleccionada marcada. Flechas, Inicio/Fin y Enter permiten elegir; Escape
cierra primero la lista y recupera el foco, y Tab sale sin modificar el valor.
Personalizar lleva el foco al texto auxiliar y mantiene la redacción literal.
Las listas flotan dentro del área visible y también se bloquean al guardar.

Verificación: `admin-contract-modal-layout.spec.js` cubre creación y reapertura
de las tres variantes, geometría y selección personalizada en los cinco
viewports del panel. Los errores y reintentos siguen cubiertos por
`admin-proposal-contract-modality.spec.js`.

#### Condiciones económicas y regeneración

En modalidad separada, Documentos explica que hosting, cobertura, cortesía,
precios y renovación pertenecen al contrato de servicio. El anexo comercial
queda centrado en el producto y su forma de pago. El modal de servicio avisa que
las condiciones se incorporan automáticamente tanto con plantilla como con texto
personalizado. Presenta los tres periodos disponibles sin elegir por el cliente.

- **Success:** el aviso de contrato desactualizado permite abrir **Regenerar
  contrato**, guardar la variante de servicio y recuperar el documento vigente.
- **Error:** si faltan condiciones económicas para generar, el servidor lo
  explica y el modal conserva los datos; no cambia parcialmente la modalidad.
- **Failure:** un contrato de servicio obsoleto impide preparar su adjunto de
  formalización hasta regenerarlo. Las preparaciones anteriores requieren revisión.
- **Display:** el aviso pertenece sólo a la fila del servicio desactualizado.
  Los documentos de propuestas cerradas conservan su historial.

Verificación: `admin-proposal-contract-modality.spec.js` recorre el aviso y la
regeneración; las pruebas backend verifican importes, ausencia del hosting en
el anexo comercial separado, rechazo de datos incompletos y de adjuntos obsoletos.
