"""REST resource authority comes from the Platform role, not Django staff flags."""
import pytest
from django.core.files.base import ContentFile
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from accounts.models import Deliverable, Project, ProjectDataModelEntity, UserProfile
from accounts.services import platform_resources
from accounts.services.tokens import get_tokens_for_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client(django_user_model):
    """Create a real Platform client with a Django staff flag."""
    user = django_user_model.objects.create_user('staff-client', email='staff-client@example.test', is_staff=True)
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True)
    return user


@pytest.fixture
def project(staff_client):
    """Create the project owned by the client under test."""
    return Project.objects.create(name='Own project', client=staff_client)


@pytest.fixture
def resource(project, staff_client):
    """Retain original bytes for rejected write assertions."""
    return Deliverable.objects.create(project=project, uploaded_by=staff_client,
        title='Original', category='documents', file=ContentFile(b'original bytes', name='manual.pdf'))


@pytest.fixture
def client_api(staff_client):
    """Authenticate using the real Platform JWT boundary."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(staff_client)["access"]}')
    return api


@pytest.mark.parametrize(('method', 'suffix', 'data'), [
    ('patch', '', {'title': 'Changed'}),
    ('delete', '', {}),
    ('post', 'upload-version/', {'title': 'Forbidden'}),
    ('post', 'attachments/', {'title': 'Forbidden'}),
])
def test_staff_client_cannot_administer_a_resource(client_api, project, resource, method, suffix, data):
    """Fails if a staff flag overrides the Platform client role for writes."""
    response = getattr(client_api, method)(
        f'/api/accounts/projects/{project.pk}/deliverables/{resource.pk}/{suffix}', data, format='json')
    assert response.status_code == 403
    resource.refresh_from_db()
    assert resource.title == 'Original'
    assert resource.is_archived is False
    assert resource.current_version == 1


def test_staff_client_cannot_include_archived_resources(client_api, project, resource):
    """Fails if include_archived widens client visibility because of staff."""
    resource.is_archived = True
    resource.save(update_fields=['is_archived'])
    response = client_api.get(f'/api/accounts/projects/{project.pk}/deliverables/?include_archived=1')
    assert response.status_code == 200
    assert response.data == []


def test_staff_client_cannot_upload_an_admin_category(client_api, project):
    """Fails if staff lets a client create an administrator-only resource."""
    response = client_api.post(f'/api/accounts/projects/{project.pk}/deliverables/', {
        'title': 'Design', 'category': 'designs', 'file': ContentFile(b'ZIP', name='design.zip'),
    }, format='multipart')
    assert response.status_code == 403
    assert Deliverable.objects.filter(project=project).count() == 0


def test_staff_client_cannot_replace_the_data_model(client_api, project):
    """Fails if Django staff grants client authority to replace project entities."""
    original = ProjectDataModelEntity.objects.create(project=project, name='Original')
    response = client_api.post(f'/api/accounts/projects/{project.pk}/data-model-entities/',
        {'entities': [{'name': 'Changed'}]}, format='json')
    assert response.status_code == 403
    assert ProjectDataModelEntity.objects.get(pk=original.pk).name == 'Original'


@pytest.fixture
def foreign_resource(django_user_model):
    """Create another client owner and preserve their original file."""
    owner = django_user_model.objects.create_user('foreign-resource-owner')
    project = Project.objects.create(name='Foreign project', client=owner)
    return Deliverable.objects.create(project=project, uploaded_by=owner, title='Foreign resource',
        file=ContentFile(b'foreign bytes', name='foreign.pdf'))


@pytest.mark.parametrize('suffix', [
    'deliverables/', 'data-model-entities/', 'deliverables/{resource}/',
    'deliverables/{resource}/client-folders/',
])
def test_staff_client_cannot_read_a_foreign_project(client_api, foreign_resource, suffix):
    """Fails if an HTTP read ignores the actual project owner."""
    response = client_api.get(f'/api/accounts/projects/{foreign_resource.project_id}/'
                              + suffix.format(resource=foreign_resource.pk))
    assert response.status_code == 403


def test_staff_client_cannot_download_foreign_bytes(staff_client, foreign_resource):
    """Fails if a no-context staff client can read another owner file."""
    with pytest.raises(NotFound):
        platform_resources.read_file(foreign_resource.project_id, staff_client, foreign_resource.pk)
    with foreign_resource.file.open('rb') as source:
        assert source.read() == b'foreign bytes'
