"""Read-only consultation of records retained after project deletion."""

import pytest

from accounts.models import Deliverable, DeliverableFile, Project, ProjectAdminAccess, ProjectPhase
from accounts.services.credential_cipher import encrypt_secret
from content.models import BusinessProposal, ProjectRetentionContext
from django.core.files.base import ContentFile
from django.db import connection
from django.test.utils import CaptureQueriesContext


pytestmark = pytest.mark.django_db


@pytest.fixture
def retained_phase(admin_user, make_client_profile):
    profile = make_client_profile(company='Retained data client')
    context = ProjectRetentionContext.objects.create(
        client=profile.user,
        original_project_id=101,
        project_name='Archived client portal',
        retained_records={},
        category_counts={},
        created_by=admin_user,
    )
    proposal = BusinessProposal.objects.create(
        title='Archived phase proposal', client_name='Retained data client',
    )
    phase = ProjectPhase.objects.create(
        project=None,
        business_proposal=proposal,
        order=3,
        retention_context=context,
    )
    context.retained_records = {'accounts.projectphase': [str(phase.pk)]}
    context.category_counts = {'accounts.projectphase': 1}
    context.save(update_fields=['retained_records', 'category_counts'])
    return {'profile': profile, 'context': context, 'phase': phase}


@pytest.fixture
def retained_attachment(admin_user, make_client_profile):
    profile = make_client_profile(company='File retention client')
    project = Project.objects.create(name='Archived file project', client=profile.user)
    context = ProjectRetentionContext.objects.create(
        client=profile.user,
        original_project_id=project.pk,
        project_name=project.name,
        retained_records={},
        category_counts={},
        created_by=admin_user,
    )
    deliverable = Deliverable.objects.create(
        project=project,
        title='Archived deliverable',
        uploaded_by=admin_user,
    )
    attachment = DeliverableFile.objects.create(
        deliverable=deliverable,
        file=ContentFile(b'retained attachment', name='archived-contract.pdf'),
        title='Archived contract',
        uploaded_by=admin_user,
    )
    context.retained_records = {'accounts.deliverablefile': [str(attachment.pk)]}
    context.category_counts = {'accounts.deliverablefile': 1}
    context.save(update_fields=['retained_records', 'category_counts'])
    return {'profile': profile, 'context': context, 'attachment': attachment}


def retained_data_url(profile):
    return f'/api/proposals/client-profiles/{profile.pk}/retained-project-data/'


def retained_reveal_url(profile, context, phase):
    return (
        f'{retained_data_url(profile)}{context.pk}/phases/{phase.pk}/reveal/'
    )


def test_staff_lists_retained_context_with_its_categories(admin_client, retained_phase):
    """Fails if staff cannot identify the original project and retained category before opening records."""
    response = admin_client.get(retained_data_url(retained_phase['profile']))

    assert response.status_code == 200
    assert response.data['contexts'][0]['id'] == retained_phase['context'].pk
    assert response.data['contexts'][0]['project_name'] == 'Archived client portal'
    assert response.data['contexts'][0]['categories'] == [
        {
            'key': 'phases',
            'label': 'Fases comerciales',
            'label_en': 'Commercial phases',
            'description': 'Fases creadas desde propuestas. Las propuestas comerciales se conservan.',
            'description_en': 'Phases created from proposals. Commercial proposals are retained.',
            'count': 1,
        },
    ]


def test_staff_context_list_limits_first_page_to_fifty(admin_client, admin_user, retained_phase):
    """Fails if retained-context summaries load every historical project in one response."""
    profile = retained_phase['profile']
    ProjectRetentionContext.objects.bulk_create([
        ProjectRetentionContext(
            client=profile.user,
            original_project_id=300 + index,
            project_name=f'Archived project {index}',
            retained_records={},
            category_counts={},
            created_by=admin_user,
        )
        for index in range(50)
    ])

    with CaptureQueriesContext(connection) as queries:
        first = admin_client.get(retained_data_url(profile))
    second = admin_client.get(f'{retained_data_url(profile)}?page=2')

    assert first.status_code == 200
    assert first.data['count'] == 51
    assert first.data['page'] == 1
    assert len(first.data['contexts']) == 50
    assert len(queries) <= 6
    assert second.data['page'] == 2
    assert len(second.data['contexts']) == 1


def test_staff_pages_retained_category_records_without_manifest_queries(admin_client, admin_user, retained_phase):
    """Fails if category records exceed one page or re-read the retention manifest per row."""
    proposals = BusinessProposal.objects.bulk_create([
        BusinessProposal(
            title=f'Paged proposal {index}',
            client_name='Retained data client',
            slug=f'paged-proposal-{index}',
        )
        for index in range(50)
    ])
    phases = ProjectPhase.objects.bulk_create([
        ProjectPhase(
            project=None,
            business_proposal=proposal,
            order=index + 4,
            retention_context=retained_phase['context'],
        )
        for index, proposal in enumerate(proposals)
    ])
    ids = [str(retained_phase['phase'].pk), *[str(phase.pk) for phase in phases]]
    retained_phase['context'].retained_records = {'accounts.projectphase': ids}
    retained_phase['context'].category_counts = {'accounts.projectphase': 51}
    retained_phase['context'].save(update_fields=['retained_records', 'category_counts'])
    url = f"{retained_data_url(retained_phase['profile'])}?context={retained_phase['context'].pk}&category=phases"

    with CaptureQueriesContext(connection) as queries:
        first = admin_client.get(url)
    second = admin_client.get(f'{url}&page=2')

    assert first.status_code == 200
    assert first.data['count'] == 51
    assert len(first.data['results']) == 50
    assert len(queries) <= 6
    assert second.data['results'][0]['id'] != first.data['results'][0]['id']
    assert len(second.data['results']) == 1


def test_staff_gets_paginated_allowlisted_retained_phase(admin_client, retained_phase):
    """Fails if retained consultation exposes project links or encrypted data outside its allowlist."""
    response = admin_client.get(
        f"{retained_data_url(retained_phase['profile'])}?context={retained_phase['context'].pk}&category=phases&page=1",
    )

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['page'] == 1
    assert response['Cache-Control'] == 'no-store'
    assert response.data['results'] == [
        {
            'id': str(retained_phase['phase'].pk),
            'key': 'phases',
            'title': 'Fases comerciales',
            'fields': {
                'order': 3,
                'hosting_start_date': None,
                'hosting_activated_at': None,
                'created_at': retained_phase['phase'].created_at,
            },
            'files': [],
            'can_reveal': False,
        },
    ]


def test_staff_gets_empty_second_page_for_single_retained_record(admin_client, retained_phase):
    """Fails if retained consultation ignores the requested page while returning a fixed-size result."""
    response = admin_client.get(
        f"{retained_data_url(retained_phase['profile'])}?context={retained_phase['context'].pk}&category=phases&page=2",
    )

    assert response.status_code == 200
    assert response.data == {'count': 1, 'page': 2, 'results': []}


def test_staff_cannot_open_context_through_another_client(admin_client, retained_phase, make_client_profile):
    """Fails if a context identifier lets staff enumerate retained data under a different client."""
    other_profile = make_client_profile(company='Other retained data client')

    response = admin_client.get(
        f"{retained_data_url(other_profile)}?context={retained_phase['context'].pk}&category=phases",
    )

    assert response.status_code == 404
    assert response.data['detail'] == 'No ProjectRetentionContext matches the given query.'


def test_staff_rejected_for_unknown_retained_category(admin_client, retained_phase):
    """Fails if arbitrary model labels become browsable through retained consultation."""
    response = admin_client.get(
        f"{retained_data_url(retained_phase['profile'])}?context={retained_phase['context'].pk}&category=auth.user",
    )

    assert response.status_code == 400
    assert response.data == {'category': 'Elige una categoría válida.'}


def test_staff_cannot_reveal_record_missing_from_context_inventory(admin_client, retained_phase):
    """Fails if a guessed record identifier bypasses the retention context inventory."""
    proposal = BusinessProposal.objects.create(
        title='Unlisted phase proposal', client_name='Retained data client',
    )
    unlisted_phase = ProjectPhase.objects.create(
        project=None,
        business_proposal=proposal,
        order=4,
        retention_context=retained_phase['context'],
    )

    response = admin_client.post(
        retained_reveal_url(retained_phase['profile'], retained_phase['context'], unlisted_phase),
        {},
        format='json',
    )

    assert response.status_code == 404
    assert response.data['detail'] == 'Ese dato no pertenece a esta consulta.'


def test_staff_cannot_reveal_non_secret_retained_phase(admin_client, retained_phase):
    """Fails if the generic retention endpoint reveals fields from a record without reveal permission."""
    response = admin_client.post(
        retained_reveal_url(
            retained_phase['profile'], retained_phase['context'], retained_phase['phase'],
        ),
        {},
        format='json',
    )

    assert response.status_code == 403
    assert response.data['detail'] == 'Este dato no admite revelar credenciales.'


def test_staff_cannot_reveal_retained_record_through_another_client(
    admin_client, retained_phase, make_client_profile,
):
    """Fails if a staff user can reveal a retained record by pairing it with another client id."""
    other_profile = make_client_profile(company='Other reveal client')

    response = admin_client.post(
        retained_reveal_url(
            other_profile,
            retained_phase['context'],
            retained_phase['phase'],
        ),
        {},
        format='json',
    )

    assert response.status_code == 404
    assert response.data['detail'] == 'No ProjectRetentionContext matches the given query.'


def test_staff_reveals_encrypted_retained_access_only_on_request(admin_client, admin_user, make_client_profile):
    """Fails if retained administrative credentials cannot be revealed through their explicit endpoint."""
    profile = make_client_profile(company='Credential retention client')
    context = ProjectRetentionContext.objects.create(
        client=profile.user,
        original_project_id=202,
        project_name='Archived credential project',
        retained_records={},
        created_by=admin_user,
    )
    access = ProjectAdminAccess.objects.create(
        project=None,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_username='archived-admin',
        admin_password_encrypted=encrypt_secret('retained-secret'),
        retention_context=context,
    )
    context.retained_records = {'accounts.projectadminaccess': [str(access.pk)]}
    context.save(update_fields=['retained_records'])

    response = admin_client.post(
        f'{retained_data_url(profile)}{context.pk}/accesses/{access.pk}/reveal/',
        {},
        format='json',
    )

    assert response.status_code == 200
    assert response.data == {'value': 'retained-secret'}
    assert response['Cache-Control'] == 'no-store'


def test_staff_downloads_file_listed_by_retention_context(admin_client, retained_attachment):
    """Fails if a retained attachment cannot be downloaded from its listed consultation record."""
    profile = retained_attachment['profile']
    context = retained_attachment['context']
    attachment = retained_attachment['attachment']

    response = admin_client.get(
        f'{retained_data_url(profile)}{context.pk}/accounts.deliverablefile/{attachment.pk}/files/file/',
    )

    assert response.status_code == 200
    assert response['Cache-Control'] == 'no-store'
    assert b''.join(response.streaming_content) == b'retained attachment'


def test_staff_cannot_download_listed_file_through_another_client(
    admin_client, retained_attachment, make_client_profile,
):
    """Fails if a listed file can be downloaded by guessing its context under another client."""
    other_profile = make_client_profile(company='Other download client')
    context = retained_attachment['context']
    attachment = retained_attachment['attachment']

    response = admin_client.get(
        f'{retained_data_url(other_profile)}{context.pk}/accounts.deliverablefile/{attachment.pk}/files/file/',
    )

    assert response.status_code == 404
    assert response.data['detail'] == 'No ProjectRetentionContext matches the given query.'


@pytest.mark.parametrize('url_suffix', [
    '',
    '101/phases/202/files/file/',
    '101/phases/202/reveal/',
])
def test_anonymous_requester_cannot_access_retained_consultation(api_client, retained_phase, url_suffix):
    """Fails if any retained consultation endpoint accepts an unauthenticated browser request."""
    response = getattr(api_client, 'post' if url_suffix.endswith('reveal/') else 'get')(
        f"{retained_data_url(retained_phase['profile'])}{url_suffix}",
        format='json',
    )

    assert response.status_code == 403
