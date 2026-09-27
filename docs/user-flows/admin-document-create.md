### FLOW: `admin-document-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents/create`
- **Description:** Crea un documento desde Markdown pegado (en un editor a todo el ancho con switch **Editar / Vista previa**) o cargado desde archivo. El bloque Identificación conserva la asociación opcional `ClientAutocomplete` (`doc-client-autocomplete`, con creación inline) + `ProjectSelect` (`doc-project-select`, `allowNoClient`): elegir primero el proyecto completa su cliente, elegir primero el cliente filtra los proyectos y limpiar el cliente limpia el proyecto. Una carpeta puede aportar su cliente/proyecto como valor heredado; sólo cuando no los declara se usa la sugerencia por mayoría estricta de documentos, siempre editable. La carpeta se elige con `DocumentFolderSelect` (`doc-folder-select`), el mismo patrón de búsqueda de cliente y proyecto: filtra por nombre, ruta, cliente o proyecto y cada resultado muestra su ubicación, su dueño y el estado del proyecto cuando no está activo, porque los nombres se repiten por diseño (cada proyecto tiene su «Entregables»). Las carpetas del archivado automático no se ofrecen: el backend las rechaza como destino. El acceso compacto `doc-client-note-open` abre **Notas**: como todavía no existe un documento, la acción **Aplicar al borrador** y sus avisos explican que falta crearlo para guardar la colección privada.
- **Steps:**
  1. Admin navega a `/panel/documents/create`.
  2. La vista ofrece **Pegar Markdown** y **Cargar Archivo**.
  3. Admin completa el título y, opcionalmente, cliente/proyecto en cualquier orden.
  4. Opcionalmente abre **Carpeta**: ve el catálogo completo en el orden del panel lateral, escribe parte del nombre o de la ruta y elige; el campo muestra la ruta completa.
  5. Admin puede abrir **Agregar notas**, completar los mensajes y agregar notas personalizadas. El modal advierte que aún no se guardan; sus textos crecen con el contenido y el pie fijo habilita **Aplicar al borrador** sólo cuando algo cambió.
  6. Admin pulsa **Aplicar al borrador**; la vista confirma que todavía falta crear el documento y muestra el estado compacto de la colección.
  7. En **Pegar Markdown**, escribe o pega contenido y cambia a **Vista previa** para revisarlo en el mismo espacio; en **Cargar Archivo**, selecciona un `.md` y revisa el contenido cargado.
  8. Admin pulsa **Crear Documento**.
  9. `POST /api/documents/create-from-markdown/` recibe markdown, asociaciones, `folder_id`, presentación, los tres mensajes privados y `client_custom_notes` (lista vacía si se omitió).
  10. Al guardar, admin llega al editor del documento nuevo.
- **Branches:**
  - [Display — notas] Cancelar cierra el modal sin aplicar el borrador; cada asunto, mensaje, título y contenido se puede copiar por separado con `📋`.
  - [Display — persistencia] El modal y la notificación posterior nombran el documento pendiente; aplicar al borrador no llama al servidor.
  - [Error — nota incompleta] Una nota personalizada sin título o contenido no se puede aplicar y muestra validación inline.
  - [Display — preview] **Vista previa** reemplaza al editor en su misma caja y **Editar** vuelve al texto sin perder el markdown.
  - [Success — asociación] El payload siempre lleva `client`/`project`, incluido `null`; una asociación heredada o sugerida nunca bloquea la edición manual.
  - [Display — selector de carpeta] Cada resultado muestra ubicación · dueño · estado del proyecto (p. ej. «Kore · Kore SAS · Suspendido»); las carpetas automáticas (Cuentas de cobro, Propuestas y sus niveles) no aparecen.
  - [Success — búsqueda por ruta] Buscar «vastago entre» separa la «Entregables» de Vástago de la de Kore y el payload lleva su `folder_id`. La ✕ del selector quita la carpeta y retira el cliente que había heredado.
  - [Success — enlace desde carpeta automática] Un `?folder=` que apunta a una carpeta automática o archivada propone la carpeta manual más cercana hacia arriba y lo avisa con **Carpeta ajustada**; así el guardado no termina en 409.
  - [Failure — carpetas sin cargar] Si la lista de carpetas no llega, el selector dice **No se pudieron cargar las carpetas.** en lugar de fingir que no hay ninguna, y **Reintentar** la vuelve a pedir sin salir del formulario.
  - [Error — validación] Campos obligatorios faltantes o un rechazo 400 muestran errores y conservan al admin en la página de creación.
  - [Failure — servidor] Un fallo 5xx conserva todas las notas en el formulario para reintentar sin volver a redactarlas.
- **Coverage:** ✅ Covered (paste, carga de archivo, asociaciones, selector de carpeta y notas privadas en display/success/error/failure; las casillas de portada y el estilo viajan en el mismo payload, pero se auditan en sus flows específicos).
- **E2E Spec:** `e2e/admin/admin-document-create.spec.js`
