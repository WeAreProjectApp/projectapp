from typing import ClassVar

import django.db.models.deletion
from django.db import migrations, models


def describe_proposals(apps, schema_editor):
    apps.get_model('content', 'McpConnector').objects.filter(slug='proposals').update(
        description=(
            'Administra propuestas, contenido, ajustes, contratos personalizados, '
            'documentos, correos, analítica, cronograma y videos. Formalización '
            'con paquetes privados por credencial y confirmación antes de enviar.'
        ),
    )


class Migration(migrations.Migration):
    dependencies: ClassVar[list] = [('content', '0271_merge_video_resources_and_document_folders')]

    operations: ClassVar[list] = [
        migrations.RunPython(describe_proposals, migrations.RunPython.noop),
        migrations.AddField(
            model_name='proposalformalization',
            name='mcp_credential',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='proposal_formalizations', to='content.mcpcredential',
            ),
        ),
    ]
