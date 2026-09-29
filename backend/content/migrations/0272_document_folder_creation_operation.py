from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("content", "0271_merge_video_resources_and_document_folders")]
    operations = [
        migrations.AddField(
            model_name="documentfolder",
            name="creation_operation",
            field=models.CharField(
                max_length=160, blank=True, default="", editable=False
            ),
        ),
        migrations.AlterField(
            model_name="documentfolder",
            name="creation_source",
            field=models.CharField(
                max_length=10,
                default="system",
                editable=False,
                choices=[
                    ("panel", "Panel"),
                    ("mcp", "MCP"),
                    ("system", "System"),
                    ("migration", "Migration"),
                    ("unknown", "Unknown"),
                ],
            ),
        ),
    ]
