# Formato editorial — contrato v1

## Herramienta elegida

Se utiliza **Tiptap 3.32.0**, con `@tiptap/vue-3`, ProseMirror y extensiones
open source fijadas a esa versión. La integración es local, sin servicios de
pago ni extensiones Pro. El editor se crea al montar el componente en el
navegador; el backend conserva su propio validador y renderizador.

La elección favorece su integración oficial con Vue 3, su esquema extensible
y el soporte de tablas y alineación que necesita ProjectApp. El núcleo declara
licencia MIT y el repositorio público muestra una comunidad activa. Fuentes
primarias consultadas el 23-10-2026:
[Vue 3](https://tiptap.dev/docs/editor/getting-started/install/vue3),
[licencia del núcleo](https://github.com/ueberdosis/tiptap/blob/main/packages/core/README.md),
[tablas](https://tiptap.dev/docs/editor/extensions/nodes/table),
[alineación](https://tiptap.dev/docs/editor/extensions/functionality/textalign).

| Alternativa considerada | Decisión para este proyecto |
| --- | --- |
| Tiptap | Elegido: Vue oficial, esquema extensible y extensiones gratuitas para los formatos requeridos. |
| Quill | Su catálogo oficial de formatos cubre texto, listas y alineación; las tablas requieren una integración adicional. [Formatos oficiales](https://quilljs.com/docs/formats). |
| CKEditor 5 | Su distribución abierta es GPL 2+ y ofrece distribución comercial; se prefirió la licencia MIT del núcleo elegido. [Licencias oficiales](https://ckeditor.com/legal/ckeditor-licensing-options/). |

El Markdown beta de Tiptap no forma parte de esta integración. La conversión
se controla mediante una gramática versionada, un corpus compartido y pruebas
con valores esperados independientes de los convertidores.

## Una fuente editable

Visual y Fuente operan sobre **una sola cadena**. El documento Tiptap es una
representación temporal en memoria; no se persisten dos cuerpos editables.
Alternar sin editar no reescribe la fuente. Editar puede normalizar delimitadores,
atributos o espacios estructurales, conservando texto, estructura y estilos.
Bloquear el control durante un guardado no publica una edición. Si el servidor
rechaza el guardado, el borrador Fuente conserva su contenido y su formato;
el documento visual anterior no puede reemplazarlo mediante un evento de estado.

Cada agregado editorial añade un `text_formats` opcional, con hasta 1000 rutas
JSON Pointer. La ausencia de una anotación conserva la interpretación histórica.
Los formatos admitidos son `plain`, `markdown`, `markdown_html_v1` y
`whatsapp_v1`. Dos anotaciones para un mismo texto deben coincidir.

```json
{
  "client_email_body": "**Aprobado**\n\n- Diseño\n- Desarrollo",
  "client_whatsapp_message": "*Aprobado*\n- Diseño\n- Desarrollo",
  "text_formats": {
    "/client_email_body": "markdown_html_v1",
    "/client_whatsapp_message": "whatsapp_v1"
  }
}
```

Dentro de contenido estructurado se prefieren mapas relativos al objeto que
contiene el texto. Los elementos de una lista conservan su posición y su
estructura, aunque un elemento contenga a su vez una tabla o una lista.

```json
{
  "introText": "Introducción",
  "steps": [
    {
      "title": "Preparación",
      "bullets": ["**Revisar** el alcance", "Confirmar responsables"],
      "text_formats": {"/bullets/0": "markdown_html_v1"}
    }
  ]
}
```

Las rutas externas a contenido JSON se resuelven también en sus lectores y
PDF. El formulario conserva los mapas en ambas proyecciones JSON ↔ formulario.
Al abrir contenido anotado desde MCP, el formulario mueve las declaraciones a
su objeto local en una copia: guardar una edición reemplaza la declaración
anterior, sin dejar dos formatos que compitan por el mismo texto. Las plantillas,
duplicaciones y restauraciones conservan estas declaraciones; una plantilla sin
formato limpia las anotaciones de la versión anterior. Las actualizaciones
agrupadas de diagnósticos validan todas las secciones antes de guardar alguna.
Eliminar o filtrar elementos remapea sus anotaciones. El historial incluye el
formato junto con la fuente; las preparaciones formales nuevas usan el hash v5.
Las revisiones confirmadas conservan los archivos y la fuente que se congelaron.

## Gramática

CommonMark con tablas y tachado; HTML limitado representa estilos que Markdown
no expresa. Se conservan `[TOC]`, avisos `[!NOTE/TIP/IMPORTANT/WARNING/CAUTION]`,
variables y código. Los estilos se serializan como HTML completo del bloque:
Markdown escrito dentro de un bloque HTML conserva la semántica normal de
HTML/CommonMark; para negrita dentro de ese bloque se usa `<strong>`.

| Construcción | Representación |
| --- | --- |
| Negrita, cursiva, tachado, encabezados, citas, listas, enlaces, código | Markdown cuando conserva la estructura |
| Tablas simples | Markdown o HTML, según su estructura |
| Subrayado | `u` |
| Color | `span` con `color` |
| Resaltado | `mark` con `background-color` |
| Izquierda, centro, derecha, justificado | `text-align` en `p`, `h1`–`h6`, `td` o `th` |
| Tablas combinadas | `table/thead/tbody/tfoot/tr/th/td`, con `colspan` y `rowspan` acotados |

Se admiten `p/br/h1`–`h6`, `strong/b/em/i/u/s/del/strike/span/mark/a`,
`ul/ol/li`, `blockquote/pre/code`, `hr` y las etiquetas de tabla anteriores.
`div` se reserva al bloque `[TOC]`. No se aceptan scripts, eventos, recursos
embebidos, imágenes, comentarios ni CSS libre. Los colores se normalizan a RGB;
se admiten hexadecimal, RGB válido y la paleta de nombres declarada en el código.
Los enlaces admiten http/https/mailto/tel o rutas relativas seguras.

Las escrituras con formato declarado validan antes de guardar. Las lecturas
históricas y el pegado HTML se sanean mediante un parser; nunca se renderiza HTML
sin validar. Si una conversión visual no puede conservar un bloque, se conserva
su fuente y se muestra el error para corregirlo. El perfil WhatsApp sólo ofrece
negrita, cursiva, tachado, código, citas y listas con su sintaxis propia. Un
borrador enriquecido conserva su canal para evitar reinterpretar su fuente.

## Inventario aplicado

| Módulo | Autoría y persistencia | Lectura y salidas |
| --- | --- | --- |
| Documentos | Cuerpo, correo preparado, WhatsApp, notas privadas y contenido de observaciones | Vista previa, hilo, copia rica, PDF, REST y MCP |
| Comunicaciones | Contenido de email y WhatsApp | Histórico, edición, copia y MCP; permisos y trazabilidad existentes |
| Correos | Composición general, seguimiento, diagnóstico, envío desde documentos y campos de plantilla | Vista previa de backend, HTML seguro, alternativa de texto, historial y MCP |
| Propuestas | Narrativas de secciones, listas estructuradas, detalle técnico, introducción y bloques del correo | Presentación pública, PDF comercial/técnico y formalización |
| Contratos | Fuentes Markdown editables de propuestas y adjuntos; contratos predeterminados mediante su flujo versionado | HTML limitado en lectura y PDF; espejos y revisiones conservan sus restricciones |
| Diagnósticos | Narrativas y elementos de secciones | Lectores públicos, PDF y MCP |
| Blog y portafolio | Blog visual/fuente y JSON editorial; el portafolio mantiene su autoría JSON | Lectura pública segura de campos y elementos; metadatos SEO siguen planos |
| Oferta | Notas de paquetes de requerimientos XS/S/M y descripciones/listas de módulos | Catálogo, detalle y PDF; límites de resumen y elementos se calculan sobre texto visible |
| Programas | Contenido bilingüe editado por MCP de Building with Us, Células y Consultoría | Lectores y PDFs; límites comerciales y alineación de idiomas conservados |

Se conservan como texto o código: JSON, prompts, diagramas, asuntos, títulos,
SEO, campos de contacto, notas contables, tareas/incidencias, credenciales,
justificaciones de auditoría y notas breves de cierre de estados/observaciones.
Los formularios públicos de contacto y los espacios operativos de plataforma no
se convierten en editores editoriales.

## MCP

Documentos, Comunicaciones, Comercial, Propuestas, Diagnósticos, Blog/Contenido,
Oferta/Módulos adicionales y Programas actualizan esquemas, instrucciones y
versiones. Los adaptadores reutilizan los serializers y servicios del panel.
`text_formats` tiene un esquema acotado explícito; los campos Markdown nativos
publican directamente la gramática `markdown_html_v1`. Las acciones sensibles
mantienen la confirmación transaccional existente.
El mapa es opcional y cerrado mediante un patrón de claves JSON Pointer, con
valores tipados y hasta 1000 entradas. Los demás campos requeridos de cada
operación conservan su obligatoriedad; añadir formato no obliga a los clientes
históricos a enviar metadatos.

Se verifica la paridad entre `initialize`, `server/discover`, `tools/list` y
`describe_capabilities`; sus huellas quedan fijadas en
`backend/content/mcp/connector_contracts.json`.

Versiones de esta entrega: Documentos 8.1.1, Comunicaciones 3.1.2, Comercial
6.3.0, Propuestas 6.1.1, Diagnósticos 2.1.1, Blog 2.1.1, Contenido 3.1.1,
Building with Us 3.1.1, Building on Demand 4.1.1, Módulos adicionales 4.1.2,
Oferta 2.1.0 y Programas 3.1.0. Los esquemas explícitos de módulos y paquetes
describen también sus argumentos y dejan de usar la excepción de esquema genérico.

## Pruebas y operación

El corpus compartido está en `docs/fixtures/editorial-format.json`.
Las pruebas abarcan cada formato, ambas direcciones, veinte alternancias,
combinaciones de marcas, listas anidadas, tablas alineadas, rechazo de CSS/HTML,
WhatsApp literal, serialización de formularios y persistencia real por MCP.
Correo y PDF verifican las salidas finales; la formalización comprueba que un
cambio de formato invalida la preparación sin modificar sus archivos congelados.

Las migraciones nuevas añaden metadatos vacíos a los registros existentes y
amplían la fuente de los resúmenes para que el marcado no consuma su límite
visible de 360 caracteres. Se incluyen en el PR; las aplica el despliegue. No
se reescriben masivamente contenidos ni se migran bases desde el worktree.

## Auditoría de flujos de esta entrega

El inventario estático quedó fresco y se regeneró el registro desde sus fuentes
por flujo. El audit concede crédito sólo a interacciones con resultados
observables; este crédito estático no sustituye la ejecución de navegador.

| Flujo modificado | Crédito del mapa | Resultados con evidencia existente |
| --- | --- | --- |
| admin-document-create | covered | display, success, error, failure |
| admin-document-edit | covered | display, success, error, failure |
| admin-client-communications | covered | display, success, error, failure |
| admin-send-proposal-email | covered | display, success, failure |
| admin-diagnostic-edit | partial | success |
| admin-blog-create | partial | display, success |
| admin-blog-edit | partial | display, success |

Las tres brechas de validación de formulario de diagnóstico/blog ya existían
en el mapa: no se las declara cerradas por incorporar el editor. El editor
compartido tiene cobertura propia de fuente inválida y conservación del borrador;
los seis E2E nuevos añaden guardado/reapertura, ambos canales, rechazo del
servidor y desplazamiento dentro de documentos largos. Los modos, estilos y
combinaciones se prueban también a nivel de
componente y del motor real Tiptap. El mapa completo registra 415 flujos
cubiertos, 28 parciales, cero junk-only y cero faltantes; 29 están exentos y
24 tests ajenos a esta entrega no conceden crédito por carecer de tags.

La revisión de rendimiento y sus límites de medición se conservan en
[el reporte editorial](performance/editorial-rich-text.md).
