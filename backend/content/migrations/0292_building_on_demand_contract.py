"""Private first cell rental contract, independent of subsequent MCP refinements."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


# Historical seed: keep the full legal-commercial copy embedded here.
CONTRACT_V1_MARKDOWN = """# CONTRATO DE ALQUILER DE CÉLULA — BUILDING ON DEMAND

Entre los suscritos, PROJECTAPP, casa de software cuya razón social es XXX-XXX-XXX, identificada con NIT XXX-XXX-XXX, representada legalmente por XXX-XXX-XXX, quien actúa con facultades suficientes y en adelante se denomina PROJECTAPP; y XXX-XXX-XXX, identificado con XXX-XXX-XXX, quien actúa en nombre propio o en representación de XXX-XXX-XXX y en adelante se denomina EL CLIENTE, se celebra este contrato de alquiler de célula Scrum, regido por las siguientes disposiciones, sus Condiciones particulares y el Anexo A.

## ANTECEDENTES

PROJECTAPP dispone de una célula Scrum de siete personas que trabajan juntas sobre un producto: dos desarrolladores, líder de proyecto, diseñador, arquitecto de desarrollo que también cubre DevOps, Scrum Master y QA. EL CLIENTE desea hacer evolucionar el producto identificado en el Anexo A mediante tareas priorizadas, estimadas y aprobadas por escrito. Building on Demand ofrece acceso a una célula compartida mediante una bolsa mensual de horas, con roles, infraestructura y ritmo según el plan elegido. Estos antecedentes orientan la interpretación del contrato y no sustituyen sus obligaciones expresas.

## CLÁUSULA PRIMERA — OBJETO

PROJECTAPP facilita a EL CLIENTE el uso de una célula Scrum COMPARTIDA a través de una bolsa mensual de horas para trabajar sobre el producto o proyecto identificado en el Anexo A. Las horas son horas de célula, sin distinguir el rol que ejecuta cada tarea. El servicio no es un proyecto llave en mano, una contratación laboral ni un equipo completo dedicado a tiempo completo al cliente. Las denominaciones de ritmo de los planes no crean disponibilidad exclusiva de ninguna persona. PROJECTAPP organiza sus recursos y conserva autonomía técnica y administrativa; el uso de roles depende del plan y de las prioridades aprobadas.

## CLÁUSULA SEGUNDA — PLANES Y PRECIOS DE REFERENCIA

Los planes de referencia son Starter, Business y Enterprise. Cada nivel amplía la bolsa, los roles disponibles, la capacidad del VPS y la atención; el precio no se presenta como una tarifa por hora. Las bolsas de referencia se calculan con cuatro (4), ocho (8) y doce (12) horas diarias, seis (6) días por semana y cuatro (4) semanas por mes. Esto determina capacidad mensual, no una jornada laboral de personas dedicadas ni un calendario de entrega.

| Plan | Bolsa mensual de horas de célula | Roles y actividades disponibles | VPS: vCPU / RAM / disco / transferencia | Respuesta objetivo | Tareas en curso | Precio base mensual sin IVA |
| --- | --- | --- | --- | --- | --- | --- |
| Starter | 96 horas | Desarrollo, líder de proyecto y QA en cada entrega. | 1 vCPU / 4 GB / 50 GB / 4 TB | 48 horas hábiles | Una | COP 1.800.000 |
| Business | 192 horas | Todo Starter; diseñador, arquitecto de desarrollo, sesiones de levantamiento de requerimientos y deploy a producción. | 4 vCPU / 16 GB / 200 GB / 16 TB | 24 horas hábiles | Dos | COP 4.200.000 |
| Enterprise | 288 horas | Todo Business; Scrum Master dedicado a la coordinación del servicio, DevOps continuo y prioridad de atención. | 8 vCPU / 32 GB / 400 GB / 32 TB | 4 horas, con prioridad | Tres | COP 9.600.000 |

| Plan | Descuento por 3 meses | Mensual equivalente / total de 3 meses | Descuento por 6 meses | Mensual equivalente / total de 6 meses | Descuento por 9 meses | Mensual equivalente / total de 9 meses |
| --- | --- | --- | --- | --- | --- | --- |
| Starter | 5 % | COP 1.710.000 / COP 5.130.000 | 10 % | COP 1.620.000 / COP 9.720.000 | 15 % | COP 1.530.000 / COP 13.770.000 |
| Business | 10 % | COP 3.780.000 / COP 11.340.000 | 15 % | COP 3.570.000 / COP 21.420.000 | 20 % | COP 3.360.000 / COP 30.240.000 |
| Enterprise | 15 % | COP 8.160.000 / COP 24.480.000 | 20 % | COP 7.680.000 / COP 46.080.000 | 25 % | COP 7.200.000 / COP 64.800.000 |

Todos los valores de estas tablas son referencias en pesos colombianos, sin IVA; se suma el IVA aplicable. El precio, descuento, impuestos y plazo que obligan a las partes son los consignados en las Condiciones particulares. Una actualización posterior de las tarjetas o de este documento de referencia no modifica un contrato ya suscrito. No se presume un descuento distinto del pactado.

## CLÁUSULA TERCERA — BOLSA MENSUAL, VENCIMIENTO Y NO TRANSFERENCIA

La bolsa se renueva al comienzo de cada ciclo mensual, contado desde la fecha de inicio acordada, incluso cuando se hayan pagado varios meses por anticipado. Las horas no utilizadas vencen al cerrar ese ciclo: no se acumulan, no se trasladan al mes siguiente ni se convierten en saldo a favor. La bolsa no se puede transferir a otra empresa o persona ni a otro proyecto del mismo cliente. El Anexo A identifica el producto o proyecto al que se destina. Esta condición forma parte del precio y debe aceptarse antes de iniciar el servicio.

## CLÁUSULA CUARTA — ESTIMACIÓN, APROBACIÓN Y CONSUMO

La calculadora de requerimientos estima cada tarea según su descripción, complejidad, roles y dependencias. PROJECTAPP envía la estimación por escrito con la tarea, sus criterios de aceptación y las horas estimadas; EL CLIENTE la aprueba por escrito mediante correo, WhatsApp o el canal acordado antes de empezar. Sólo una estimación aprobada descuenta horas de la bolsa del ciclo de ejecución. Se descuentan las horas estimadas aprobadas, sin distinguir el rol que ejecuta; la estimación es una referencia de esfuerzo, no una promesa de duración exacta o de fecha de entrega.

El registro conserva solicitud, estimación, aceptación, ciclo y saldo resultante. El silencio no equivale a aprobación. Si cambian la descripción o los criterios de una tarea, PROJECTAPP presenta su nueva estimación y EL CLIENTE la aprueba antes de ejecutar el cambio o efectuar un descuento adicional. No se presume autorización de horas extra por haber iniciado una tarea. La aprobación de una estimación no elimina el tope de bolsa ni las reglas de la cláusula séptima.

## CLÁUSULA QUINTA — RITMO Y PRIORIZACIÓN

El máximo de tareas en curso es una (1) en Starter, dos (2) en Business y tres (3) en Enterprise. PROJECTAPP y EL CLIENTE ordenan las tareas conforme a la prioridad de negocio, las estimaciones aprobadas, las dependencias y el saldo del ciclo. Starter trabaja de forma asíncrona con una ceremonia cada dos semanas y una persona que solicita y prioriza; Business incluye sprint semanal con demo y hasta tres personas solicitantes; Enterprise incluye sprint de dos semanas, canal dedicado y solicitudes del equipo del cliente. EL CLIENTE identifica a las personas autorizadas en las Condiciones particulares. La coordinación y el Scrum Master de Enterprise no convierten la célula en un equipo exclusivo ni modifican la bolsa mensual.

## CLÁUSULA SEXTA — ALCANCE Y FECHAS

El contrato no compromete un alcance fijo ni una fecha de entrega del producto completo. El trabajo avanza por tareas priorizadas, estimadas y aprobadas, dentro de la bolsa y los roles del plan. Cada tarea define criterios de aceptación para evaluar lo solicitado; las previsiones de ejecución son referencias sujetas a insumos, decisiones y dependencias. Una fecha comprometida o un proyecto con alcance cerrado requieren un acuerdo escrito independiente que identifique sus obligaciones y remuneración. EL CLIENTE proporciona oportunamente accesos, información, decisiones y validaciones, y las partes registran lo que impida continuar.

## CLÁUSULA SÉPTIMA — EXCESO DE HORAS

No hay horas extra automáticas ni cobros adicionales implícitos cuando la tarea supera el saldo mensual. Antes de ejecutarla, las partes eligen por escrito dividirla en partes estimadas que quepan en la bolsa, esperar al siguiente ciclo o subir de nivel conforme a la cláusula décima. Ninguna tarea puede descontar más que la bolsa disponible sin un acuerdo permitido por estas reglas. La división requiere estimaciones y aprobaciones propias, y no produce acumulación ni préstamo de horas del mes siguiente.

## CLÁUSULA OCTAVA — PLAZOS, PAGO Y CONTINUIDAD

EL CLIENTE elige modalidad mensual o un plazo de tres (3), seis (6) o nueve (9) meses. El periodo elegido se paga completo y por adelantado, incluidos los impuestos aplicables, antes del inicio. Un plazo mayor no equivale a pago en cuotas y mantiene la renovación de la bolsa cada mes. La fecha de inicio, el ciclo mensual, el precio y las instrucciones de pago quedan en las Condiciones particulares.

Al terminar el plazo pagado, el servicio continúa en modalidad mensual al precio base vigente que corresponda, sin conservar automáticamente el descuento del plazo anterior, hasta que EL CLIENTE elija y pague otro plazo o comunique su terminación conforme a la cláusula undécima. PROJECTAPP informa el vencimiento y el precio aplicable antes del nuevo ciclo. No se inicia trabajo ni se descuenta una nueva bolsa sin el pago correspondiente; cualquier suspensión se comunica por escrito con medidas razonables para proteger código y datos.

## CLÁUSULA NOVENA — REAJUSTE ANUAL

El precio base se reajusta una vez por año con la regla de PROJECTAPP: la variación porcentual anual del salario mínimo legal mensual vigente en Colombia más doce (12) puntos porcentuales. PROJECTAPP comunica por escrito el cálculo, la referencia utilizada y la fecha de aplicación antes del primer ciclo afectado. El reajuste nunca se aplica a un plazo ya pagado, no altera retroactivamente las sumas causadas y opera al siguiente ciclo o plazo que deba pagarse después de su entrada en vigor. La fecha anual de reajuste se consigna en las Condiciones particulares.

## CLÁUSULA DÉCIMA — CAMBIO DE PLAN

Subir de plan rige desde el ciclo mensual siguiente, previa elección y aceptación escrita del precio y condiciones del nivel superior. Si existe un plazo ya pagado, las partes documentan la diferencia que corresponda a los ciclos aún no iniciados y su pago antes de activar el nuevo nivel, sin reajustar los ciclos ya pagados bajo la cláusula novena. No se habilita capacidad adicional de manera retroactiva.

Bajar de plan requiere aviso escrito con treinta (30) días calendario de anticipación. Dentro de un plazo de varios meses, la reducción sólo rige al terminar ese plazo. Las partes registran el ciclo efectivo, la bolsa, los roles, el precio y la infraestructura aplicables. El cambio de nivel no permite transferir ni acumular horas y no autoriza cargos que no hayan sido aceptados.

## CLÁUSULA UNDÉCIMA — SALIDA ANTICIPADA Y DEVOLUCIÓN

EL CLIENTE puede terminar anticipadamente un plazo pagado. Se devuelven los importes de los meses no iniciados, menos el descuento ya recibido en los meses usados. El mes iniciado se considera usado y su bolsa no genera devolución por horas sin consumir. El descuento recibido se calcula como la diferencia entre el precio base mensual pactado y el precio mensual descontado pactado, multiplicada por los meses usados; se descuenta una sola vez de la devolución de los meses no iniciados. Si esa diferencia supera el saldo de los meses no iniciados, la devolución es cero y no nace un cobro adicional por este concepto. Las partes dejan liquidación escrita de meses, precio, descuento e impuestos que deban ajustarse.

En modalidad mensual, la terminación exige aviso escrito con treinta (30) días calendario de anticipación; se registra el último ciclo que corresponda cubrir y su fecha de cierre. La terminación no elimina obligaciones causadas ni las entregas de código, datos y transición previstas en la cláusula decimocuarta. No se exige adquirir un nuevo plazo para ejercer la salida.

## CLÁUSULA DUODÉCIMA — HOSTING, MANTENIMIENTO Y SOPORTE

El servicio incluye un VPS bajo la cuenta de PROJECTAPP, con las especificaciones del plan recogidas en el Anexo A, en un proveedor elegido por PROJECTAPP. No se transfiere la cuenta del proveedor al cliente. Si EL CLIENTE ya dispone de hosting propio, las partes acuerdan por escrito en las Condiciones particulares el lugar de operación, los accesos y las responsabilidades; no se presume descuento o modificación de precio.

El mantenimiento preventivo incluye actualizaciones del servidor, copias de seguridad y monitoreo, junto con la atención de incidentes del servidor. Estas actividades no consumen la bolsa. Los cambios, ajustes y nuevas funcionalidades del producto sí la consumen conforme a estimaciones aprobadas. No se promete detección propia de malware en esta versión del servicio. Las partes delimitan accesos, canales y dependencias de terceros en el Anexo A.

Los tiempos de respuesta son objetivos según el plan: cuarenta y ocho (48) horas hábiles en Starter, veinticuatro (24) horas hábiles en Business y cuatro (4) horas con prioridad en Enterprise. Son tiempos objetivo de atención, no plazos garantizados de resolución ni un acuerdo de nivel de servicio con penalidades. La respuesta requiere recepción del reporte en el canal acordado y datos suficientes para identificar el incidente. PROJECTAPP informa las acciones y dependencias para recuperar la operación.

## CLÁUSULA DECIMOTERCERA — PROPIEDAD INTELECTUAL

Los desarrollos específicos entregados y pagados pertenecen patrimonialmente a EL CLIENTE. PROJECTAPP conserva la titularidad de sus herramientas, metodologías, bibliotecas y componentes previos o reutilizables, con licencia de uso para EL CLIENTE suficiente para operar, mantener y continuar el producto que los integra, sin transferencia de titularidad ni derecho a explotarlos separadamente. Los activos, marcas, contenidos y datos aportados por EL CLIENTE siguen siendo suyos. Se respetan las licencias de terceros y los derechos morales de los autores.

PROJECTAPP administra el repositorio durante el servicio y documenta las entregas. Cada parte obtiene de su personal y contratistas las cesiones o autorizaciones escritas de derechos patrimoniales necesarias, conforme al artículo 20 de la Ley 23 de 1982, para asegurar la cadena de titularidad. La terminación no transfiere herramientas preexistentes ni revoca la licencia integrada necesaria para la continuidad del producto entregado y pagado.

## CLÁUSULA DECIMOCUARTA — TERMINACIÓN Y TRANSICIÓN

Al terminar, PROJECTAPP entrega a EL CLIENTE una copia completa del código y los datos de su producto, la documentación disponible y los accesos propios que corresponda transferir, sin revelar secretos o activos de terceros. Facilita treinta (30) días calendario de transición desde la terminación para organizar la salida del VPS o la continuidad en el hosting acordado. La cuenta del proveedor permanece en PROJECTAPP; la entrega permite continuar el producto por cuenta de EL CLIENTE o de quien éste autorice.

Las partes documentan la recepción de código y datos, las copias, los responsables y el cierre de accesos. Cualquier nuevo desarrollo durante la transición requiere acuerdo escrito de estimación y pago; la entrega y la transición no se condicionan a contratar otro plazo. La terminación no extingue obligaciones causadas, confidencialidad, protección de datos ni los derechos de propiedad intelectual establecidos en este contrato.

## CLÁUSULA DECIMOQUINTA — CONFIDENCIALIDAD Y DATOS PERSONALES

Las partes protegen la información técnica, comercial, financiera y de usuarios recibida durante el servicio, la usan sólo para el producto y limitan el acceso a quienes deban conocerla bajo deber de reserva. Se exceptúa la información pública sin infracción, conocida legítimamente con anterioridad o exigida por autoridad competente, con aviso cuando sea permitido. La reserva subsiste después de la terminación mientras la información conserve carácter confidencial.

Las partes cumplen la Ley 1581 de 2012 y sus normas aplicables, definen sus roles de responsable y encargado, obtienen las autorizaciones que procedan y aplican medidas de seguridad. Acuerdan la devolución, conservación legal o eliminación de datos al cerrar, después de entregar las copias correspondientes. Ninguna parte puede utilizar datos del producto para fines propios no autorizados.

## CLÁUSULA DECIMOSEXTA — INDEPENDENCIA DE OTROS CONTRATOS

Building on Demand se rige por este contrato propio y no es un anexo de un contrato de proyecto. Puede coexistir con contratos de desarrollo u otros servicios, sin modificarlos, sustituirlos ni extinguirlos. Sus objetos, precios, entregas y obligaciones son independientes. No se compensan pagos de un contrato contra otro sin acuerdo escrito expreso. Cuando una actividad se relacione con ambos, las partes identifican por escrito su remuneración y las horas que correspondan para evitar duplicidades.

## CLÁUSULA DECIMOSÉPTIMA — RESPONSABILIDAD

Las obligaciones técnicas son de medios dentro de las tareas y criterios aprobados. PROJECTAPP no garantiza ventas, ingresos, rentabilidad ni aceptación del mercado; EL CLIENTE conserva las decisiones de negocio. Cada parte responde por sus incumplimientos imputables y los daños directos demostrados. Se excluyen daños indirectos, salvo dolo o culpa grave. Esta estipulación no exonera deberes inderogables ni autoriza incumplir las obligaciones expresas de entrega, protección de datos o propiedad intelectual.

## CLÁUSULA DECIMOCTAVA — NOTIFICACIONES

Las notificaciones contractuales se envían por escrito al correo de PROJECTAPP XXX-XXX-XXX y al de EL CLIENTE XXX-XXX-XXX. Cada parte conserva evidencia de envío y recepción y avisa por escrito cualquier cambio de dirección. Los avisos de salida, cambio de plan, reajuste y controversia identifican su objeto y anexan la evidencia pertinente. Las estimaciones y aprobaciones operativas pueden usar correo, WhatsApp o el canal escrito acordado en las Condiciones particulares; no sustituyen los acuerdos firmados exigidos para modificar el contrato.

## CLÁUSULA DECIMONOVENA — SOLUCIÓN DE CONTROVERSIAS

Las partes intentan un arreglo directo durante quince (15) días hábiles desde la recepción del aviso escrito de controversia. Si no hay acuerdo, acuden a un centro de conciliación en XXX-XXX-XXX. Agotada la conciliación sin solución, someten la controversia a la jurisdicción ordinaria competente de XXX-XXX-XXX, bajo la ley colombiana. Durante su trámite cumplen las obligaciones no controvertidas que puedan ejecutarse y conservan la evidencia de estimaciones, aceptaciones, consumo y pagos.

## CLÁUSULA VIGÉSIMA — DISPOSICIONES FINALES

Toda modificación consta por escrito y es aceptada por ambas partes. Ninguna puede ceder el contrato o sus obligaciones sin consentimiento escrito de la otra, sin perjuicio de la prohibición de transferir la bolsa. Las Condiciones particulares y el Anexo A forman parte integral del contrato; sus ajustes no lo contradicen sin un otrosí expreso. La eventual invalidez de una disposición no afecta las restantes, y las partes acuerdan su sustitución conforme al objeto del servicio.

La firma se realiza por fuera del sistema: las partes descargan el PDF desde el panel, completan los espacios XXX-XXX-XXX y lo firman. No se usa el flujo de formalización de propuestas. Se admite firma electrónica y conservación de mensajes de datos conforme a la Ley 527 de 1999. El contrato y su PDF son privados; la página y el PDF públicos presentan únicamente el programa comercial.

## CONDICIONES PARTICULARES

| Condición | Acuerdo con EL CLIENTE |
| --- | --- |
| Producto o proyecto destinatario de la bolsa | XXX-XXX-XXX |
| Plan elegido y bolsa mensual | XXX-XXX-XXX |
| Modalidad mensual o plazo de 3, 6 o 9 meses | XXX-XXX-XXX |
| Fecha de inicio y límites de cada ciclo mensual | XXX-XXX-XXX |
| Precio base, descuento, IVA, precio mensual y total anticipado | XXX-XXX-XXX |
| Fecha e instrucciones del pago completo por adelantado | XXX-XXX-XXX |
| Fecha anual de reajuste y referencia para el cálculo | XXX-XXX-XXX |
| Personas autorizadas para solicitar, priorizar y aprobar | XXX-XXX-XXX |
| Correos, WhatsApp o canal escrito de estimaciones y avisos | XXX-XXX-XXX |
| Hosting bajo PROJECTAPP o hosting propio, accesos y responsabilidades | XXX-XXX-XXX |
| Condiciones específicas aceptadas por escrito | XXX-XXX-XXX |

## ANEXO A — PRODUCTO, CÉLULA E INFRAESTRUCTURA

| Elemento | Definición del servicio |
| --- | --- |
| Nombre y descripción del producto o proyecto único | XXX-XXX-XXX |
| Plan, roles disponibles y máximo de tareas en curso | XXX-XXX-XXX |
| Bolsa mensual de horas de célula | XXX-XXX-XXX |
| VPS: vCPU, RAM, disco y transferencia | XXX-XXX-XXX |
| Cuenta de PROJECTAPP u operación en hosting propio acordada | XXX-XXX-XXX |
| Canal, horario de atención y tiempo de respuesta objetivo | XXX-XXX-XXX |
| Mantenimiento preventivo y atención de incidentes sin consumo de bolsa | Actualizaciones del servidor, copias, monitoreo e incidentes del servidor; detalle XXX-XXX-XXX. |
| Dependencias de terceros, insumos y exclusiones | XXX-XXX-XXX |
| Entrega de código y datos y transición de 30 días al terminar | XXX-XXX-XXX |

El Anexo A identifica el destinatario y las condiciones del servicio, sin establecer un alcance fijo ni una fecha de entrega del producto completo. Las tareas se registran y aprueban conforme a la cláusula cuarta.

## EN CONSTANCIA DE LO ANTERIOR,

Las partes firman este contrato y su Anexo A en XXX-XXX-XXX, el XXX-XXX-XXX, en ejemplares del mismo tenor o mediante firma electrónica.

**PROJECTAPP**

Razón social: XXX-XXX-XXX

NIT: XXX-XXX-XXX

Representante legal: XXX-XXX-XXX

Identificación: XXX-XXX-XXX

Firma: XXX-XXX-XXX

**EL CLIENTE**

Nombre o razón social: XXX-XXX-XXX

Identificación: XXX-XXX-XXX

Representante, si aplica: XXX-XXX-XXX

Firma: XXX-XXX-XXX
"""


def seed_contract(apps, schema_editor):
    Contract = apps.get_model('content', 'BuildingOnDemandContract')
    Revision = apps.get_model('content', 'BuildingOnDemandContractRevision')
    alias = schema_editor.connection.alias
    if not Contract.objects.using(alias).exists():
        revision, _ = Revision.objects.using(alias).get_or_create(version=1, defaults={
            'markdown': CONTRACT_V1_MARKDOWN, 'author_label': 'Sistema',
            'change_note': 'Versión inicial del contrato de Building on Demand (PA-177/PA-179).',
        })
        Contract.objects.using(alias).create(pk=1, current_revision=revision)


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0291_building_on_demand_program'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BuildingOnDemandContractRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('author_label', models.CharField(default='Sistema', max_length=255)),
                ('change_note', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('markdown', models.TextField()),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('credential', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='content.mcpcredential')),
                ('restored_from', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='content.buildingondemandcontractrevision')),
            ],
            options={'ordering': ['-version'], 'abstract': False},
        ),
        migrations.CreateModel(
            name='BuildingOnDemandContract',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('current_revision', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='content.buildingondemandcontractrevision')),
            ],
        ),
        migrations.CreateModel(
            name='BuildingOnDemandContractMirror',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pdf_content', models.BinaryField()),
                ('synced_at', models.DateTimeField()),
                ('contract', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='mirror', to='content.buildingondemandcontract')),
                ('document', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='building_on_demand_mirror', to='content.document')),
                ('revision', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='content.buildingondemandcontractrevision')),
            ],
        ),
        migrations.AddConstraint(
            model_name='buildingondemandcontractrevision',
            constraint=models.UniqueConstraint(fields=('version',), name='content_buildingondemandcontractrevision_unique_version'),
        ),
        migrations.AddConstraint(
            model_name='buildingondemandcontract',
            constraint=models.CheckConstraint(condition=models.Q(('id', 1)), name='building_on_demand_contract_singleton'),
        ),
        migrations.RunPython(seed_contract, migrations.RunPython.noop),
    ]
