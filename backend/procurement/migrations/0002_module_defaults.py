from django.db import migrations


def seed(apps, schema_editor):
    apps.get_model('procurement', 'Settings').objects.get_or_create(pk=1)
    apps.get_model('content', 'McpConnector').objects.get_or_create(
        slug='procurement', defaults={
            'name': 'Contratación estatal',
            'description': 'Procesos SECOP II, búsquedas, alertas, destinatarios, horarios, entregas y seguimiento con análisis externo. Sin IA interna ni acceso a buzones.',
            'is_active': False,
        })


class Migration(migrations.Migration):
    dependencies = [('procurement', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
