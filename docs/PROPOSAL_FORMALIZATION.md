# Formalización de propuestas

En **Propuestas → editar → Documentos**, el administrador descarga los anexos
y prepara un correo para revisión y firma. El cliente recibe el contenido que
ya revisó en la propuesta. El anexo comercial sólo retira seis secciones
completas; el detalle técnico conserva todo el contenido de su PDF original.

## Contenido de los anexos

| Elemento del PDF original | Propuesta comercial de Documentos | Detalle técnico de Documentos |
|---|---|---|
| Resumen ejecutivo, diagnóstico, estrategia de conversión | Se excluyen las tres secciones completas. | No aplica. |
| Proyección de retorno, nota final, próximos pasos | Se excluyen las tres secciones completas. | No aplica. |
| Las demás secciones habilitadas, incluidas las condiciones comerciales | Se conservan con sus títulos, orden y contenido originales. | No aplica. |
| Detalle técnico | Mantiene la separación del PDF comercial original. | Se conserva completo, con las mismas reglas del PDF técnico original. |
| Selección de módulos, importes, pagos, hosting y paquetes de horas | Hereda las reglas originales; no tiene un cálculo ni una selección de campos propios. | Hereda el filtro técnico original para la selección de módulos. |
| Texto pegado y campos estructurados | Se muestran como en el original. | Se muestran como en el original. |

No se reescriben párrafos, eliminan campos dentro de una sección conservada ni
se agregan notas contractuales o una identidad documental distinta. El índice
y la paginación se generan a partir de las secciones presentes. Las condiciones
comerciales conservan sus paquetes y las reglas de catálogo automático o manual
que ya aplica el PDF original. El detalle técnico conserva, entre otros campos
que imprime el original, la evolución prevista y las columnas de ambientes.

Los contratos único, de producto y de servicio continúan usando sus PDF finales
guardados, de acuerdo con la modalidad de cierre elegida.

## Generación y revisión

- `FormalContent` captura las secciones habilitadas sin transformarlas.
  `formalization_pdf` invoca los generadores originales; sólo el comercial
  recibe la lista de secciones después de las seis exclusiones.
- **Copiar Markdown** extrae el texto del PDF del anexo, sin una segunda
  interpretación del contenido. Avisa que reconstruye el formato y que las
  imágenes y firmas gráficas no se copian. Se mantienen los límites de extracción
  de 100 páginas, 50 MB de contenido descomprimido y un millón de caracteres.
- Los archivos adjuntos se generan una vez al preparar el correo. La revisión
  y el envío usan esos mismos bytes. Las preparaciones pendientes con anexos
  del formato anterior deben prepararse y revisarse nuevamente; nunca se
  reemplazan sus archivos silenciosamente. Los envíos históricos se conservan.
- La huella de origen comprueba los datos y títulos de las secciones, la
  selección y la modalidad de cierre antes de enviar.

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
  Sus modelos son temporales, excluidos de fake data persistente y del MCP.

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
