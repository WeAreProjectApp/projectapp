from django.db import migrations


OLD_DESCRIPTION = (
    'Administra hilos y mensajes de clientes: consulta, crea y edita; cierra, '
    'reabre, archiva o restaura hilos; elimina borradores, registra envíos, '
    'anula mensajes y corrige fechas sin enviar por los canales.'
)
NEW_DESCRIPTION = (
    'Administra hilos y mensajes de clientes: consulta, crea y edita; cierra, '
    'reabre, archiva o restaura hilos; elimina borradores, registra envíos, '
    'anula mensajes y corrige fechas sin enviar por los canales. Crea enlaces '
    'seguros de un solo uso para compartir información sensible.'
)


def update_description(apps, schema_editor):
    McpConnector = apps.get_model('content', 'McpConnector')
    McpConnector.objects.filter(slug='communications').update(description=NEW_DESCRIPTION)


def restore_description(apps, schema_editor):
    McpConnector = apps.get_model('content', 'McpConnector')
    McpConnector.objects.filter(slug='communications').update(description=OLD_DESCRIPTION)


class Migration(migrations.Migration):
    """Only the description changes: credentials and active state are kept."""

    dependencies = [
        ('content', '0258_communication_folders'),
    ]

    operations = [
        migrations.RunPython(update_description, restore_description),
    ]
