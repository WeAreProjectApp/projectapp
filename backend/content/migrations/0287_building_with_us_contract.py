"""Private first contract, independent of subsequent MCP refinements."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# Historical seed: keep the full legal-commercial copy embedded here.
CONTRACT_V1_MARKDOWN = """# CONTRATO DE ALIANZA COMERCIAL BUILDING WITH US

Entre los suscritos, PROJECTAPP, casa de software cuya razón social es XXX-XXX-XXX, identificada con NIT XXX-XXX-XXX, representada legalmente por XXX-XXX-XXX, quien actúa con facultades suficientes y en adelante se denomina PROJECTAPP; y XXX-XXX-XXX, identificado con XXX-XXX-XXX, quien actúa en nombre propio o en representación de XXX-XXX-XXX y en adelante se denomina EL ALIADO o EXPERTO DE NEGOCIO, se celebra este contrato de alianza comercial, regido por las siguientes disposiciones y sus anexos.

## ANTECEDENTES

PROJECTAPP dispone de una cadena de producción de software que comprende levantamiento de requerimientos, diseño, desarrollo, implementación, entrega, lanzamiento y operación en producción. EL ALIADO conoce un sector de negocio y propone una idea o problema con impacto económico susceptible de monetización, cuya descripción se consignará en el Anexo A. Las partes desean unir estas capacidades mediante el programa Building with Us, validar un producto útil y desarrollar una oportunidad comercial bajo compromisos verificables, un alcance delimitado y una participación que se gana por hitos. Estos antecedentes orientan la interpretación del contrato y no sustituyen las obligaciones expresas que siguen.

## CLÁUSULA PRIMERA — OBJETO

Las partes acuerdan incubar el producto de software descrito en el Anexo A, en adelante el PRODUCTO, bajo el modelo de alianza elegido en las Condiciones particulares. La alianza comprende su implementación, validación y estabilización dentro del alcance y periodo pactados, así como las actividades comerciales acordadas para llevarlo a usuarios reales. La descripción del PRODUCTO, sus objetivos y los entregables exigibles serán los de los anexos aprobados; ninguna idea adicional se incorpora por el solo hecho de ser comentada durante la ejecución.

## CLÁUSULA SEGUNDA — MODELOS DE ALIANZA

Los siguientes modelos coexisten dentro del programa, pero cada alianza elige uno en las Condiciones particulares. El cambio de modelo exige un otrosí escrito firmado por ambas partes, que ajuste aportes, hitos y participación sin presumir efectos retroactivos.

| Modelo | Aporte principal del EXPERTO DE NEGOCIO | Participación de referencia |
| --- | --- | --- |
| Modelo 1 «Con inversión mensual» | Paga una cuota mensual del orden de COP 1.000.000 durante el periodo de incubación. | 50 % PROJECTAPP / 50 % EL ALIADO |
| Modelo 2 «Con validación» | No aporta dinero al desarrollo; asume el control de calidad, la validación con criterio de negocio y el trabajo necesario para llegar a un MVP que las personas puedan usar. | 70 % PROJECTAPP / 30 % EL ALIADO |
| Modelo 3 «Con inversión comercial» | Compromete dinero para mercadeo y la estrategia de ventas durante el periodo acordado. | 50 % PROJECTAPP / 50 % EL ALIADO o 60 % PROJECTAPP / 40 % EL ALIADO |

Los valores anteriores son referencias y no obligaciones económicas automáticamente exigibles. Los importes, porcentajes, fechas y presupuesto efectivos de cada alianza se fijan en las Condiciones particulares. La cuota mensual depende del alcance y tamaño del PRODUCTO. En todos los modelos subsiste el aporte propio a ventas exigido en la cláusula sexta; en el Modelo 3 se precisará qué parte de su inversión comercial satisface ese presupuesto, para evitar duplicar un mismo aporte.

## CLÁUSULA TERCERA — PERIODO DE INCUBACIÓN

La incubación tendrá una duración elegida de tres (3), seis (6), nueve (9) o doce (12) meses, contados desde el acta de inicio firmada por las partes. El cronograma distribuirá las etapas de implementación, validación y estabilización, con responsables y dependencias identificadas. No existe prórroga automática por retrasos, nuevas solicitudes o continuidad de reuniones. Toda ampliación requiere acuerdo escrito sobre su duración, alcance, aportes y presupuesto antes de ejecutarse. El vencimiento no borra los derechos consolidados ni las obligaciones que expresamente sobrevivan.

## CLÁUSULA CUARTA — ALCANCE Y OBJETIVOS

El Anexo A es la línea base del proyecto e identifica cada requerimiento, criterio de aceptación, evidencia, responsable, dependencia y exclusión. Las partes distinguirán lo incluido de lo que queda fuera de alcance y aprobarán sus objetivos antes de iniciar. Cada cambio se registrará con su efecto sobre plazo, costo, aportes y hitos; los cambios materiales sólo se ejecutarán después de su aprobación escrita por ambas partes. El silencio, la falta de respuesta o el uso parcial no equivalen a aceptación de un entregable ni de un cambio. Esta alianza no constituye un proyecto infinito: al agotarse el alcance o el periodo pactado, cualquier trabajo adicional requiere una nueva definición escrita.

## CLÁUSULA QUINTA — APORTES DE PROJECTAPP

PROJECTAPP aportará su cadena de producción para levantar requerimientos, diseñar, desarrollar, implementar, entregar y lanzar el PRODUCTO conforme al Anexo A. Durante la incubación asumirá la operación en producción con hosting, mantenimiento y soporte previstos en el alcance y presupuesto aprobados. Identificará los accesos, insumos y decisiones que necesite del ALIADO, documentará entregas y facilitará evidencia para su validación. Los servicios de terceros, capacidad de infraestructura y niveles de soporte se delimitarán por escrito; no se presume cobertura ilimitada ni obligación de asumir gastos comerciales del ALIADO.

## CLÁUSULA SEXTA — COMPROMISO ESPERADO DEL ALIADO

EL ALIADO cumplirá el aporte propio del modelo elegido: cuota mensual en el Modelo 1; control de calidad, validación con criterio y acompañamiento hasta un MVP utilizable en el Modelo 2; inversión en mercadeo y estrategia de ventas en el Modelo 3. En todos los modelos aportará conocimiento de negocio, información oportuna y disponibilidad para decidir y validar. Además, la contraparte también deberá poner su dinero en las ventas: el presupuesto de ventas y mercadeo con recursos propios, su calendario de ejecución y su destinación se definirán en las Condiciones particulares.

El compromiso se medirá, como mínimo, por: pagos realizados dentro de XXX-XXX-XXX días de su vencimiento; revisiones y validaciones entregadas dentro de cinco (5) días hábiles de recibir un entregable y su evidencia completa; y presupuesto de ventas ejecutado conforme al calendario aprobado, con reporte mensual de gastos, acciones y resultados. El comité registrará la entrega de insumos y las dependencias que impidan revisar. Una observación debe identificar el criterio no satisfecho y su evidencia; no reemplaza la validación una respuesta genérica. Estos indicadores podrán complementarse en las Condiciones particulares sin eliminar el aporte propio a ventas.

## CLÁUSULA SÉPTIMA — HITOS Y CONSOLIDACIÓN DE LA PARTICIPACIÓN

La participación pactada a favor del ALIADO se gana progresivamente al cumplir los hitos del Anexo B; no se entrega íntegramente al firmar. Como referencia, se consolidará el diez por ciento (10 %) de esa participación con H1, alcance aprobado y acta de inicio; el treinta por ciento (30 %) con H2, primera versión funcional validada; el treinta por ciento (30 %) con H3, MVP en producción con usuarios reales; y el treinta por ciento (30 %) con H4, meta comercial acordada. Estas fracciones se calculan sobre la participación total pactada del ALIADO, no sobre el cien por ciento del PRODUCTO. El Anexo B puede ajustar criterios y fracciones por proyecto, siempre que su suma corresponda a la totalidad de la participación pactada.

Un comité integrado por un representante de cada parte verificará la evidencia y declarará cada hito mediante acta firmada dentro de cinco (5) días hábiles de recibirla completa. El acta expresará el criterio cumplido, evidencia, fecha y participación acumulada. La falta de acta no se suple por silencio. Los desacuerdos se documentarán y tramitarán por la cláusula vigésima, sin dar por cumplido un hito unilateralmente. La consolidación está sujeta a las reglas de pérdida por incumplimiento o abandono de las cláusulas novena y decimocuarta.

## CLÁUSULA OCTAVA — NATURALEZA DE LA PARTICIPACIÓN

La participación recae sobre los derechos económicos del PRODUCTO: los ingresos netos obtenidos de su explotación y el valor recibido por su venta o licenciamiento, según los porcentajes consolidados y la liquidación acordada. Son ingresos netos los efectivamente recibidos, descontados impuestos, devoluciones y costos directos aprobados y soportados; no se deducirán cargos unilaterales ajenos al PRODUCTO. Las partes definirán en las Condiciones particulares la periodicidad de cuentas y distribución.

La participación no representa acciones o cuotas de PROJECTAPP ni de otra sociedad. Este contrato no constituye sociedad de hecho, mandato, representación recíproca ni relación laboral. Ninguna parte puede obligar a la otra frente a terceros sin autorización escrita. Las partes podrán migrar la alianza a una SAS o a un contrato de cuentas en participación mediante un acuerdo definitivo posterior que reconozca lo consolidado y regule su transición.

## CLÁUSULA NOVENA — INCUMPLIMIENTO DEL COMPROMISO ESPERADO

Si EL ALIADO incumple el compromiso esperado, PROJECTAPP notificará por escrito el hecho, el indicador afectado y la evidencia disponible, y concederá quince (15) días hábiles desde la recepción para subsanarlo. La subsanación deberá acreditarse ante el comité; una promesa de cumplimiento no equivale a ejecución. Si el incumplimiento no se subsana dentro del plazo, EL ALIADO pierde toda su participación, tanto consolidada como pendiente, la cual permanece con PROJECTAPP. Esta consecuencia incluye los derechos económicos y la proporción patrimonial sobre los desarrollos del PRODUCTO correspondiente a esa participación, sin afectar los activos preexistentes del ALIADO.

PROJECTAPP podrá continuar el PRODUCTO por su cuenta, explotarlo y mantenerlo, dejando constancia escrita del cierre y de los derechos que permanecen a su favor. EL ALIADO suscribirá los instrumentos necesarios para documentar esa consecuencia. No habrá devolución de cuotas, inversiones comerciales u otros aportes ejecutados. Una controversia sobre el incumplimiento o su subsanación seguirá el mecanismo de la cláusula vigésima y no autoriza apropiaciones o accesos no consentidos.

## CLÁUSULA DÉCIMA — ÉXITO DEL PROYECTO

El proyecto se considera exitoso para efectos de esta alianza cuando se hayan cumplido los hitos pactados en el Anexo B, el MVP opere en producción con usuarios reales, se acredite la meta comercial acordada y EL ALIADO haya satisfecho su compromiso esperado. El comité dejará constancia de este resultado en acta. Si se alcanzan los hitos y se mantiene el compromiso, EL ALIADO conserva la participación consolidada y sus derechos económicos conforme a este contrato. El éxito no supone ingresos perpetuos ni una rentabilidad garantizada; la meta, periodo de medición y evidencia comercial deben quedar definidos antes de su evaluación.

## CLÁUSULA UNDÉCIMA — PROPIEDAD INTELECTUAL Y CÓDIGO

Los activos, marcas, contenidos, metodologías y software preexistentes continúan perteneciendo a quien los aporta. Los desarrollos específicos del PRODUCTO pertenecen patrimonialmente a las partes en proporción a la participación consolidada; la porción no consolidada permanece en PROJECTAPP y la pérdida prevista en la cláusula novena produce la correspondiente asignación a su favor. Los componentes reutilizables, bibliotecas y know-how de PROJECTAPP siguen siendo de PROJECTAPP, con licencia de uso integrada al PRODUCTO para su operación y continuidad, sin transferencia de su titularidad ni derecho a explotarlos separadamente. Se respetarán las licencias de terceros y los derechos morales de los autores.

PROJECTAPP administrará el repositorio y otorgará al ALIADO acceso de lectura al código y documentación del PRODUCTO durante la alianza, con resguardo de secretos y componentes ajenos. Ninguna parte explotará individualmente el PRODUCTO ni enajenará o licenciará su participación sin consentimiento escrito de la otra. Ante una venta autorizada a terceros, la otra parte tendrá derecho de compra preferente en iguales condiciones, ejercitable dentro de treinta (30) días calendario de recibir la oferta completa por escrito. La terminación se regirá por las cláusulas novena y decimocuarta y no transfiere los activos preexistentes. Cada parte obtendrá de su personal y contratistas los acuerdos escritos de cesión o autorización de derechos patrimoniales necesarios, conforme al artículo 20 de la Ley 23 de 1982, para asegurar la cadena de titularidad del PRODUCTO.

## CLÁUSULA DUODÉCIMA — OPERACIÓN DESPUÉS DE LA INCUBACIÓN

Antes de finalizar la incubación, las partes aprobarán un presupuesto de hosting, mantenimiento y soporte, con niveles de servicio, responsables, periodicidad y tratamiento de ampliaciones. Estos gastos se pagarán primero con los ingresos del PRODUCTO. Si dichos ingresos son insuficientes, las partes cubrirán el faltante en proporción a la participación vigente, conforme al presupuesto acordado. No se presume operación gratuita o ilimitada al terminar la incubación. Cualquier suspensión o ajuste por falta de recursos deberá informarse con medidas razonables para proteger la información y ordenar la continuidad.

## CLÁUSULA DECIMOTERCERA — EXCLUSIVIDAD Y NO CIRCUNVENCIÓN

EL ALIADO concede exclusividad sobre la idea delimitada en el Anexo A y el PRODUCTO durante la vigencia de la alianza y doce (12) meses después de su terminación. En ese periodo no llevará ese PRODUCTO a otro desarrollador ni eludirá a PROJECTAPP mediante terceros para explotar la misma oportunidad. PROJECTAPP no desarrollará un producto sustancialmente similar para un competidor directo del PRODUCTO durante la vigencia; el Anexo A identificará el mercado y los competidores directos relevantes. La exclusividad no comprende todo el conocimiento profesional de una parte ni los componentes reutilizables de PROJECTAPP. La continuidad autorizada del ALIADO por salida sin causa de PROJECTAPP, prevista en la cláusula decimocuarta, constituye una excepción expresa a la restricción de acudir a otro desarrollador.

## CLÁUSULA DECIMOCUARTA — SALIDA, ABANDONO Y TERMINACIÓN

Cualquiera de las partes podrá comunicar su salida con treinta (30) días calendario de aviso escrito, sin omitir las entregas, cuentas y deberes de confidencialidad pendientes. La salida o abandono del ALIADO antes del éxito implica la pérdida de su participación según la cláusula novena, cualquiera que sea el modelo elegido. Se considera abandono la suspensión injustificada de sus aportes o validaciones que impida continuar, documentada y notificada con la oportunidad de subsanación de esa cláusula. La salida después del éxito exige liquidar los derechos consolidados y acordar por escrito la continuidad, sin presumir su pérdida por el solo aviso.

Si PROJECTAPP sale sin causa imputable al ALIADO, éste conserva la participación consolidada y recibe copia del código y documentación del PRODUCTO, junto con licencia suficiente para continuarlo, incluidos los componentes integrados necesarios sin derecho de explotación separada. No recibe la participación pendiente ni los activos preexistentes de PROJECTAPP. En los demás supuestos se aplicarán los derechos consolidados, las reglas de incumplimiento y las decisiones escritas de liquidación.

| Supuesto de terminación | Participación | Entregas y liquidación |
| --- | --- | --- |
| Salida o abandono del ALIADO antes del éxito | Consolidada y pendiente permanecen con PROJECTAPP conforme a la cláusula novena. | Acta de cierre, cuentas de aportes y obligaciones pendientes; sin devolución de aportes. |
| Incumplimiento del ALIADO no subsanado | Toda la participación permanece con PROJECTAPP. | Evidencia del aviso y plazo de subsanación; PROJECTAPP puede continuar el PRODUCTO. |
| Salida de PROJECTAPP sin causa | EL ALIADO conserva su participación consolidada. | Copia del código y documentación y licencia para continuar el PRODUCTO; cierre de cuentas. |
| Salida después del éxito o acuerdo de terminación | Se respetan los derechos consolidados según acuerdo escrito. | Balance de ingresos y gastos, distribución pendiente y plan de continuidad o venta. |

El acta de liquidación identificará ingresos recibidos, costos aprobados, obligaciones frente a terceros, accesos, datos, entregas y titularidad resultante. La terminación no extingue obligaciones causadas, confidencialidad ni las restricciones que expresamente sobrevivan.

## CLÁUSULA DECIMOQUINTA — CONFIDENCIALIDAD Y DATOS PERSONALES

Las partes protegerán la información técnica, comercial, financiera y de usuarios recibida para la alianza, la usarán sólo para el PRODUCTO y limitarán el acceso a quienes deban conocerla bajo deber de reserva. Se exceptúa la información pública sin infracción, conocida legítimamente con anterioridad o exigida por autoridad competente, con aviso cuando sea permitido. La reserva subsiste después de la terminación mientras la información conserve carácter confidencial. Las partes cumplirán la Ley 1581 de 2012 y sus normas aplicables, definirán sus roles de responsable y encargado, obtendrán autorizaciones cuando proceda, aplicarán medidas de seguridad y acordarán la devolución, conservación o eliminación de datos al cerrar. Ninguna parte puede usar bases de datos del PRODUCTO para fines propios no autorizados.

## CLÁUSULA DECIMOSEXTA — GOBIERNO

El comité tendrá un representante autorizado por cada parte y se reunirá cada dos semanas durante la incubación, con actas de decisiones, riesgos y tareas. Requieren decisión conjunta por escrito la aprobación del alcance y sus cambios materiales, la declaración de hitos, los presupuestos comerciales y operativos, la meta de éxito, las condiciones de venta o licencia del PRODUCTO, el ingreso de terceros y cualquier modificación de participación. Las tareas ordinarias dentro del alcance aprobado corresponderán a su responsable. La falta de consenso se escalará conforme a la cláusula vigésima; ninguna reunión informal modifica el contrato.

## CLÁUSULA DECIMOSÉPTIMA — INDEPENDENCIA DE OTROS CONTRATOS

Esta alianza no modifica, sustituye ni extingue ningún contrato de desarrollo o de servicios celebrado entre las partes. Sus objetos, precios, entregas y obligaciones son independientes. No se compensarán aportes o facturas de un contrato contra otro sin acuerdo escrito expreso. Si una misma actividad se relaciona con ambos instrumentos, las partes identificarán por escrito su alcance y remuneración para evitar duplicidad; un cambio en esta alianza no se interpreta como reforma tácita del contrato de desarrollo.

## CLÁUSULA DECIMOCTAVA — RESPONSABILIDAD

Las obligaciones técnicas y comerciales son de medios, dentro de los entregables y criterios de aceptación pactados. PROJECTAPP no garantiza ventas, ingresos, rentabilidad ni aceptación del mercado; EL ALIADO asume el riesgo de sus aportes y decisiones comerciales. Cada parte responde por sus incumplimientos imputables y los daños directos demostrados. Se excluyen los daños indirectos, salvo dolo o culpa grave. Esta estipulación no exonera deberes inderogables ni autoriza incumplir las obligaciones expresas de entrega, protección de datos o propiedad intelectual.

## CLÁUSULA DECIMONOVENA — NOTIFICACIONES

Las notificaciones contractuales se enviarán por escrito al correo de PROJECTAPP XXX-XXX-XXX y al correo del ALIADO XXX-XXX-XXX. Cada parte conservará evidencia de envío y recepción y avisará por escrito cualquier cambio de dirección. Los avisos de incumplimiento, salida, modificación y controversia deberán identificar claramente su objeto y anexar la evidencia pertinente. Las comunicaciones de trabajo no sustituyen las actas o acuerdos firmados exigidos por el contrato.

## CLÁUSULA VIGÉSIMA — SOLUCIÓN DE CONTROVERSIAS

Las partes intentarán un arreglo directo durante quince (15) días hábiles desde la recepción del aviso escrito de controversia. Si no hay acuerdo, acudirán a un centro de conciliación en XXX-XXX-XXX. Agotada la conciliación sin solución, someterán la controversia a la jurisdicción ordinaria competente de XXX-XXX-XXX, bajo la ley colombiana. El desacuerdo sobre un hito no permite declararlo unilateralmente ni alterar la evidencia; durante su trámite las partes cumplirán las obligaciones no controvertidas que puedan ejecutarse.

## CLÁUSULA VIGESIMOPRIMERA — DISPOSICIONES FINALES

Toda modificación deberá constar por escrito y ser aceptada por ambas partes. Ninguna podrá ceder el contrato o sus obligaciones sin consentimiento escrito de la otra. Las Condiciones particulares y los anexos A y B hacen parte integral del contrato; sus ajustes no podrán contradecirlo sin un otrosí expreso. La eventual invalidez de una disposición no afecta las restantes, y las partes acordarán su sustitución conforme al objeto de la alianza. Se admite firma electrónica y conservación de mensajes de datos conforme a la Ley 527 de 1999. Los espacios XXX-XXX-XXX deberán completarse en la versión particular antes de suscribirla.

## CONDICIONES PARTICULARES

| Condición | Acuerdo de esta alianza |
| --- | --- |
| Modelo elegido | XXX-XXX-XXX |
| Periodo de incubación | XXX-XXX-XXX |
| Fecha de inicio según acta | XXX-XXX-XXX |
| Cuota mensual y vencimientos | XXX-XXX-XXX |
| Presupuesto de ventas y mercadeo, calendario y destinación | XXX-XXX-XXX |
| Participación pactada | XXX-XXX-XXX |
| Indicadores de compromiso, meta comercial y evidencia de éxito | XXX-XXX-XXX |
| Periodicidad de cuentas y distribución de ingresos netos | XXX-XXX-XXX |

## ANEXO A — FICHA DE ALCANCE

| Elemento | Definición de esta alianza |
| --- | --- |
| Nombre y descripción del PRODUCTO | XXX-XXX-XXX |
| Problema, mercado y competidores directos | XXX-XXX-XXX |
| Objetivos y exclusiones generales | XXX-XXX-XXX |

| Requerimiento | Criterio de aceptación | Evidencia | Responsable | Dependencias | Dentro del alcance | Fuera del alcance |
| --- | --- | --- | --- | --- | --- | --- |
| XXX-XXX-XXX | XXX-XXX-XXX | XXX-XXX-XXX | XXX-XXX-XXX | XXX-XXX-XXX | XXX-XXX-XXX | XXX-XXX-XXX |

Todo cambio de esta ficha registrará solicitud, motivo, impacto, aprobación y nueva línea base conforme a la cláusula cuarta.

## ANEXO B — HITOS Y CONSOLIDACIÓN

| Hito de referencia | Criterio de esta alianza | Evidencia requerida | Fracción de la participación pactada del ALIADO |
| --- | --- | --- | --- |
| H1 — Alcance aprobado y acta de inicio | XXX-XXX-XXX | Anexo A aprobado y acta de inicio firmada; detalle XXX-XXX-XXX. | 10 % |
| H2 — Primera versión funcional validada | XXX-XXX-XXX | Evidencia de pruebas y validación; detalle XXX-XXX-XXX. | 30 % |
| H3 — MVP en producción con usuarios reales | XXX-XXX-XXX | Registro de puesta en producción y uso real; detalle XXX-XXX-XXX. | 30 % |
| H4 — Meta comercial acordada | XXX-XXX-XXX | Reporte comercial y soportes de la meta; detalle XXX-XXX-XXX. | 30 % |

Las fracciones anteriores son referencias ajustables por acuerdo escrito. El comité dejará acta de cada cumplimiento y de la participación acumulada; el cumplimiento de las obligaciones del ALIADO se verifica conforme a la cláusula sexta.

## EN CONSTANCIA DE LO ANTERIOR,

Las partes firman este contrato y sus anexos en XXX-XXX-XXX, el XXX-XXX-XXX, en ejemplares del mismo tenor o mediante firma electrónica.

**PROJECTAPP**

Razón social: XXX-XXX-XXX

NIT: XXX-XXX-XXX

Representante legal: XXX-XXX-XXX

Identificación: XXX-XXX-XXX

Firma: XXX-XXX-XXX

**EL ALIADO / EXPERTO DE NEGOCIO**

Nombre o razón social: XXX-XXX-XXX

Identificación: XXX-XXX-XXX

Representante, si aplica: XXX-XXX-XXX

Firma: XXX-XXX-XXX
"""


def seed_contract(apps, schema_editor):
    Contract = apps.get_model('content', 'BuildingWithUsContract')
    Revision = apps.get_model('content', 'BuildingWithUsContractRevision')
    alias = schema_editor.connection.alias
    if not Contract.objects.using(alias).exists():
        revision, _ = Revision.objects.using(alias).get_or_create(version=1, defaults={
            'markdown': CONTRACT_V1_MARKDOWN, 'author_label': 'Sistema',
            'change_note': 'Versión inicial del contrato de alianza Building with Us (PA-175).',
        })
        Contract.objects.using(alias).create(pk=1, current_revision=revision)


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0286_building_with_us_program'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BuildingWithUsContractRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('author_label', models.CharField(default='Sistema', max_length=255)),
                ('change_note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('markdown', models.TextField()),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('credential', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='content.mcpcredential')),
                ('restored_from', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='content.buildingwithuscontractrevision')),
            ],
            options={'ordering': ['-version'], 'abstract': False},
        ),
        migrations.CreateModel(
            name='BuildingWithUsContract',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('current_revision', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='content.buildingwithuscontractrevision')),
            ],
        ),
        migrations.CreateModel(
            name='BuildingWithUsContractMirror',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pdf_content', models.BinaryField()),
                ('synced_at', models.DateTimeField()),
                ('contract', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='mirror', to='content.buildingwithuscontract')),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='building_with_us_mirror', to='content.document')),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='content.buildingwithuscontractrevision')),
            ],
        ),
        migrations.AddConstraint(
            model_name='buildingwithuscontractrevision',
            constraint=models.UniqueConstraint(fields=('version',), name='content_buildingwithuscontractrevision_unique_version'),
        ),
        migrations.AddConstraint(
            model_name='buildingwithuscontract',
            constraint=models.CheckConstraint(condition=models.Q(('id', 1)), name='building_with_us_contract_singleton'),
        ),
        migrations.RunPython(seed_contract, migrations.RunPython.noop),
    ]
