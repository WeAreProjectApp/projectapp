### FLOW: `admin-client-communications`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Routes:** `/panel/communications`
- **API:** `GET/POST /api/communications/threads/`, `POST /api/communications/threads/tab-counts/`, `GET /api/communications/threads/:id/`, `POST /api/communications/threads/:id/messages/`, `GET/PATCH /api/accounts/panel-preferences/communications/`, `POST /api/accounts/panel-preferences/communications/reset/`, `/api/accounts/saved-filter-tabs/`, `POST /api/accounts/saved-filter-tabs/reset/`
- **Description:** El administrador abre «Configuraciones» junto a «Nuevo hilo» y administra preferencias personales de navegación, orden, paginación, canal inicial, ayuda y ancho, persistidas por cuenta entre dispositivos. La navegación enumera todos los proyectos aunque tengan cero hilos, conserva PRUEBA entre los activos y ubica Candle en «Proyectos archivados» por su ciclo. También identifica y busca varios hilos mediante resúmenes compactos de título y metadata, sin contenido del mensaje ni desplazamiento horizontal, navega por proyecto, cliente o «Sin proyecto», aplica filtros prediseñados con conteos completos, combina criterios y guarda recortes propios diferenciados. La tira se puede restablecer sin borrar las vistas propias; el contenido completo permanece en el detalle modal y cada hilo conserva mensajes entrantes o salientes con canal, fecha, estado y documentos referenciados.
- **Steps:**
  1. El administrador entra a Comunicaciones desde el panel y navega por proyectos o clientes en un panel ajustable, con conteos que incluyen sus hilos.
  2. Encuentra «Configuraciones» inmediatamente al lado de «Nuevo hilo» y abre una pantalla interna que sustituye temporalmente el listado sin perder su contexto.
  3. Define navegación inicial, orden, hilos por página, ancho lateral, canal inicial y visibilidad de la ayuda; guarda sólo los cambios y los recupera al volver, incluso desde otro dispositivo.
  4. Puede descartar cambios pendientes, restablecer las preferencias personales o restablecer las pestañas de fábrica sin eliminar sus vistas propias.
  5. Identifica cada hilo por asunto, cliente, proyecto, canal, estado, cantidad, fecha y borradores; el cuerpo de los mensajes no aparece en el índice.
  6. Cambia entre recientes, antiguos o alfabético y recupera el criterio activo al volver al listado; una URL o vista guardada explícita conserva prioridad.
  7. Elige «Sin proyecto» cuando necesita consultar conversaciones todavía no asociadas a uno y busca por cliente, proyecto, asunto o contenido.
  8. Elige de un clic un recorte prediseñado —primero «Borradores pendientes»— y consulta su conteo aunque sea cero; «Enviados sin respuesta» limita el resultado a hilos abiertos con salidas enviadas todavía no respondidas.
  9. Combina varios valores dentro de un filtro, guarda el recorte con nombre como vista propia y reordena la tira según su uso.
  10. Ajusta el ancho de la navegación para leer nombres largos y recupera ese ancho en otra visita.
  11. Selecciona un hilo; el detalle se abre sobre la lista y muestra la línea de tiempo, sus estados y documentos referenciados.
  12. Cierra el aviso del registro manual y puede reabrirlo desde la ayuda contextual.
  13. Escribe o pega el texto exacto y registra una salida como borrador o enviada, o una entrada como recibida; los mensajes nuevos parten del canal personal y las respuestas conservan el canal original.
  14. Cierra el detalle o vuelve atrás y recupera el mismo contexto de navegación y filtros.
- **Branches:**
  - [Branch A — Display] La navegación muestra el catálogo completo de proyectos y clientes, incluidos proyectos con conteo cero, PRUEBA activo, Candle archivado y «Sin proyecto»; el modal presenta juntos lo enviado, lo recibido y los documentos referenciados.
  - [Branch B — Resumen compacto] En viewport angosto aparecen varias tarjetas identificables sólo por el título y la metadata operativa, sin contenido del mensaje ni desplazamiento horizontal interno.
  - [Branch C — Orden persistente] El criterio elegido se guarda en la cuenta, queda activo y vuelve a aplicarse en una visita posterior sin parámetro explícito en la URL.
  - [Branch D — Conteos prediseñados] Todos los filtros de fábrica muestran su conteo, incluido cero.
  - [Branch E — Sin respuesta] El recorte aplica estado abierto, salida enviada y ausencia de respuesta.
  - [Branch F — Configuración y restablecimiento] La acción adyacente a «Nuevo hilo» abre la pantalla interna y permite restaurar preferencias o prediseñados sin borrar ni alterar las vistas propias.
  - [Branch G — Recorte guardado] La selección por cliente y los estados múltiples se guardan y restauran como una vista identificada como «Propia».
  - [Branch H — Búsqueda] La consulta global encuentra por cliente, proyecto, asunto o contenido sin perder el alcance activo.
  - [Branch I — Alcance de canal] El cierre del aviso se guarda en la cuenta al recargar y puede reabrirse desde ayuda.
  - [Branch J — Navegación ajustable] El panel lateral guarda el ancho elegido en la cuenta y permite leer nombres largos.
  - [Branch K — Preferencias personales] Canal y paginación se guardan explícitamente, sobreviven otra visita y el canal elegido inicia el siguiente mensaje nuevo.
  - [Branch L — Registro exitoso] Un mensaje saliente queda con estado `sent`, canal preferido y fecha explícita.
  - [Branch M — Error de negocio] La API rechaza el registro y el panel conserva el texto, mostrando la razón.
  - [Branch N — Fallo de carga] El listado no está disponible y el panel mantiene un reintento visible.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-client-communications.spec.js`
- **Unit Tests:** `test/components/CommunicationSettingsPanel.spec.js`, `test/components/CommunicationThreadTable.spec.js`, `test/composables/useCommunicationFilters.spec.js`, `test/composables/useCommunicationPanelWidth.spec.js`, `test/stores/communicationPreferences.test.js`, `test/stores/communications.test.js`
- **Backend Tests:** `accounts/tests/test_communication_panel_preferences.py`, `content/tests/views/test_communication_views.py`, `content/tests/views/test_communication_filters.py`

- **Lectura e identificación (2026-09-25):** buscar `#ID` exacto o número junto al texto; IDs visibles en lista, hilo, mensajes y documentos vinculados. Ir al inicio/final desplaza sólo el histórico. La redacción empieza plegada con mensajes existentes; Responder/Editar borrador la abre. Detalles del mensaje y formulario conservan valores al plegarse. Copiar es un icono directo; Marcar enviado vive en Más.

- **Formato editorial:** La redacción admite Visual y Fuente, con perfiles de correo y WhatsApp y copia adaptada al canal; conserva contenido y formato al guardar o ante un error. WhatsApp utiliza únicamente sus marcas nativas.
- **E2E editorial:** `e2e/admin/editorial-rich-text-communications.spec.js` (correo, WhatsApp y conservación ante rechazo).
