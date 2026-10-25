"""Prepare the published help catalog when focused tests skip migrations."""
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection

from accounts.tests.project_collaboration_helpers import context


def help_context():
    """Seed only help defaults inside the test's isolated database transaction."""
    defaults = import_module('accounts.migrations.0087_platform_help_defaults')
    defaults.seed(apps, SimpleNamespace(connection=connection))
    return context()
