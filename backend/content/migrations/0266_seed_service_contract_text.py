"""Seed the standalone service contract for deals that close with two documents.

A deal can close with one contract or with two: a product contract (software
development and implementation) and a service contract (hosting, maintenance
and support). The product contract is derived at runtime from the default
text (clauses 21-24 removed plus three anchored adjustments, see
``content.services.contract_variants``). The service contract is new text: the
default contract's clauses 21-24, renumbered, plus the general clauses it
needs to stand alone, with cross-references adjusted to the new numbering.

Only an empty field on the default template is filled, so a later curated
text is never overwritten. The reverse empties it.
"""

from django.db import migrations

SERVICE_CONTRACT_MARKDOWN = """\
Entre las partes, por un lado **{client_full_name}** identificado con número de cédula {client_cedula}, quien en adelante y para los efectos del presente contrato se denomina como **EL CONTRATANTE**, y por el otro, **{contractor_full_name}** identificado con {contractor_id_type} número {contractor_id_number}, quien en adelante y para los efectos del presente contrato se denomina como **EL CONTRATISTA**, ambos mayores de edad, identificados como aparece al pie de las firmas, hemos acordado suscribir este contrato de prestación del servicio de hosting, mantenimiento y soporte, el cual se regirá por las siguientes cláusulas:

---

## CLÁUSULA PRIMERA — OBJETO DEL CONTRATO

EL CONTRATISTA se obliga a prestar, por sus propios medios y con plena autonomía técnica y administrativa, el servicio de hosting, mantenimiento y soporte del producto software desarrollado en virtud del contrato de prestación de servicios de desarrollo de software suscrito entre las partes (en adelante, el CONTRATO DE DESARROLLO). El valor, la periodicidad y las condiciones económicas del servicio se definen en el Documento Propuesta Comercial o en el documento que las partes suscriban para el efecto.

Este servicio comprende la operación de la plataforma en el ambiente de producción, su mantenimiento técnico y el soporte ante incidentes, dentro de la capacidad de infraestructura descrita en la CLÁUSULA SEXTA. Como contraprestación, EL CONTRATANTE pagará a EL CONTRATISTA el valor del servicio conforme a la CLÁUSULA SEGUNDA.

---

## CLÁUSULA SEGUNDA — PRECIO, INICIO DEL COBRO Y FORMA DE PAGO

### Parágrafo Primero — Inicio del Cobro

El cobro del servicio se causa únicamente a partir de la fecha de puesta en producción del producto software, entendida como el momento en que este queda desplegado y disponible en vivo para la operación de EL CONTRATANTE, fecha que las partes harán constar por escrito. Antes de esa fecha no se causará cobro alguno por este concepto, y el primer periodo del servicio se contará a partir de ella.

### Parágrafo Segundo — Forma y Fecha de Pago

El servicio se paga por periodos anticipados, conforme a la periodicidad definida en el Documento Propuesta Comercial. EL CONTRATISTA remitirá la cuenta de cobro o factura con una antelación no inferior a diez (10) días calendario al inicio de cada periodo, y EL CONTRATANTE la pagará dentro de los cinco (5) primeros días calendario del periodo que se inicia. El pago se entenderá realizado únicamente cuando los recursos hayan sido recibidos efectivamente por EL CONTRATISTA. La mora en el pago del servicio activa el protocolo previsto en la CLÁUSULA SÉPTIMA.

### Parágrafo Tercero — Medio de Pago

Los pagos se realizarán mediante transferencia bancaria a la cuenta {bank_name} {bank_account_type} No. {bank_account_number} a nombre de EL CONTRATISTA identificado con {contractor_id_type} número {contractor_id_number}.

### Parágrafo Cuarto — Intereses de Mora

En caso de mora en los pagos por parte de EL CONTRATANTE, se causarán intereses de mora a la tasa máxima legal vigente, sin perjuicio de la aplicación del protocolo previsto en la CLÁUSULA SÉPTIMA.

### Parágrafo Quinto — Condiciones Mínimas de Reajuste del Valor del Servicio

El valor del servicio estará sujeto a reajuste anual, conforme a las condiciones mínimas previstas en este parágrafo y a las condiciones particulares establecidas en el Documento Propuesta Comercial aceptado por las partes.

Como base mínima de reajuste se aplicará al valor vigente del servicio el porcentaje de incremento del salario mínimo mensual legal vigente (SMMLV) decretado por el Gobierno Nacional para el año en que corresponda efectuar el ajuste. Si para dicho año no se decretare incremento del SMMLV, se utilizará la variación anual del Índice de Precios al Consumidor (IPC) certificada por el DANE para el año inmediatamente anterior.

La periodicidad de pago, la fecha del primer reajuste, su aplicación en las renovaciones y los porcentajes o componentes adicionales que integren la fórmula de actualización serán los expresamente establecidos en el Documento Propuesta Comercial aceptado por las partes, respetando la base mínima aquí prevista. En consecuencia, el reajuste no se causará por el solo inicio del año calendario, sino en la oportunidad pactada en dicho documento, sin duplicarse por razón de la periodicidad de facturación.

El reajuste tiene por finalidad actualizar la contraprestación del servicio y atender la evolución de sus costos de operación, mantenimiento y soporte.

---

## CLÁUSULA TERCERA — DURACIÓN Y RENOVACIÓN

El presente contrato tendrá una duración inicial de {service_initial_term}, contada a partir de la fecha de puesta en producción prevista en el PARÁGRAFO PRIMERO de la CLÁUSULA SEGUNDA, y se renovará automáticamente por periodos iguales a la periodicidad de pago pactada en el Documento Propuesta Comercial, salvo que alguna de las partes manifieste por escrito su intención de no renovarlo con al menos {service_renewal_notice_days} días calendario de antelación al vencimiento del periodo en curso.

---

## CLÁUSULA CUARTA — RESPONSABILIDAD OPERATIVA

Durante la vigencia del servicio, EL CONTRATISTA tendrá la responsabilidad de mantener la plataforma operativa dentro de las condiciones técnicas contratadas, siempre que se cumplan todas las siguientes condiciones:

**a)** EL CONTRATANTE se encuentre al día en sus pagos.

**b)** El servicio se encuentre activo y vigente.

**c)** No existan intervenciones de terceros no autorizados sobre el código, la infraestructura o los ambientes del producto.

**d)** EL CONTRATANTE entregue oportunamente la información, accesos, aprobaciones y recursos necesarios.

**e)** La operación se desarrolle dentro de la capacidad de infraestructura prevista en la CLÁUSULA SEXTA.

**f)** No se presenten los eventos descritos en el PARÁGRAFO SÉPTIMO de la CLÁUSULA QUINTA.

---

## CLÁUSULA QUINTA — ATENCIÓN DE INCIDENTES, NIVELES DE SERVICIO Y CONTINUIDAD OPERATIVA

### Parágrafo Primero — Definiciones Operativas

Para todos los efectos del presente contrato, las partes adoptan las siguientes definiciones:

**a) Día hábil:** el comprendido de lunes a viernes, con exclusión de sábados, domingos y días festivos de la República de Colombia conforme a la Ley 51 de 1983 y las normas que la modifiquen.

**b) Hora hábil:** la comprendida entre las nueve (9:00) y las dieciséis (16:00) horas, hora de Bogotá D.C., de un día hábil. Los plazos expresados en horas hábiles corren únicamente dentro de esa franja y se reanudan al inicio de la franja hábil siguiente.

**c) Protocolo de reporte de incidentes:** todo reporte se remitirá por el medio de notificación de la CLÁUSULA DÉCIMA TERCERA e incluirá, en el cuerpo del mensaje o en documento adjunto: **i)** título corto que identifique el problema; **ii)** dirección (URL) de la página en la que inició la operación; **iii)** dirección (URL) de la página en la que se presentó el problema, si es distinta de la anterior; **iv)** pasos realizados, enumerados en orden; **v)** lo que ocurrió, con el mensaje de error exacto o una captura de pantalla; **vi)** lo que se esperaba que ocurriera; **vii)** dispositivo y navegador utilizados; y **viii)** fecha y hora aproximada del suceso. Para el cómputo de los plazos, y en concordancia con la CLÁUSULA DÉCIMA TERCERA, el reporte se entenderá recibido al inicio de la franja hábil del día hábil siguiente al de su envío; el reporte que no reúna la información señalada no dará inicio al cómputo sino desde el momento en que sea completado.

**d) Restablecimiento:** se entenderá restablecido el servicio cuando la operación se reanude, aun mediante solución temporal, alternativa o parcial que permita continuar la operación de EL CONTRATANTE. La corrección definitiva de la causa raíz podrá adelantarse con posterioridad, sin que por ello subsista el incidente ni se entienda incumplido el plazo de resolución.

**e) Ventana de mantenimiento programado:** la interrupción planificada del servicio para actualizaciones, parches o labores de mantenimiento, informada a EL CONTRATANTE con una antelación no inferior a veinticuatro (24) horas. No constituye indisponibilidad, incidente ni incumplimiento.

### Parágrafo Segundo — Compromisos Permanentes de Operación

Mientras el servicio de hosting, mantenimiento y soporte se encuentre vigente, EL CONTRATISTA mantendrá sobre la plataforma:

**a)** Monitoreo automatizado y permanente de su disponibilidad, con alertamiento independiente ante la falta de respuesta del servidor.

**b)** Copias de seguridad periódicas de la base de datos y copia integral del sistema, con retención no inferior a treinta (30) días y pruebas periódicas de restauración.

**c)** Aplicación de actualizaciones de seguridad y parches del sistema operativo y de los componentes de la plataforma.

**d)** Vigencia de los certificados de seguridad (SSL/TLS) del dominio de operación.

**e)** Notificación de los incidentes de seguridad conforme a la CLÁUSULA DÉCIMA, dentro de las veinticuatro (24) horas siguientes a su conocimiento.

Estos mecanismos corresponden a las prácticas operativas vigentes de EL CONTRATISTA, quien podrá sustituirlos o actualizarlos por otros de alcance equivalente o superior sin que ello requiera modificación del presente contrato.

### Parágrafo Tercero — Naturaleza de la Obligación

Las obligaciones de EL CONTRATISTA en materia de operación, atención de incidentes y soporte son obligaciones de medio y no de resultado: comprometen la diligencia debida, los medios técnicos descritos y los tiempos de atención pactados, y no un porcentaje de disponibilidad garantizado ni la ausencia de fallas. Las partes reconocen que ningún sistema informático opera libre de interrupciones, y que el valor del servicio retribuye la operación diligente dentro de ese marco y no el aseguramiento de resultados económicos de EL CONTRATANTE o de terceros.

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

Fuera de la franja hábil, EL CONTRATISTA atenderá los incidentes de nivel CRÍTICO en la medida de la disponibilidad de su equipo técnico, sin que ello constituya compromiso de tiempo ni genere obligación exigible; el monitoreo automatizado del PARÁGRAFO SEGUNDO opera de manera permanente. En ausencia del servicio de hosting, mantenimiento y soporte, la atención de defectos se rige exclusivamente por los plazos de la garantía previstos en el CONTRATO DE DESARROLLO.

### Parágrafo Quinto — Protocolo de Atención de Incidentes Críticos

Reportado un incidente de nivel CRÍTICO, EL CONTRATISTA aplicará el siguiente protocolo:

**a) Recepción y clasificación**, dentro del plazo de respuesta: acuse de recibo, clasificación del nivel de prioridad y asignación del responsable técnico.

**b) Diagnóstico y contención**, durante el curso de la atención: identificación de la causa probable, medidas de contención y estimación del restablecimiento, con informe de estado por escrito a EL CONTRATANTE.

**c) Restablecimiento**, dentro del plazo de resolución o de su prórroga, en los términos del literal d) del PARÁGRAFO PRIMERO.

**d) Informe de cierre**, dentro de los cinco (5) días hábiles siguientes al restablecimiento, con la causa raíz, las acciones ejecutadas y las medidas preventivas adoptadas.

El informe de cierre constituye para EL CONTRATANTE la constancia escrita de la atención prestada y para EL CONTRATISTA la acreditación del cumplimiento de sus obligaciones respecto de ese incidente.

### Parágrafo Sexto — Prórroga y Suspensión de los Plazos

Cuando por la naturaleza, la complejidad o el origen del incidente la resolución no resulte alcanzable dentro del plazo previsto, EL CONTRATISTA lo informará por escrito a EL CONTRATANTE antes de su vencimiento, señalando la causa y la nueva fecha estimada de restablecimiento, y el plazo se entenderá prorrogado por el término allí indicado, el cual deberá ser razonable y proporcional a la causa invocada; comunicada la prórroga en estos términos, no habrá incumplimiento del plazo original.

Asimismo, los plazos de respuesta y de resolución se suspenden, y se reanudan al cesar la causa, mientras subsista:

**a)** La espera de información, accesos, credenciales, aprobaciones o decisiones a cargo de EL CONTRATANTE.

**b)** La ocurrencia de cualquiera de los eventos del PARÁGRAFO SÉPTIMO.

**c)** La imposibilidad de reproducir el incidente por insuficiencia de la información reportada.

**d)** La vigencia de las etapas del protocolo previsto en la CLÁUSULA SÉPTIMA, en cuanto a los servicios allí suspendidos.

### Parágrafo Séptimo — Exclusiones, Fuerza Mayor y Caso Fortuito

EL CONTRATISTA no responderá, y no se entenderán incumplidos los compromisos de esta cláusula, cuando la indisponibilidad, la degradación, la demora o el daño obedezcan a fuerza mayor o caso fortuito en los términos del artículo 64 del Código Civil, subrogado por el artículo 1.º de la Ley 95 de 1890, o a circunstancias ajenas a su control razonable, quedando comprendidos, de manera enunciativa y no taxativa:

**a)** Fallas, interrupciones, degradación o suspensión del servicio del proveedor de infraestructura, del centro de datos, de la red o del suministro de energía.

**b)** Interrupciones de conectividad ajenas a la infraestructura administrada por EL CONTRATISTA, incluidas las de los equipos, redes o dispositivos de EL CONTRATANTE.

**c)** Ataques informáticos, accesos no autorizados o actos maliciosos de terceros, pese a la adopción de medidas de seguridad razonables.

**d)** Indisponibilidad, cambios o fallas de servicios de terceros integrados a la plataforma, incluidos los de autoridades tributarias, proveedores de facturación electrónica, pasarelas de pago y proveedores de correo electrónico.

**e)** Actos de autoridad, cambios normativos, desastres naturales, conmoción interna, huelgas o paros ajenos a EL CONTRATISTA.

**f)** Intervención de terceros no autorizados sobre el código, la infraestructura o los ambientes del producto.

**g)** Uso de la plataforma fuera de las condiciones contratadas, o datos, cargas o configuraciones provistos por EL CONTRATANTE.

**h)** Insuficiencia de los recursos de infraestructura en los términos de la CLÁUSULA SEXTA.

Durante la ocurrencia de estos eventos se suspenden los plazos y la responsabilidad operativa de EL CONTRATISTA, quien informará la situación a EL CONTRATANTE y desplegará los esfuerzos razonables a su alcance para mitigar sus efectos. Cuando la normalización del servicio dependa de un tercero, los tiempos y las fechas estimadas de restablecimiento quedarán sujetos a los de dicho tercero; EL CONTRATISTA lo informará así a EL CONTRATANTE, hará el seguimiento correspondiente y documentará la causa raíz, las fechas y la solución aplicada en el informe de cierre previsto en el PARÁGRAFO QUINTO. Lo anterior es concordante y acumulativo con las condiciones y exclusiones de la garantía prevista en el CONTRATO DE DESARROLLO y con el PARÁGRAFO NOVENO de la presente cláusula.

### Parágrafo Octavo — Responsabilidad frente a Clientes y Usuarios Finales

EL CONTRATISTA no tiene relación contractual alguna con los clientes, usuarios o terceros de EL CONTRATANTE: es EL CONTRATANTE quien contrata con ellos, define sus condiciones comerciales, asume sus compromisos de servicio y responde frente a ellos. En consecuencia, EL CONTRATANTE es el único responsable frente a sus clientes y usuarios finales por la prestación de sus propios servicios, y mantendrá indemne a EL CONTRATISTA de cualquier reclamación, demanda, sanción o requerimiento que aquellos formulen, así como de los costos de defensa que ello le irrogue, salvo en los casos de dolo o culpa grave de EL CONTRATISTA.

### Parágrafo Noveno — Límite de Responsabilidad del Servicio

En ningún caso EL CONTRATISTA responderá por lucro cesante, pérdida de ingresos, de ventas, de negocio o de clientela, daño reputacional, ni por daños indirectos, imprevisibles o consecuenciales de EL CONTRATANTE o de terceros, derivados de la prestación o de la interrupción del servicio de hosting, mantenimiento y soporte, en concordancia con el artículo 1616 del Código Civil. La responsabilidad total y agregada de EL CONTRATISTA por toda reclamación derivada de dicho servicio no excederá el valor efectivamente pagado por EL CONTRATANTE por el último periodo de suscripción del servicio contratado —conforme a la periodicidad definida en el Documento Propuesta Comercial, sea esta mensual, trimestral, semestral, anual u otra— inmediatamente anterior al hecho que la origine; cuando aún no se hubiere pagado un periodo completo del servicio, el límite será el valor vigente de un (1) periodo de suscripción del servicio. Este límite no aplica en los casos de dolo o culpa grave de EL CONTRATISTA, ni respecto de las obligaciones de confidencialidad y de protección de datos personales, conforme a los artículos 63 y 1522 del Código Civil.

---

## CLÁUSULA SEXTA — RECURSOS DE INFRAESTRUCTURA, CAPACIDAD OPERATIVA Y ESCALAMIENTO

El servicio de hosting se presta sobre la infraestructura cuya capacidad técnica se describe en el Documento Propuesta Comercial. El valor del servicio retribuye la operación, el mantenimiento y el soporte de la plataforma dentro de dicha capacidad; toda operación que la exceda requiere infraestructura de capacidad superior y no se encuentra comprendida en el valor pactado.

### Parágrafo Primero — Monitoreo y Reporte de Consumo

EL CONTRATISTA monitoreará de forma continua el consumo efectivo de procesamiento, memoria, almacenamiento y transferencia de datos, y entregará a EL CONTRATANTE un reporte de consumo con cada periodo de facturación del servicio, así como cada vez que este lo solicite por escrito.

### Parágrafo Segundo — Alerta Temprana

Cuando el consumo de cualquiera de los recursos supere el ochenta por ciento (80%) de su capacidad de forma sostenida durante siete (7) días calendario, EL CONTRATISTA lo notificará a EL CONTRATANTE de manera formal y por escrito, acompañando la evidencia técnica de la medición y una propuesta de escalamiento de la infraestructura, con su especificación técnica y su costo.

### Parágrafo Tercero — Decisión y Costo del Escalamiento

EL CONTRATANTE dispondrá de quince (15) días hábiles, contados desde la notificación anterior, para aprobar por escrito el escalamiento propuesto. La provisión oportuna de los recursos que la operación de su negocio demande es una obligación de EL CONTRATANTE. Aprobado el escalamiento, EL CONTRATISTA contratará y administrará la infraestructura ampliada; el mayor costo se trasladará a EL CONTRATANTE y se facturará de manera separada, sin perjuicio del ajuste del valor del servicio que las partes acuerden por escrito por el mayor esfuerzo operativo.

### Parágrafo Cuarto — Exoneración por Insuficiencia de Recursos

Vencido el plazo del parágrafo anterior sin que EL CONTRATANTE haya aprobado el escalamiento, EL CONTRATISTA quedará exonerado de toda responsabilidad por la degradación del rendimiento, la lentitud, la indisponibilidad, la interrupción del servicio o la pérdida de datos atribuibles a la insuficiencia de los recursos de infraestructura, y quedarán suspendidos los niveles de atención de la CLÁUSULA QUINTA mientras persista dicha condición, sin que ello constituya incumplimiento imputable a EL CONTRATISTA ni dé lugar a indemnización, descuento o reclamación en su contra. Esta exoneración opera únicamente si EL CONTRATISTA ha cumplido los deberes de monitoreo, reporte y notificación oportuna de los PARÁGRAFOS PRIMERO y SEGUNDO: EL CONTRATISTA responde por medir, advertir y proponer a tiempo; EL CONTRATANTE, por proveer los recursos que su operación demande.

### Parágrafo Quinto — Crecimiento por Nuevos Desarrollos

La incorporación de nuevas fases, módulos o funcionalidades al producto puede incrementar el consumo de recursos. El dimensionamiento de la infraestructura necesaria para soportarlos se evaluará dentro del alcance de cada nuevo desarrollo, conforme al procedimiento de esta cláusula.

---

## CLÁUSULA SÉPTIMA — PROTOCOLO DE MORA Y SUSPENSIÓN DEL SERVICIO

En caso de mora en las obligaciones de pago del servicio de hosting, mantenimiento y soporte, EL CONTRATISTA aplicará el siguiente protocolo escalonado, que constituye el único procedimiento por el cual puede suspenderse la operación de la plataforma por causa de dicha mora. Los plazos se cuentan en días calendario de mora, desde el día siguiente al vencimiento del plazo de pago:

| Etapa | Día de mora | Actuación de EL CONTRATISTA | Efecto sobre la operación |
|---|---|---|---|
| 1 — Aviso | Día 1 | Aviso formal de mora al medio de notificación de EL CONTRATANTE, con el detalle de la obligación vencida y los intereses causados | Ninguno. Todos los servicios continúan con normalidad |
| 2 — Suspensión de evolución | Día 30 | Suspensión del desarrollo de nuevas funcionalidades, de los desarrollos evolutivos, de las actualizaciones y del soporte no crítico | La plataforma sigue operando. Se conservan disponibilidad, copias de seguridad y atención de incidentes CRÍTICOS |
| 3 — Suspensión de servicios | Día 60 | Suspensión del mantenimiento y del soporte, conservando únicamente la disponibilidad de la plataforma y las copias de seguridad. Remisión del preaviso formal de suspensión de la operación | La plataforma sigue operando |
| 4 — Vencimiento del plazo de cura | Día 90 | EL CONTRATISTA queda facultado para suspender la operación de la plataforma, previo aviso escrito con quince (15) días calendario de antelación, y para dar por terminado el contrato conforme a la CLÁUSULA DÉCIMA CUARTA | Agotado el preaviso, cesa la operación |

### Parágrafo Primero — Continuidad Durante el Periodo de Cura

Durante las etapas 1, 2 y 3 del protocolo —los primeros noventa (90) días calendario de mora— lo que se suspende es la evolución, el soporte y el mantenimiento, y nunca el uso operativo del producto ya desplegado. EL CONTRATISTA reconoce que la operación de EL CONTRATANTE, y la de los clientes de este cuando los tenga, dependen de la continuidad de la plataforma, y asume el compromiso de no interrumpirla dentro del periodo de cura.

### Parágrafo Segundo — Plazo Máximo de Cura y Obligaciones Durante la Mora

El plazo máximo para normalizar los pagos es de noventa (90) días calendario contados desde el primer día de mora; la mora en varias obligaciones simultáneas no lo amplía, y el plazo se cuenta desde la primera obligación impagada que permanezca sin pago. El transcurso del protocolo no suspende la causación de las obligaciones económicas: los periodos del servicio que se inicien durante el protocolo se causan y se facturan íntegramente, por cuanto el servicio continúa prestándose, y los intereses de mora se causan de manera independiente sobre cada obligación incumplida. El periodo de cura es un término de tolerancia operativa y no constituye condonación, aplazamiento ni novación de las obligaciones de EL CONTRATANTE.

### Parágrafo Tercero — Reanudación

Pagada la totalidad de las obligaciones vencidas junto con sus intereses, EL CONTRATISTA reanudará los servicios suspendidos dentro de los cinco (5) días hábiles siguientes a la verificación del pago, y el protocolo se entenderá agotado sin efectos ulteriores.

### Parágrafo Cuarto — Salida Ordenada

Si se llegare a la suspensión de la operación prevista en la etapa 4, EL CONTRATISTA entregará a EL CONTRATANTE, dentro del preaviso de quince (15) días calendario, una exportación completa de sus datos operativos alojados en la plataforma, en formato estándar de intercambio, y los conservará por treinta (30) días calendario adicionales antes de su eliminación definitiva. Esta salida ordenada no habilita la entrega del código fuente cuando existan saldos pendientes, conforme a lo pactado en el CONTRATO DE DESARROLLO, ni extingue las obligaciones económicas pendientes de EL CONTRATANTE.

### Parágrafo Quinto — Concordancia

Este protocolo rige la suspensión de la operación de la plataforma por mora en las obligaciones del servicio. Los intereses de mora previstos en el PARÁGRAFO CUARTO de la CLÁUSULA SEGUNDA y la terminación prevista en la CLÁUSULA DÉCIMA CUARTA conservan su aplicación en sus propios ámbitos. Las obligaciones derivadas del desarrollo del producto software, incluidas su suspensión, terminación y el derecho de retención, se rigen por el CONTRATO DE DESARROLLO.

---

## CLÁUSULA OCTAVA — EXCLUSIÓN DE LA RELACIÓN LABORAL

Dada la naturaleza del presente contrato, no existirá relación laboral alguna entre EL CONTRATANTE y EL CONTRATISTA, ni con el personal que este vincule para apoyar la ejecución del objeto contractual. EL CONTRATISTA ejecutará el contrato de forma independiente y con plena autonomía técnica y administrativa. EL CONTRATISTA será responsable del pago de sus propias obligaciones en materia de seguridad social integral (salud, pensión y riesgos laborales), así como de las correspondientes al personal que subcontrate.

---

## CLÁUSULA NOVENA — CONFIDENCIALIDAD

Ambas partes se obligan recíprocamente a mantener la confidencialidad sobre toda la información que conozcan o a la que tengan acceso con ocasión de la negociación, celebración y ejecución del presente contrato, incluidos los datos, accesos, credenciales y configuraciones de la plataforma, con independencia del medio en el cual se encuentre soportada.

La parte que reciba la información no podrá divulgarla, publicarla, comercializarla ni compartirla con terceros sin autorización previa y escrita de la otra parte, ni usarla para fines distintos de la ejecución del presente contrato. Solo podrá darla a conocer a sus administradores, empleados, subcontratistas, colaboradores y asesores que necesiten conocerla para la ejecución del contrato, siempre que se encuentren sujetos a obligaciones de confidencialidad no menos exigentes que las previstas en la presente cláusula, y responderá por el incumplimiento de dichas personas como si se tratara del suyo propio.

Las obligaciones de la presente cláusula no aplican sobre aquella información que: **a)** sea o llegue a ser del dominio público sin que medie acto u omisión de la parte que la recibe; **b)** estuviese en posesión legítima de la parte que la recibe con anterioridad a su divulgación; **c)** sea legalmente divulgada por un tercero que no esté sujeto a restricciones en cuanto a su divulgación y la haya obtenido de buena fe; o **d)** deba ser divulgada por orden judicial o requerimiento de autoridad competente, en cuyo caso se notificará a la otra parte con la mayor antelación posible y se divulgará únicamente la información estrictamente requerida.

Las obligaciones de la presente cláusula permanecerán vigentes durante la ejecución del contrato y por un periodo de dos (2) años contados a partir de su terminación por cualquier causa.

---

## CLÁUSULA DÉCIMA — PROTECCIÓN Y TRATAMIENTO DE DATOS PERSONALES

EL CONTRATISTA asume la obligación de proteger los datos personales a los que acceda con ocasión del presente contrato, en cumplimiento de la Ley 1581 de 2012 y sus decretos reglamentarios. Para tal efecto, EL CONTRATISTA deberá:

**a)** Adoptar las medidas técnicas, administrativas y humanas necesarias para garantizar la seguridad de los datos personales y evitar su adulteración, pérdida, consulta, uso o acceso no autorizado.

**b)** Limitar el tratamiento de los datos personales de terceros entregados por EL CONTRATANTE exclusivamente a la finalidad propia de sus obligaciones contractuales.

**c)** Garantizar los derechos de privacidad, intimidad y buen nombre de los titulares de los datos personales.

**d)** Informar a EL CONTRATANTE de manera inmediata cualquier sospecha de pérdida, fuga, acceso no autorizado o incidente de seguridad que afecte los datos personales a los que haya tenido acceso.

**e)** Una vez finalizado el contrato, devolver o eliminar los datos personales que le hayan sido entregados, salvo que exista obligación legal de conservarlos.

---

## CLÁUSULA DÉCIMA PRIMERA — MODIFICACIONES

Cualquier modificación a los términos y condiciones del presente contrato deberá ser acordada entre las partes y requerirá de un "OTROSÍ" firmado por ellas.

---

## CLÁUSULA DÉCIMA SEGUNDA — ACUERDO

El presente contrato, junto con el Documento Propuesta Comercial en lo relativo al servicio de hosting, mantenimiento y soporte, constituye el acuerdo total entre las partes sobre su objeto. Este acuerdo reemplaza en su integridad y deja sin efecto cualquier otro acuerdo verbal o escrito celebrado con anterioridad entre las partes sobre el mismo objeto. El desarrollo del producto software se rige por el CONTRATO DE DESARROLLO.

---

## CLÁUSULA DÉCIMA TERCERA — NOTIFICACIÓN

Para todos los efectos legales y de notificación derivados del presente contrato, las partes establecen los siguientes medios de contacto:

**a) EL CONTRATANTE:** correo electrónico {client_email}

**b) EL CONTRATISTA:** correo electrónico {contractor_email}

Toda notificación enviada a las direcciones de correo electrónico aquí indicadas se entenderá válidamente surtida al día hábil siguiente a su envío. Cualquier cambio en los datos de notificación deberá ser comunicado por escrito a la otra parte con al menos cinco (5) días hábiles de antelación.

---

## CLÁUSULA DÉCIMA CUARTA — TERMINACIÓN

El presente contrato podrá darse por terminado en los siguientes casos:

### Parágrafo Primero — Terminación por Mutuo Acuerdo

Las partes podrán dar por terminado el contrato en cualquier momento mediante acuerdo escrito, en el cual se definirán la liquidación de pagos y demás aspectos pendientes.

### Parágrafo Segundo — Terminación por EL CONTRATANTE

EL CONTRATANTE podrá dar por terminado el contrato mediante notificación escrita con al menos {service_termination_notice_days} días calendario de antelación. Los valores correspondientes a periodos del servicio ya iniciados no serán reembolsables.

### Parágrafo Tercero — Terminación por EL CONTRATISTA

EL CONTRATISTA podrá dar por terminado el contrato en los siguientes casos:

**a)** Por mora en el pago del servicio, conforme a la etapa 4 del protocolo previsto en la CLÁUSULA SÉPTIMA.

**b)** Cuando EL CONTRATANTE incumpla reiteradamente sus obligaciones contractuales, afectando de manera sustancial la prestación del servicio, mediante notificación escrita con al menos quince (15) días hábiles de antelación.

En caso de terminación del contrato por cualquier causa, se aplicará lo previsto en el PARÁGRAFO CUARTO de la CLÁUSULA SÉPTIMA respecto de la exportación y conservación de los datos operativos de EL CONTRATANTE.

---

## CLÁUSULA DÉCIMA QUINTA — INCUMPLIMIENTO

En caso de que cualquiera de las partes incumpla una o varias de las obligaciones derivadas del presente contrato, la parte afectada deberá notificar por escrito a la parte incumplida, describiendo el incumplimiento de manera detallada.

### Parágrafo Primero — Plazo para Subsanar

La parte incumplida dispondrá de un plazo de quince (15) días hábiles, contados a partir del día siguiente a la recepción de la notificación, para subsanar el incumplimiento. Tratándose de obligaciones de pago, se aplicará el protocolo previsto en la CLÁUSULA SÉPTIMA.

### Parágrafo Segundo — Consecuencias del Incumplimiento No Subsanado

Si transcurrido el plazo correspondiente el incumplimiento no ha sido subsanado, la parte afectada podrá:

**a)** Dar por terminado el contrato conforme a lo establecido en la CLÁUSULA DÉCIMA CUARTA, sin perjuicio de las acciones legales a que haya lugar.

**b)** Exigir el cumplimiento de las obligaciones pendientes junto con la indemnización de los perjuicios causados, conforme a la legislación civil colombiana y sujeto a los límites establecidos en el PARÁGRAFO NOVENO de la CLÁUSULA QUINTA.

---

## CLÁUSULA DÉCIMA SEXTA — RESOLUCIÓN DE CONFLICTOS

Toda controversia o diferencia que surja entre las partes con ocasión del presente contrato, su interpretación, ejecución o terminación, se resolverá conforme al siguiente procedimiento:

**a) Negociación directa:** Las partes intentarán resolver la controversia de manera directa y de buena fe dentro de un plazo de quince (15) días hábiles contados a partir de la notificación escrita de la controversia.

**b) Conciliación:** Si la negociación directa no resuelve la controversia, las partes acudirán a un centro de conciliación legalmente establecido en la ciudad de {contract_city}, Colombia. Los costos de la conciliación serán asumidos por partes iguales.

**c) Jurisdicción ordinaria:** Si la conciliación no prospera dentro de los treinta (30) días calendario siguientes a la solicitud, las partes someterán la controversia a la jurisdicción civil ordinaria de la ciudad de {contract_city}, Colombia, con renuncia expresa a cualquier otro fuero que pudiera corresponderles.

Las costas y gastos judiciales del proceso serán asumidos por la parte vencida, salvo decisión diferente del juez competente.

Durante el trámite de cualquier controversia, las obligaciones de confidencialidad y protección de datos personales previstas en el presente contrato continuarán plenamente vigentes.

---

## CLÁUSULA DÉCIMA SÉPTIMA — MÉRITO EJECUTIVO

El presente contrato, junto con sus anexos, las cuentas de cobro o facturas y los comprobantes de pago, prestará mérito ejecutivo para el cobro de las obligaciones claras, expresas y exigibles que de él se deriven, sin necesidad de requerimiento judicial previo ni constitución en mora, de conformidad con lo establecido en el artículo 422 del Código General del Proceso colombiano.

Para todos los efectos legales, las partes reconocen que las obligaciones de pago contenidas en el presente contrato y en el Documento Propuesta Comercial constituyen títulos ejecutivos suficientes para iniciar las acciones de cobro correspondientes."""


def seed_service_contract(apps, schema_editor):
    ContractTemplate = apps.get_model('content', 'ContractTemplate')
    database = schema_editor.connection.alias
    template = ContractTemplate.objects.using(database).filter(is_default=True).first()
    if template is None or template.service_content_markdown:
        return
    template.service_content_markdown = SERVICE_CONTRACT_MARKDOWN
    template.save(using=database, update_fields=['service_content_markdown', 'updated_at'])


def clear_service_contract(apps, schema_editor):
    ContractTemplate = apps.get_model('content', 'ContractTemplate')
    database = schema_editor.connection.alias
    ContractTemplate.objects.using(database).filter(is_default=True).update(
        service_content_markdown='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0265_contract_modality_split'),
    ]

    operations = [
        migrations.RunPython(seed_service_contract, clear_service_contract),
    ]
