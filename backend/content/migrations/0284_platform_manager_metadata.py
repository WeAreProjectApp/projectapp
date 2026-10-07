from django.db import migrations


def update_metadata(apps, schema_editor):
    connector = apps.get_model('content', 'McpConnector')
    connector.objects.filter(slug='projects').update(
        name='Gestor de la plataforma',
        description=('Proyectos, entregas contractuales, recursos, modelo de datos, tickets, ideas, '
                     'políticas de acceso, contexto de cobro, documentos, historial y avisos. '
                     'Comparte las reglas de Platform; las aprobaciones actuales pertenecen al cliente.'),
    )


class Migration(migrations.Migration):
    dependencies = [('content', '0283_proposal_project_reassignment')]
    operations = [migrations.RunPython(update_metadata, migrations.RunPython.noop)]
