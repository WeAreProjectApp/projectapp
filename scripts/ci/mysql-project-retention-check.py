"""Upgrade populated project tables on an isolated, CI-only MySQL database."""
from importlib import import_module
import os
from pathlib import Path
import sys
import unittest


def configure_fixture():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Refused: this MySQL fixture only runs in GitHub Actions')
    if os.environ.get('DJANGO_ENV') == 'production' or os.environ.get('DJANGO_SETTINGS_MODULE'):
        raise SystemExit('Refused: inherited settings are not fixture configuration')
    backend = Path(__file__).resolve().parents[2] / 'backend'
    if (backend / '.env').exists():
        raise SystemExit('Refused: the CI checkout must not contain backend/.env')
    sys.path.insert(0, str(backend))

    import django
    from django.conf import settings

    safe = import_module('projectapp.settings_test')
    values = {key: getattr(safe, key) for key in dir(safe) if key.isupper()}
    values['DATABASES'] = {'default': {
        'ENGINE': 'django.db.backends.mysql', 'NAME': 'test_projectapp_retention',
        'USER': 'retention_fixture', 'PASSWORD': os.environ['MYSQL_FIXTURE_PASSWORD'],
        'HOST': '127.0.0.1', 'PORT': '33306', 'OPTIONS': {'charset': 'utf8mb4'},
    }}
    settings.configure(**values)
    django.setup()


def run_checks():
    from django.db import connection, IntegrityError, transaction
    from django.db.migrations.executor import MigrationExecutor

    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE(), CURRENT_USER(), VERSION()')
        database, principal, version = cursor.fetchone()
        if (database != 'test_projectapp_retention'
                or not principal.startswith('retention_fixture@')
                or not version.startswith('8.4.')):
            raise SystemExit('Refused: unexpected fixture database, principal or engine')

    executor = MigrationExecutor(connection)
    new_targets = executor.loader.graph.leaf_nodes()
    previous = {
        'accounts': '0076_userprofile_billing_address',
        'content': '0280_import_contract_template_versions',
    }
    # Names for these two small apps are discovered from the real predecessor
    # dependencies rather than assuming a numbering convention.
    for app in ('monitoring', 'secure_links'):
        migration = executor.loader.get_migration(app, '0003_project_data_retention' if app == 'monitoring' else '0005_project_data_retention')
        previous[app] = next(name for dependency_app, name in migration.dependencies if dependency_app == app)
    old_targets = [(app, previous.get(app, name)) for app, name in new_targets]
    executor.migrate(old_targets)
    before = executor.loader.project_state(old_targets).apps
    user = before.get_model('auth', 'User').objects.create(username='retention-fixture')
    project = before.get_model('accounts', 'Project').objects.create(name='Proyecto conservado 🌳', client_id=user.pk)
    access = before.get_model('accounts', 'ProjectAdminAccess').objects.create(
        project_id=project.pk, environment='production', admin_username='fixture-admin',
        admin_password_encrypted='ciphertext-preserved',
    )
    document = before.get_model('content', 'Document').objects.create(
        project_id=project.pk, client_user_id=user.pk, title='Documento previo',
        content_markdown='Contenido previo a la migración',
    )

    executor = MigrationExecutor(connection)
    executor.migrate(new_targets)
    after = executor.loader.project_state(new_targets).apps
    Access = after.get_model('accounts', 'ProjectAdminAccess')
    Document = after.get_model('content', 'Document')
    Context = after.get_model('content', 'ProjectRetentionContext')

    class MySQLProjectRetentionTests(unittest.TestCase):
        def test_upgrade_preserves_existing_project_records(self):
            saved = Access.objects.get(pk=access.pk)
            self.assertEqual(saved.project_id, project.pk)
            self.assertIsNone(saved.retention_context_id)
            self.assertEqual(saved.admin_password_encrypted, 'ciphertext-preserved')
            saved_document = Document.objects.get(pk=document.pk)
            self.assertEqual(saved_document.content_markdown, 'Contenido previo a la migración')
            self.assertEqual(saved_document.project_id, project.pk)
            self.assertIsNone(saved_document.retention_context_id)

        def test_retention_reference_enforces_foreign_key(self):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Access.objects.filter(pk=access.pk).update(retention_context_id=999999)
            self.assertIsNone(Access.objects.get(pk=access.pk).retention_context_id)

        def test_detached_records_survive_project_removal(self):
            Project = after.get_model('accounts', 'Project')
            retained_project = Project.objects.create(name='Proyecto a retirar', client_id=user.pk)
            retained_access = Access.objects.create(project_id=retained_project.pk, environment='production')
            retained_document = Document.objects.create(project_id=retained_project.pk, client_user_id=user.pk, title='Documento conservado')
            context = Context.objects.create(
                client_id=user.pk, created_by_id=user.pk, original_project_id=retained_project.pk,
                project_name=retained_project.name,
                retained_records={'accounts.projectadminaccess': [str(retained_access.pk)], 'content.document': [str(retained_document.pk)]},
                category_counts={'accounts.projectadminaccess': 1, 'content.document': 1},
            )
            Access.objects.filter(pk=retained_access.pk).update(project_id=None, retention_context_id=context.pk)
            Document.objects.filter(pk=retained_document.pk).update(project_id=None, retention_context_id=context.pk)
            Project.objects.filter(pk=retained_project.pk).delete()
            saved = Access.objects.get(pk=retained_access.pk)
            self.assertIsNone(saved.project_id)
            self.assertEqual(saved.retention_context_id, context.pk)
            saved_document = Document.objects.get(pk=retained_document.pk)
            self.assertEqual(saved_document.client_user_id, user.pk)
            self.assertIsNone(saved_document.project_id)
            self.assertEqual(saved_document.retention_context_id, context.pk)
            self.assertEqual(Context.objects.get(pk=context.pk).client_id, user.pk)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLProjectRetentionTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    connection.close()
    return result.wasSuccessful()


if __name__ == '__main__':
    configure_fixture()
    raise SystemExit(0 if run_checks() else 1)
