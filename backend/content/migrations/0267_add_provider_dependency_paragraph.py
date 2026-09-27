"""Add the technology provider dependency paragraph to both default contracts.

Paragraph Ten of the hosting, maintenance and support terms: the service rests
on third-party technology and artificial intelligence providers, a provider
event is not a breach of contract, and the paragraph sets how such an event is
notified, how the provider is replaced, how a higher cost is approved and when
either party may end the service. The full contract gets it after Paragraph
Nine of CLÁUSULA VIGÉSIMA SEGUNDA; the standalone service contract gets its own
wording after Paragraph Nine of CLÁUSULA QUINTA. The product contract is cut
from the full text before CLÁUSULA VIGÉSIMA PRIMERA, so it does not change.

Each text is patched only at its exact shipped anchor, so curated wording is
preserved. Generated PDFs and custom proposal contracts are untouched. The
reverse removes exactly the inserted paragraph.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


FULL_CONTRACT_PARAGRAPH = """\
### Parágrafo Décimo — Dependencia de Proveedores Tecnológicos y de Inteligencia Artificial

**a) Alcance.** El servicio de hosting, mantenimiento y soporte se apoya en infraestructura, plataformas, modelos, interfaces de programación de aplicaciones (API) y demás servicios tecnológicos prestados por terceros, incluidos los proveedores de servicios de inteligencia artificial (en adelante, los PROVEEDORES TECNOLÓGICOS), sea que se encuentren integrados a la plataforma o que EL CONTRATISTA los utilice en la operación, el mantenimiento o el soporte del servicio. Las partes reconocen que la disponibilidad, las condiciones técnicas y comerciales y la continuidad de los PROVEEDORES TECNOLÓGICOS son definidas unilateralmente por estos y son ajenas al control de EL CONTRATISTA.

**b) Evento de proveedor.** Se entenderá por EVENTO DE PROVEEDOR la suspensión, restricción, modificación sustancial, incremento sustancial de costos, cambio de condiciones de uso, discontinuación o desaparición, temporal o definitiva, de uno o varios PROVEEDORES TECNOLÓGICOS o de la categoría de servicio que prestan, así como la prohibición o limitación de su uso por disposición de autoridad competente.

**c) Ausencia de incumplimiento.** La ocurrencia de un EVENTO DE PROVEEDOR no constituirá incumplimiento de EL CONTRATISTA ni dará lugar a indemnización, descuento, crédito, compensación o penalidad a su cargo, con independencia de que el evento reúna o no los requisitos de la fuerza mayor o el caso fortuito, por cuanto las partes lo reconocen como un riesgo propio de la naturaleza del servicio contratado. EL CONTRATISTA no garantiza la permanencia de las funcionalidades que dependan exclusivamente de un PROVEEDOR TECNOLÓGICO.

**d) Aviso.** EL CONTRATISTA informará por escrito a EL CONTRATANTE la ocurrencia del EVENTO DE PROVEEDOR, las funcionalidades afectadas y las medidas previstas, dentro de los cinco (5) días hábiles siguientes a que tenga conocimiento de su impacto sobre el servicio.

**e) Sustitución.** Ante un EVENTO DE PROVEEDOR, EL CONTRATISTA podrá sustituir al proveedor afectado por otro de funcionalidad equivalente o razonablemente similar, o implementar una solución alternativa, sin que ello requiera modificación del presente contrato. Durante el periodo de transición, que no excederá de treinta (30) días calendario salvo que la complejidad técnica justifique un plazo mayor informado por escrito a EL CONTRATANTE, se suspenderán los niveles de atención del PARÁGRAFO CUARTO y la responsabilidad operativa de EL CONTRATISTA respecto de las funcionalidades afectadas, y EL CONTRATISTA mantendrá en operación las demás funcionalidades en la medida de lo técnicamente posible.

**f) Mayores costos.** Si la sustitución implica un incremento en el costo del servicio, EL CONTRATISTA presentará a EL CONTRATANTE una propuesta de ajuste del valor, acompañada de su soporte. EL CONTRATANTE dispondrá de quince (15) días hábiles para aprobarla por escrito; si no la aprueba dentro de dicho plazo, se aplicará lo previsto en el literal g).

**g) Imposibilidad de sustitución.** Si no existe una alternativa técnica o económicamente viable, o si EL CONTRATANTE no aprueba el ajuste previsto en el literal f), cualquiera de las partes podrá dar por terminado el servicio de hosting, mantenimiento y soporte mediante notificación escrita, sin penalidad ni indemnización a cargo de ninguna de ellas y sin que ello afecte las demás obligaciones del presente contrato. En tal caso, EL CONTRATANTE pagará únicamente los periodos del servicio efectivamente prestados hasta la fecha de terminación, EL CONTRATISTA reintegrará la parte proporcional de los valores pagados por anticipado que correspondan a periodos no prestados, y se aplicará, en lo pertinente, la salida ordenada prevista en el PARÁGRAFO CUARTO de la CLÁUSULA VIGÉSIMA CUARTA.

**h) Concordancia.** Lo previsto en el presente parágrafo es concordante y acumulativo con los PARÁGRAFOS SÉPTIMO y NOVENO de la presente cláusula y con la CLÁUSULA VIGÉSIMA, y prevalecerá sobre cualquier otra estipulación que establezca niveles de servicio o compromisos de disponibilidad respecto de las funcionalidades afectadas por un EVENTO DE PROVEEDOR."""

SERVICE_CONTRACT_PARAGRAPH = """\
### Parágrafo Décimo — Dependencia de Proveedores Tecnológicos y de Inteligencia Artificial

**a) Alcance.** El servicio se apoya en infraestructura, plataformas, modelos, interfaces de programación de aplicaciones (API) y demás servicios tecnológicos prestados por terceros, incluidos los proveedores de servicios de inteligencia artificial (en adelante, los PROVEEDORES TECNOLÓGICOS), sea que se encuentren integrados a la plataforma o que EL CONTRATISTA los utilice en la operación, el mantenimiento o el soporte del servicio. Las partes reconocen que la disponibilidad, las condiciones técnicas y comerciales y la continuidad de los PROVEEDORES TECNOLÓGICOS son definidas unilateralmente por estos y son ajenas al control de EL CONTRATISTA.

**b) Evento de proveedor.** Se entenderá por EVENTO DE PROVEEDOR la suspensión, restricción, modificación sustancial, incremento sustancial de costos, cambio de condiciones de uso, discontinuación o desaparición, temporal o definitiva, de uno o varios PROVEEDORES TECNOLÓGICOS o de la categoría de servicio que prestan, así como la prohibición o limitación de su uso por disposición de autoridad competente.

**c) Ausencia de incumplimiento.** La ocurrencia de un EVENTO DE PROVEEDOR no constituirá incumplimiento de EL CONTRATISTA ni dará lugar a indemnización, descuento, crédito, compensación o penalidad a su cargo, con independencia de que el evento reúna o no los requisitos de la fuerza mayor o el caso fortuito, por cuanto las partes lo reconocen como un riesgo propio de la naturaleza del servicio contratado. EL CONTRATISTA no garantiza la permanencia de las funcionalidades que dependan exclusivamente de un PROVEEDOR TECNOLÓGICO.

**d) Aviso.** EL CONTRATISTA informará por escrito a EL CONTRATANTE la ocurrencia del EVENTO DE PROVEEDOR, las funcionalidades afectadas y las medidas previstas, dentro de los cinco (5) días hábiles siguientes a que tenga conocimiento de su impacto sobre el servicio.

**e) Sustitución.** Ante un EVENTO DE PROVEEDOR, EL CONTRATISTA podrá sustituir al proveedor afectado por otro de funcionalidad equivalente o razonablemente similar, o implementar una solución alternativa, sin que ello requiera modificación del presente contrato. Durante el periodo de transición, que no excederá de treinta (30) días calendario salvo que la complejidad técnica justifique un plazo mayor informado por escrito a EL CONTRATANTE, se suspenderán los niveles de atención del PARÁGRAFO CUARTO y la responsabilidad operativa de EL CONTRATISTA respecto de las funcionalidades afectadas, y EL CONTRATISTA mantendrá en operación las demás funcionalidades en la medida de lo técnicamente posible.

**f) Mayores costos.** Si la sustitución implica un incremento en el costo del servicio, EL CONTRATISTA presentará a EL CONTRATANTE una propuesta de ajuste del valor, acompañada de su soporte. EL CONTRATANTE dispondrá de quince (15) días hábiles para aprobarla por escrito; si no la aprueba dentro de dicho plazo, se aplicará lo previsto en el literal g).

**g) Imposibilidad de sustitución.** Si no existe una alternativa técnica o económicamente viable, o si EL CONTRATANTE no aprueba el ajuste previsto en el literal f), cualquiera de las partes podrá dar por terminado el presente contrato mediante notificación escrita, sin penalidad ni indemnización a cargo de ninguna de ellas. En tal caso, EL CONTRATANTE pagará únicamente los periodos del servicio efectivamente prestados hasta la fecha de terminación, EL CONTRATISTA reintegrará la parte proporcional de los valores pagados por anticipado que correspondan a periodos no prestados, y se aplicará, en lo pertinente, la salida ordenada prevista en el PARÁGRAFO CUARTO de la CLÁUSULA SÉPTIMA.

**h) Concordancia.** Lo previsto en el presente parágrafo es concordante y acumulativo con los PARÁGRAFOS SÉPTIMO y NOVENO de la presente cláusula, y prevalecerá sobre cualquier otra estipulación que establezca niveles de servicio o compromisos de disponibilidad respecto de las funcionalidades afectadas por un EVENTO DE PROVEEDOR."""

# (field, last sentence of Paragraph Nine, start of the next clause, paragraph)
INSERTIONS = (
    (
        'content_markdown',
        'En lo no previsto en este parágrafo, rige la CLÁUSULA VIGÉSIMA.',
        '\n\n---\n\n## CLÁUSULA VIGÉSIMA TERCERA',
        FULL_CONTRACT_PARAGRAPH,
    ),
    (
        'service_content_markdown',
        'conforme a los artículos 63 y 1522 del Código Civil.',
        '\n\n---\n\n## CLÁUSULA SEXTA',
        SERVICE_CONTRACT_PARAGRAPH,
    ),
)


def _patch_default_template(apps, schema_editor, *, insert):
    ContractTemplate = apps.get_model('content', 'ContractTemplate')
    database = schema_editor.connection.alias
    template = ContractTemplate.objects.using(database).filter(is_default=True).first()
    if template is None:
        return
    changed = []
    for field, paragraph_end, next_clause, paragraph in INSERTIONS:
        text = getattr(template, field)
        heading = paragraph.partition('\n')[0]
        without = f'{paragraph_end}{next_clause}'
        with_paragraph = f'{paragraph_end}\n\n{paragraph}{next_clause}'
        if insert:
            if not text or heading in text:
                continue
            old, new = without, with_paragraph
        else:
            if heading not in text:
                continue
            old, new = with_paragraph, without
        if old not in text:
            logger.warning(
                'Provider dependency paragraph: anchor not found in %s of the '
                'default template %s; preserving its custom wording.',
                field, template.pk,
            )
            continue
        setattr(template, field, text.replace(old, new, 1))
        changed.append(field)
    if changed:
        template.save(using=database, update_fields=[*changed, 'updated_at'])


def add_provider_dependency_paragraph(apps, schema_editor):
    _patch_default_template(apps, schema_editor, insert=True)


def remove_provider_dependency_paragraph(apps, schema_editor):
    _patch_default_template(apps, schema_editor, insert=False)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0266_seed_service_contract_text'),
    ]

    operations = [
        migrations.RunPython(
            add_provider_dependency_paragraph, remove_provider_dependency_paragraph,
        ),
    ]
