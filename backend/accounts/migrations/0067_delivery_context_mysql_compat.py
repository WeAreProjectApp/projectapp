"""Keep new UUID foreign keys compatible with legacy MySQL table defaults.

Replace the unapplied 0067 without editing its published operations. Databases
that already applied that migration keep their existing migration history.
"""

from importlib import import_module
import re

from django.db import migrations


original = import_module('accounts.migrations.0067_explicit_delivery_authoring_context')


def align_requirement_default(apps, schema_editor):
    """Change only the default for future columns, never existing text/data."""
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return

    table = apps.get_model('accounts', 'Requirement')._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT s.DEFAULT_CHARACTER_SET_NAME, s.DEFAULT_COLLATION_NAME, '
            't.TABLE_COLLATION FROM information_schema.SCHEMATA s '
            'JOIN information_schema.TABLES t ON t.TABLE_SCHEMA = s.SCHEMA_NAME '
            'WHERE s.SCHEMA_NAME = DATABASE() AND t.TABLE_NAME = %s',
            [table],
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError('Cannot inspect the legacy Requirement table collation')
    charset, collation, table_collation = row
    if table_collation == collation:
        return
    if not all(re.fullmatch(r'[a-zA-Z0-9_]+', value) for value in (charset, collation)):
        raise RuntimeError('Invalid MySQL character set or collation metadata')

    quote = schema_editor.quote_name
    # DEFAULT affects columns added by 0067. CONVERT TO would rewrite existing
    # columns and potentially change their comparison semantics; do not use it.
    schema_editor.execute(
        f'ALTER TABLE {quote(table)} DEFAULT CHARACTER SET {quote(charset)} '
        f'COLLATE {quote(collation)}'
    )


class Migration(original.Migration):
    replaces = [('accounts', '0067_explicit_delivery_authoring_context')]

    operations = [
        migrations.RunPython(
            align_requirement_default,
            reverse_code=migrations.RunPython.noop,
            atomic=False,
        ),
        *original.Migration.operations,
    ]
