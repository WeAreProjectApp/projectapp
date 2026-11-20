### FLOW: `admin-document-navigation`

- **Module:** admin
- **Role:** admin
- **Priority:** P1
- **Route:** `/panel/documents`
- **API:** `GET /api/documents/navigation/`, `GET/PATCH /api/accounts/panel-preferences/documents/`, `GET /api/documents/`, `GET /api/document-folders/`
- **Description:** El administrador recorre el gestor por proyecto o por cliente con el mismo interruptor y en la misma posición que Comunicaciones. El catálogo muestra por defecto sólo proyectos operativos —incluido PRUEBA aunque tenga inventario cero— y «Ver proyectos no activos» es excluyente: encendido deja ver sólo el grupo donde aparece Candle y retira los activos del catálogo, sin archivar ningún documento. Este control local de la visita es independiente de «Ver documentos archivados», que cambia el ámbito de carpetas/documentos y se ubica justo antes de «Carpetas propias». Cada entrada muestra por separado cuántas carpetas y documentos tiene en el ámbito activo, archivado o combinado. «Sin proyecto» y «Sin cliente» permanecen visibles incluso con cero elementos. Al descender por las carpetas de una entidad, esa entidad sigue seleccionada y forma parte del origen al abrir un documento, de modo que «Volver» restaura el mismo recorrido. La preferencia se guarda por cuenta, mientras `?by=` permite compartir una visita sin cambiar esa memoria. «Carpetas propias» contiene exclusivamente raíces sin proyecto ni cliente; la conciliación es una tarea operativa interna y no genera avisos técnicos en esta navegación.
- **Steps:**
  1. El administrador entra al Gestor Documental y encuentra el interruptor Proyectos/Clientes encima de la navegación lateral.
  2. Recorre los proyectos operativos y activa «Ver proyectos no activos» cuando necesita consultar ese grupo; en cualquiera de los dos giros, un proyecto seleccionado que deje de listarse devuelve la selección a «Todos».
  3. Elige un proyecto o «Sin proyecto» y el listado consulta únicamente esa asociación.
  4. Dentro de un proyecto, abre una subcarpeta y luego un documento; al regresar desde el editor recupera la subcarpeta con el proyecto todavía seleccionado.
  5. Cambia a Clientes, elige una persona o «Sin cliente» y consulta su inventario.
  6. Recarga o abre el enlace guardado de Clientes: recupera el cliente, la carpeta y el foco del documento. Al entrar sin enlace, reaparece el último modo elegido.
  7. Abre una carpeta propia; la navegación limpia cualquier proyecto o cliente previamente seleccionado.
- **Branches:**
  - [Branch A — Display] Cada entidad declara conteos separados de carpetas y documentos; los proyectos no operativos están ocultos al entrar y, mientras su control excluyente está encendido, son los únicos que se listan. Los clientes archivados tienen su propio grupo secundario, y desde el 31-ago-2026 el mismo interruptor excluyente lo gobierna: en modo cliente se rotula «Ver clientes archivados» y, apagado, los archivados no se listan.
  - [Branch B — Sin asignar] Las entradas «Sin proyecto»/«Sin cliente» existen permanentemente y filtran los registros sin esa asociación.
  - [Branch C — Memoria] Un cambio desde el interruptor hace `PATCH`; una visita posterior hidrata el modo mediante `GET`. Un `?by=` explícito sólo gobierna esa visita.
  - [Branch D — Carpetas propias] La sección manual no cambia al alternar el eje, excluye raíces que ya tengan proyecto o cliente y sigue navegable si falla la carga de facetas.
  - [Branch E — Contexto y ejes excluyentes] Elegir proyecto limpia cliente y elegir cliente limpia proyecto. Las carpetas descendientes de la entidad conservan el eje activo y ese origen sobrevive al ciclo documento→editor→volver; entrar a una carpeta propia o ajena limpia ambos ejes, sin enviar intersecciones accidentales.
  - [Branch F — Fallo recuperable] Un 5xx de `/documents/navigation/` muestra una explicación con «Reintentar» sin bloquear el resto del gestor.
  - [Branch G — Ámbitos independientes] «Ver proyectos no activos» no altera `scope`; «Ver documentos archivados» sigue filtrando contenido activo/archivado en cualquier proyecto, cliente o carpeta propia.
- **Coverage:** ✅ Covered
- **E2E Spec:** `e2e/admin/admin-document-navigation.spec.js`
- **Unit Tests:** `test/utils/documentNavigationFilters.test.js`, `test/components/FolderSidebar.spec.js`, `test/stores/document_navigation.test.js`, `test/composables/useDocumentFilterQuery.test.js`
- **Backend Tests:** `content/tests/views/test_document_navigation.py`, `accounts/tests/test_document_panel_preferences.py`
