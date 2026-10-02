"""Exercise the delivery UUID migration on an isolated GitHub MySQL service.

This is a CI-only database integration check, separate from the SQLite pytest
suite. It never loads ProjectApp settings, .env files, application data or
production credentials. The connection and disposable schema are fixed here.
"""

from importlib import import_module
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid


def configure_fixture():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Refused: this MySQL fixture only runs in GitHub Actions')
    if os.environ.get('DJANGO_ENV') == 'production' or os.environ.get('DJANGO_SETTINGS_MODULE'):
        raise SystemExit('Refused: inherited Django settings are not fixture configuration')
    backend = Path(__file__).resolve().parents[2] / 'backend'
    if (backend / '.env').exists():
        raise SystemExit('Refused: the CI checkout must not contain backend/.env')
    sys.path.insert(0, str(backend))

    import django
    from django.conf import settings

    root = tempfile.TemporaryDirectory(prefix='projectapp-mysql-fixture-')
    settings.configure(
        SECRET_KEY='isolated-schema-fixture',
        INSTALLED_APPS=[],
        DATABASES={'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': 'test_projectapp_delivery_migration',
            'USER': 'migration_fixture',
            'PASSWORD': os.environ['MYSQL_FIXTURE_PASSWORD'],
            'HOST': '127.0.0.1',
            'PORT': '33306',
            'OPTIONS': {'charset': 'utf8mb4'},
        }},
        STORAGES={name: {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
            'OPTIONS': {'location': root.name},
        } for name in ('default', 'private')},
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        USE_TZ=True,
    )
    django.setup()
    return root


def run_checks():
    from django.db import connection, IntegrityError, models, OperationalError
    from django.db.migrations.state import ModelState, ProjectState

    replacement = import_module('accounts.migrations.0067_delivery_context_mysql_compat')
    original = import_module('accounts.migrations.0067_explicit_delivery_authoring_context')
    context_field = next(
        operation for operation in original.Migration.operations
        if getattr(operation, 'model_name', None) == 'requirement'
        and getattr(operation, 'name', None) == 'context'
    )
    context_id = uuid.UUID('31d79b75-d888-4b93-b5cb-9cc700d43503')

    class MySQLDeliveryMigrationTests(unittest.TestCase):
        def setUp(self):
            with connection.cursor() as cursor:
                cursor.execute('SELECT DATABASE(), CURRENT_USER(), VERSION()')
                database, principal, version = cursor.fetchone()
                self.assertEqual(database, 'test_projectapp_delivery_migration')
                self.assertTrue(principal.startswith('migration_fixture@'))
                self.assertTrue(version.startswith('8.4.'))
                cursor.execute('DROP TABLE IF EXISTS accounts_requirement')
                cursor.execute('DROP TABLE IF EXISTS accounts_deliverypromptcontext')
                cursor.execute(
                    'ALTER DATABASE test_projectapp_delivery_migration '
                    'CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci'
                )
                cursor.execute(
                    'CREATE TABLE accounts_requirement ('
                    'id bigint PRIMARY KEY, title varchar(300) NOT NULL) '
                    'CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci'
                )
                cursor.execute(
                    'CREATE TABLE accounts_deliverypromptcontext (id char(32) PRIMARY KEY)'
                )
                cursor.execute(
                    'INSERT INTO accounts_requirement (id, title) VALUES (1, %s)',
                    ['Árbol conservado 🌳'],
                )
                cursor.execute(
                    'INSERT INTO accounts_deliverypromptcontext (id) VALUES (%s)',
                    [context_id.hex],
                )
            self.before = ProjectState()
            self.before.add_model(ModelState('accounts', 'Requirement', [
                ('id', models.BigIntegerField(primary_key=True)),
                ('title', models.CharField(max_length=300)),
            ]))
            self.before.add_model(ModelState('accounts', 'DeliveryPromptContext', [
                ('id', models.UUIDField(primary_key=True)),
            ]))
            self.after = self.before.clone()
            context_field.state_forwards('accounts', self.after)

        def add_context_field(self):
            with connection.schema_editor() as editor:
                context_field.database_forwards('accounts', editor, self.before, self.after)

        def apply_compatibility(self):
            with connection.schema_editor() as editor:
                replacement.Migration.operations[0].database_forwards(
                    'accounts', editor, self.before, self.before.clone(),
                )

        def column_collation(self, table, column):
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT COLLATION_NAME FROM information_schema.COLUMNS '
                    'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s',
                    [table, column],
                )
                return cursor.fetchone()[0]

        def assert_context_round_trip(self):
            requirement = self.after.apps.get_model('accounts', 'Requirement')
            requirement.objects.filter(pk=1).update(context_id=context_id)
            saved = requirement.objects.select_related('context').get(pk=1)
            self.assertEqual(saved.title, 'Árbol conservado 🌳')
            self.assertEqual(saved.context.pk, context_id)
            self.assertEqual(
                self.column_collation('accounts_requirement', 'context_id'),
                'utf8mb4_unicode_ci',
            )
            with self.assertRaises(IntegrityError):
                requirement.objects.filter(pk=1).update(
                    context_id=uuid.UUID('50832758-acfb-48d5-b4e1-0975e929bdcc'),
                )
            self.assertEqual(requirement.objects.get(pk=1).context_id, context_id)

        def test_original_operation_reproduces_production_failure(self):
            """Prove that this real MySQL fixture catches the original bug."""
            with self.assertRaises(OperationalError) as error:
                self.add_context_field()
            self.assertEqual(error.exception.args[0], 3780)
            self.assertEqual(
                self.column_collation('accounts_requirement', 'title'),
                'utf8mb4_0900_ai_ci',
            )

        def test_legacy_table_accepts_validated_uuid_reference(self):
            """The fix must neither rewrite legacy text nor omit the new FK."""
            self.apply_compatibility()
            self.add_context_field()
            self.assert_context_round_trip()
            self.assertEqual(
                self.column_collation('accounts_requirement', 'title'),
                'utf8mb4_0900_ai_ci',
            )

        def test_compatible_table_preparation_is_idempotent(self):
            """Already compatible tables still migrate, including a safe retry."""
            with connection.cursor() as cursor:
                cursor.execute(
                    'ALTER TABLE accounts_requirement DEFAULT CHARACTER SET utf8mb4 '
                    'COLLATE utf8mb4_unicode_ci'
                )
            self.apply_compatibility()
            self.apply_compatibility()
            self.add_context_field()
            self.assert_context_round_trip()

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(MySQLDeliveryMigrationTests)
    )
    connection.close()
    return result.wasSuccessful()


if __name__ == '__main__':
    fixture_root = configure_fixture()
    try:
        succeeded = run_checks()
    finally:
        fixture_root.cleanup()
    raise SystemExit(0 if succeeded else 1)
