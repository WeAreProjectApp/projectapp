from django.db import migrations


def classify(apps, schema_editor):
    Project = apps.get_model('accounts', 'Project')
    Profile = apps.get_model('accounts', 'UserProfile')
    Folder = apps.get_model('secure_links', 'SecureLinkFolder')
    Link = apps.get_model('secure_links', 'SecureLink')
    Lock = apps.get_model('secure_links', 'SecureLinkFolderLock')
    alias = schema_editor.connection.alias
    Lock.objects.using(alias).get_or_create(pk=1)
    Connector = apps.get_model('content', 'McpConnector')
    for connector in Connector.objects.using(alias).filter(slug='communications'):
        suffix = ' Administra también carpetas propias de enlaces seguros, subcarpetas, movimientos y archivo reversible sin revocar enlaces.'
        if suffix not in connector.description:
            connector.description += suffix
            connector.save(using=alias, update_fields=['description'])
    profiles = dict(Profile.objects.using(alias).values_list('user_id', 'pk'))
    for project in Project.objects.using(alias).iterator():
        root, _ = Folder.objects.using(alias).get_or_create(
            managed_project_id=project.pk,
            defaults={'name': project.name, 'project_id': project.pk, 'client_id': profiles.get(project.client_id)},
        )
        Link.objects.using(alias).filter(project_id=project.pk, folder__isnull=True).update(folder_id=root.pk)


class Migration(migrations.Migration):
    dependencies = [('secure_links', '0006_securelinkfolderlock_securelink_archived_at_and_more')]
    operations = [migrations.RunPython(classify, migrations.RunPython.noop)]
