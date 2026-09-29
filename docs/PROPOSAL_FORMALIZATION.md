# Formalización de propuestas

En **Propuestas → editar → Documentos**, el administrador descarga los anexos
y prepara un correo para revisión y firma. El cliente recibe el contenido que
ya revisó en la propuesta. Los PDF ordenan y numeran sus capítulos sin cambiar
la redacción de las secciones conservadas ni el orden editable de la web.

## Contenido de los anexos

| Capítulo | PDF comercial público | Propuesta comercial formal |
|---|---:|---:|
| Resumen ejecutivo | 01 | 01 |
| Contexto y diagnóstico | 02 | — |
| Enfoque propuesto y estrategia de conversión | 03 | 02 |
| Proyección de retorno y beneficios | 04 | — |
| Diseño Visual y Experiencia de Usuario | 05 | 03 |
| Acompañamiento Creativo Personalizado | 06 | 04 |
| Proceso y Metodología | 07 | 05 |
| Cronograma del Proyecto | 08 | 06 |
| Inversión y Formas de Pago | 09 | 07 |
| Requerimientos Funcionales del Proyecto | 10 | 08 |
| Incluido sin costo adicional | 11 | 09 |
| Etapas de contratación y desarrollo | 12 | — |
| Nota Final y Próximos Pasos | 13 | — |
| Próximos pasos | 14 | — |
| Condiciones comerciales | 15 | 10 |

El detalle técnico **formal** conserva únicamente **Stack tecnológico**, **Modelo
de datos** y **Módulos del producto**, en ese orden. El detalle técnico público
continúa completo. Las tablas, justificaciones, entidades y requerimientos de
los capítulos conservados usan los mismos renderizadores y filtro de selección
que el original. Los indicadores iniciales sólo cuentan contenido incluido.

Los números de la tabla suponen todos los capítulos habilitados y con contenido
imprimible. Las secciones deshabilitadas, el retorno vacío y los módulos
adicionales sin contenido resoluble no consumen un número ni una entrada del
índice. Cada PDF comienza en 01, y los subcapítulos de requerimientos se numeran
según su padre y los grupos visibles. Portadas y presentación no son capítulos.
El índice utiliza esos mismos números y enlaza las páginas reales, incluso
cuando ocupa varias páginas o no hay presentación.

Se preservan los títulos personalizados, párrafos, texto pegado, tablas y reglas
de selección, precios y pagos del producto. En contrato único se conserva también
el hosting; en modalidad separada, su bloque completo pasa al contrato de servicio. Condiciones comerciales mantiene sus
paquetes y las reglas vigentes del catálogo automático o manual. No se editan
los datos guardados ni los identificadores de módulos o requerimientos.

Los contratos único, de producto y de servicio continúan usando sus PDF finales
guardados, de acuerdo con la modalidad de cierre elegida.

## Generación y revisión

- `FormalContent` captura las secciones habilitadas sin transformarlas.
  `formalization_pdf` invoca los generadores originales con la selección de
  capítulos correspondiente. El orden comercial es exclusivo del PDF, y el
  técnico recibe `included_sections=("stack", "dataModel", "epics")`.
- Los renderizadores comercial y técnico comparten medidas de texto, badges y
  filas: 6 pt mínimos dentro de tablas, 30 pt alrededor de badges externos y
  saltos explícitos entre párrafos. Las filas largas continúan en otra página
  con encabezado repetido; no cambian el contenido ni los capítulos elegidos.
- **Copiar Markdown** extrae el texto del PDF del anexo, sin una segunda
  interpretación del contenido. Avisa que reconstruye el formato y que las
  imágenes y firmas gráficas no se copian. Se mantienen los límites de extracción
  de 100 páginas, 50 MB de contenido descomprimido y un millón de caracteres.
- La versión documental 5 exige revisar de nuevo las preparaciones anteriores
  con anexos o contrato de servicio; no sustituye sus archivos ni altera envíos históricos.
- Los archivos adjuntos se generan una vez al preparar el correo. La revisión
  y el envío usan esos mismos bytes. Las preparaciones pendientes con anexos
  del formato anterior deben prepararse y revisarse nuevamente; nunca se
  reemplazan sus archivos silenciosamente. Los envíos históricos se conservan.
- La huella de origen comprueba los datos y títulos de las secciones, la
  selección, la modalidad de cierre y los tres descuentos de hosting antes de enviar.

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

### Condiciones de hosting en contratos separados

En **Producto y servicio**, el anexo comercial conserva la inversión y la forma
de pago del producto. Su bloque de hosting, incluido el indicador de precio,
pasa íntegro al contrato de servicio: infraestructura, cobertura, cortesía,
precios, descuentos y condiciones de renovación. La propuesta pública y el
anexo técnico mantienen su contenido habitual.

El contrato presenta las modalidades **trimestral, semestral y cada nueve meses**,
con el equivalente mensual y el total de cada periodo calculados desde los
valores vigentes de la propuesta. La redacción pide al cliente comunicar por
escrito su elección antes del primer cobro; no se presupone una modalidad.
El bloque se incorpora también a los contratos personalizados, conservando su
texto. Al regenerar se reemplaza el bloque automático anterior sin duplicarlo.

Si durante la negociación cambian las condiciones, la fila del contrato de
servicio muestra **Regenerar contrato**. Abrir, guardar y revisar ese contrato
actualiza el archivo y su texto. La formalización rechaza un contrato obsoleto
hasta completar esa revisión; no reemplaza adjuntos ya preparados ni archivos
históricos. Los contratos cerrados no se marcan para regeneración automática.
La migración `content.0276` actualiza las remisiones de la plantilla estándar e
inserta el bloque en su cláusula de precio; se aplica durante el despliegue.

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
