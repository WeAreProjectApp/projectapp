"""A database which already applied 0067 must never replay its schema changes."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder


@pytest.mark.django_db(transaction=True)
def test_applied_original_delivery_migration_does_not_replay():
    """Catch an incompatible dependency that recreates existing context tables."""
    recorder = MigrationRecorder(connection)
    replacement = ('accounts', '0067_delivery_context_mysql_compat')
    recorder.record_unapplied(*replacement)
    try:
        executor = MigrationExecutor(connection)
        executor.loader.check_consistent_history(connection)

        assert executor.loader.applied_migrations[replacement].name == replacement[1]
        assert executor.migration_plan(executor.loader.graph.leaf_nodes()) == []
    finally:
        recorder.record_applied(*replacement)
