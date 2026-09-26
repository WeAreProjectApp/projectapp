### FLOW: `admin-document-create`

- **Module:** admin
- **Role:** admin
- **Priority:** P2
- **Routes:** `/panel/documents/create`
- **Description:** Crea un documento desde Markdown pegado (en un editor a todo el ancho con switch **Editar / Vista previa**) o cargado desde archivo. El bloque Identificación conserva la asociación opcional `ClientAutocomplete` (`doc-client-autocomplete`, con creación inline) + `ProjectSelect` (`doc-project-select`, `allowNoClient`): elegir primero el proyecto completa su cliente, elegir primero el cliente filtra los proyectos y limpiar el cliente limpia el proyecto. Una carpeta puede aportar su cliente/proyecto como valor heredado; sólo cuando no los declara se usa la sugerencia por mayoría estricta de documentos, siempre editable. El acceso compacto `doc-client-note-open` abre **Notas**: como todavía no existe un documento, la acción **Aplicar al borrador** y sus avisos explican que falta crearlo para guardar la colección privada.
- **Steps:**
  1. Admin navega a `/panel/documents/create`.
  2. La vista ofrece **Pegar Markdown** y **Cargar Archivo**.
  3. Admin completa el título y, opcionalmente, cliente/proyecto en cualquier orden.
  4. Admin puede abrir **Agregar notas**, completar los mensajes y agregar notas personalizadas. El modal advierte que aún no se guardan; sus textos crecen con el contenido y el pie fijo habilita **Aplicar al borrador** sólo cuando algo cambió.
  5. Admin pulsa **Aplicar al borrador**; la vista confirma que todavía falta crear el documento y muestra el estado compacto de la colección.
  6. En **Pegar Markdown**, escribe o pega contenido y cambia a **Vista previa** para revisarlo en el mismo espacio; en **Cargar Archivo**, selecciona un `.md` y revisa el contenido cargado.
  7. Admin pulsa **Crear Documento**. La fila de acciones sólo contiene **Cancelar → Crear Documento**, a la derecha y centrados, en la cabecera desde landscape y al pie por debajo.
  8. `POST /api/documents/create-from-markdown/` recibe markdown, asociaciones, presentación, los tres mensajes privados y `client_custom_notes` (lista vacía si se omitió).
  9. Al guardar, admin navega al editor del documento creado (`/panel/documents/:id/edit`).
- **Branches:**
  - [Display — notas] Cancelar cierra el modal sin aplicar el borrador; cada asunto, mensaje, título y contenido se puede copiar por separado con `📋`.
  - [Display — persistencia] El modal y la notificación posterior nombran el documento pendiente; aplicar al borrador no llama al servidor.
  - [Error — nota incompleta] Una nota personalizada sin título o contenido no se puede aplicar y muestra validación inline.
  - [Display — preview] **Vista previa** reemplaza al editor en su misma caja y **Editar** vuelve al texto sin perder el markdown.
  - [Success — asociación] El payload siempre lleva `client`/`project`, incluido `null`; una asociación heredada o sugerida nunca bloquea la edición manual.
  - [Error — validación] **Crear Documento** sigue disponible. Al pulsarlo sin título o sin contenido, cada aviso aparece bajo su campo (también en **Cargar Archivo**), lo marca inválido y lleva el foco al primero; no se llama al servidor y el aviso se retira al completar el campo. Un rechazo 400 de `title` o `markdown` se muestra bajo su campo; el resto de rechazos sigue en la notificación, y el admin permanece en la página de creación.
  - [Failure — servidor] Un fallo 5xx conserva todas las notas en el formulario para reintentar sin volver a redactarlas.
- **Coverage:** ✅ Covered (paste, carga de archivo, asociaciones y notas privadas en display/success/error/failure; las casillas de portada y el estilo viajan en el mismo payload, pero se auditan en sus flows específicos).
- **E2E Spec:** `e2e/admin/admin-document-create.spec.js`
