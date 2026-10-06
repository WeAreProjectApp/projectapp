"""Project library isolation, upload validation and public Linktree continuity."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied
from accounts.models import Project
from content.models import Linktree, ProjectBrandAsset, ProjectRetentionContext
from content.services.project_force_deletion import (
    force_delete_project,
    forced_deletion_preview,
)

pytestmark = pytest.mark.django_db

@pytest.fixture
def project(admin_user):
    return Project.objects.create(name='Brand project', client=admin_user)

@pytest.fixture
def other_project(admin_user):
    return Project.objects.create(name='Other project', client=admin_user)

@pytest.fixture
def asset(project):
    return ProjectBrandAsset.objects.create(project=project, title='Manual', category='manual',
        file=SimpleUploadedFile('manual.pdf', b'%PDF-1.4 brand manual'), filename='manual.pdf', size=21)

def test_linktree_can_be_linked_and_unlinked_without_changing_public_page(admin_client, api_client, project):
    tree = Linktree.objects.create(name='Brand', handle='brand-project')
    endpoint = reverse('update-linktree', args=[tree.pk])
    linked = admin_client.patch(endpoint, {'project': project.pk}, format='json')
    assert linked.status_code == 200
    library = admin_client.get(reverse('project-brand', args=[project.pk]))
    assert library.data['linktrees'][0]['id'] == str(tree.pk)
    public = api_client.get(reverse('public-linktree', args=[tree.handle]))
    assert public.status_code == 200
    assert 'project' not in public.data
    unlinked = admin_client.patch(endpoint, {'project': None}, format='json')
    assert unlinked.status_code == 200
    tree.refresh_from_db()
    assert tree.project_id is None
    assert tree.handle == 'brand-project'

def test_nonexistent_project_rejected(admin_client):
    response = admin_client.post(reverse('create-linktree'), {
        'name': 'Invalid', 'handle': 'missing-project', 'project': 999999,
    }, format='json')
    assert response.status_code == 400
    assert not Linktree.objects.filter(handle='missing-project').exists()

def test_empty_force_selection_retains_public_linktree(project, superuser, api_client):
    """Fails if an unselected public Linktree loses its handle or becomes editable after project deletion."""
    tree = Linktree.objects.create(name='Brand', handle='keep-public', project=project)
    preview = forced_deletion_preview(project, actor=superuser, delete_keys=[])

    force_delete_project(
        project.pk,
        actor=superuser,
        confirmation='DELETE',
        impact_token=preview['impact_token'],
        delete_keys=[],
    )

    tree.refresh_from_db()
    context = ProjectRetentionContext.objects.get(pk=tree.retention_context_id)
    assert tree.project_id is None
    assert tree.handle == 'keep-public'
    assert context.client_id == project.client_id
    public = api_client.get(reverse('public-linktree', args=[tree.handle]))
    assert public.status_code == 200
    assert 'project' not in public.data
    with pytest.raises(PermissionDenied, match='sólo permiten consulta'):
        tree.save()

def test_upload_is_downloadable_and_not_exposed_as_public_media(admin_client, project):
    response = admin_client.post(reverse('project-brand', args=[project.pk]), {
        'title': 'Brand manual', 'category': 'manual',
        'file': SimpleUploadedFile('manual.pdf', b'%PDF-1.4 content'),
    }, format='multipart')
    assert response.status_code == 201
    assert 'file' not in response.data
    download = admin_client.get(reverse('project-brand-asset', args=[project.pk, response.data['id']]))
    assert download.status_code == 200
    assert b''.join(download.streaming_content) == b'%PDF-1.4 content'
    assert download['Content-Disposition'].startswith('attachment;')
    assert download['Cache-Control'] == 'private, no-store'

def test_library_excludes_other_project_assets(admin_client, project, other_project, asset):
    response = admin_client.get(reverse('project-brand', args=[other_project.pk]))
    assert response.data['assets'] == []
    own = admin_client.get(reverse('project-brand', args=[project.pk]))
    assert own.data['assets'][0]['id'] == asset.pk

@pytest.mark.parametrize('method', ['get', 'delete'])
def test_asset_cannot_be_accessed_via_another_project(admin_client, other_project, asset, method):
    response = getattr(admin_client, method)(reverse('project-brand-asset', args=[other_project.pk, asset.pk]))
    assert response.status_code == 404
    assert ProjectBrandAsset.objects.filter(pk=asset.pk).exists()

@pytest.mark.parametrize('filename,category', [('page.html', 'branding'), ('manual.pdf', 'invalid')])
def test_invalid_upload_is_not_saved(admin_client, project, filename, category):
    response = admin_client.post(reverse('project-brand', args=[project.pk]), {
        'title': 'Unsafe', 'category': category,
        'file': SimpleUploadedFile(filename, b'content'),
    }, format='multipart')
    assert response.status_code == 400
    assert not project.brand_assets.exists()

def test_oversized_upload_is_rejected(admin_client, project):
    response = admin_client.post(reverse('project-brand', args=[project.pk]), {
        'title': 'Large', 'category': 'branding',
        'file': SimpleUploadedFile('large.zip', b'x' * (25 * 1024 * 1024 + 1)),
    }, format='multipart')
    assert response.status_code == 400
    assert 'file' in response.data
    assert not project.brand_assets.exists()

def test_delete_removes_file_after_commit(admin_client, project, asset, django_capture_on_commit_callbacks):
    storage, name = asset.file.storage, asset.file.name
    with django_capture_on_commit_callbacks(execute=True):
        response = admin_client.delete(reverse('project-brand-asset', args=[project.pk, asset.pk]))
    assert response.status_code == 204
    assert not ProjectBrandAsset.objects.filter(pk=asset.pk).exists()
    assert not storage.exists(name)

@pytest.mark.parametrize('method,route', [('get', 'project-brand'), ('post', 'project-brand'), ('get', 'project-brand-asset'), ('delete', 'project-brand-asset')])
def test_anonymous_users_cannot_read_or_mutate_library(api_client, project, asset, method, route):
    args = [project.pk] if route == 'project-brand' else [project.pk, asset.pk]
    response = getattr(api_client, method)(reverse(route, args=args))
    assert response.status_code == 401
    assert ProjectBrandAsset.objects.filter(pk=asset.pk).exists()


def test_authenticated_nonstaff_cannot_download_asset(api_client, admin_user, project, asset):
    admin_user.is_staff = False
    admin_user.is_superuser = False
    admin_user.save(update_fields=['is_staff', 'is_superuser'])
    api_client.force_authenticate(admin_user)
    response = api_client.get(reverse('project-brand-asset', args=[project.pk, asset.pk]))
    assert response.status_code == 403
