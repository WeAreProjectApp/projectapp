"""Contract template v8: mutual confidentiality, IP carve-outs, lettered lists.

1. CLÁUSULA DÉCIMA becomes PROPIEDAD INTELECTUAL Y DERECHOS PATRIMONIALES.
   The client owns the DESARROLLO ESPECÍFICO; know-how, and reusable
   components and industry standards, stay with EL CONTRATISTA in their own
   paragraphs, even when written during the project. The temporary licence
   moves from Parágrafo Tercero to Quinto.
2. CLÁUSULA DÉCIMA PRIMERA becomes CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN:
   reciprocal, with a non-use duty, no derived products from the revealed
   opportunity, and a two-year non-circumvention covering staff and
   subcontractors.
3. Every enumeration uses bold letters (roman numerals when nested), one
   paragraph per item. The PDF parser only treats '-', '*' and 'N.' as list
   items, so consecutive 'a)' lines were printed as one run-on paragraph and
   numbered lists were renumbered by both renderers, contradicting in-text
   references such as "numerales 6 y 7". Literal bold letters in separate
   paragraphs render the same in the PDF and on the web. References now say
   "literal", and the three Cláusula Tercera paragraphs get titles.

Only the default template is patched. Every changed section is one pair and
all pairs form a single group: cross-references tie the sections together,
so a customized or ambiguous section leaves the whole template untouched and
logs a warning. Existing PDFs, proposal-specific contracts and other
templates are preserved.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


PAIRS = (
    # CLÁUSULA SEGUNDA — Parágrafo Primero — Actividades
    (
        """\
### Parágrafo Primero — Actividades

EL CONTRATISTA ejecutará las siguientes actividades dentro del marco del presente contrato. Las especificaciones técnicas, tecnologías, herramientas y arquitectura se detallan en el Documento Propuesta Comercial anexo al presente contrato.

1. **Diseño:** Definición de objetivos, diseño de la arquitectura del software y modelado de la solución conforme a los requerimientos de EL CONTRATANTE.
2. **Desarrollo:** Programación e implementación de los componentes del producto software.
3. **Control de calidad:** Ejecución de pruebas para verificar el correcto funcionamiento del software conforme al alcance definido.
4. **Despliegue:** Instalación y puesta en marcha del producto software en el ambiente de producción, sujeto a lo establecido en el PARÁGRAFO SÉPTIMO del presente contrato.
5. **Capacitación:** Orientación a EL CONTRATANTE sobre el uso y operación del producto software entregado.
6. **Entrega:** Entrega formal del código fuente, documentación técnica y demás entregables definidos en el Documento Propuesta Comercial, sujeta a la condición establecida en la CLÁUSULA NOVENA.""",
        """\
### Parágrafo Primero — Actividades

EL CONTRATISTA ejecutará las siguientes actividades dentro del marco del presente contrato. Las especificaciones técnicas, tecnologías, herramientas y arquitectura se detallan en el Documento Propuesta Comercial anexo al presente contrato.

**a) Diseño:** Definición de objetivos, diseño de la arquitectura del software y modelado de la solución conforme a los requerimientos de EL CONTRATANTE.

**b) Desarrollo:** Programación e implementación de los componentes del producto software.

**c) Control de calidad:** Ejecución de pruebas para verificar el correcto funcionamiento del software conforme al alcance definido.

**d) Despliegue:** Instalación y puesta en marcha del producto software en el ambiente de producción, sujeto a lo establecido en el PARÁGRAFO SÉPTIMO de la presente cláusula.

**e) Capacitación:** Orientación a EL CONTRATANTE sobre el uso y operación del producto software entregado.

**f) Entrega:** Entrega formal del código fuente, documentación técnica y demás entregables definidos en el Documento Propuesta Comercial, sujeta a la condición establecida en la CLÁUSULA NOVENA.""",
    ),
    # CLÁUSULA SEGUNDA — Parágrafo Quinto — Entrega a Satisfacción
    (
        """\
### Parágrafo Quinto — Entrega a Satisfacción

Una vez realizada la notificación de entrega indicada en el PARÁGRAFO CUARTO, se seguirá el siguiente procedimiento de aceptación:

1. **Revisión:** EL CONTRATANTE dispondrá de cuatro (4) días hábiles, contados a partir del día siguiente a la notificación, para revisar el entregable y comunicar sus observaciones o solicitudes de ajuste a través del medio definido en la CLÁUSULA DÉCIMA QUINTA. Las observaciones deberán limitarse al alcance definido en el PARÁGRAFO SEGUNDO.
2. **Corrección:** Una vez recibidas las observaciones, EL CONTRATISTA dispondrá de ocho (8) días hábiles, contados a partir del día siguiente a su recepción, para atender los ajustes solicitados y notificar nuevamente a EL CONTRATANTE.
3. **Rondas de revisión:** El procedimiento descrito en los numerales 1 y 2 podrá repetirse hasta un máximo de tres (3) rondas de revisión por cada entregable.
4. **Aceptación tácita:** Si EL CONTRATANTE no comunica observaciones dentro de los cuatro (4) días hábiles siguientes a cualquier notificación de entrega, se entenderá que el entregable ha sido recibido a satisfacción.
5. **Agotamiento de rondas:** Una vez agotadas las tres (3) rondas de revisión, las partes acordarán por escrito las condiciones para resolver las observaciones pendientes, lo cual podrá formalizarse mediante un OTROSÍ al presente contrato.""",
        """\
### Parágrafo Quinto — Entrega a Satisfacción

Una vez realizada la notificación de entrega indicada en el PARÁGRAFO CUARTO, se seguirá el siguiente procedimiento de aceptación:

**a) Revisión:** EL CONTRATANTE dispondrá de cuatro (4) días hábiles, contados a partir del día siguiente a la notificación, para revisar el entregable y comunicar sus observaciones o solicitudes de ajuste a través del medio definido en la CLÁUSULA DÉCIMA QUINTA. Las observaciones deberán limitarse al alcance definido en el PARÁGRAFO SEGUNDO.

**b) Corrección:** Una vez recibidas las observaciones, EL CONTRATISTA dispondrá de ocho (8) días hábiles, contados a partir del día siguiente a su recepción, para atender los ajustes solicitados y notificar nuevamente a EL CONTRATANTE.

**c) Rondas de revisión:** El procedimiento descrito en los literales a) y b) podrá repetirse hasta un máximo de tres (3) rondas de revisión por cada entregable.

**d) Aceptación tácita:** Si EL CONTRATANTE no comunica observaciones dentro de los cuatro (4) días hábiles siguientes a cualquier notificación de entrega, se entenderá que el entregable ha sido recibido a satisfacción.

**e) Agotamiento de rondas:** Una vez agotadas las tres (3) rondas de revisión, las partes acordarán por escrito las condiciones para resolver las observaciones pendientes, lo cual podrá formalizarse mediante un OTROSÍ al presente contrato.""",
    ),
    # CLÁUSULA SEGUNDA — Parágrafo Sexto — Garantía y Soporte
    (
        """\
### Parágrafo Sexto — Garantía y Soporte

1. Los productos software entregados bajo el presente contrato tendrán una garantía por un periodo de un (1) año, contado a partir de la fecha de aceptación del entregable final. Se entiende por garantía la corrección sin costo de funcionalidades que no operen o no se visualicen conforme a lo definido dentro del alcance del proyecto en el Documento Propuesta Comercial.
2. Para efectos de la garantía, se considerará un error o defecto (bug) toda falla, comportamiento inesperado o resultado incorrecto del producto software respecto de las funcionalidades y especificaciones expresamente definidas en el alcance del proyecto. No se considerarán errores o defectos cubiertos por la garantía:
   a) Nuevas funcionalidades, módulos o características no contempladas en el alcance original del proyecto.
   b) Cambios en el comportamiento del software solicitados por EL CONTRATANTE que impliquen modificaciones al alcance definido.
   c) Ajustes derivados de cambios en las reglas de negocio, procesos operativos o necesidades de EL CONTRATANTE posteriores a la aceptación del entregable.
   d) Problemas originados por el uso inadecuado del producto software, por datos incorrectos ingresados por EL CONTRATANTE o sus usuarios, o por factores externos al código desarrollado.
   Los requerimientos que no califiquen como errores o defectos podrán ser atendidos mediante un nuevo acuerdo OTROSÍ o un contrato independiente entre las partes.
3. EL CONTRATANTE deberá reportar los problemas detectados a través del medio de notificación definido en la CLÁUSULA DÉCIMA QUINTA, cumpliendo el protocolo de reporte de incidentes definido en el PARÁGRAFO PRIMERO de la CLÁUSULA VIGÉSIMA SEGUNDA. El reporte que no reúna la información allí señalada no dará inicio al cómputo de los plazos del presente parágrafo sino desde el momento en que sea completado.
4. A partir del día hábil siguiente a la recepción del reporte, EL CONTRATISTA dispondrá de un plazo máximo de ocho (8) días hábiles para: replicar el problema reportado, analizar su causa y brindar una respuesta indicando si el origen está relacionado con el código desarrollado, los datos proporcionados u otro factor. Si la información suministrada resulta insuficiente, EL CONTRATISTA solicitará a EL CONTRATANTE los detalles adicionales necesarios.
5. Dentro del mismo plazo, EL CONTRATISTA informará a EL CONTRATANTE el tiempo estimado de resolución o las acciones necesarias para solucionar el inconveniente.
6. La garantía definida en el presente parágrafo estará sujeta al cumplimiento de las siguientes condiciones:
   a) EL CONTRATISTA deberá contar con acceso al servidor y al código fuente desplegado en el ambiente de producción.
   b) El código fuente en producción deberá corresponder íntegramente al entregado por EL CONTRATISTA, sin modificaciones realizadas por terceros ajenos al equipo de desarrollo.
   c) El ambiente de producción no deberá haber sido alterado en su configuración por personas distintas a EL CONTRATISTA.
7. La garantía quedará sin efecto si EL CONTRATANTE o terceros autorizados por este modifican el código fuente, la configuración del servidor o cualquier componente del producto software sin autorización escrita de EL CONTRATISTA. En este caso, la restitución de la garantía podrá acordarse mediante un OTROSÍ, previa auditoría técnica por parte de EL CONTRATISTA.""",
        """\
### Parágrafo Sexto — Garantía y Soporte

**a)** Los productos software entregados bajo el presente contrato tendrán una garantía por un periodo de un (1) año, contado a partir de la fecha de aceptación del entregable final. Se entiende por garantía la corrección sin costo de funcionalidades que no operen o no se visualicen conforme a lo definido dentro del alcance del proyecto en el Documento Propuesta Comercial.

**b)** Para efectos de la garantía, se considerará un error o defecto (bug) toda falla, comportamiento inesperado o resultado incorrecto del producto software respecto de las funcionalidades y especificaciones expresamente definidas en el alcance del proyecto. No se considerarán errores o defectos cubiertos por la garantía:

**i)** Nuevas funcionalidades, módulos o características no contempladas en el alcance original del proyecto.

**ii)** Cambios en el comportamiento del software solicitados por EL CONTRATANTE que impliquen modificaciones al alcance definido.

**iii)** Ajustes derivados de cambios en las reglas de negocio, procesos operativos o necesidades de EL CONTRATANTE posteriores a la aceptación del entregable.

**iv)** Problemas originados por el uso inadecuado del producto software, por datos incorrectos ingresados por EL CONTRATANTE o sus usuarios, o por factores externos al código desarrollado.

Los requerimientos que no califiquen como errores o defectos podrán ser atendidos mediante un nuevo acuerdo OTROSÍ o un contrato independiente entre las partes.

**c)** EL CONTRATANTE deberá reportar los problemas detectados a través del medio de notificación definido en la CLÁUSULA DÉCIMA QUINTA, cumpliendo el protocolo de reporte de incidentes definido en el PARÁGRAFO PRIMERO de la CLÁUSULA VIGÉSIMA SEGUNDA. El reporte que no reúna la información allí señalada no dará inicio al cómputo de los plazos del presente parágrafo sino desde el momento en que sea completado.

**d)** A partir del día hábil siguiente a la recepción del reporte, EL CONTRATISTA dispondrá de un plazo máximo de ocho (8) días hábiles para: replicar el problema reportado, analizar su causa y brindar una respuesta indicando si el origen está relacionado con el código desarrollado, los datos proporcionados u otro factor. Si la información suministrada resulta insuficiente, EL CONTRATISTA solicitará a EL CONTRATANTE los detalles adicionales necesarios.

**e)** Dentro del mismo plazo, EL CONTRATISTA informará a EL CONTRATANTE el tiempo estimado de resolución o las acciones necesarias para solucionar el inconveniente.

**f)** La garantía definida en el presente parágrafo estará sujeta al cumplimiento de las siguientes condiciones:

**i)** EL CONTRATISTA deberá contar con acceso al servidor y al código fuente desplegado en el ambiente de producción.

**ii)** El código fuente en producción deberá corresponder íntegramente al entregado por EL CONTRATISTA, sin modificaciones realizadas por terceros ajenos al equipo de desarrollo.

**iii)** El ambiente de producción no deberá haber sido alterado en su configuración por personas distintas a EL CONTRATISTA.

**g)** La garantía quedará sin efecto si EL CONTRATANTE o terceros autorizados por este modifican el código fuente, la configuración del servidor o cualquier componente del producto software sin autorización escrita de EL CONTRATISTA. En este caso, la restitución de la garantía podrá acordarse mediante un OTROSÍ, previa auditoría técnica por parte de EL CONTRATISTA.""",
    ),
    # CLÁUSULA SEGUNDA — Parágrafo Séptimo — Hosting y Despliegue
    (
        """\
### Parágrafo Séptimo — Hosting y Despliegue

1. EL CONTRATANTE tendrá el derecho de alojar el producto software en el proveedor de hosting de su preferencia.
2. El ambiente de producción en el que se aloje el producto software deberá cumplir, como mínimo, con los requerimientos técnicos definidos en el Documento Propuesta Comercial anexo al presente contrato. Lo anterior es condición necesaria para garantizar el correcto funcionamiento del producto software y el cumplimiento de los atributos de calidad esperados, tales como disponibilidad, rendimiento, escalabilidad, seguridad y certificados SSL.
3. La garantía y el soporte definidos en el PARÁGRAFO SEXTO aplicarán siempre que se cumplan las condiciones establecidas en los numerales 6 y 7 de dicho parágrafo, independientemente del proveedor de hosting utilizado.
4. Dado que el alcance del presente contrato comprende el desarrollo del producto software y no su despliegue, no es obligación de EL CONTRATISTA realizar instalaciones en dominios operativos diferentes a los de Project App.
5. En caso de que EL CONTRATANTE solicite la instalación y despliegue del producto en un ambiente diferente a los dominios de Project App, dicho ambiente deberá cumplir con las condiciones descritas en el numeral 2 del presente parágrafo. Este servicio tendrá un costo adicional equivalente al dieciocho por ciento (18%) del valor total del presente contrato. Dicho valor responde al trabajo adicional que implica realizar el despliegue en un entorno distinto al contemplado inicialmente, incluyendo configuración de infraestructura, adaptación de scripts, variables de entorno, validaciones técnicas, endurecimiento de seguridad y puesta en marcha en un ambiente nuevo.
6. Además de las condiciones generales establecidas en el PARÁGRAFO SEXTO, para que la garantía se mantenga vigente en ambientes de hosting externos a Project App, deberán cumplirse las siguientes condiciones:
   a) EL CONTRATANTE deberá garantizar el acceso permanente e ininterrumpido de EL CONTRATISTA al servidor y al código fuente desplegado en producción. La pérdida, revocación o restricción de dicho acceso, por cualquier causa atribuible a EL CONTRATANTE, causará la suspensión inmediata de la garantía hasta que el acceso sea restablecido en su totalidad.
   b) El servicio de hosting deberá ser contratado y pagado por anticipado por EL CONTRATANTE por un periodo mínimo de seis (6) meses continuos. Esta condición es necesaria para garantizar la continuidad operativa del ambiente de producción durante el periodo de garantía de un (1) año establecido en el PARÁGRAFO SEXTO, permitiendo a EL CONTRATISTA acceder al ambiente, diagnosticar y corregir los defectos reportados sin interrupciones derivadas de la caducidad del servicio. El vencimiento del servicio de hosting sin renovación oportuna suspenderá la garantía hasta que EL CONTRATANTE restablezca el servicio y EL CONTRATISTA verifique la integridad del ambiente de producción.
7. Por razones de seguridad, integridad del código fuente y trazabilidad de las operaciones realizadas en el ambiente de producción, EL CONTRATISTA implementará un mecanismo de notificación que registre y comunique todo acceso al servidor. Este mecanismo tiene como finalidad proteger el producto software contra modificaciones no autorizadas, garantizar la cadena de custodia del código desplegado y facilitar el diagnóstico ante eventuales incidentes de seguridad o funcionamiento. Ambas partes recibirán las notificaciones correspondientes.
8. Cuando EL CONTRATANTE contrate con EL CONTRATISTA el servicio de hosting, mantenimiento y soporte, dicho servicio se regirá por las CLÁUSULAS VIGÉSIMA PRIMERA a VIGÉSIMA CUARTA del presente contrato y por las condiciones económicas definidas en el Documento Propuesta Comercial.""",
        """\
### Parágrafo Séptimo — Hosting y Despliegue

**a)** EL CONTRATANTE tendrá el derecho de alojar el producto software en el proveedor de hosting de su preferencia.

**b)** El ambiente de producción en el que se aloje el producto software deberá cumplir, como mínimo, con los requerimientos técnicos definidos en el Documento Propuesta Comercial anexo al presente contrato. Lo anterior es condición necesaria para garantizar el correcto funcionamiento del producto software y el cumplimiento de los atributos de calidad esperados, tales como disponibilidad, rendimiento, escalabilidad, seguridad y certificados SSL.

**c)** La garantía y el soporte definidos en el PARÁGRAFO SEXTO aplicarán siempre que se cumplan las condiciones establecidas en los literales f) y g) de dicho parágrafo, independientemente del proveedor de hosting utilizado.

**d)** Dado que el alcance del presente contrato comprende el desarrollo del producto software y no su despliegue, no es obligación de EL CONTRATISTA realizar instalaciones en dominios operativos diferentes a los de Project App.

**e)** En caso de que EL CONTRATANTE solicite la instalación y despliegue del producto en un ambiente diferente a los dominios de Project App, dicho ambiente deberá cumplir con las condiciones descritas en el literal b) del presente parágrafo. Este servicio tendrá un costo adicional equivalente al dieciocho por ciento (18%) del valor total del presente contrato. Dicho valor responde al trabajo adicional que implica realizar el despliegue en un entorno distinto al contemplado inicialmente, incluyendo configuración de infraestructura, adaptación de scripts, variables de entorno, validaciones técnicas, endurecimiento de seguridad y puesta en marcha en un ambiente nuevo.

**f)** Además de las condiciones generales establecidas en el PARÁGRAFO SEXTO, para que la garantía se mantenga vigente en ambientes de hosting externos a Project App, deberán cumplirse las siguientes condiciones:

**i)** EL CONTRATANTE deberá garantizar el acceso permanente e ininterrumpido de EL CONTRATISTA al servidor y al código fuente desplegado en producción. La pérdida, revocación o restricción de dicho acceso, por cualquier causa atribuible a EL CONTRATANTE, causará la suspensión inmediata de la garantía hasta que el acceso sea restablecido en su totalidad.

**ii)** El servicio de hosting deberá ser contratado y pagado por anticipado por EL CONTRATANTE por un periodo mínimo de seis (6) meses continuos. Esta condición es necesaria para garantizar la continuidad operativa del ambiente de producción durante el periodo de garantía de un (1) año establecido en el PARÁGRAFO SEXTO, permitiendo a EL CONTRATISTA acceder al ambiente, diagnosticar y corregir los defectos reportados sin interrupciones derivadas de la caducidad del servicio. El vencimiento del servicio de hosting sin renovación oportuna suspenderá la garantía hasta que EL CONTRATANTE restablezca el servicio y EL CONTRATISTA verifique la integridad del ambiente de producción.

**g)** Por razones de seguridad, integridad del código fuente y trazabilidad de las operaciones realizadas en el ambiente de producción, EL CONTRATISTA implementará un mecanismo de notificación que registre y comunique todo acceso al servidor. Este mecanismo tiene como finalidad proteger el producto software contra modificaciones no autorizadas, garantizar la cadena de custodia del código desplegado y facilitar el diagnóstico ante eventuales incidentes de seguridad o funcionamiento. Ambas partes recibirán las notificaciones correspondientes.

**h)** Cuando EL CONTRATANTE contrate con EL CONTRATISTA el servicio de hosting, mantenimiento y soporte, dicho servicio se regirá por las CLÁUSULAS VIGÉSIMA PRIMERA a VIGÉSIMA CUARTA del presente contrato y por las condiciones económicas definidas en el Documento Propuesta Comercial.""",
    ),
    # CLÁUSULA SEGUNDA — Parágrafo Octavo — Exclusiones
    (
        """\
### Parágrafo Octavo — Exclusiones

Salvo que se pacte expresamente lo contrario en el Documento Propuesta Comercial, los productos software desarrollados bajo el presente contrato no incluyen:

1. Costos derivados por ambientes de producción, cómputo, hosting, servidores, herramientas de monitoreo y gestión.
2. Costos asociados con la obtención de licencias, permisos y cumplimiento normativo.
3. Costos de desarrollo para actualizaciones, mejoras continuas o nuevas funcionalidades posteriores a la entrega.
4. Gastos relacionados con soporte técnico y atención al usuario final de EL CONTRATANTE, una vez finalizado el periodo de garantía definido en el PARÁGRAFO SEXTO.
5. Costos de seguros relacionados con la propiedad intelectual y responsabilidad civil.
6. Costos derivados por herramientas, plataformas, soluciones o servicios de terceros, incluyendo pero sin limitarse a: dominios, pasarelas de pago y sus comisiones, correos corporativos y certificados SSL.
7. Migración de datos existentes de EL CONTRATANTE hacia el producto software.
8. Integración con sistemas o plataformas de terceros no definidos explícitamente en el alcance del proyecto.
9. Creación de contenidos tales como textos, copywriting, traducciones, imágenes, videos, audios y/o recursos audiovisuales.
10. Capacitación adicional más allá de la contemplada en la actividad de entrega definida en el PARÁGRAFO PRIMERO.
11. Compatibilidad con navegadores, dispositivos o sistemas operativos no definidos en el alcance del proyecto.
12. Reportes, informes, notificaciones, estadísticas y visualizaciones de datos, a menos que sean definidos explícitamente dentro del alcance del producto software.
13. Inventario y/o manejo de inventarios, dejando claro que el portal administrativo no es un gestor de inventario, ni un inventario.""",
        """\
### Parágrafo Octavo — Exclusiones

Salvo que se pacte expresamente lo contrario en el Documento Propuesta Comercial, los productos software desarrollados bajo el presente contrato no incluyen:

**a)** Costos derivados de ambientes de producción, cómputo, hosting, servidores, herramientas de monitoreo y gestión.

**b)** Costos asociados con la obtención de licencias, permisos y cumplimiento normativo.

**c)** Costos de desarrollo para actualizaciones, mejoras continuas o nuevas funcionalidades posteriores a la entrega.

**d)** Gastos relacionados con soporte técnico y atención al usuario final de EL CONTRATANTE, una vez finalizado el periodo de garantía definido en el PARÁGRAFO SEXTO.

**e)** Costos de seguros relacionados con la propiedad intelectual y responsabilidad civil.

**f)** Costos derivados de herramientas, plataformas, soluciones o servicios de terceros, incluyendo pero sin limitarse a: dominios, pasarelas de pago y sus comisiones, correos corporativos y certificados SSL.

**g)** Migración de datos existentes de EL CONTRATANTE hacia el producto software.

**h)** Integración con sistemas o plataformas de terceros no definidos explícitamente en el alcance del proyecto.

**i)** Creación de contenidos tales como textos, copywriting, traducciones, imágenes, videos, audios y/o recursos audiovisuales.

**j)** Capacitación adicional más allá de la contemplada en la actividad de capacitación prevista en el literal e) del PARÁGRAFO PRIMERO.

**k)** Compatibilidad con navegadores, dispositivos o sistemas operativos no definidos en el alcance del proyecto.

**l)** Reportes, informes, notificaciones, estadísticas y visualizaciones de datos, a menos que sean definidos explícitamente dentro del alcance del producto software.

**m)** Inventario y/o manejo de inventarios, dejando claro que el portal administrativo no es un gestor de inventario, ni un inventario.""",
    ),
    # CLÁUSULA SEGUNDA — Parágrafo Noveno — Condiciones de Pago y Entrega
    (
        """\
### Parágrafo Noveno — Condiciones de Pago y Entrega

1. La entrega de cada producto está sujeta al pago oportuno por parte de EL CONTRATANTE. Un retraso en los pagos causará un aplazamiento equivalente en los plazos de entrega del siguiente entregable.
2. Cada pago se documentará mediante un acta de entrega y un comprobante de transferencia con la fecha de la transacción.
3. Una vez confirmado el pago correspondiente, se dará inicio al siguiente periodo de desarrollo conforme al cronograma definido en el Documento Propuesta Comercial.""",
        """\
### Parágrafo Noveno — Condiciones de Pago y Entrega

**a)** La entrega de cada producto está sujeta al pago oportuno por parte de EL CONTRATANTE. Un retraso en los pagos causará un aplazamiento equivalente en los plazos de entrega del siguiente entregable.

**b)** Cada pago se documentará mediante un acta de entrega y un comprobante de transferencia con la fecha de la transacción.

**c)** Una vez confirmado el pago correspondiente, se dará inicio al siguiente periodo de desarrollo conforme al cronograma definido en el Documento Propuesta Comercial.""",
    ),
    # CLÁUSULA SEGUNDA — Parágrafo Décimo — Alcance del Trabajo Contratado
    (
        """\
### Parágrafo Décimo — Alcance del Trabajo Contratado

1. El trabajo contratado y cotizado corresponde únicamente a lo descrito dentro del alcance del Documento Propuesta Comercial y del Documento Detalle Técnico anexos al presente contrato. Cualquier conversación, mensaje, correo electrónico, reunión, idea, recurso, archivo, referencia o solicitud que surja antes o durante la ejecución del contrato y que no esté explícitamente descrita dentro de dicho alcance no constituye, por sí sola, un compromiso de implementación por parte de EL CONTRATISTA ni hace parte del trabajo contratado.
2. Lo anterior no limita la comunicación entre las partes: estas podrán conversar y explorar ideas libremente durante la ejecución del proyecto. Sin embargo, para que una funcionalidad, cambio o entregable pase a formar parte del trabajo contratado, deberá quedar documentado y cotizado como parte del alcance, y formalizarse mediante un OTROSÍ conforme a la CLÁUSULA DÉCIMA TERCERA o mediante un contrato independiente entre las partes. Esto protege a ambas partes: evita malentendidos sobre lo que está incluido, mantiene el proyecto enfocado y asegura que cada esfuerzo adicional se planifique y se remunere de forma justa.
3. En consecuencia, los plazos, precios, garantías y obligaciones del presente contrato aplican exclusivamente sobre el alcance descrito en los anexos. Todo requerimiento que exceda dicho alcance se gestionará mediante los paquetes de horas definidos en el Documento Propuesta Comercial cuando se trate de esfuerzos bajos o medio-bajos, y como una cotización independiente cuando se trate de esfuerzos medios o superiores.
4. La ejecución por parte de EL CONTRATISTA de cualquier actividad no comprendida en el alcance no constituirá modificación del mismo, no generará derecho a exigir prestaciones similares en el futuro, ni podrá interpretarse como renuncia a lo establecido en el presente parágrafo.""",
        """\
### Parágrafo Décimo — Alcance del Trabajo Contratado

**a)** El trabajo contratado y cotizado corresponde únicamente a lo descrito dentro del alcance del Documento Propuesta Comercial y del Documento Detalle Técnico anexos al presente contrato. Cualquier conversación, mensaje, correo electrónico, reunión, idea, recurso, archivo, referencia o solicitud que surja antes o durante la ejecución del contrato y que no esté explícitamente descrita dentro de dicho alcance no constituye, por sí sola, un compromiso de implementación por parte de EL CONTRATISTA ni hace parte del trabajo contratado.

**b)** Lo anterior no limita la comunicación entre las partes: estas podrán conversar y explorar ideas libremente durante la ejecución del proyecto. Sin embargo, para que una funcionalidad, cambio o entregable pase a formar parte del trabajo contratado, deberá quedar documentado y cotizado como parte del alcance, y formalizarse mediante un OTROSÍ conforme a la CLÁUSULA DÉCIMA TERCERA o mediante un contrato independiente entre las partes. Esto protege a ambas partes: evita malentendidos sobre lo que está incluido, mantiene el proyecto enfocado y asegura que cada esfuerzo adicional se planifique y se remunere de forma justa.

**c)** En consecuencia, los plazos, precios, garantías y obligaciones del presente contrato aplican exclusivamente sobre el alcance descrito en los anexos. Todo requerimiento que exceda dicho alcance se gestionará mediante los paquetes de horas definidos en el Documento Propuesta Comercial cuando se trate de esfuerzos bajos o medio-bajos, y como una cotización independiente cuando se trate de esfuerzos medios o superiores.

**d)** La ejecución por parte de EL CONTRATISTA de cualquier actividad no comprendida en el alcance no constituirá modificación del mismo, no generará derecho a exigir prestaciones similares en el futuro, ni podrá interpretarse como renuncia a lo establecido en el presente parágrafo.""",
    ),
    # CLÁUSULA TERCERA — Parágrafo Primero — Medio de Pago
    (
        """\
### Parágrafo Primero

Los pagos se realizarán mediante transferencia bancaria a la cuenta {bank_name} {bank_account_type} No. {bank_account_number} a nombre de EL CONTRATISTA identificado con {contractor_id_type} número {contractor_id_number}.""",
        """\
### Parágrafo Primero — Medio de Pago

Los pagos se realizarán mediante transferencia bancaria a la cuenta {bank_name} {bank_account_type} No. {bank_account_number} a nombre de EL CONTRATISTA identificado con {contractor_id_type} número {contractor_id_number}.""",
    ),
    # CLÁUSULA TERCERA — Parágrafo Segundo — Intereses de Mora
    (
        """\
### Parágrafo Segundo

En caso de mora en los pagos por parte de EL CONTRATANTE, se causarán intereses de mora a la tasa máxima legal vigente, sin perjuicio del aplazamiento de los plazos de entrega conforme a lo establecido en el PARÁGRAFO NOVENO de la CLÁUSULA SEGUNDA.""",
        """\
### Parágrafo Segundo — Intereses de Mora

En caso de mora en los pagos por parte de EL CONTRATANTE, se causarán intereses de mora a la tasa máxima legal vigente, sin perjuicio del aplazamiento de los plazos de entrega conforme a lo establecido en el PARÁGRAFO NOVENO de la CLÁUSULA SEGUNDA.""",
    ),
    # CLÁUSULA TERCERA — Parágrafo Tercero — Pagos No Reembolsables
    (
        """\
### Parágrafo Tercero

Los pagos correspondientes a fases entregadas y aceptadas conforme al procedimiento del PARÁGRAFO QUINTO de la CLÁUSULA SEGUNDA no serán reembolsables.""",
        """\
### Parágrafo Tercero — Pagos No Reembolsables

Los pagos correspondientes a fases entregadas y aceptadas conforme al procedimiento del PARÁGRAFO QUINTO de la CLÁUSULA SEGUNDA no serán reembolsables.""",
    ),
    # CLÁUSULA SÉPTIMA — OBLIGACIONES DEL CONTRATISTA
    (
        """\
## CLÁUSULA SÉPTIMA — OBLIGACIONES DEL CONTRATISTA

a) Cumplir oportunamente el objeto y las actividades definidas en la CLÁUSULA SEGUNDA del presente contrato.
b) Aportar su experiencia y conocimientos para la adecuada ejecución del contrato.
c) Entregar el código fuente, la documentación técnica y los demás entregables conforme a lo establecido en el Documento Propuesta Comercial, en los términos y bajo la condición establecida en la CLÁUSULA NOVENA.
d) Cumplir con la garantía y soporte en los términos del PARÁGRAFO SEXTO de la CLÁUSULA SEGUNDA.
e) Absolver las consultas de EL CONTRATANTE relacionadas con el objeto del contrato.
f) Asistir a las reuniones en los días y horas previamente acordados entre las partes.
g) Informar oportunamente a EL CONTRATANTE sobre cualquier circunstancia que pueda afectar el cumplimiento de los plazos o el alcance del proyecto.""",
        """\
## CLÁUSULA SÉPTIMA — OBLIGACIONES DEL CONTRATISTA

**a)** Cumplir oportunamente el objeto y las actividades definidas en la CLÁUSULA SEGUNDA del presente contrato.

**b)** Aportar su experiencia y conocimientos para la adecuada ejecución del contrato.

**c)** Entregar el código fuente, la documentación técnica y los demás entregables conforme a lo establecido en el Documento Propuesta Comercial, en los términos y bajo la condición establecida en la CLÁUSULA NOVENA.

**d)** Cumplir con la garantía y soporte en los términos del PARÁGRAFO SEXTO de la CLÁUSULA SEGUNDA.

**e)** Absolver las consultas de EL CONTRATANTE relacionadas con el objeto del contrato.

**f)** Asistir a las reuniones en los días y horas previamente acordados entre las partes.

**g)** Informar oportunamente a EL CONTRATANTE sobre cualquier circunstancia que pueda afectar el cumplimiento de los plazos o el alcance del proyecto.""",
    ),
    # CLÁUSULA OCTAVA — OBLIGACIONES DEL CONTRATANTE
    (
        """\
## CLÁUSULA OCTAVA — OBLIGACIONES DEL CONTRATANTE

a) Pagar los honorarios en los términos establecidos en la CLÁUSULA TERCERA del presente contrato.
b) Facilitar a EL CONTRATISTA, de manera oportuna, el acceso a la información, insumos, contenidos y recursos necesarios para la ejecución del contrato.
c) Designar una persona de contacto con capacidad de decisión para la comunicación con EL CONTRATISTA durante la ejecución del proyecto.
d) Dar respuesta a las entregas dentro de los plazos establecidos en el PARÁGRAFO QUINTO de la CLÁUSULA SEGUNDA.
e) Cumplir con las demás obligaciones y condiciones previstas en el presente contrato y sus anexos.""",
        """\
## CLÁUSULA OCTAVA — OBLIGACIONES DEL CONTRATANTE

**a)** Pagar los honorarios en los términos establecidos en la CLÁUSULA TERCERA del presente contrato.

**b)** Facilitar a EL CONTRATISTA, de manera oportuna, el acceso a la información, insumos, contenidos y recursos necesarios para la ejecución del contrato.

**c)** Designar una persona de contacto con capacidad de decisión para la comunicación con EL CONTRATISTA durante la ejecución del proyecto.

**d)** Dar respuesta a las entregas dentro de los plazos establecidos en el PARÁGRAFO QUINTO de la CLÁUSULA SEGUNDA.

**e)** Cumplir con las demás obligaciones y condiciones previstas en el presente contrato y sus anexos.""",
    ),
    # CLÁUSULA NOVENA — Parágrafo Primero — Elementos Sujetos a la Condición
    (
        """\
### Parágrafo Primero — Elementos Sujetos a la Condición

Hasta tanto no se acredite el pago del cien por ciento (100%) del valor total del contrato, EL CONTRATISTA no estará obligado a entregar, y EL CONTRATANTE no tendrá derecho a exigir ni a acceder a:

a) El código fuente del producto software, en cualquier soporte, formato o medio.
b) El acceso, en cualquier modalidad, a los repositorios de control de versiones del proyecto, así como a su historial de cambios, ramas y confirmaciones.
c) La transferencia de titularidad, propiedad o administración de dichos repositorios a EL CONTRATANTE o a terceros designados por este.
d) Los archivos de configuración de integración y despliegue continuo, scripts de construcción, scripts de despliegue y plantillas de variables de entorno.
e) La documentación técnica de arquitectura, modelo de datos y demás documentación asociada directamente al código fuente.""",
        """\
### Parágrafo Primero — Elementos Sujetos a la Condición

Hasta tanto no se acredite el pago del cien por ciento (100%) del valor total del contrato, EL CONTRATISTA no estará obligado a entregar, y EL CONTRATANTE no tendrá derecho a exigir ni a acceder a:

**a)** El código fuente del producto software, en cualquier soporte, formato o medio.

**b)** El acceso, en cualquier modalidad, a los repositorios de control de versiones del proyecto, así como a su historial de cambios, ramas y confirmaciones.

**c)** La transferencia de titularidad, propiedad o administración de dichos repositorios a EL CONTRATANTE o a terceros designados por este.

**d)** Los archivos de configuración de integración y despliegue continuo, scripts de construcción, scripts de despliegue y plantillas de variables de entorno.

**e)** La documentación técnica de arquitectura, modelo de datos y demás documentación asociada directamente al código fuente.""",
    ),
    # CLÁUSULA NOVENA — Parágrafo Cuarto — Efectos sobre la Ejecución y la Aceptación
    (
        """\
### Parágrafo Cuarto — Efectos sobre la Ejecución y la Aceptación

La condición establecida en la presente cláusula no afecta las demás obligaciones de EL CONTRATISTA. En particular:

1. El producto software permanecerá desplegado y operativo en el ambiente de producción, de modo que EL CONTRATANTE pueda usarlo conforme a la licencia temporal prevista en el PARÁGRAFO TERCERO de la CLÁUSULA DÉCIMA.
2. La revisión y aceptación de los entregables conforme al PARÁGRAFO QUINTO de la CLÁUSULA SEGUNDA se realizará sobre el producto software desplegado y en funcionamiento, sin que ello requiera la entrega del código fuente ni el acceso a los repositorios.
3. La garantía prevista en el PARÁGRAFO SEXTO de la CLÁUSULA SEGUNDA se causa desde la aceptación del entregable final, con independencia del momento en que se produzca la entrega del código fuente.
4. La retención prevista en la presente cláusula no constituye incumplimiento contractual por parte de EL CONTRATISTA, en concordancia con el PARÁGRAFO TERCERO de la CLÁUSULA DÉCIMA SÉPTIMA, ni causa mora ni genera indemnización alguna a favor de EL CONTRATANTE.""",
        """\
### Parágrafo Cuarto — Efectos sobre la Ejecución y la Aceptación

La condición establecida en la presente cláusula no afecta las demás obligaciones de EL CONTRATISTA. En particular:

**a)** El producto software permanecerá desplegado y operativo en el ambiente de producción, de modo que EL CONTRATANTE pueda usarlo conforme a la licencia temporal prevista en el PARÁGRAFO QUINTO de la CLÁUSULA DÉCIMA.

**b)** La revisión y aceptación de los entregables conforme al PARÁGRAFO QUINTO de la CLÁUSULA SEGUNDA se realizará sobre el producto software desplegado y en funcionamiento, sin que ello requiera la entrega del código fuente ni el acceso a los repositorios.

**c)** La garantía prevista en el PARÁGRAFO SEXTO de la CLÁUSULA SEGUNDA se causa desde la aceptación del entregable final, con independencia del momento en que se produzca la entrega del código fuente.

**d)** La retención prevista en la presente cláusula no constituye incumplimiento contractual por parte de EL CONTRATISTA, en concordancia con el PARÁGRAFO TERCERO de la CLÁUSULA DÉCIMA SÉPTIMA, ni causa mora ni genera indemnización alguna a favor de EL CONTRATANTE.""",
    ),
    # CLÁUSULA NOVENA — Parágrafo Quinto — Entrega una vez Cumplida la Condición
    (
        """\
### Parágrafo Quinto — Entrega una vez Cumplida la Condición

Acreditado el pago del cien por ciento (100%) del valor total del contrato, EL CONTRATISTA dispondrá de cinco (5) días hábiles, contados a partir del día siguiente a la confirmación del pago final, para:

a) Entregar el código fuente del producto software y la documentación técnica asociada.
b) Otorgar a EL CONTRATANTE el acceso a los repositorios del proyecto y transferir su titularidad o administración, según lo acuerden las partes.
c) Suscribir el acta de entrega final correspondiente.

La entrega se notificará conforme a la CLÁUSULA DÉCIMA QUINTA y se documentará mediante acta de entrega, momento a partir del cual operará de pleno derecho la cesión de derechos prevista en la CLÁUSULA DÉCIMA.""",
        """\
### Parágrafo Quinto — Entrega una vez Cumplida la Condición

Acreditado el pago del cien por ciento (100%) del valor total del contrato, EL CONTRATISTA dispondrá de cinco (5) días hábiles, contados a partir del día siguiente a la confirmación del pago final, para:

**a)** Entregar el código fuente del producto software y la documentación técnica asociada.

**b)** Otorgar a EL CONTRATANTE el acceso a los repositorios del proyecto y transferir su titularidad o administración, según lo acuerden las partes.

**c)** Suscribir el acta de entrega final correspondiente.

La entrega se notificará conforme a la CLÁUSULA DÉCIMA QUINTA y se documentará mediante acta de entrega, momento a partir del cual operará de pleno derecho la cesión de derechos prevista en la CLÁUSULA DÉCIMA.""",
    ),
    # CLÁUSULA DÉCIMA — PROPIEDAD INTELECTUAL Y DERECHOS PATRIMONIALES
    (
        """\
## CLÁUSULA DÉCIMA — DERECHOS PATRIMONIALES Y DERECHOS DE EXPLOTACIÓN

En virtud del presente contrato y una vez cumplida la condición suspensiva establecida en la CLÁUSULA NOVENA, EL CONTRATANTE adquiere, de manera exclusiva, los derechos patrimoniales y de explotación sobre los desarrollos originales realizados específicamente para su proyecto dentro del alcance contratado, con las excepciones y reservas del PARÁGRAFO SEGUNDO de la presente cláusula. La cesión comprende los derechos de uso, reproducción, modificación, transformación, adaptación, distribución, comercialización, traducción, disposición, exportación, edición y comunicación pública de dichos desarrollos, por cualquier medio, sin restricción territorial y por todo el tiempo de protección legal conforme a la normatividad colombiana vigente. La incorporación de herramientas generales o de componentes propios reutilizables o de terceros no amplía el objeto de esta cesión.

Estos derechos se transfieren de manera permanente y de pleno derecho una vez cumplidas las condiciones establecidas en la CLÁUSULA NOVENA, incluidas las aplicables a la terminación unilateral por EL CONTRATANTE, con las excepciones del PARÁGRAFO SEGUNDO de la presente cláusula. No se causará una contraprestación adicional por la cesión, sin perjuicio del pago del precio contractual y de la penalidad y demás obligaciones económicas que resulten exigibles por la terminación unilateral.

### Parágrafo Primero — Uso por el Contratante

EL CONTRATANTE podrá utilizar los resultados parciales y finales del proyecto para adaptarlos, modificarlos o integrarlos en cualquier tipo de producto, proyecto o aplicación que considere necesario, sin requerir autorización adicional de EL CONTRATISTA y sin que ello genere derecho a contraprestación adicional, una vez cumplida la condición suspensiva establecida en la CLÁUSULA NOVENA y siempre que se encuentre al día en el cumplimiento de sus obligaciones de pago conforme a la CLÁUSULA TERCERA.

### Parágrafo Segundo — Excepciones a la Cesión de Derechos

La cesión recae sobre la expresión original de los desarrollos específicos del proyecto y no confiere exclusividad sobre ideas, métodos, funcionalidades o soluciones técnicas generales. Quedan excluidos de la cesión:

a) Los activos preexistentes y los elementos propios de carácter general y reutilizable de EL CONTRATISTA que no hayan sido desarrollados exclusivamente para EL CONTRATANTE, incluidos plantillas, fragmentos de código (snippets), módulos generales, herramientas, librerías propias y marcos de trabajo.
b) Los componentes genéricos y reutilizables de autenticación, registros de actividad (logs), formularios, operaciones de creación, consulta, actualización y eliminación (CRUD), paginación y demás utilidades de aplicación general. Esta reserva no excluye de la cesión las implementaciones originales desarrolladas específicamente para el proyecto por el solo hecho de emplear dichos recursos o realizar esas funciones.
c) El conocimiento técnico (know-how), la experiencia acumulada, las habilidades y los conocimientos generales de EL CONTRATISTA y de su equipo, incluidos los adquiridos o perfeccionados durante la ejecución del contrato. Este acervo forma parte de su activo intelectual y podrá continuar utilizándose en otros proyectos, respetando la confidencialidad y los derechos sobre los desarrollos específicos de EL CONTRATANTE.
d) Los patrones de diseño, las arquitecturas estándar, las metodologías Agile/Scrum, las prácticas DevOps, las estructuras comunes de bases de datos y los algoritmos o procesos estándar de búsqueda, checkout, almacenamiento en caché (caching), colas y validaciones. Su utilización no otorga a ninguna de las partes exclusividad sobre tales ideas, métodos o conocimientos generales, sin perjuicio de los derechos que correspondan sobre implementaciones originales concretas.
e) Las librerías de código abierto (open source), los frameworks y los demás componentes de terceros, cuya titularidad permanecerá en cabeza de sus respectivos titulares y cuyo uso, modificación y distribución se regirán por las licencias aplicables. Su incorporación al producto no transfiere su propiedad a ninguna de las partes ni permite imponer restricciones contrarias a dichas licencias.

EL CONTRATISTA conservará los derechos que le correspondan sobre sus activos propios excluidos de la cesión. Una vez cumplida la condición suspensiva de la CLÁUSULA NOVENA, EL CONTRATANTE recibirá sobre los componentes propios descritos en los literales a) y b) que se incorporen al producto una licencia de uso perpetua, irrevocable, no exclusiva y sin costo adicional, que le permitirá utilizarlos, modificarlos e integrarlos dentro del producto software entregado y sus derivados, sin que esta licencia se extienda a su comercialización como productos independientes. Los componentes de terceros conservarán el régimen de sus propias licencias.

En consecuencia, EL CONTRATANTE adquirirá los derechos patrimoniales pactados sobre lo desarrollado específicamente para su proyecto, mientras EL CONTRATISTA conservará sus herramientas y activos reutilizables y no renunciará al conocimiento y experiencia de su equipo. Esta reserva no autoriza la divulgación de información confidencial, la reutilización de desarrollos específicos cedidos al cliente ni la apropiación de elementos que pertenezcan a terceros o sean de uso general.

### Parágrafo Tercero — Licencia Temporal de Uso

Mientras no se cumpla la condición suspensiva establecida en la CLÁUSULA NOVENA, y siempre que EL CONTRATANTE se encuentre al día en sus obligaciones de pago conforme a la CLÁUSULA TERCERA, EL CONTRATISTA otorga a EL CONTRATANTE una licencia de uso temporal, revocable, no exclusiva e intransferible sobre el producto software desplegado, limitada a su uso y operación en el ambiente de producción para los fines propios del negocio de EL CONTRATANTE.

Esta licencia temporal no comprende, y EL CONTRATANTE se abstendrá de ejercer, los derechos de reproducción, modificación, transformación, adaptación, distribución, comercialización, sublicenciamiento o cesión a terceros, ni el encargo a terceros de desarrollos derivados del producto software.

La licencia temporal se extinguirá automáticamente en cualquiera de los siguientes eventos:

a) Al cumplirse la condición suspensiva establecida en la CLÁUSULA NOVENA, momento en el cual operará la cesión plena de derechos prevista en la presente cláusula.
b) Cuando EL CONTRATANTE incurra en mora en los pagos por un periodo superior a treinta (30) días calendario, conforme al literal a) del PARÁGRAFO TERCERO de la CLÁUSULA DÉCIMA SEXTA.
c) Por terminación del contrato sin que se haya cumplido la condición suspensiva de la CLÁUSULA NOVENA. En caso de terminación unilateral por EL CONTRATANTE, el pago de la liquidación y de la penalidad no mantiene vigente esta licencia ni habilita la cesión de derechos.""",
        """\
## CLÁUSULA DÉCIMA — PROPIEDAD INTELECTUAL Y DERECHOS PATRIMONIALES

En virtud del presente contrato y una vez cumplida la condición suspensiva establecida en la CLÁUSULA NOVENA, EL CONTRATANTE adquiere, de manera exclusiva, los derechos patrimoniales y de explotación sobre el DESARROLLO ESPECÍFICO, entendido como los desarrollos originales realizados específicamente para su proyecto dentro del alcance contratado: el código fuente escrito para el proyecto, la lógica y las reglas de negocio implementadas para EL CONTRATANTE, el modelo de datos diseñado para dichas reglas, las interfaces y diseños gráficos elaborados para el proyecto, su configuración particular y su documentación específica. La cesión comprende los derechos de uso, reproducción, modificación, transformación, adaptación, distribución, comercialización, traducción, disposición, exportación, edición y comunicación pública del DESARROLLO ESPECÍFICO, por cualquier medio, sin restricción territorial y por todo el tiempo de protección legal conforme a la normatividad colombiana vigente. La cesión recae sobre la expresión original del DESARROLLO ESPECÍFICO y no confiere exclusividad sobre ideas, métodos, funcionalidades o soluciones técnicas generales; la incorporación de herramientas generales o de componentes propios reutilizables o de terceros no amplía su objeto.

Estos derechos se transfieren de manera permanente y de pleno derecho una vez cumplidas las condiciones establecidas en la CLÁUSULA NOVENA, incluidas las aplicables a la terminación unilateral por EL CONTRATANTE, con las exclusiones previstas en los PARÁGRAFOS SEGUNDO y TERCERO de la presente cláusula, respecto de las cuales lo aquí pactado constituye pacto en contrario para los efectos del artículo 20 de la Ley 23 de 1982 y de las normas que lo modifiquen. No se causará una contraprestación adicional por la cesión, sin perjuicio del pago del precio contractual y de la penalidad y demás obligaciones económicas que resulten exigibles por la terminación unilateral.

### Parágrafo Primero — Uso por el Contratante

EL CONTRATANTE podrá utilizar los resultados parciales y finales del proyecto para adaptarlos, modificarlos o integrarlos en cualquier tipo de producto, proyecto o aplicación que considere necesario, sin requerir autorización adicional de EL CONTRATISTA y sin que ello genere derecho a contraprestación adicional, una vez cumplida la condición suspensiva establecida en la CLÁUSULA NOVENA y siempre que se encuentre al día en el cumplimiento de sus obligaciones de pago conforme a la CLÁUSULA TERCERA. Respecto de los elementos de titularidad de EL CONTRATISTA incorporados en el producto, dicho uso se rige por la licencia prevista en el PARÁGRAFO CUARTO de la presente cláusula.

### Parágrafo Segundo — Conocimiento Técnico y Experiencia Acumulada

El conocimiento técnico (know-how), la experiencia acumulada, las habilidades, técnicas, competencias, lecciones aprendidas y conocimientos generales de EL CONTRATISTA y de su equipo, incluidos los adquiridos o perfeccionados durante la ejecución del contrato, pertenecen a EL CONTRATISTA y no son objeto de la cesión prevista en la presente cláusula. Este acervo constituye su activo intelectual y la base profesional con la que presta sus servicios a todos sus clientes, por lo que EL CONTRATISTA podrá continuar utilizándolo libremente en proyectos propios o de terceros, respetando la confidencialidad prevista en la CLÁUSULA DÉCIMA PRIMERA y los derechos de EL CONTRATANTE sobre el DESARROLLO ESPECÍFICO.

### Parágrafo Tercero — Componentes Técnicos Reutilizables y Estándares de la Industria

EL CONTRATANTE es titular de lo que se desarrolla específicamente para su proyecto, y no de las herramientas generales utilizadas para construirlo. En consecuencia, quedan excluidos de la cesión, y EL CONTRATANTE no podrá reclamar como propios, los siguientes elementos, sea que existieran antes del presente contrato o que se desarrollen, adapten o perfeccionen durante su ejecución:

**a)** Los activos preexistentes y los elementos propios de carácter general y reutilizable de EL CONTRATISTA, incluidos plantillas, fragmentos de código (snippets), módulos generales, herramientas, utilidades, librerías propias, marcos de trabajo y código base reutilizable.

**b)** Los componentes genéricos de autenticación y gestión de usuarios, registros de actividad (logs), formularios, operaciones de creación, consulta, actualización y eliminación (CRUD), paginación, filtros, notificaciones y demás utilidades de aplicación general.

**c)** Los patrones de diseño, las arquitecturas de software estándar y las soluciones técnicas de carácter genérico.

**d)** Las metodologías Agile/Scrum y demás metodologías, procesos, flujos de trabajo y prácticas de desarrollo de EL CONTRATISTA.

**e)** Las prácticas DevOps, tales como integración y despliegue continuos, automatización de infraestructura, monitoreo y copias de seguridad.

**f)** Las estructuras comunes de bases de datos.

**g)** Los algoritmos y procesos estándar, tales como búsqueda, checkout, almacenamiento en caché (caching), colas y validaciones.

**h)** Las librerías de código abierto (open source), los frameworks y los demás componentes de terceros, cuya titularidad permanecerá en cabeza de sus respectivos titulares y cuyo uso, modificación y distribución se regirán por las licencias aplicables. Su incorporación al producto no transfiere su propiedad a ninguna de las partes ni permite imponer restricciones contrarias a dichas licencias.

Hacen parte del DESARROLLO ESPECÍFICO la lógica, las reglas de negocio, el modelo de datos, las interfaces y la configuración particulares que se construyan para EL CONTRATANTE sobre dichos elementos, sin que ello le transfiera la titularidad del elemento general subyacente. EL CONTRATISTA conserva la titularidad o, según corresponda, el libre uso de los elementos descritos en el presente parágrafo, y podrá seguir utilizándolos, adaptándolos y licenciándolos en otros proyectos. Esta reserva no autoriza la divulgación de información confidencial, la reutilización del DESARROLLO ESPECÍFICO cedido a EL CONTRATANTE ni la apropiación de elementos que pertenezcan a terceros o sean de uso general.

### Parágrafo Cuarto — Licencia sobre los Componentes Incorporados

Una vez cumplida la condición suspensiva de la CLÁUSULA NOVENA, EL CONTRATANTE recibirá, sobre los elementos de titularidad de EL CONTRATISTA descritos en el PARÁGRAFO TERCERO que queden incorporados en el producto, una licencia de uso perpetua, irrevocable, no exclusiva y sin costo adicional, que le permitirá utilizarlos, modificarlos e integrarlos, directamente o por medio de terceros, dentro del producto software entregado y sus derivados, sin que esta licencia se extienda a su comercialización como productos independientes. Los componentes de terceros conservarán el régimen de sus propias licencias.

### Parágrafo Quinto — Licencia Temporal de Uso

Mientras no se cumpla la condición suspensiva establecida en la CLÁUSULA NOVENA, y siempre que EL CONTRATANTE se encuentre al día en sus obligaciones de pago conforme a la CLÁUSULA TERCERA, EL CONTRATISTA otorga a EL CONTRATANTE una licencia de uso temporal, revocable, no exclusiva e intransferible sobre el producto software desplegado, limitada a su uso y operación en el ambiente de producción para los fines propios del negocio de EL CONTRATANTE.

Esta licencia temporal no comprende, y EL CONTRATANTE se abstendrá de ejercer, los derechos de reproducción, modificación, transformación, adaptación, distribución, comercialización, sublicenciamiento o cesión a terceros, ni el encargo a terceros de desarrollos derivados del producto software.

La licencia temporal se extinguirá automáticamente en cualquiera de los siguientes eventos:

**a)** Al cumplirse la condición suspensiva establecida en la CLÁUSULA NOVENA, momento en el cual operará la cesión plena de derechos prevista en la presente cláusula.

**b)** Cuando EL CONTRATANTE incurra en mora en los pagos por un periodo superior a treinta (30) días calendario, conforme al literal a) del PARÁGRAFO TERCERO de la CLÁUSULA DÉCIMA SEXTA.

**c)** Por terminación del contrato sin que se haya cumplido la condición suspensiva de la CLÁUSULA NOVENA. En caso de terminación unilateral por EL CONTRATANTE, el pago de la liquidación y de la penalidad no mantiene vigente esta licencia ni habilita la cesión de derechos.""",
    ),
    # CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN
    (
        """\
## CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD

Ambas partes se obligan a mantener la confidencialidad sobre toda la información que conozcan o a la que tengan acceso con ocasión del presente contrato, con independencia del medio en el cual se encuentre soportada. En adelante, la parte que revela información se denominará PARTE REVELADORA y la que la recibe, PARTE RECEPTORA.

Se tendrá como información confidencial cualquier información no divulgada que posea legítimamente la PARTE REVELADORA y que pueda usarse en alguna actividad académica, productiva, industrial o comercial y que sea susceptible de comunicarse a un tercero. Sin fines restrictivos, la información confidencial podrá versar sobre invenciones, modelos de utilidad, programas de software, fórmulas, métodos, know-how, procesos, diseños, metodologías, arquitecturas técnicas, nuevos productos, trabajos en desarrollo, requisitos de comercialización, planes de mercadeo, estrategias comerciales, información financiera, nombres de clientes y proveedores existentes y potenciales, así como toda otra información que cualquiera de las partes identifique como confidencial.

La información confidencial incluye también toda información recibida de terceros que la PARTE RECEPTORA esté obligada a tratar como confidencial.

La obligación de confidencialidad no aplica sobre aquella información que:

a) Sea o llegue a ser del dominio público sin que medie acto u omisión de la PARTE RECEPTORA.
b) Estuviese en posesión legítima de la PARTE RECEPTORA con anterioridad a su divulgación y no hubiese sido obtenida de forma directa o indirecta de la PARTE REVELADORA.
c) Sea legalmente divulgada por un tercero que no esté sujeto a restricciones en cuanto a su divulgación y la haya obtenido de buena fe.
d) Deba ser divulgada por orden judicial o requerimiento de autoridad competente, en cuyo caso la PARTE RECEPTORA notificará a la PARTE REVELADORA con la mayor antelación posible.

La obligación de confidencialidad permanecerá vigente durante la ejecución del contrato y por un periodo de dos (2) años contados a partir de su terminación por cualquier causa.""",
        """\
## CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN

Ambas partes se obligan recíprocamente a mantener la confidencialidad sobre toda la información que conozcan o a la que tengan acceso con ocasión de la negociación, celebración y ejecución del presente contrato, con independencia del medio en el cual se encuentre soportada. En adelante, la parte que revela información se denominará PARTE REVELADORA y la que la recibe, PARTE RECEPTORA. Cada una de las partes tendrá una u otra calidad según la información de que se trate, de manera que las obligaciones de la presente cláusula protegen por igual a EL CONTRATANTE y a EL CONTRATISTA.

### Parágrafo Primero — Información Confidencial

Se tendrá como INFORMACIÓN CONFIDENCIAL cualquier información no divulgada que posea legítimamente la PARTE REVELADORA, que pueda usarse en alguna actividad académica, productiva, industrial o comercial y que sea susceptible de comunicarse a un tercero, así como toda otra información que cualquiera de las partes identifique como confidencial. Incluye también la información recibida de terceros que la PARTE RECEPTORA esté obligada a tratar como confidencial. Sin fines restrictivos, se considera INFORMACIÓN CONFIDENCIAL:

**a)** De EL CONTRATANTE: su modelo de negocio, la oportunidad comercial y las ideas de producto que revele, sus planes de mercadeo, estrategias comerciales, información financiera, bases de datos, nombres de clientes y proveedores existentes y potenciales, y la demás información de negocio que entregue para la ejecución del proyecto.

**b)** De EL CONTRATISTA: sus propuestas y cotizaciones, incluidos el Documento Propuesta Comercial y el Documento Detalle Técnico; sus tarifas y condiciones comerciales; sus métodos, procesos, metodologías, arquitecturas técnicas y herramientas; el código fuente y los componentes de su titularidad conforme a la CLÁUSULA DÉCIMA; su know-how; y la identidad y condiciones de sus proveedores, aliados, subcontratistas y colaboradores.

**c)** De cualquiera de las partes: invenciones, modelos de utilidad, programas de software, fórmulas, diseños, nuevos productos, trabajos en desarrollo, requisitos de comercialización y las condiciones económicas del presente contrato y sus anexos.

### Parágrafo Segundo — Obligaciones de la Parte Receptora

La PARTE RECEPTORA se obliga a:

**a)** Mantener la INFORMACIÓN CONFIDENCIAL en estricta reserva y protegerla con un grado de diligencia no inferior al que emplea para proteger su propia información confidencial, que en ningún caso será inferior a un estándar razonable.

**b)** No divulgarla, publicarla, comercializarla ni compartirla con terceros sin autorización previa y escrita de la PARTE REVELADORA, salvo en los términos del PARÁGRAFO TERCERO de la presente cláusula.

**c)** No usar, explotar, implementar, reproducir ni aprovechar, directa o indirectamente, la INFORMACIÓN CONFIDENCIAL para fines distintos de la negociación, celebración y ejecución del presente contrato, que constituyen su único objeto autorizado.

**d)** No utilizar la INFORMACIÓN CONFIDENCIAL para desarrollar, directa o indirectamente, por sí o mediante terceros, productos, servicios, modelos comerciales o alianzas derivados de la oportunidad comercial revelada, salvo autorización previa y escrita de la PARTE REVELADORA.

**e)** Informar a la PARTE REVELADORA, tan pronto tenga conocimiento, de cualquier uso o divulgación no autorizados de la INFORMACIÓN CONFIDENCIAL, y adoptar las medidas razonables a su alcance para mitigar sus efectos.

### Parágrafo Tercero — Personal, Subcontratistas y Asesores

La PARTE RECEPTORA solo podrá dar a conocer la INFORMACIÓN CONFIDENCIAL a sus administradores, empleados, subcontratistas, colaboradores y asesores que necesiten conocerla para la ejecución del contrato, en la medida estrictamente necesaria y siempre que se encuentren sujetos a obligaciones de confidencialidad no menos exigentes que las previstas en la presente cláusula, lo que comprende la subcontratación prevista en la CLÁUSULA CUARTA. La PARTE RECEPTORA responderá por el incumplimiento de dichas personas como si se tratara del suyo propio.

### Parágrafo Cuarto — No Circunvención

Durante la vigencia del presente contrato y por el término de dos (2) años contados a partir de su terminación por cualquier causa, ninguna de las partes podrá, directa o indirectamente, por sí o por interpuesta persona, contactar, negociar, contratar ni celebrar acuerdos con los clientes, proveedores, aliados, inversionistas, empleados, subcontratistas, colaboradores o demás contactos comerciales que la otra parte le haya presentado o vinculado con ocasión del presente contrato, cuando ello tenga por objeto o por efecto eludir, sustituir, desplazar o reducir la participación de la parte que los presentó o vinculó, o apropiarse de la oportunidad comercial revelada, salvo autorización previa y escrita de esta. No constituye circunvención:

**a)** La relación con personas con quienes la parte ya mantuviera una relación comercial acreditable antes de que le fueran presentadas.

**b)** La vinculación de personas que se postulen a convocatorias públicas o abiertas que no hayan sido dirigidas específicamente a ellas.

**c)** La contratación de proveedores de servicios tecnológicos de oferta pública y uso general, tales como los de infraestructura, dominios, pasarelas de pago o correo electrónico, ni el ejercicio por EL CONTRATANTE del derecho previsto en el literal a) del PARÁGRAFO SÉPTIMO de la CLÁUSULA SEGUNDA.

### Parágrafo Quinto — Actividad Independiente de las Partes

Las obligaciones de la presente cláusula no restringen la actividad ordinaria de las partes. En particular:

**a)** EL CONTRATISTA podrá prestar servicios de desarrollo de software a terceros y desarrollar, para sí o para terceros, productos o soluciones similares o con funcionalidades equivalentes, siempre que no utilice ni revele la INFORMACIÓN CONFIDENCIAL de EL CONTRATANTE ni reproduzca el DESARROLLO ESPECÍFICO. El uso del conocimiento técnico, la experiencia acumulada y los componentes técnicos reutilizables y estándares de la industria previstos en los PARÁGRAFOS SEGUNDO y TERCERO de la CLÁUSULA DÉCIMA no constituye uso de INFORMACIÓN CONFIDENCIAL.

**b)** EL CONTRATANTE, una vez cumplida la condición establecida en la CLÁUSULA NOVENA, podrá explotar libremente el DESARROLLO ESPECÍFICO conforme a la CLÁUSULA DÉCIMA y contratar con terceros su mantenimiento o evolución, con sujeción a lo previsto en el PARÁGRAFO CUARTO de la presente cláusula.

### Parágrafo Sexto — Excepciones

Las obligaciones de la presente cláusula no aplican sobre aquella información que:

**a)** Sea o llegue a ser del dominio público sin que medie acto u omisión de la PARTE RECEPTORA.

**b)** Estuviese en posesión legítima de la PARTE RECEPTORA con anterioridad a su divulgación y no hubiese sido obtenida de forma directa o indirecta de la PARTE REVELADORA.

**c)** Sea legalmente divulgada por un tercero que no esté sujeto a restricciones en cuanto a su divulgación y la haya obtenido de buena fe.

**d)** Sea desarrollada de manera independiente por la PARTE RECEPTORA, sin utilizar la INFORMACIÓN CONFIDENCIAL de la PARTE REVELADORA.

**e)** Deba ser divulgada por orden judicial o requerimiento de autoridad competente, en cuyo caso la PARTE RECEPTORA notificará a la PARTE REVELADORA con la mayor antelación posible y divulgará únicamente la información estrictamente requerida.

### Parágrafo Séptimo — Devolución de la Información

A la terminación del contrato, o antes si la PARTE REVELADORA lo solicita por escrito, la PARTE RECEPTORA devolverá o eliminará la INFORMACIÓN CONFIDENCIAL que obre en su poder. Se exceptúan el presente contrato y sus anexos; la información que deba conservarse por disposición legal o como soporte de la ejecución del contrato y del ejercicio de los derechos derivados de él; la necesaria para cumplir las obligaciones que subsistan; y las copias contenidas en respaldos automáticos, que se eliminarán conforme a sus ciclos ordinarios. La información conservada seguirá sujeta a la presente cláusula, y los datos personales se regirán por la CLÁUSULA DÉCIMA SEGUNDA.

### Parágrafo Octavo — Vigencia

Las obligaciones de la presente cláusula permanecerán vigentes durante la ejecución del contrato y por un periodo de dos (2) años contados a partir de su terminación por cualquier causa. Tratándose de información que constituya secreto empresarial en los términos de la Decisión 486 de 2000 de la Comisión de la Comunidad Andina, la obligación de reserva se mantendrá mientras dicha información conserve tal carácter.""",
    ),
    # CLÁUSULA DÉCIMA SEGUNDA — PROTECCIÓN Y TRATAMIENTO DE DATOS PERSONALES
    (
        """\
## CLÁUSULA DÉCIMA SEGUNDA — PROTECCIÓN Y TRATAMIENTO DE DATOS PERSONALES

EL CONTRATISTA asume la obligación de proteger los datos personales a los que acceda con ocasión del presente contrato, en cumplimiento de la Ley 1581 de 2012 y sus decretos reglamentarios. Para tal efecto, EL CONTRATISTA deberá:

a) Adoptar las medidas técnicas, administrativas y humanas necesarias para garantizar la seguridad de los datos personales y evitar su adulteración, pérdida, consulta, uso o acceso no autorizado.
b) Limitar el tratamiento de los datos personales de terceros entregados por EL CONTRATANTE exclusivamente a la finalidad propia de sus obligaciones contractuales.
c) Garantizar los derechos de privacidad, intimidad y buen nombre de los titulares de los datos personales.
d) Informar a EL CONTRATANTE de manera inmediata cualquier sospecha de pérdida, fuga, acceso no autorizado o incidente de seguridad que afecte los datos personales a los que haya tenido acceso.
e) Una vez finalizado el contrato, devolver o eliminar los datos personales que le hayan sido entregados, salvo que exista obligación legal de conservarlos.""",
        """\
## CLÁUSULA DÉCIMA SEGUNDA — PROTECCIÓN Y TRATAMIENTO DE DATOS PERSONALES

EL CONTRATISTA asume la obligación de proteger los datos personales a los que acceda con ocasión del presente contrato, en cumplimiento de la Ley 1581 de 2012 y sus decretos reglamentarios. Para tal efecto, EL CONTRATISTA deberá:

**a)** Adoptar las medidas técnicas, administrativas y humanas necesarias para garantizar la seguridad de los datos personales y evitar su adulteración, pérdida, consulta, uso o acceso no autorizado.

**b)** Limitar el tratamiento de los datos personales de terceros entregados por EL CONTRATANTE exclusivamente a la finalidad propia de sus obligaciones contractuales.

**c)** Garantizar los derechos de privacidad, intimidad y buen nombre de los titulares de los datos personales.

**d)** Informar a EL CONTRATANTE de manera inmediata cualquier sospecha de pérdida, fuga, acceso no autorizado o incidente de seguridad que afecte los datos personales a los que haya tenido acceso.

**e)** Una vez finalizado el contrato, devolver o eliminar los datos personales que le hayan sido entregados, salvo que exista obligación legal de conservarlos.""",
    ),
    # CLÁUSULA DÉCIMA QUINTA — NOTIFICACIÓN
    (
        """\
## CLÁUSULA DÉCIMA QUINTA — NOTIFICACIÓN

Para todos los efectos legales y de notificación derivados del presente contrato, las partes establecen los siguientes medios de contacto:

- **EL CONTRATANTE:** correo electrónico {client_email}
- **EL CONTRATISTA:** correo electrónico {contractor_email}

Toda notificación enviada a las direcciones de correo electrónico aquí indicadas se entenderá válidamente surtida al día hábil siguiente a su envío. Cualquier cambio en los datos de notificación deberá ser comunicado por escrito a la otra parte con al menos cinco (5) días hábiles de antelación.""",
        """\
## CLÁUSULA DÉCIMA QUINTA — NOTIFICACIÓN

Para todos los efectos legales y de notificación derivados del presente contrato, las partes establecen los siguientes medios de contacto:

**a) EL CONTRATANTE:** correo electrónico {client_email}

**b) EL CONTRATISTA:** correo electrónico {contractor_email}

Toda notificación enviada a las direcciones de correo electrónico aquí indicadas se entenderá válidamente surtida al día hábil siguiente a su envío. Cualquier cambio en los datos de notificación deberá ser comunicado por escrito a la otra parte con al menos cinco (5) días hábiles de antelación.""",
    ),
    # CLÁUSULA DÉCIMA SEXTA — Parágrafo Segundo — Terminación Unilateral por EL CONTRATANTE
    (
        """\
### Parágrafo Segundo — Terminación Unilateral por EL CONTRATANTE

EL CONTRATANTE podrá dar por terminado el contrato de forma unilateral, sin necesidad de invocar justa causa, mediante notificación escrita con al menos quince (15) días hábiles de antelación. En este caso:

a) EL CONTRATANTE deberá pagar la totalidad de las fases entregadas y aceptadas, el valor total de la fase en curso al momento de la notificación, y una penalidad por terminación unilateral equivalente al treinta por ciento (30%) del valor de las fases restantes del contrato. Esta penalidad se causa exclusivamente por el ejercicio de la terminación unilateral aquí prevista, no por una postergación o suspensión del proyecto, y es independiente del precio del desarrollo.
b) Los pagos realizados por fases entregadas y aceptadas no serán reembolsables.
c) El pago de la penalidad y de las demás sumas correspondientes a la liquidación de esta terminación unilateral no confiere a EL CONTRATANTE derecho a recibir el código fuente, la documentación técnica asociada ni acceso a los repositorios, ni produce la cesión de derechos patrimoniales. Si EL CONTRATANTE solicita dichos elementos, deberá acreditar el pago del cien por ciento (100%) del valor total del contrato y haber satisfecho la penalidad y las demás obligaciones de pago derivadas de la terminación. Para completar el valor contractual se imputarán únicamente los pagos efectuados por concepto del precio del desarrollo; la penalidad es independiente y no constituye abono a dicho precio. La entrega se regirá por el PARÁGRAFO SEXTO de la CLÁUSULA NOVENA y comprenderá exclusivamente el código fuente íntegro y la documentación técnica existentes respecto del trabajo efectivamente desarrollado hasta la fecha de terminación. El pago posterior no reactivará el contrato ni generará obligación de ejecutar las fases pendientes, cuya eventual realización requerirá un nuevo acuerdo escrito.

Las partes reconocen que EL CONTRATISTA organiza su operación conforme al alcance y duración acordados, reservando capacidad de trabajo, asignando personal y comprometiendo recursos para atender el proyecto. Así como EL CONTRATANTE planifica los recursos necesarios para cumplir sus pagos, EL CONTRATISTA realiza una planeación económica y operativa para ejecutar sus obligaciones. La terminación unilateral anticipada altera esa planeación, genera costos de desmovilización y reasignación y afecta la capacidad comprometida y los ingresos previstos, sin que los recursos reservados puedan destinarse inmediatamente a otros proyectos. Esta es la justificación comercial de la penalidad pactada, cuyo pago permite liquidar la salida unilateral en los términos aquí previstos y no sustituye el precio exigido para obtener el código fuente.""",
        """\
### Parágrafo Segundo — Terminación Unilateral por EL CONTRATANTE

EL CONTRATANTE podrá dar por terminado el contrato de forma unilateral, sin necesidad de invocar justa causa, mediante notificación escrita con al menos quince (15) días hábiles de antelación. En este caso:

**a)** EL CONTRATANTE deberá pagar la totalidad de las fases entregadas y aceptadas, el valor total de la fase en curso al momento de la notificación, y una penalidad por terminación unilateral equivalente al treinta por ciento (30%) del valor de las fases restantes del contrato. Esta penalidad se causa exclusivamente por el ejercicio de la terminación unilateral aquí prevista, no por una postergación o suspensión del proyecto, y es independiente del precio del desarrollo.

**b)** Los pagos realizados por fases entregadas y aceptadas no serán reembolsables.

**c)** El pago de la penalidad y de las demás sumas correspondientes a la liquidación de esta terminación unilateral no confiere a EL CONTRATANTE derecho a recibir el código fuente, la documentación técnica asociada ni acceso a los repositorios, ni produce la cesión de derechos patrimoniales. Si EL CONTRATANTE solicita dichos elementos, deberá acreditar el pago del cien por ciento (100%) del valor total del contrato y haber satisfecho la penalidad y las demás obligaciones de pago derivadas de la terminación. Para completar el valor contractual se imputarán únicamente los pagos efectuados por concepto del precio del desarrollo; la penalidad es independiente y no constituye abono a dicho precio. La entrega se regirá por el PARÁGRAFO SEXTO de la CLÁUSULA NOVENA y comprenderá exclusivamente el código fuente íntegro y la documentación técnica existentes respecto del trabajo efectivamente desarrollado hasta la fecha de terminación. El pago posterior no reactivará el contrato ni generará obligación de ejecutar las fases pendientes, cuya eventual realización requerirá un nuevo acuerdo escrito.

Las partes reconocen que EL CONTRATISTA organiza su operación conforme al alcance y duración acordados, reservando capacidad de trabajo, asignando personal y comprometiendo recursos para atender el proyecto. Así como EL CONTRATANTE planifica los recursos necesarios para cumplir sus pagos, EL CONTRATISTA realiza una planeación económica y operativa para ejecutar sus obligaciones. La terminación unilateral anticipada altera esa planeación, genera costos de desmovilización y reasignación y afecta la capacidad comprometida y los ingresos previstos, sin que los recursos reservados puedan destinarse inmediatamente a otros proyectos. Esta es la justificación comercial de la penalidad pactada, cuyo pago permite liquidar la salida unilateral en los términos aquí previstos y no sustituye el precio exigido para obtener el código fuente.""",
    ),
    # CLÁUSULA DÉCIMA SEXTA — Parágrafo Tercero — Terminación Unilateral por EL CONTRATISTA
    (
        """\
### Parágrafo Tercero — Terminación Unilateral por EL CONTRATISTA

EL CONTRATISTA podrá dar por terminado el contrato de forma unilateral, mediante notificación escrita con al menos quince (15) días hábiles de antelación, en los siguientes casos:

a) Cuando EL CONTRATANTE incurra en mora en los pagos por un periodo superior a treinta (30) días calendario.
b) Cuando EL CONTRATANTE incumpla reiteradamente sus obligaciones contractuales, afectando de manera sustancial la ejecución del proyecto.
c) Cuando EL CONTRATANTE no suministre la información, insumos o recursos necesarios para la ejecución del contrato dentro de un plazo razonable, causando una paralización efectiva del proyecto por más de veinte (20) días hábiles.

En caso de terminación por cualquiera de estas causas, EL CONTRATISTA conservará la totalidad de los pagos recibidos hasta la fecha y tendrá derecho al pago del trabajo ejecutado en la fase en curso. La entrega del trabajo realizado estará sujeta al cumplimiento de las obligaciones de pago pendientes.""",
        """\
### Parágrafo Tercero — Terminación Unilateral por EL CONTRATISTA

EL CONTRATISTA podrá dar por terminado el contrato de forma unilateral, mediante notificación escrita con al menos quince (15) días hábiles de antelación, en los siguientes casos:

**a)** Cuando EL CONTRATANTE incurra en mora en los pagos por un periodo superior a treinta (30) días calendario.

**b)** Cuando EL CONTRATANTE incumpla reiteradamente sus obligaciones contractuales, afectando de manera sustancial la ejecución del proyecto.

**c)** Cuando EL CONTRATANTE no suministre la información, insumos o recursos necesarios para la ejecución del contrato dentro de un plazo razonable, causando una paralización efectiva del proyecto por más de veinte (20) días hábiles.

En caso de terminación por cualquiera de estas causas, EL CONTRATISTA conservará la totalidad de los pagos recibidos hasta la fecha y tendrá derecho al pago del trabajo ejecutado en la fase en curso. La entrega del trabajo realizado estará sujeta al cumplimiento de las obligaciones de pago pendientes.""",
    ),
    # CLÁUSULA DÉCIMA SÉPTIMA — Parágrafo Segundo — Consecuencias del Incumplimiento No Subsanado
    (
        """\
### Parágrafo Segundo — Consecuencias del Incumplimiento No Subsanado

Si transcurrido el plazo correspondiente el incumplimiento no ha sido subsanado, la parte afectada podrá:

a) Dar por terminado el contrato conforme a lo establecido en la CLÁUSULA DÉCIMA SEXTA, sin perjuicio de las acciones legales a que haya lugar.
b) Exigir el cumplimiento de las obligaciones pendientes junto con la indemnización de los perjuicios causados, incluyendo el daño emergente y el lucro cesante, conforme a la legislación civil colombiana y sujeto a los límites establecidos en la CLÁUSULA VIGÉSIMA.""",
        """\
### Parágrafo Segundo — Consecuencias del Incumplimiento No Subsanado

Si transcurrido el plazo correspondiente el incumplimiento no ha sido subsanado, la parte afectada podrá:

**a)** Dar por terminado el contrato conforme a lo establecido en la CLÁUSULA DÉCIMA SEXTA, sin perjuicio de las acciones legales a que haya lugar.

**b)** Exigir el cumplimiento de las obligaciones pendientes junto con la indemnización de los perjuicios causados, incluyendo el daño emergente y el lucro cesante, conforme a la legislación civil colombiana y sujeto a los límites establecidos en la CLÁUSULA VIGÉSIMA.""",
    ),
    # CLÁUSULA DÉCIMA OCTAVA — RESOLUCIÓN DE CONFLICTOS
    (
        """\
## CLÁUSULA DÉCIMA OCTAVA — RESOLUCIÓN DE CONFLICTOS

Toda controversia o diferencia que surja entre las partes con ocasión del presente contrato, su interpretación, ejecución o terminación, se resolverá conforme al siguiente procedimiento:

1. **Negociación directa:** Las partes intentarán resolver la controversia de manera directa y de buena fe dentro de un plazo de quince (15) días hábiles contados a partir de la notificación escrita de la controversia.
2. **Conciliación:** Si la negociación directa no resuelve la controversia, las partes acudirán a un centro de conciliación legalmente establecido en la ciudad de {contract_city}, Colombia. Los costos de la conciliación serán asumidos por partes iguales.
3. **Jurisdicción ordinaria:** Si la conciliación no prospera dentro de los treinta (30) días calendario siguientes a la solicitud, las partes someterán la controversia a la jurisdicción civil ordinaria de la ciudad de {contract_city}, Colombia, con renuncia expresa a cualquier otro fuero que pudiera corresponderles.

Las costas y gastos judiciales del proceso serán asumidos por la parte vencida, salvo decisión diferente del juez competente.

Durante el trámite de cualquier controversia, las obligaciones de confidencialidad y protección de datos personales previstas en el presente contrato continuarán plenamente vigentes.""",
        """\
## CLÁUSULA DÉCIMA OCTAVA — RESOLUCIÓN DE CONFLICTOS

Toda controversia o diferencia que surja entre las partes con ocasión del presente contrato, su interpretación, ejecución o terminación, se resolverá conforme al siguiente procedimiento:

**a) Negociación directa:** Las partes intentarán resolver la controversia de manera directa y de buena fe dentro de un plazo de quince (15) días hábiles contados a partir de la notificación escrita de la controversia.

**b) Conciliación:** Si la negociación directa no resuelve la controversia, las partes acudirán a un centro de conciliación legalmente establecido en la ciudad de {contract_city}, Colombia. Los costos de la conciliación serán asumidos por partes iguales.

**c) Jurisdicción ordinaria:** Si la conciliación no prospera dentro de los treinta (30) días calendario siguientes a la solicitud, las partes someterán la controversia a la jurisdicción civil ordinaria de la ciudad de {contract_city}, Colombia, con renuncia expresa a cualquier otro fuero que pudiera corresponderles.

Las costas y gastos judiciales del proceso serán asumidos por la parte vencida, salvo decisión diferente del juez competente.

Durante el trámite de cualquier controversia, las obligaciones de confidencialidad y protección de datos personales previstas en el presente contrato continuarán plenamente vigentes.""",
    ),
    # CLÁUSULA VIGÉSIMA PRIMERA — Parágrafo Cuarto — Responsabilidad Operativa
    (
        """\
### Parágrafo Cuarto — Responsabilidad Operativa

Durante la vigencia del servicio, EL CONTRATISTA tendrá la responsabilidad de mantener la plataforma operativa dentro de las condiciones técnicas contratadas, siempre que se cumplan todas las siguientes condiciones: (i) EL CONTRATANTE se encuentre al día en sus pagos; (ii) el servicio se encuentre activo y vigente; (iii) no existan intervenciones de terceros no autorizados sobre el código, la infraestructura o los ambientes del producto; (iv) EL CONTRATANTE entregue oportunamente la información, accesos, aprobaciones y recursos necesarios; (v) la operación se desarrolle dentro de la capacidad de infraestructura prevista en la CLÁUSULA VIGÉSIMA TERCERA; y (vi) no se presenten los eventos descritos en el PARÁGRAFO SÉPTIMO de la CLÁUSULA VIGÉSIMA SEGUNDA.""",
        """\
### Parágrafo Cuarto — Responsabilidad Operativa

Durante la vigencia del servicio, EL CONTRATISTA tendrá la responsabilidad de mantener la plataforma operativa dentro de las condiciones técnicas contratadas, siempre que se cumplan todas las siguientes condiciones:

**a)** EL CONTRATANTE se encuentre al día en sus pagos.

**b)** El servicio se encuentre activo y vigente.

**c)** No existan intervenciones de terceros no autorizados sobre el código, la infraestructura o los ambientes del producto.

**d)** EL CONTRATANTE entregue oportunamente la información, accesos, aprobaciones y recursos necesarios.

**e)** La operación se desarrolle dentro de la capacidad de infraestructura prevista en la CLÁUSULA VIGÉSIMA TERCERA.

**f)** No se presenten los eventos descritos en el PARÁGRAFO SÉPTIMO de la CLÁUSULA VIGÉSIMA SEGUNDA.""",
    ),
    # CLÁUSULA VIGÉSIMA SEGUNDA — Parágrafo Primero — Definiciones Operativas
    (
        """\
### Parágrafo Primero — Definiciones Operativas

Para todos los efectos del presente contrato, las partes adoptan las siguientes definiciones:

1. **Día hábil:** el comprendido de lunes a viernes, con exclusión de sábados, domingos y días festivos de la República de Colombia conforme a la Ley 51 de 1983 y las normas que la modifiquen.
2. **Hora hábil:** la comprendida entre las nueve (9:00) y las dieciséis (16:00) horas, hora de Bogotá D.C., de un día hábil. Los plazos expresados en horas hábiles corren únicamente dentro de esa franja y se reanudan al inicio de la franja hábil siguiente.
3. **Protocolo de reporte de incidentes:** todo reporte se remitirá por el medio de notificación de la CLÁUSULA DÉCIMA QUINTA e incluirá, en el cuerpo del mensaje o en documento adjunto: a) título corto que identifique el problema; b) dirección (URL) de la página en la que inició la operación; c) dirección (URL) de la página en la que se presentó el problema, si es distinta de la anterior; d) pasos realizados, enumerados en orden; e) lo que ocurrió, con el mensaje de error exacto o una captura de pantalla; f) lo que se esperaba que ocurriera; g) dispositivo y navegador utilizados; y h) fecha y hora aproximada del suceso. Para el cómputo de los plazos, y en concordancia con la CLÁUSULA DÉCIMA QUINTA, el reporte se entenderá recibido al inicio de la franja hábil del día hábil siguiente al de su envío; el reporte que no reúna la información señalada no dará inicio al cómputo sino desde el momento en que sea completado.
4. **Restablecimiento:** se entenderá restablecido el servicio cuando la operación se reanude, aun mediante solución temporal, alternativa o parcial que permita continuar la operación de EL CONTRATANTE. La corrección definitiva de la causa raíz podrá adelantarse con posterioridad, sin que por ello subsista el incidente ni se entienda incumplido el plazo de resolución.
5. **Ventana de mantenimiento programado:** la interrupción planificada del servicio para actualizaciones, parches o labores de mantenimiento, informada a EL CONTRATANTE con una antelación no inferior a veinticuatro (24) horas. No constituye indisponibilidad, incidente ni incumplimiento.""",
        """\
### Parágrafo Primero — Definiciones Operativas

Para todos los efectos del presente contrato, las partes adoptan las siguientes definiciones:

**a) Día hábil:** el comprendido de lunes a viernes, con exclusión de sábados, domingos y días festivos de la República de Colombia conforme a la Ley 51 de 1983 y las normas que la modifiquen.

**b) Hora hábil:** la comprendida entre las nueve (9:00) y las dieciséis (16:00) horas, hora de Bogotá D.C., de un día hábil. Los plazos expresados en horas hábiles corren únicamente dentro de esa franja y se reanudan al inicio de la franja hábil siguiente.

**c) Protocolo de reporte de incidentes:** todo reporte se remitirá por el medio de notificación de la CLÁUSULA DÉCIMA QUINTA e incluirá, en el cuerpo del mensaje o en documento adjunto: **i)** título corto que identifique el problema; **ii)** dirección (URL) de la página en la que inició la operación; **iii)** dirección (URL) de la página en la que se presentó el problema, si es distinta de la anterior; **iv)** pasos realizados, enumerados en orden; **v)** lo que ocurrió, con el mensaje de error exacto o una captura de pantalla; **vi)** lo que se esperaba que ocurriera; **vii)** dispositivo y navegador utilizados; y **viii)** fecha y hora aproximada del suceso. Para el cómputo de los plazos, y en concordancia con la CLÁUSULA DÉCIMA QUINTA, el reporte se entenderá recibido al inicio de la franja hábil del día hábil siguiente al de su envío; el reporte que no reúna la información señalada no dará inicio al cómputo sino desde el momento en que sea completado.

**d) Restablecimiento:** se entenderá restablecido el servicio cuando la operación se reanude, aun mediante solución temporal, alternativa o parcial que permita continuar la operación de EL CONTRATANTE. La corrección definitiva de la causa raíz podrá adelantarse con posterioridad, sin que por ello subsista el incidente ni se entienda incumplido el plazo de resolución.

**e) Ventana de mantenimiento programado:** la interrupción planificada del servicio para actualizaciones, parches o labores de mantenimiento, informada a EL CONTRATANTE con una antelación no inferior a veinticuatro (24) horas. No constituye indisponibilidad, incidente ni incumplimiento.""",
    ),
    # CLÁUSULA VIGÉSIMA SEGUNDA — Parágrafo Segundo — Compromisos Permanentes de Operación
    (
        """\
### Parágrafo Segundo — Compromisos Permanentes de Operación

Mientras el servicio de hosting, mantenimiento y soporte se encuentre vigente, EL CONTRATISTA mantendrá sobre la plataforma: (i) monitoreo automatizado y permanente de su disponibilidad, con alertamiento independiente ante la falta de respuesta del servidor; (ii) copias de seguridad periódicas de la base de datos y copia integral del sistema, con retención no inferior a treinta (30) días y pruebas periódicas de restauración; (iii) aplicación de actualizaciones de seguridad y parches del sistema operativo y de los componentes de la plataforma; (iv) vigencia de los certificados de seguridad (SSL/TLS) del dominio de operación; y (v) notificación de los incidentes de seguridad conforme a la CLÁUSULA DÉCIMA SEGUNDA, dentro de las veinticuatro (24) horas siguientes a su conocimiento. Estos mecanismos corresponden a las prácticas operativas vigentes de EL CONTRATISTA, quien podrá sustituirlos o actualizarlos por otros de alcance equivalente o superior sin que ello requiera modificación del presente contrato.""",
        """\
### Parágrafo Segundo — Compromisos Permanentes de Operación

Mientras el servicio de hosting, mantenimiento y soporte se encuentre vigente, EL CONTRATISTA mantendrá sobre la plataforma:

**a)** Monitoreo automatizado y permanente de su disponibilidad, con alertamiento independiente ante la falta de respuesta del servidor.

**b)** Copias de seguridad periódicas de la base de datos y copia integral del sistema, con retención no inferior a treinta (30) días y pruebas periódicas de restauración.

**c)** Aplicación de actualizaciones de seguridad y parches del sistema operativo y de los componentes de la plataforma.

**d)** Vigencia de los certificados de seguridad (SSL/TLS) del dominio de operación.

**e)** Notificación de los incidentes de seguridad conforme a la CLÁUSULA DÉCIMA SEGUNDA, dentro de las veinticuatro (24) horas siguientes a su conocimiento.

Estos mecanismos corresponden a las prácticas operativas vigentes de EL CONTRATISTA, quien podrá sustituirlos o actualizarlos por otros de alcance equivalente o superior sin que ello requiera modificación del presente contrato.""",
    ),
    # CLÁUSULA VIGÉSIMA SEGUNDA — Parágrafo Cuarto — Niveles de Atención
    (
        """\
### Parágrafo Cuarto — Niveles de Atención

Durante la vigencia del servicio de hosting, mantenimiento y soporte, los incidentes se atenderán conforme a los siguientes niveles de prioridad:

| Nivel | Descripción del incidente | Respuesta | Resolución |
|---|---|---|---|
| CRÍTICO | Sistema caído, pérdida de datos o acceso completamente bloqueado | 4 horas hábiles | 1 día hábil |
| MEDIO | Funcionalidad importante degradada o con comportamiento incorrecto, pero el sistema sigue operando | 1 día hábil | 5 días hábiles |
| BAJO | Error menor, visual o de usabilidad, sin impacto operativo significativo | 3 días hábiles | 9 días hábiles |

Para el cómputo de estos plazos: (i) el plazo de respuesta se cuenta desde que el reporte completo se entiende recibido conforme al numeral 3 del PARÁGRAFO PRIMERO; (ii) el plazo de resolución se cuenta desde el momento en que se surte la respuesta; (iii) ambos corren exclusivamente en horas y días hábiles; y (iv) la clasificación inicial del nivel corresponde a EL CONTRATISTA conforme a la descripción de la tabla, y podrá ser reclasificada de forma motivada cuando el diagnóstico así lo determine. Fuera de la franja hábil, EL CONTRATISTA atenderá los incidentes de nivel CRÍTICO en la medida de la disponibilidad de su equipo técnico, sin que ello constituya compromiso de tiempo ni genere obligación exigible; el monitoreo automatizado del PARÁGRAFO SEGUNDO opera de manera permanente. En ausencia del servicio de hosting, mantenimiento y soporte, la atención de defectos se rige exclusivamente por los plazos de la garantía previstos en el PARÁGRAFO SEXTO de la CLÁUSULA SEGUNDA.""",
        """\
### Parágrafo Cuarto — Niveles de Atención

Durante la vigencia del servicio de hosting, mantenimiento y soporte, los incidentes se atenderán conforme a los siguientes niveles de prioridad:

| Nivel | Descripción del incidente | Respuesta | Resolución |
|---|---|---|---|
| CRÍTICO | Sistema caído, pérdida de datos o acceso completamente bloqueado | 4 horas hábiles | 1 día hábil |
| MEDIO | Funcionalidad importante degradada o con comportamiento incorrecto, pero el sistema sigue operando | 1 día hábil | 5 días hábiles |
| BAJO | Error menor, visual o de usabilidad, sin impacto operativo significativo | 3 días hábiles | 9 días hábiles |

Para el cómputo de estos plazos:

**a)** El plazo de respuesta se cuenta desde que el reporte completo se entiende recibido conforme al literal c) del PARÁGRAFO PRIMERO.

**b)** El plazo de resolución se cuenta desde el momento en que se surte la respuesta.

**c)** Ambos corren exclusivamente en horas y días hábiles.

**d)** La clasificación inicial del nivel corresponde a EL CONTRATISTA conforme a la descripción de la tabla, y podrá ser reclasificada de forma motivada cuando el diagnóstico así lo determine.

Fuera de la franja hábil, EL CONTRATISTA atenderá los incidentes de nivel CRÍTICO en la medida de la disponibilidad de su equipo técnico, sin que ello constituya compromiso de tiempo ni genere obligación exigible; el monitoreo automatizado del PARÁGRAFO SEGUNDO opera de manera permanente. En ausencia del servicio de hosting, mantenimiento y soporte, la atención de defectos se rige exclusivamente por los plazos de la garantía previstos en el PARÁGRAFO SEXTO de la CLÁUSULA SEGUNDA.""",
    ),
    # CLÁUSULA VIGÉSIMA SEGUNDA — Parágrafo Quinto — Protocolo de Atención de Incidentes Críticos
    (
        """\
### Parágrafo Quinto — Protocolo de Atención de Incidentes Críticos

Reportado un incidente de nivel CRÍTICO, EL CONTRATISTA aplicará el siguiente protocolo: 1) **Recepción y clasificación**, dentro del plazo de respuesta: acuse de recibo, clasificación del nivel de prioridad y asignación del responsable técnico; 2) **Diagnóstico y contención**, durante el curso de la atención: identificación de la causa probable, medidas de contención y estimación del restablecimiento, con informe de estado por escrito a EL CONTRATANTE; 3) **Restablecimiento**, dentro del plazo de resolución o de su prórroga, en los términos del numeral 4 del PARÁGRAFO PRIMERO; y 4) **Informe de cierre**, dentro de los cinco (5) días hábiles siguientes al restablecimiento, con la causa raíz, las acciones ejecutadas y las medidas preventivas adoptadas. El informe de cierre constituye para EL CONTRATANTE la constancia escrita de la atención prestada y para EL CONTRATISTA la acreditación del cumplimiento de sus obligaciones respecto de ese incidente.""",
        """\
### Parágrafo Quinto — Protocolo de Atención de Incidentes Críticos

Reportado un incidente de nivel CRÍTICO, EL CONTRATISTA aplicará el siguiente protocolo:

**a) Recepción y clasificación**, dentro del plazo de respuesta: acuse de recibo, clasificación del nivel de prioridad y asignación del responsable técnico.

**b) Diagnóstico y contención**, durante el curso de la atención: identificación de la causa probable, medidas de contención y estimación del restablecimiento, con informe de estado por escrito a EL CONTRATANTE.

**c) Restablecimiento**, dentro del plazo de resolución o de su prórroga, en los términos del literal d) del PARÁGRAFO PRIMERO.

**d) Informe de cierre**, dentro de los cinco (5) días hábiles siguientes al restablecimiento, con la causa raíz, las acciones ejecutadas y las medidas preventivas adoptadas.

El informe de cierre constituye para EL CONTRATANTE la constancia escrita de la atención prestada y para EL CONTRATISTA la acreditación del cumplimiento de sus obligaciones respecto de ese incidente.""",
    ),
    # CLÁUSULA VIGÉSIMA SEGUNDA — Parágrafo Sexto — Prórroga y Suspensión de los Plazos
    (
        """\
### Parágrafo Sexto — Prórroga y Suspensión de los Plazos

Cuando por la naturaleza, la complejidad o el origen del incidente la resolución no resulte alcanzable dentro del plazo previsto, EL CONTRATISTA lo informará por escrito a EL CONTRATANTE antes de su vencimiento, señalando la causa y la nueva fecha estimada de restablecimiento, y el plazo se entenderá prorrogado por el término allí indicado, el cual deberá ser razonable y proporcional a la causa invocada; comunicada la prórroga en estos términos, no habrá incumplimiento del plazo original. Asimismo, los plazos de respuesta y de resolución se suspenden, y se reanudan al cesar la causa, mientras subsista: (i) la espera de información, accesos, credenciales, aprobaciones o decisiones a cargo de EL CONTRATANTE; (ii) la ocurrencia de cualquiera de los eventos del PARÁGRAFO SÉPTIMO; (iii) la imposibilidad de reproducir el incidente por insuficiencia de la información reportada; o (iv) la vigencia de las etapas del protocolo previsto en la CLÁUSULA VIGÉSIMA CUARTA, en cuanto a los servicios allí suspendidos.""",
        """\
### Parágrafo Sexto — Prórroga y Suspensión de los Plazos

Cuando por la naturaleza, la complejidad o el origen del incidente la resolución no resulte alcanzable dentro del plazo previsto, EL CONTRATISTA lo informará por escrito a EL CONTRATANTE antes de su vencimiento, señalando la causa y la nueva fecha estimada de restablecimiento, y el plazo se entenderá prorrogado por el término allí indicado, el cual deberá ser razonable y proporcional a la causa invocada; comunicada la prórroga en estos términos, no habrá incumplimiento del plazo original.

Asimismo, los plazos de respuesta y de resolución se suspenden, y se reanudan al cesar la causa, mientras subsista:

**a)** La espera de información, accesos, credenciales, aprobaciones o decisiones a cargo de EL CONTRATANTE.

**b)** La ocurrencia de cualquiera de los eventos del PARÁGRAFO SÉPTIMO.

**c)** La imposibilidad de reproducir el incidente por insuficiencia de la información reportada.

**d)** La vigencia de las etapas del protocolo previsto en la CLÁUSULA VIGÉSIMA CUARTA, en cuanto a los servicios allí suspendidos.""",
    ),
    # CLÁUSULA VIGÉSIMA SEGUNDA — Parágrafo Séptimo — Exclusiones, Fuerza Mayor y Caso Fortuito
    (
        """\
### Parágrafo Séptimo — Exclusiones, Fuerza Mayor y Caso Fortuito

EL CONTRATISTA no responderá, y no se entenderán incumplidos los compromisos de esta cláusula, cuando la indisponibilidad, la degradación, la demora o el daño obedezcan a fuerza mayor o caso fortuito en los términos del artículo 64 del Código Civil, subrogado por el artículo 1.º de la Ley 95 de 1890, o a circunstancias ajenas a su control razonable, quedando comprendidos, de manera enunciativa y no taxativa: (i) fallas, interrupciones, degradación o suspensión del servicio del proveedor de infraestructura, del centro de datos, de la red o del suministro de energía; (ii) interrupciones de conectividad ajenas a la infraestructura administrada por EL CONTRATISTA, incluidas las de los equipos, redes o dispositivos de EL CONTRATANTE; (iii) ataques informáticos, accesos no autorizados o actos maliciosos de terceros, pese a la adopción de medidas de seguridad razonables; (iv) indisponibilidad, cambios o fallas de servicios de terceros integrados a la plataforma, incluidos los de autoridades tributarias, proveedores de facturación electrónica, pasarelas de pago y proveedores de correo electrónico; (v) actos de autoridad, cambios normativos, desastres naturales, conmoción interna, huelgas o paros ajenos a EL CONTRATISTA; (vi) intervención de terceros no autorizados sobre el código, la infraestructura o los ambientes del producto; (vii) uso de la plataforma fuera de las condiciones contratadas, o datos, cargas o configuraciones provistos por EL CONTRATANTE; y (viii) insuficiencia de los recursos de infraestructura en los términos de la CLÁUSULA VIGÉSIMA TERCERA. Durante la ocurrencia de estos eventos se suspenden los plazos y la responsabilidad operativa de EL CONTRATISTA, quien informará la situación a EL CONTRATANTE y desplegará los esfuerzos razonables a su alcance para mitigar sus efectos. Cuando la normalización del servicio dependa de un tercero, los tiempos y las fechas estimadas de restablecimiento quedarán sujetos a los de dicho tercero; EL CONTRATISTA lo informará así a EL CONTRATANTE, hará el seguimiento correspondiente y documentará la causa raíz, las fechas y la solución aplicada en el informe de cierre previsto en el PARÁGRAFO QUINTO. Lo anterior es concordante y acumulativo con las condiciones y exclusiones de la garantía y con la CLÁUSULA VIGÉSIMA.""",
        """\
### Parágrafo Séptimo — Exclusiones, Fuerza Mayor y Caso Fortuito

EL CONTRATISTA no responderá, y no se entenderán incumplidos los compromisos de esta cláusula, cuando la indisponibilidad, la degradación, la demora o el daño obedezcan a fuerza mayor o caso fortuito en los términos del artículo 64 del Código Civil, subrogado por el artículo 1.º de la Ley 95 de 1890, o a circunstancias ajenas a su control razonable, quedando comprendidos, de manera enunciativa y no taxativa:

**a)** Fallas, interrupciones, degradación o suspensión del servicio del proveedor de infraestructura, del centro de datos, de la red o del suministro de energía.

**b)** Interrupciones de conectividad ajenas a la infraestructura administrada por EL CONTRATISTA, incluidas las de los equipos, redes o dispositivos de EL CONTRATANTE.

**c)** Ataques informáticos, accesos no autorizados o actos maliciosos de terceros, pese a la adopción de medidas de seguridad razonables.

**d)** Indisponibilidad, cambios o fallas de servicios de terceros integrados a la plataforma, incluidos los de autoridades tributarias, proveedores de facturación electrónica, pasarelas de pago y proveedores de correo electrónico.

**e)** Actos de autoridad, cambios normativos, desastres naturales, conmoción interna, huelgas o paros ajenos a EL CONTRATISTA.

**f)** Intervención de terceros no autorizados sobre el código, la infraestructura o los ambientes del producto.

**g)** Uso de la plataforma fuera de las condiciones contratadas, o datos, cargas o configuraciones provistos por EL CONTRATANTE.

**h)** Insuficiencia de los recursos de infraestructura en los términos de la CLÁUSULA VIGÉSIMA TERCERA.

Durante la ocurrencia de estos eventos se suspenden los plazos y la responsabilidad operativa de EL CONTRATISTA, quien informará la situación a EL CONTRATANTE y desplegará los esfuerzos razonables a su alcance para mitigar sus efectos. Cuando la normalización del servicio dependa de un tercero, los tiempos y las fechas estimadas de restablecimiento quedarán sujetos a los de dicho tercero; EL CONTRATISTA lo informará así a EL CONTRATANTE, hará el seguimiento correspondiente y documentará la causa raíz, las fechas y la solución aplicada en el informe de cierre previsto en el PARÁGRAFO QUINTO. Lo anterior es concordante y acumulativo con las condiciones y exclusiones de la garantía y con la CLÁUSULA VIGÉSIMA.""",
    ),
)


def _apply_group(markdown, pairs):
    """Apply every pair or none; already-applied pairs are skipped."""
    updated = markdown
    for old, new in pairs:
        if updated.count(new) == 1 and old not in updated:
            continue
        if updated.count(old) != 1 or new in updated:
            logger.warning(
                'Contract template v8: preserving custom or ambiguous '
                'provisions; review the default template manually.',
            )
            return markdown
        updated = updated.replace(old, new, 1)
    return updated


def _patch_default_template(apps, schema_editor, reverse=False):
    ContractTemplate = apps.get_model('content', 'ContractTemplate')
    database = schema_editor.connection.alias
    template = (
        ContractTemplate.objects.using(database).select_for_update()
        .filter(is_default=True).first()
    )
    if template is None:
        return
    pairs = [(new, old) for old, new in reversed(PAIRS)] if reverse else PAIRS
    updated = _apply_group(template.content_markdown, pairs)
    if updated != template.content_markdown:
        template.content_markdown = updated
        template.save(using=database, update_fields=['content_markdown', 'updated_at'])


def update_default_template(apps, schema_editor):
    _patch_default_template(apps, schema_editor)


def revert_default_template(apps, schema_editor):
    _patch_default_template(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0258_communication_folders'),
    ]

    operations = [
        migrations.RunPython(update_default_template, revert_default_template),
    ]
