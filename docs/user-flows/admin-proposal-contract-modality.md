### FLOW: `admin-proposal-contract-modality`

- **Módulo:** admin
- **Rol:** admin
- **Prioridad:** P1
- **Ruta:** `/panel/proposals/:id/edit` → Documentos; Seguimiento → Historial.
- **Recorrido:** elegir contrato único o producto y servicio en cualquier estado. Fuera de negociación, escribir nota, completar los tres plazos del servicio si corresponde, revisar qué contratos se crearán, trasladarán o archivarán y confirmar o cancelar.
- **Display:** selector disponible en todos los estados; cada contrato indica plantilla o personalizado. La vista previa advierte sobre documentos anteriores enviados o firmados. Historial ofrece instantáneas permanentes con Markdown, descarga PDF y restauración.
- **Success:** confirmar activa los contratos elegidos, conserva exactamente texto y PDF del personalizado trasladado y guarda primero una instantánea. Restaurar recupera contratos y parámetros anteriores, conserva el estado comercial y genera otra instantánea.
- **Error:** nota obligatoria fuera de negociación; split exige plazo inicial y ambos preavisos guardados o enviados expresamente, sin completar valores globales. Un conflicto entre personalizados exige resolución explícita. Los errores mantienen el borrador.
- **Failure:** un fallo no aplica cambios parciales. Una vista previa vencida, cancelada o cuyos documentos cambiaron no puede confirmarse; una confirmación repetida no duplica el cambio.
- **Límites:** conservar documentos, paquetes aprobados, firmas y envíos históricos. No enviar ni solicitar firma automáticamente, modificar plantillas o regenerar contratos de otras propuestas.

#### Datos del servicio configurables

Los formularios de creación y edición de contratos conservan sus opciones
globales. El cambio de modalidad exige los valores guardados o ingresados
expresamente, sin usar esas preselecciones. En creación y edición,
duración y ambos preavisos ofrecen opciones globales y **Personalizar**, que
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
