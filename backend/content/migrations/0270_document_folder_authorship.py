import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0269_merge_service_contract_and_proposal_explainer"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="DocumentFolderMutationLock",
            fields=[
                (
                    "id",
                    models.PositiveSmallIntegerField(
                        default=1, editable=False, primary_key=True, serialize=False
                    ),
                )
            ],
        ),
        migrations.AddField(
            model_name="documentfolder",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_document_folders",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="documentfolder",
            name="creation_source",
            field=models.CharField(
                max_length=10,
                editable=False,
                default="unknown",
                choices=[
                    ("panel", "Panel"),
                    ("mcp", "MCP"),
                    ("system", "System"),
                    ("unknown", "Unknown"),
                ],
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="documentfolder",
            name="creation_source",
            field=models.CharField(
                max_length=10,
                editable=False,
                default="system",
                choices=[
                    ("panel", "Panel"),
                    ("mcp", "MCP"),
                    ("system", "System"),
                    ("unknown", "Unknown"),
                ],
            ),
        ),
    ]
