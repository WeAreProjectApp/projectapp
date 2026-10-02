"""Secondary project dependencies stay attached when deletion is refused."""
import pytest

from accounts.models import ProjectAdminAccess, ProjectAccessNote, ProjectPhase
from content.models import BusinessProposal, CommunicationFolder, ProjectBrandAsset
from content.tests.views.test_panel_project_deletion import unused_project, delete_url

pytestmark = pytest.mark.django_db


def test_project_access_blocks_deletion(admin_client, unused_project):
    access = ProjectAdminAccess.objects.create(project=unused_project, environment='production')

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'][0]['key'] == 'accesses'
    assert ProjectAdminAccess.objects.filter(pk=access.pk, project=unused_project).exists()


def test_project_note_blocks_deletion(admin_client, unused_project):
    note = ProjectAccessNote.objects.create(project=unused_project, title='Operational note')

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'][0]['key'] == 'notes'
    assert ProjectAccessNote.objects.filter(pk=note.pk, project=unused_project).exists()


def test_project_phase_blocks_deletion(admin_client, unused_project):
    proposal = BusinessProposal.objects.create(title='Development proposal')
    phase = ProjectPhase.objects.create(project=unused_project, business_proposal=proposal, order=1)

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'][0]['key'] == 'phases'
    assert ProjectPhase.objects.filter(pk=phase.pk, business_proposal=proposal).exists()


def test_brand_asset_blocks_deletion(admin_client, unused_project):
    asset = ProjectBrandAsset.objects.create(
        project=unused_project, title='Brand manual', category='manual',
        file='project-brand/manual.pdf', filename='manual.pdf', size=123,
    )

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'][0]['key'] == 'brand_assets'
    assert ProjectBrandAsset.objects.filter(pk=asset.pk, project=unused_project).exists()


def test_communication_folder_blocks_deletion(admin_client, unused_project):
    folder = CommunicationFolder.objects.create(
        project=unused_project, client=unused_project.client.profile, name='Technical messages',
    )

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'][0]['key'] == 'communication_folders'
    assert CommunicationFolder.objects.filter(pk=folder.pk, project=unused_project).exists()


def test_project_configuration_blocks_deletion(admin_client, unused_project):
    unused_project.repository_url = 'https://git.example.test/client/project'
    unused_project.save()

    response = admin_client.delete(delete_url(unused_project))

    assert response.status_code == 409
    assert response.data['blockers'] == [{'key': 'configuration', 'label': 'Configuración operativa del proyecto', 'count': 1}]


def test_blocked_delete_does_not_record_a_deletion(admin_client, unused_project):
    ProjectAdminAccess.objects.create(project=unused_project, environment='production')

    admin_client.delete(delete_url(unused_project))

    from content.models import AccountingChangeLog
    assert not AccountingChangeLog.objects.filter(entity_type='project', object_id=unused_project.pk, action='deleted').exists()
