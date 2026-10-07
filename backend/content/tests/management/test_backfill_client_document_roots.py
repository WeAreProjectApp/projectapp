"""Dry-run-first adoption of the roots that already represent a client."""
import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.core.management import call_command
from io import StringIO

from content.models import DocumentFolder


pytestmark = pytest.mark.django_db


def _client_user(email):
    user = get_user_model().objects.create_user(
        username=email, email=email, password='pass12345', first_name='Cliente',
    )
    UserProfile.objects.update_or_create(
        user=user, defaults={'role': UserProfile.ROLE_CLIENT},
    )
    return user


def _run(*args):
    out = StringIO()
    call_command('backfill_client_document_roots', *args, stdout=out)
    return out.getvalue()


def test_dry_run_reports_without_writing():
    user = _client_user('dry@example.com')
    root = DocumentFolder.objects.create(name='Littigio', client_user=user)

    output = _run()

    assert f'adoptar  carpeta {root.pk}' in output
    assert 'Dry-run' in output
    root.refresh_from_db()
    assert root.managed_client_id is None


def test_apply_adopts_the_root():
    user = _client_user('apply@example.com')
    root = DocumentFolder.objects.create(name='Littigio', client_user=user)

    _run('--apply')

    root.refresh_from_db()
    assert root.managed_client_id == user.pk
    assert root.folder_kind == 'client'


def test_a_client_with_two_roots_is_reported_not_guessed():
    """Elegir por orden de id sería inventar la decisión del operador."""
    user = _client_user('two@example.com')
    first = DocumentFolder.objects.create(name='Gustavo', client_user=user)
    second = DocumentFolder.objects.create(name='Gustavo CLI', client_user=user)

    output = _run('--apply')

    assert 'tiene 2 raíces' in output
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.managed_client_id is None
    assert second.managed_client_id is None


def test_it_never_touches_a_project_space_or_a_subfolder():
    user = _client_user('scoped@example.com')
    Project.objects.bulk_create([Project(name='Kore', client=user)])
    project = Project.objects.get(name='Kore')
    project_root = DocumentFolder.objects.create(
        name='Kore', client_user=user, project=project,
    )
    nested = DocumentFolder.objects.create(
        name='Anidada', parent=project_root, client_user=user,
    )

    _run('--apply')

    project_root.refresh_from_db()
    nested.refresh_from_db()
    assert project_root.managed_client_id is None
    assert nested.managed_client_id is None


def test_is_idempotent():
    user = _client_user('twice@example.com')
    DocumentFolder.objects.create(name='Littigio', client_user=user)

    _run('--apply')
    output = _run('--apply')

    assert '0 carpeta(s) adoptada(s)' in output
    assert DocumentFolder.objects.filter(managed_client=user).count() == 1


def test_retained_project_root_is_reported_not_adopted(admin_user):
    """Fails if the root retained from a deleted project is adopted as the client root."""
    from content.models import ProjectRetentionContext

    user = _client_user('retained@example.com')
    context = ProjectRetentionContext.objects.create(
        client=user, original_project_id=9014, project_name='Littigio', created_by=admin_user,
    )
    root = DocumentFolder.objects.create(name='Littigio', client_user=user, retention_context=context)

    output = _run('--apply')

    assert f'saltar   carpeta {root.pk} «Littigio» — conservada de un proyecto eliminado' in output
    root.refresh_from_db()
    assert root.managed_client_id is None
