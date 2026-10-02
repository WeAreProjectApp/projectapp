"""Move standalone service economics into the service contract itself."""

from django.db import migrations

PRICE_HEADING = '## CLÁUSULA SEGUNDA — PRECIO, INICIO DEL COBRO Y FORMA DE PAGO'
CONDITIONS = '\n\n{service_conditions}'
REPLACEMENTS = (
    (
        'El valor, la periodicidad y las condiciones económicas del servicio se definen en el Documento Propuesta Comercial o en el documento que las partes suscriban para el efecto.',
        'El valor, las modalidades de pago y las condiciones económicas del servicio se establecen en el apartado de Condiciones particulares del servicio de la CLÁUSULA SEGUNDA del presente contrato.',
    ),
    (
        'conforme a la periodicidad definida en el Documento Propuesta Comercial, sea esta mensual, trimestral, semestral, anual u otra',
        'conforme a la modalidad de pago elegida de las condiciones particulares del presente contrato',
    ),
    (
        'El presente contrato, junto con el Documento Propuesta Comercial en lo relativo al servicio de hosting, mantenimiento y soporte,',
        'El presente contrato, incluidas sus condiciones particulares del servicio,',
    ),
    (
        'la periodicidad de pago pactada en el Documento Propuesta Comercial',
        'la modalidad de pago elegida de las condiciones particulares del presente contrato',
    ),
    (
        'la periodicidad definida en el Documento Propuesta Comercial',
        'la modalidad de pago elegida de las condiciones particulares del presente contrato',
    ),
    ('Documento Propuesta Comercial aceptado por las partes', 'apartado de Condiciones particulares del servicio del presente contrato'),
    ('Documento Propuesta Comercial', 'apartado de Condiciones particulares del servicio del presente contrato'),
    ('oportunidad pactada en dicho documento', 'oportunidad pactada en estas condiciones particulares'),
)


def forwards(apps, schema_editor):
    template = apps.get_model('content', 'ContractTemplate').objects.using(
        schema_editor.connection.alias,
    ).filter(is_default=True).first()
    if template is None or not template.service_content_markdown:
        return
    text = template.service_content_markdown
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if '{service_conditions}' not in text and PRICE_HEADING in text:
        text = text.replace(PRICE_HEADING, PRICE_HEADING + CONDITIONS, 1)
    if text != template.service_content_markdown:
        template.service_content_markdown = text
        template.save(using=schema_editor.connection.alias, update_fields=['service_content_markdown', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [('content', '0275_materialize_manual_proposal_pricing')]
    operations = [migrations.RunPython(forwards)]
