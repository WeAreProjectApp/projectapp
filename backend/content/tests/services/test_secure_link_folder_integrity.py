"""Secure-link folder participation in reversible integrity operations."""
import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def project_lifecycle_catalog(db):
    from content.models import DocumentState, DocumentStateGroup

    group, _ = DocumentStateGroup.objects.get_or_create(
        catalog='projects', name='Secure folder integrity lifecycle',
        defaults={'selection_mode': 'exclusive'},
    )
    for key, name in [('development', 'En desarrollo'), ('suspended', 'Suspendido')]:
        DocumentState.objects.get_or_create(
            catalog='projects', system_key=key,
            defaults={'group': group, 'name': name, 'operational_effect': key},
        )


def test_client_merge_relinks_secure_folder_client(superuser):
    from content.tests.data_integrity_merge_factories import client_pair, run_client_merge
    from secure_links.models import SecureLinkFolder

    survivor, duplicate = client_pair()
    folder = SecureLinkFolder.objects.create(name='Entregas', client=duplicate)

    run_client_merge(superuser, survivor, duplicate)

    folder.refresh_from_db()
    assert folder.client_id == survivor.pk


def test_client_merge_preserves_secure_folder_creator(superuser):
    from content.tests.data_integrity_merge_factories import client_pair, run_client_merge
    from secure_links.models import SecureLinkFolder

    survivor, duplicate = client_pair()
    folder = SecureLinkFolder.objects.create(
        name='Entregas', client=duplicate, created_by=duplicate.user,
    )

    run_client_merge(superuser, survivor, duplicate)

    folder.refresh_from_db()
    assert folder.created_by_id == duplicate.user_id


def test_client_merge_undo_restores_drifted_secure_root(superuser):
    """A root changed by the project signal returns to its exact pre-merge values."""
    from content.tests.data_integrity_helpers import undo
    from content.tests.data_integrity_merge_factories import client_pair, make_client_project, run_client_merge
    from secure_links.models import SecureLinkFolder

    survivor, duplicate = client_pair()
    project = make_client_project(duplicate, 'Portal')
    root = SecureLinkFolder.objects.get(managed_project=project)
    SecureLinkFolder.objects.filter(pk=root.pk).update(name='Raíz anterior', client=None)

    _, result = run_client_merge(superuser, survivor, duplicate)
    undo(superuser, result['operation_id'])

    root.refresh_from_db()
    assert (root.name, root.client_id) == ('Raíz anterior', None)


def test_project_rename_syncs_secure_root(make_client_profile, superuser):
    """The project writer synchronizes the secure root captured by the rename closure."""
    from content.tests.data_integrity_helpers import apply, only, scan, selection
    from content.tests.data_integrity_merge_factories import make_client_project
    from secure_links.models import SecureLinkFolder

    profile = make_client_profile(company='Kore SAS')
    make_client_project(profile, 'Kore')
    renamed = make_client_project(profile, 'KORE')
    root = SecureLinkFolder.objects.get(managed_project=renamed)
    SecureLinkFolder.objects.filter(pk=root.pk).update(client=None)
    finding = only(scan(rule_ids=['PJ4']), 'PJ4')[0]

    apply(superuser, [selection(finding, project=renamed.pk, name='Kore Web')])

    root.refresh_from_db()
    assert (root.name, root.client_id) == ('Kore Web', profile.pk)


def test_project_rename_undo_restores_secure_root_values(make_client_profile, superuser):
    """Exact undo restores secure-root drift that existed before the rename."""
    from content.tests.data_integrity_helpers import apply, only, scan, selection, undo
    from content.tests.data_integrity_merge_factories import make_client_project
    from secure_links.models import SecureLinkFolder

    profile = make_client_profile(company='Kore SAS')
    make_client_project(profile, 'Kore')
    renamed = make_client_project(profile, 'KORE')
    root = SecureLinkFolder.objects.get(managed_project=renamed)
    SecureLinkFolder.objects.filter(pk=root.pk).update(name='Raíz anterior', client=None)
    finding = only(scan(rule_ids=['PJ4']), 'PJ4')[0]

    _, result = apply(superuser, [selection(finding, project=renamed.pk, name='Kore Web')])
    undo(superuser, result['operation_id'])

    root.refresh_from_db()
    assert (root.name, root.client_id) == ('Raíz anterior', None)
