from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('secure_links', '0001_initial')]

    operations = [
        migrations.AlterField(
            model_name='securelinkevent',
            name='kind',
            field=models.CharField(max_length=20, choices=[
                ('created', 'Creado'),
                ('revealed', 'Abierto por el destinatario'),
                ('reveal_blocked', 'Intento de apertura rechazado'),
                ('reactivated', 'Reactivado'),
                ('rotated', 'Enlace regenerado'),
                ('revoked', 'Revocado'),
                ('updated', 'Editado'),
                ('panel_viewed', 'Contenido visto en el panel'),
                ('mcp_viewed', 'Contenido consultado desde MCP'),
            ]),
        ),
    ]
