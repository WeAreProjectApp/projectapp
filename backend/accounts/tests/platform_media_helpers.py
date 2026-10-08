"""Real four-family resource fixtures inside the per-run test file boundary."""
from pathlib import Path

import pytest
from content.models import ProjectRetentionContext
from content.services.project_deletion_catalog import CATEGORIES
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import transaction
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import (
    Deliverable,
    DeliverableClientUpload,
    DeliverableFile,
    DeliverableVersion,
    Project,
    UserProfile,
)
from accounts.services.tokens import get_tokens_for_user

KINDS = ('current', 'version', 'attachment', 'client_upload')


@pytest.fixture
def media_context(django_user_model):
    """Use real profiles and a staff client to pin the Platform role boundary."""
    with transaction.atomic():
        admin = django_user_model.objects.create_user('media-admin', is_staff=True)
        owner = django_user_model.objects.create_user('media-owner', is_staff=True)
        foreign = django_user_model.objects.create_user('media-foreign')
        UserProfile.objects.create(user=admin, role=UserProfile.ROLE_ADMIN)
        UserProfile.objects.create(user=owner, role=UserProfile.ROLE_CLIENT)
        UserProfile.objects.create(user=foreign, role=UserProfile.ROLE_CLIENT)
    project = Project.objects.create(name='Protected resources', client=owner)
    bodies = {kind: f'original {kind} resource bytes'.encode() for kind in KINDS}
    resource = Deliverable.objects.create(project=project, uploaded_by=admin, title='Private resource',
        file=ContentFile(bodies['current'], name='current.pdf'))
    rows = {
        'current': resource,
        'version': DeliverableVersion.objects.create(deliverable=resource, uploaded_by=admin,
            version_number=1, file=ContentFile(bodies['version'], name='version.pdf')),
        'attachment': DeliverableFile.objects.create(deliverable=resource, uploaded_by=admin,
            file=ContentFile(bodies['attachment'], name='attachment.pdf')),
        'client_upload': DeliverableClientUpload.objects.create(deliverable=resource, uploaded_by=owner,
            file=ContentFile(bodies['client_upload'], name='client_upload.pdf')),
    }
    return {'admin': admin, 'owner': owner, 'foreign': foreign, 'project': project,
            'resource': resource, 'rows': rows, 'bodies': bodies}


@pytest.fixture
def large_resource(media_context):
    """Grow only the temporary source to exercise streaming above the MCP cap."""
    with Path(media_context['resource'].file.path).open('r+b') as source:
        source.truncate(26 * 1024 * 1024 + 1)
    return media_context


def api_for(user):
    """Authenticate through the real JWT backend, not force_authenticate."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(user)["access"]}')
    return api


def download_url(context, kind):
    """Select the child id from the actual resource, with no path in the URL."""
    url = reverse('platform-resource-file', kwargs={'project_id': context['project'].pk,
        'resource_id': context['resource'].pk, 'kind': kind})
    return url if kind == 'current' else f'{url}?file_id={context["rows"][kind].pk}'


def response_bytes(response):
    """Consume a real FileResponse and close its opened file."""
    body = b''.join(response.streaming_content)
    response.close()
    return body


def legacy_files(context):
    """Preserve historical database pointers without pretending they are private."""
    for kind, row in context['rows'].items():
        name = storages['default'].save(f'deliverables/{kind}/{row.pk}/legacy.pdf',
            ContentFile(context['bodies'][kind]))
        type(row)._base_manager.filter(pk=row.pk).update(file=name)
        row.refresh_from_db()
    return context


def file_names(context):
    """Read persisted pointers, including retained rows whose save is forbidden."""
    return {kind: type(row)._base_manager.get(pk=row.pk).file.name for kind, row in context['rows'].items()}


def retain_files(context):
    """Detach the parent while retaining the indexed descendants and their owner."""
    retained = ProjectRetentionContext.objects.create(client=context['owner'],
        original_project_id=context['project'].pk, project_name=context['project'].name,
        created_by=context['admin'], retained_records={
            row._meta.label_lower: [str(row.pk)] for row in context['rows'].values()},
        category_counts={row._meta.label_lower: 1 for row in context['rows'].values()})
    Deliverable._base_manager.filter(pk=context['resource'].pk).update(project=None, retention_context=retained)
    context['resource'].refresh_from_db()
    context['retention'] = retained
    return context


def retained_url(context, kind):
    """Use the existing session route and the exact indexed retained record."""
    row = context['rows'][kind]
    category = CATEGORIES[row._meta.label_lower]['key']
    return (f'/api/proposals/client-profiles/{context["owner"].profile.pk}/retained-project-data/'
        f'{context["retention"].pk}/{category}/{row.pk}/files/file/')


def manifest_path(name='inventory'):
    """Keep every inventory under the private temporary test root."""
    return Path(settings.PRIVATE_MEDIA_ROOT) / 'migration_manifests' / f'{name}.json'


def other_resource_child(context, kind):
    """Make a real child of a different resource in the same owned project."""
    parent = Deliverable.objects.create(project=context['project'], title='Other resource',
        uploaded_by=context['admin'])
    values = {'deliverable': parent, 'uploaded_by': context['admin'],
              'file': ContentFile(b'other parent bytes', name='other.pdf')}
    if kind == 'version':
        values['version_number'] = 1
    return type(context['rows'][kind]).objects.create(**values)
