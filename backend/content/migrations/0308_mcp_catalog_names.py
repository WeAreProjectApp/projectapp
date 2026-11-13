"""Normalize display names without changing endpoints, grants or activation."""
from django.db import migrations, models


NAMES = {
    'operations': 'Gestor de operaciones', 'commercial': 'Gestor de clientes y ventas',
    'offerings': 'Gestor de nuestra oferta', 'programs': 'Gestor de programas',
    'projects': 'Gestor de proyectos', 'data-integrity': 'Gestor de integridad de datos',
    'documents': 'Gestor de documentos', 'communications': 'Gestor de comunicaciones',
    'content': 'Gestor de contenido', 'accounting': 'Gestor de contabilidad',
    'tasks': 'Gestor de tareas', 'procurement': 'Gestor de contratación pública',
}


def normalize_names(apps, schema_editor):
    connector = apps.get_model('content', 'McpConnector')
    for slug, name in NAMES.items():
        connector.objects.using(schema_editor.connection.alias).filter(slug=slug).update(name=name)


class Migration(migrations.Migration):
    dependencies = [('content', '0307_merge_parallel_features')]
    operations = [
        migrations.AddField(
            model_name='mcpconnector', name='retirement_evidence',
            field=models.JSONField(default=dict, blank=True, editable=False),
        ),
        migrations.RunPython(normalize_names, migrations.RunPython.noop),
    ]
