"""Import current texts without changing any existing proposal."""
from django.db import migrations

PRODUCT_CUT = '\n\n---\n\n## CLÁUSULA VIGÉSIMA PRIMERA'
PRODUCT_ADJUSTMENTS = (('**c)** EL CONTRATANTE deberá reportar los problemas detectados a través del medio de notificación definido en la CLÁUSULA DÉCIMA QUINTA, cumpliendo el protocolo de reporte de incidentes definido en el PARÁGRAFO PRIMERO de la CLÁUSULA VIGÉSIMA SEGUNDA. El reporte que no reúna la información allí señalada no dará inicio al cómputo de los plazos del presente parágrafo sino desde el momento en que sea completado.', '**c)** EL CONTRATANTE deberá reportar los problemas detectados a través del medio de notificación definido en la CLÁUSULA DÉCIMA QUINTA. Todo reporte incluirá, en el cuerpo del mensaje o en documento adjunto: **i)** título corto que identifique el problema; **ii)** dirección (URL) de la página en la que inició la operación; **iii)** dirección (URL) de la página en la que se presentó el problema, si es distinta de la anterior; **iv)** pasos realizados, enumerados en orden; **v)** lo que ocurrió, con el mensaje de error exacto o una captura de pantalla; **vi)** lo que se esperaba que ocurriera; **vii)** dispositivo y navegador utilizados; y **viii)** fecha y hora aproximada del suceso. El reporte que no reúna la información aquí señalada no dará inicio al cómputo de los plazos del presente parágrafo sino desde el momento en que sea completado.'), ('dicho servicio se regirá por las CLÁUSULAS VIGÉSIMA PRIMERA a VIGÉSIMA CUARTA del presente contrato y por las condiciones económicas definidas en el Documento Propuesta Comercial.', 'dicho servicio se regirá por el contrato de prestación del servicio de hosting, mantenimiento y soporte que las partes suscriban de manera independiente, incluidas las condiciones económicas establecidas en ese contrato de servicio.'), ('con al menos cinco (5) días hábiles de antelación.\n\n---\n\n## CLÁUSULA DÉCIMA SEXTA', 'con al menos cinco (5) días hábiles de antelación.\n\nPara todos los efectos del presente contrato, se entiende por día hábil el comprendido de lunes a viernes, con exclusión de sábados, domingos y días festivos de la República de Colombia conforme a la Ley 51 de 1983 y las normas que la modifiquen.\n\n---\n\n## CLÁUSULA DÉCIMA SEXTA'))

def import_versions(apps, schema_editor):
    Template = apps.get_model('content', 'ContractTemplate')
    Version = apps.get_model('content', 'ContractTemplateVersion')
    database = schema_editor.connection.alias
    for template in Template.objects.using(database).all():
        combined = template.content_markdown
        if combined.count(PRODUCT_CUT) != 1:
            if template.is_default:
                raise RuntimeError('No se puede importar el producto: revisa sus anclas.')
            continue
        product = combined[:combined.index(PRODUCT_CUT)]
        for before, after in PRODUCT_ADJUSTMENTS:
            if product.count(before) != 1:
                if template.is_default:
                    raise RuntimeError('No se puede importar el producto: ancla ambigua.')
                break
            product = product.replace(before, after, 1)
        else:
            template.product_content_markdown = product
            template.save(using=database, update_fields=['product_content_markdown'])
            for variant, markdown in [('combined', combined), ('product', product), ('service', template.service_content_markdown)]:
                Version.objects.using(database).create(template_id=template.pk, variant=variant, version=1,
                    markdown=markdown, author_label='Importación', change_note='Importación de la plantilla vigente antes de habilitar edición versionada.')


class Migration(migrations.Migration):
    dependencies = [('content', '0279_contract_template_versions')]
    operations = [migrations.RunPython(import_versions, migrations.RunPython.noop)]
