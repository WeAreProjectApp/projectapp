# Formalización de propuestas

En **Propuestas → editar → Documentos**, el administrador puede descargar los
anexos formales y preparar un correo para revisión y firma. Los anexos formales comparten los generadores, portadas y componentes visuales
de los PDF públicos comercial y técnico. Usan los datos guardados en la
propuesta y reglas de contenido explícitas: cambia lo que se incluye,
conservando la identidad visual del documento que ya conoce el cliente.

## Contenido curado

| Documento | Contenido incluido | Contenido excluido |
|---|---|---|
| Propuesta comercial formal | Cliente, proyecto, referencia y emisión; alcance y entregables incluidos con sus IDs; prestaciones concretas de diseño y acompañamiento; cronograma, etapas y aportes del cliente; inversión efectiva y moneda; hitos y medios de pago; condiciones guardadas de hosting, mantenimiento y soporte; condiciones de módulos incluidos; límites y cambios de alcance. | ROI y proyecciones de retorno, argumentos de venta, diagnósticos persuasivos, paquetes de ampliación, precios de alcance no seleccionado, urgencia, testimonios, badges de garantías, próximos pasos comerciales y llamadas a comprar. |
| Detalle técnico formal | Propósito, stack, arquitectura y modelo de datos; preparación técnica actual; épicas y requerimientos del alcance seleccionado, IDs, configuración, flujo de uso y referencias comerciales; API, integraciones incluidas y excluidas; ambientes y roles; seguridad, rendimiento, respaldos, calidad, pruebas y decisiones técnicas. | Evoluciones futuras ofrecidas como posibilidad, ampliaciones no seleccionadas, venta o ROI, URLs y nombres de bases de datos de ambientes y campos arbitrarios de credenciales. |
| Contrato de desarrollo | El PDF final ya generado desde los parámetros de contrato de la propuesta, con el tratamiento de firma existente. | La variante de contrato borrador. |
| Contrato de producto | En cierre separado: el PDF final del desarrollo e implementación del software (el contrato único sin las cláusulas 21–24). | El borrador y el contrato único, que ya no corresponde a la modalidad. |
| Contrato de servicio | En cierre separado: el PDF final del contrato autónomo de hosting, mantenimiento y soporte, con su duración inicial y sus preavisos. | El borrador y el contrato único. |

Los campos estructurados son la fuente. Una sección necesaria en modo de texto
pegado requiere completar sus campos antes de preparar ese anexo. No se extraen
compromisos automáticamente de texto comercial libre ni se inventan obligaciones
o criterios de aceptación. Las garantías y obligaciones remiten al contrato.

La selección funcional y los IDs normalizados se comparten entre anexos. Los
importes porcentuales se calculan sobre la inversión efectiva. Si hosting tiene
varias modalidades guardadas, se presentan como opciones de periodicidad, sin
afirmar que el cliente eligió una. No se refrescan catálogos al producir los PDFs.

## Presentación compartida

Markdown adapta las mismas proyecciones curadas (`formalization_blocks`):
conserva títulos y orden guardados, importes resueltos y condiciones de hosting,
sin volver a leer campos crudos ni recalcular la inversión. La migración `0256`
une el snapshot Markdown del contrato y el reajuste contractual incorporados
por las dos migraciones `0255`.

- La proyección de `FormalContent` entrega secciones comerciales y un payload
  técnico con campos permitidos. El adaptador `formalization_pdf` los pasa a
  `ProposalPdfService` y `generate_technical_document_pdf` mediante un contexto
  interno; los endpoints y las llamadas públicas conservan sus interfaces.
- Los renderers reutilizan tipografías, colores, portadas, índice y componentes.
  El comercial respeta el orden guardado de sus secciones habilitadas. Las
  exclusiones retiran también encabezados y columnas; no dejan tablas vacías.
- Los importes y condiciones formales llegan resueltos: no se refrescan catálogos,
  no se normaliza hosting y no se agregan cláusulas comerciales predeterminadas.
  Las filas extensas se dividen entre páginas y el índice conserva sus destinos
  cuando sus títulos requieren más de una página.
- Cliente, proyecto, referencia, emisión e IDs se conservan. Las nuevas
  preparaciones incluyen los títulos de sección en la huella de origen. Las
  anteriores conservan la versión original de esa huella y sus bytes revisados;
  el cambio visual no regenera adjuntos existentes.

## Modalidad de cierre

Durante la negociación, Documentos muestra **Modalidad de cierre**:

- **Contrato único** (valor por defecto y el de toda propuesta existente): el
  contrato de desarrollo con el servicio de hosting incluido en sus cláusulas
  21 a 24.
- **Producto y servicio**: dos documentos. El contrato de **producto** es el
  mismo contrato sin las cláusulas 21 a 24. Hay tres ajustes en las remisiones
  que las mencionaban: el protocolo de reporte en la garantía, el literal h) de
  hosting y la definición de día hábil. El contrato de **servicio** es autónomo,
  con esas cláusulas renumeradas y las generales que necesita. Sus tres datos
  propios (duración inicial, preaviso de no renovación y preaviso de terminación
  del cliente) se piden al generarlo.

El interruptor se usa sólo en negociación y queda visible, bloqueado, en
aceptada o rechazada. Cambiar de modalidad no borra documentos: los de la
modalidad elegida se regeneran con los datos vigentes, y los de la otra no se
sirven, no se adjuntan y no pasan a la plataforma. Cada documento puede usar el
texto estándar o uno personalizado, por separado. Una preparación de correo
hecha en la otra modalidad queda obsoleta.

### Opciones de los datos del servicio

La duración inicial ofrece 3, 6, 9 y 12 meses; ambos preavisos ofrecen 30, 60 y
90 días. Las preselecciones iniciales son **9 meses / 60 días / 60 días**.
Cada selector admite **Personalizar**: aparece debajo un campo de texto libre,
precargado con la opción vigente. Conserva el borrador al alternar opciones.
La duración admite hasta 100 caracteres e incluye la unidad; los preavisos
admiten hasta 60 y la plantilla agrega «días calendario». Las opciones frecuentes
siguen enviándose como números y el servidor las convierte a letras; el texto
personalizado se conserva literalmente.

En **Propuestas → Configuraciones → Datos del contrato de servicio** se
administran las dos listas y las tres preselecciones. Cada lista requiere
valores únicos y al menos una opción; sus preselecciones deben pertenecer a
ella. Guardar aplica el conjunto completo. Las nuevas aperturas consultan la
configuración vigente, mientras los contratos existentes conservan sus valores.
Un texto que no coincida exactamente con una opción abre **Personalizar** y
queda editable. Si falla la carga de configuración, la generación mediante
plantilla queda bloqueada y ofrece **Reintentar**.

El modal se cierra sólo después de guardar correctamente. Durante el envío se
bloquean nuevos envíos y el cierre. Ante un error de validación o del servidor,
conserva lo escrito, muestra la explicación y permite corregir o reintentar,
tanto desde el listado como desde el editor. El contenido Markdown personalizado
mantiene su flujo habitual y comparte esta protección del guardado.

## Preparar y enviar

1. Generar el contrato final (o los contratos de producto y servicio) desde
   Documentos y completar los datos de la propuesta.
2. Elegir **Preparar correo de formalización**. Todos los documentos de la
   modalidad empiezan seleccionados: el contrato único, o los contratos de
   producto y servicio, más los dos anexos. Se puede desmarcar cualquiera y
   agregar otros adjuntos de esa propuesta. Una selección incompleta indica qué
   corregir o desmarcar.
3. Revisar destinatarios y CC, asunto, introducción y cierre de la plantilla
   `proposal_formalization`. Agregar, reordenar o quitar secciones de texto o Markdown.
4. Elegir **Preparar vista previa**. Revisar el correo final y descargar o
   previsualizar cada PDF del manifiesto preparado.
5. Elegir **Enviar documentación**. La confirmación permanece visible hasta
   cerrar la ventana; el historial de Correos conserva el mensaje y los adjuntos.

## Revisión y entrega

- La revisión guarda una copia privada del HTML, texto y bytes de cada adjunto.
  El envío utiliza esas copias, sin regenerarlas después de la revisión.
- Sólo el administrador creador puede consultar o enviar esa preparación.
  El acceso vence a las 24 horas; la limpieza diaria retira sus archivos.
- Si cambia el origen o falta un archivo, se requiere preparar y revisar de nuevo.
  El formulario conserva el mensaje para hacerlo.
- Una preparación admite un único intento de entrega. Si el resultado es
  incierto, se consulta su estado y se indica revisar el historial; no se reenvía
  automáticamente. La limpieza concede una hora de margen a un envío en curso
  que atraviese el vencimiento.
- El gateway habitual conserva copias configuradas, destinatarios, evidencias e
  historial. Enviar estos documentos no cambia el estado de la propuesta.
- La migración `content.0249` crea las preparaciones y sus archivos privados.
  Sus modelos son temporales y quedan excluidos de fake data persistente. El MCP
  permite preparar, revisar y confirmar el envío de paquetes propios, aislados por
  credencial; no consulta preparaciones del panel. Ver [MCP de Propuestas](PROPOSALS_MCP.md).

## Copiar y consultar documentos

**Copiar Markdown** lleva al portapapeles el contenido del documento elegido.
Los anexos comercial y técnico usan los mismos datos guardados y filtros de sus
PDF. El contrato conserva su texto al generar el PDF: un cambio posterior de
plantilla no altera su copia. Los contratos anteriores sin snapshot usan el
texto del PDF guardado y avisan que su formato fue reconstruido.

Los adjuntos muestran acciones explícitas de vista previa, descarga del original
y copia. PDF conserva su visor; DOCX y XLSX presentan texto y tablas, sin reproducir
el diseño de Office. Las fórmulas se muestran como texto. Las imágenes se pueden
visualizar y descargar; copiar requiere OCR, fuera de este alcance. DOC y XLS
requieren conversión a los formatos modernos. Escaneos, archivos protegidos,
corruptos o sin texto muestran una explicación; no se copia una respuesta vacía.

La extracción ocurre bajo demanda en un proceso local con 256 MB de memoria,
8 segundos de CPU y 12 segundos de espera máxima. Rechaza archivos de más de
15 MB, PDF de más de 100 páginas, libros de más de 20.000 celdas, contenido
expandido de más de 50 MB o salidas de más de un millón de caracteres. Los
límites no truncan silenciosamente el texto. PDF con páginas sin texto avisa
cuáles requieren revisión. No hay consultas externas ni ejecución de macros.

La migración `content.0255` añade el snapshot interno `content_markdown` a
`ProposalDocument`; los registros existentes permanecen vacíos hasta una nueva
generación explícita del contrato. No requiere regeneración ni backfill masivo.
