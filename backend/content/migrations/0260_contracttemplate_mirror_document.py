import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0259_update_default_contract_template_v8'),
    ]

    operations = [
        migrations.AddField(
            model_name='contracttemplate',
            name='mirror_document',
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    'Documento del Gestor que muestra este contrato en vivo y en solo '
                    'lectura (PDF y Markdown). No guarda una copia del texto.'
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contract_template',
                to='content.document',
            ),
        ),
    ]
