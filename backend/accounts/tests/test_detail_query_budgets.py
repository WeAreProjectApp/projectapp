"""Query and contract guards for optimized platform detail endpoints."""
from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal

import pytest
from content.models import BusinessProposal, Document, DocumentType
from content.services.document_type_codes import COLLECTION_ACCOUNT
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.signals import post_init
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import (
    DataModelEntity,
    Deliverable,
    DeliverableClientFolder,
    DeliverableClientUpload,
    DeliverableFile,
    DeliverableVersion,
    HostingSubscription,
    Project,
    ProjectAdminAccess,
    ProjectPhase,
    UserProfile,
)
from accounts.services.credential_cipher import encrypt_secret
from accounts.services.tokens import get_tokens_for_user

User = get_user_model()
pytestmark = pytest.mark.django_db

MAX_CLIENT_DETAIL_QUERIES = 4
MAX_PROJECT_DETAIL_QUERIES = 4
# Explicit exception: this detail preserves six unpaginated nested collections.
MAX_DELIVERABLE_DETAIL_QUERIES = 10


def _user(email, role, *, first_name='Test', last_name='User'):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='pass12345',
        first_name=first_name,
        last_name=last_name,
    )
    UserProfile.objects.create(
        user=user,
        role=role,
        is_onboarded=True,
        profile_completed=True,
    )
    return user


def _jwt_client(user):
    client = APIClient()
    token = get_tokens_for_user(user)['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


def _project(client, name='Project', **fields):
    return Project.objects.create(name=name, client=client, **fields)


def _subscription(project, *, plan, next_billing_date, billing_amount):
    return HostingSubscription.objects.create(
        project=project,
        plan=plan,
        base_monthly_amount=Decimal('100'),
        effective_monthly_amount=Decimal('100'),
        billing_amount=billing_amount,
        start_date=date(2026, 1, 1),
        next_billing_date=next_billing_date,
        status=HostingSubscription.STATUS_ACTIVE,
    )


def _add_client_relations(client, count, *, prefix):
    projects = []
    for number in range(count):
        project = _project(
            client,
            name=f'{prefix} project {number}',
            status=Project.STATUS_ACTIVE,
        )
        projects.append(project)
        if number != count - 1:
            _subscription(
                project,
                plan=HostingSubscription.PLAN_QUARTERLY,
                next_billing_date=date(2026, 4, 1),
                billing_amount=Decimal('300'),
            )
    return projects


def _proposal(title, *, investment, percent=60, currency='COP', quarterly=10, semiannual=20, nine_month=40):
    return BusinessProposal.objects.create(
        title=title,
        client_name='Detail client',
        total_investment=investment,
        hosting_percent=percent,
        currency=currency,
        hosting_discount_quarterly=quarterly,
        hosting_discount_semiannual=semiannual,
        hosting_discount_nine_month=nine_month,
    )


def _add_phases(project, count, *, prefix):
    for number in range(1, count + 1):
        ProjectPhase.objects.create(
            project=project,
            business_proposal=_proposal(
                f'{prefix} proposal {number}',
                investment=Decimal('100.00'),
            ),
            order=number,
        )


def _detail_url(project, deliverable):
    return f'/api/accounts/projects/{project.id}/deliverables/{deliverable.id}/'


def _collection_document_type():
    document_type, _ = DocumentType.objects.get_or_create(
        code=COLLECTION_ACCOUNT,
        defaults={'name': 'Collection account'},
    )
    return document_type


def _populate_deliverable_collections(deliverable, uploader, count, *, start=1):
    document_type = _collection_document_type()
    folder = DeliverableClientFolder.objects.create(
        deliverable=deliverable,
        name='Evidence folder',
        created_by=uploader,
        order=1,
    )
    for number in range(start, start + count):
        DeliverableVersion.objects.create(
            deliverable=deliverable,
            file=f'deliverables/versions/version-{number}.pdf',
            version_number=number,
            uploaded_by=uploader,
        )
        DeliverableFile.objects.create(
            deliverable=deliverable,
            file=f'deliverables/attachments/attachment-{number}.pdf',
            title=f'Attachment {number}',
            category=Deliverable.CATEGORY_DOCUMENTS,
            uploaded_by=uploader,
        )
        DeliverableClientUpload.objects.create(
            deliverable=deliverable,
            folder=folder,
            file=f'deliverables/client_uploads/upload-{number}.pdf',
            title=f'Upload {number}',
            uploaded_by=uploader,
        )
        DataModelEntity.objects.create(
            deliverable=deliverable,
            name=f'Entity {number}',
            source_entity_name=f'entity-{number}',
        )
        Document.objects.create(
            document_type=document_type,
            project=deliverable.project,
            deliverable=deliverable,
            title=f'Collection account {number}',
            public_number=f'PA-{number:03d}',
            commercial_status=Document.CommercialStatus.ISSUED,
        )
    return folder


def _create_target_collection_accounts(deliverable, document_type):
    base = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
    oldest = Document.objects.create(
        document_type=document_type,
        project=deliverable.project,
        deliverable=deliverable,
        title='Oldest target account',
        public_number='PA-TARGET-00',
        commercial_status=Document.CommercialStatus.ISSUED,
    )
    Document.objects.filter(pk=oldest.pk).update(created_at=base)
    included = []
    for number in range(1, 51):
        document = Document.objects.create(
            document_type=document_type,
            project=deliverable.project,
            deliverable=deliverable,
            title=f'Target account {number}',
            public_number=f'PA-TARGET-{number:02d}',
            commercial_status=Document.CommercialStatus.ISSUED,
        )
        Document.objects.filter(pk=document.pk).update(created_at=base + timedelta(minutes=number))
        included.append(document)
    return oldest, included


def test_client_detail_query_budget_stays_constant_with_fifty_projects():
    """Fails if client detail reads subscriptions or aggregates once per project."""
    admin = _user('client-detail-admin@example.com', UserProfile.ROLE_ADMIN)
    client = _user('client-detail-owner@example.com', UserProfile.ROLE_CLIENT)
    first_project = _project(client, 'First client project', status=Project.STATUS_ACTIVE)
    _subscription(
        first_project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        next_billing_date=date(2026, 4, 1),
        billing_amount=Decimal('300'),
    )
    api_client = _jwt_client(admin)
    url = f'/api/accounts/clients/{client.id}/'

    with CaptureQueriesContext(connection) as one_queries:
        one_response = api_client.get(url)

    _add_client_relations(client, 49, prefix='Expanded client')
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = api_client.get(url)

    assert one_response.status_code == 200
    assert fifty_response.status_code == 200
    assert fifty_response.json()['hosting_plan'] == HostingSubscription.PLAN_QUARTERLY
    assert len(one_queries) == len(fifty_queries) <= MAX_CLIENT_DETAIL_QUERIES


def _client_summary_response():
    admin = _user('client-summary-admin@example.com', UserProfile.ROLE_ADMIN)
    client = _user('client-summary-owner@example.com', UserProfile.ROLE_CLIENT)
    active = _project(client, 'Active', status=Project.STATUS_ACTIVE)
    suspended = _project(client, 'Suspended', status=Project.STATUS_SUSPENDED)
    archived = _project(client, 'Archived', status=Project.STATUS_ARCHIVED)
    _subscription(
        active,
        plan=HostingSubscription.PLAN_QUARTERLY,
        next_billing_date=None,
        billing_amount=Decimal('275'),
    )
    _subscription(
        suspended,
        plan=HostingSubscription.PLAN_SEMIANNUAL,
        next_billing_date=date(2026, 4, 1),
        billing_amount=Decimal('600'),
    )
    Project.objects.filter(pk__in=[active.pk, suspended.pk]).update(
        updated_at=datetime(2026, 2, 1, 10, 0, tzinfo=datetime_timezone.utc),
    )
    Project.objects.filter(pk=archived.pk).update(
        updated_at=datetime(2026, 2, 2, 10, 0, tzinfo=datetime_timezone.utc),
    )
    User.objects.filter(pk=client.pk).update(
        last_login=datetime(2026, 2, 3, 10, 0, tzinfo=datetime_timezone.utc),
    )

    return _jwt_client(admin).get(f'/api/accounts/clients/{client.id}/')


def test_client_detail_uses_first_active_subscription():
    """Fails if client detail ignores the earliest active subscription."""
    response = _client_summary_response()

    assert response.status_code == 200
    assert (
        response.json()['hosting_plan'],
        response.json()['hosting_renewal_at'],
        response.json()['hosting_renewal_value'],
    ) == (
        HostingSubscription.PLAN_QUARTERLY,
        None,
        275.0,
    )


def test_client_detail_counts_active_projects():
    """Fails if client detail includes non-active projects in the active count."""
    response = _client_summary_response()

    assert response.status_code == 200
    assert response.json()['active_projects_count'] == 1


def test_client_detail_excludes_archived_projects_from_total():
    """Fails if client detail counts archived projects in the total."""
    response = _client_summary_response()

    assert response.status_code == 200
    assert response.json()['total_projects_count'] == 2


def test_client_detail_prefers_login_for_latest_activity():
    """Fails if client detail changes the project-versus-login activity precedence."""
    response = _client_summary_response()

    assert response.status_code == 200
    assert response.json()['last_activity_at'] == '2026-02-03T10:00:00Z'


def test_client_detail_reports_completed_login():
    """Fails if client detail loses the login-history boolean."""
    response = _client_summary_response()

    assert response.status_code == 200
    assert response.json()['has_logged_in_once'] is True


def test_client_detail_returns_null_hosting_fields_without_subscription():
    """Fails if annotated client detail invents hosting data when none exists."""
    admin = _user('client-empty-admin@example.com', UserProfile.ROLE_ADMIN)
    client = _user('client-empty-owner@example.com', UserProfile.ROLE_CLIENT)

    response = _jwt_client(admin).get(f'/api/accounts/clients/{client.id}/')

    assert response.status_code == 200
    assert {
        field: response.json()[field]
        for field in ('hosting_plan', 'hosting_renewal_at', 'hosting_renewal_value')
    } == {
        'hosting_plan': None,
        'hosting_renewal_at': None,
        'hosting_renewal_value': None,
    }


def test_project_detail_query_budget_stays_constant_with_fifty_phases():
    """Fails if project detail loads proposals or aggregates per phase."""
    admin = _user('project-budget-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('project-budget-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Project phase budget')
    _add_phases(project, 1, prefix='First')
    api_client = _jwt_client(admin)
    url = f'/api/accounts/projects/{project.id}/'

    with CaptureQueriesContext(connection) as one_queries:
        one_response = api_client.get(url)

    _add_phases(project, 49, prefix='Expanded')
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = api_client.get(url)

    assert one_response.status_code == 200
    assert fifty_response.status_code == 200
    assert fifty_response.json()['phases_total_amount'] == 5000.0
    assert len(one_queries) == len(fifty_queries) <= MAX_PROJECT_DETAIL_QUERIES


def test_project_detail_streams_phase_values_without_model_hydration():
    """Fails if the optimized phase summary instantiates phase or proposal models."""
    admin = _user('project-hydration-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('project-hydration-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Project hydration guard')
    _add_phases(project, 2, prefix='Hydration')
    phase_instances = []
    proposal_instances = []

    def remember_phase(sender, instance, **kwargs):
        phase_instances.append(instance)

    def remember_proposal(sender, instance, **kwargs):
        proposal_instances.append(instance)

    post_init.connect(remember_phase, sender=ProjectPhase, dispatch_uid='detail-budget-phases')
    post_init.connect(remember_proposal, sender=BusinessProposal, dispatch_uid='detail-budget-proposals')
    try:
        response = _jwt_client(admin).get(f'/api/accounts/projects/{project.id}/')
    finally:
        post_init.disconnect(sender=ProjectPhase, dispatch_uid='detail-budget-phases')
        post_init.disconnect(sender=BusinessProposal, dispatch_uid='detail-budget-proposals')

    assert response.status_code == 200
    assert phase_instances == []
    assert proposal_instances == []


def _project_financial_detail():
    admin = _user('project-tier-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('project-tier-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Project commercial tiers')
    first = _proposal(
        'Primary commercial proposal',
        investment=Decimal('1200.00'),
        percent=60,
        currency='USD',
        quarterly=10,
        semiannual=20,
        nine_month=40,
    )
    second = _proposal(
        'Later commercial proposal',
        investment=Decimal('600.00'),
        percent=50,
        currency='COP',
        quarterly=1,
        semiannual=2,
        nine_month=3,
    )
    ProjectPhase.objects.create(project=project, business_proposal=second, order=2)
    ProjectPhase.objects.create(project=project, business_proposal=first, order=1)

    response = _jwt_client(admin).get(f'/api/accounts/projects/{project.id}/')
    return response, first


def test_project_detail_uses_primary_phase_proposal():
    """Fails if project detail selects a later phase as its primary proposal."""
    response, first = _project_financial_detail()

    assert response.status_code == 200
    assert (response.json()['proposal_id'], response.json()['proposal_title']) == (
        first.id,
        'Primary commercial proposal',
    )


def test_project_detail_totals_all_phase_investment():
    """Fails if project detail omits a phase from the investment total."""
    response, _ = _project_financial_detail()

    assert response.status_code == 200
    assert response.json()['phases_total_amount'] == 1800.0


@pytest.mark.parametrize(
    ('frequency', 'expected'),
    [
        (
            'nine_month',
            {
                'frequency': 'nine_month', 'months': 9,
                'label': 'Cada 9 meses', 'badge': 'Máximo descuento',
                'discount_percent': 40, 'base_monthly': 85,
                'effective_monthly': 51, 'billing_amount': 459, 'currency': 'USD',
            },
        ),
        (
            'semiannual',
            {
                'frequency': 'semiannual', 'months': 6,
                'label': 'Semestral', 'badge': '20% dcto',
                'discount_percent': 20, 'base_monthly': 85,
                'effective_monthly': 68, 'billing_amount': 408, 'currency': 'USD',
            },
        ),
        (
            'quarterly',
            {
                'frequency': 'quarterly', 'months': 3,
                'label': 'Trimestral', 'badge': '10% dcto',
                'discount_percent': 10, 'base_monthly': 85,
                'effective_monthly': 77, 'billing_amount': 231, 'currency': 'USD',
            },
        ),
    ],
)
def test_project_detail_rounds_primary_phase_hosting_tier(frequency, expected):
    """Fails if a primary-phase discount changes a commercial tier amount."""
    response, _ = _project_financial_detail()
    tier = next(item for item in response.json()['hosting_tiers'] if item['frequency'] == frequency)

    assert response.status_code == 200
    assert tier == expected


def test_project_detail_uses_legacy_snapshot_without_phases():
    """Fails if the phase summary drops the legacy proposal or tier snapshot."""
    admin = _user('project-legacy-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('project-legacy-owner@example.com', UserProfile.ROLE_CLIENT)
    snapshot = [{'frequency': 'quarterly', 'billing_amount': 700, 'currency': 'COP'}]
    project = _project(owner, 'Project legacy fallback', hosting_tiers=snapshot)
    first_deliverable = Deliverable.objects.create(
        project=project,
        title='First legacy deliverable',
        category=Deliverable.CATEGORY_OTHER,
        uploaded_by=admin,
    )
    second_deliverable = Deliverable.objects.create(
        project=project,
        title='Second legacy deliverable',
        category=Deliverable.CATEGORY_OTHER,
        uploaded_by=admin,
    )
    second_proposal = _proposal('Second legacy proposal', investment=Decimal('200.00'))
    second_proposal.deliverable = second_deliverable
    second_proposal.save(update_fields=['deliverable'])
    first_proposal = _proposal('First legacy proposal', investment=Decimal('100.00'))
    first_proposal.deliverable = first_deliverable
    first_proposal.save(update_fields=['deliverable'])

    response = _jwt_client(admin).get(f'/api/accounts/projects/{project.id}/')

    assert response.status_code == 200
    assert {
        'proposal_id': response.json()['proposal_id'],
        'proposal_title': response.json()['proposal_title'],
        'hosting_tiers': response.json()['hosting_tiers'],
    } == {
        'proposal_id': first_proposal.id,
        'proposal_title': 'First legacy proposal',
        'hosting_tiers': snapshot,
    }


def test_project_detail_returns_empty_phase_values_without_legacy_proposal():
    """Fails if the optimized empty phase summary changes the no-proposal contract."""
    admin = _user('project-empty-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('project-empty-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Project without phases')

    response = _jwt_client(admin).get(f'/api/accounts/projects/{project.id}/')

    assert response.status_code == 200
    assert {
        field: response.json()[field]
        for field in ('proposal_id', 'proposal_title', 'phases_total_amount', 'hosting_tiers')
    } == {
        'proposal_id': None,
        'proposal_title': None,
        'phases_total_amount': 0.0,
        'hosting_tiers': [],
    }


def test_project_detail_masks_access_presence_from_owning_client():
    """Fails if the optimized access annotation leaks administrative secrets to clients."""
    admin = _user('project-secret-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('project-secret-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(
        owner,
        'Project secret mask',
        payment_milestones=[{'label': 'Private milestone'}],
        production_url='https://production.example.com',
        staging_url='https://staging.example.com',
        repository_url='https://github.com/example/private',
    )
    ProjectAdminAccess.objects.create(
        project=project,
        environment=ProjectAdminAccess.Environment.PRODUCTION,
        admin_password_encrypted=encrypt_secret('access-password'),
        updated_by=admin,
    )

    response = _jwt_client(owner).get(f'/api/accounts/projects/{project.id}/')

    assert response.status_code == 200
    assert {
        field: response.json()[field]
        for field in (
            'payment_milestones', 'production_url', 'staging_url',
            'repository_url', 'has_admin_password',
        )
    } == {
        'payment_milestones': [],
        'production_url': '',
        'staging_url': '',
        'repository_url': '',
        'has_admin_password': False,
    }


def _deliverable_nested_collection_detail():
    admin = _user('deliverable-detail-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('deliverable-detail-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Deliverable collection contract')
    deliverable = Deliverable.objects.create(
        project=project,
        title='Deliverable collection contract',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin,
    )
    folder = _populate_deliverable_collections(deliverable, admin, 1)
    DataModelEntity.objects.create(
        deliverable=deliverable,
        name='Archived entity',
        source_entity_name='archived-entity',
        is_archived=True,
    )

    response = _jwt_client(admin).get(_detail_url(project, deliverable))
    return response, folder


def test_deliverable_detail_shares_versions_with_count():
    """Fails if cached detail versions diverge from the reported version count."""
    response, _ = _deliverable_nested_collection_detail()

    assert response.status_code == 200
    assert response.json()['versions_count'] == len(response.json()['versions']) == 1


def test_deliverable_detail_serializes_attachment_files():
    """Fails if detail loses the attachment collection after optimization."""
    response, _ = _deliverable_nested_collection_detail()

    assert response.status_code == 200
    assert [item['title'] for item in response.json()['attachment_files']] == ['Attachment 1']


def test_deliverable_detail_serializes_client_folders():
    """Fails if detail loses client folders after optimization."""
    response, _ = _deliverable_nested_collection_detail()

    assert response.status_code == 200
    assert [item['name'] for item in response.json()['client_folders']] == ['Evidence folder']


def test_deliverable_detail_keeps_upload_folder_reference():
    """Fails if detail serializes an upload without its client-folder reference."""
    response, folder = _deliverable_nested_collection_detail()

    assert response.status_code == 200
    assert response.json()['client_uploads'][0]['folder'] == folder.id


def test_deliverable_detail_serializes_collection_accounts():
    """Fails if detail loses its scoped collection-account rows."""
    response, _ = _deliverable_nested_collection_detail()

    assert response.status_code == 200
    assert [item['public_number'] for item in response.json()['collection_accounts']] == ['PA-001']


def test_deliverable_detail_excludes_archived_data_model_entities():
    """Fails if detail exposes archived data-model entities."""
    response, _ = _deliverable_nested_collection_detail()

    assert response.status_code == 200
    assert [item['name'] for item in response.json()['data_model_entities']] == ['Entity 1']


def test_deliverable_detail_query_budget_stays_constant_with_fifty_rows_per_collection():
    """Fails if nested deliverable rows reintroduce lazy uploader or count queries."""
    admin = _user('deliverable-budget-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('deliverable-budget-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Deliverable collection budget')
    deliverable = Deliverable.objects.create(
        project=project,
        title='Deliverable collection budget',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin,
    )
    _populate_deliverable_collections(deliverable, admin, 1)
    api_client = _jwt_client(admin)
    url = _detail_url(project, deliverable)

    with CaptureQueriesContext(connection) as one_queries:
        one_response = api_client.get(url)

    _populate_deliverable_collections(deliverable, admin, 49, start=2)
    with CaptureQueriesContext(connection) as fifty_queries:
        fifty_response = api_client.get(url)

    assert one_response.status_code == 200
    assert fifty_response.status_code == 200
    assert len(fifty_response.json()['versions']) == 50
    assert len(one_queries) == len(fifty_queries) <= MAX_DELIVERABLE_DETAIL_QUERIES


def test_deliverable_detail_returns_empty_nested_collections():
    """Fails if the optimized detail cache changes empty collection payloads."""
    admin = _user('deliverable-empty-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('deliverable-empty-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Deliverable without collections')
    deliverable = Deliverable.objects.create(
        project=project,
        title='Deliverable without collections',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin,
    )

    response = _jwt_client(admin).get(_detail_url(project, deliverable))

    assert response.status_code == 200
    assert {
        field: response.json()[field]
        for field in (
            'versions', 'attachment_files', 'client_folders', 'client_uploads',
            'collection_accounts', 'data_model_entities',
        )
    } == {
        'versions': [],
        'attachment_files': [],
        'client_folders': [],
        'client_uploads': [],
        'collection_accounts': [],
        'data_model_entities': [],
    }


def test_deliverable_detail_defers_unserialized_document_columns():
    """Fails if collection-account detail hydrates document payload columns it does not return."""
    admin = _user('document-projection-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('document-projection-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Document projection project')
    deliverable = Deliverable.objects.create(
        project=project,
        title='Document projection deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin,
    )
    Document.objects.create(
        document_type=_collection_document_type(),
        project=project,
        deliverable=deliverable,
        title='Narrow document',
        public_number='PA-NARROW',
        commercial_status=Document.CommercialStatus.ISSUED,
        terms_and_conditions='large private document payload',
        metadata={'private': 'payload'},
    )
    deferred_columns = []

    def remember_document(sender, instance, **kwargs):
        deferred_columns.append(instance.get_deferred_fields())

    post_init.connect(remember_document, sender=Document, dispatch_uid='detail-budget-documents')
    try:
        response = _jwt_client(admin).get(_detail_url(project, deliverable))
    finally:
        post_init.disconnect(sender=Document, dispatch_uid='detail-budget-documents')

    assert response.status_code == 200
    assert len(deferred_columns) == 1
    assert {
        'content_json', 'content_markdown', 'metadata', 'terms_and_conditions',
    }.issubset(deferred_columns[0])


def test_deliverable_detail_limits_collection_accounts_to_target_scope():
    """Fails if deliverable detail widens collection-account scope or removes its limit."""
    admin = _user('deliverable-account-admin@example.com', UserProfile.ROLE_ADMIN)
    owner = _user('deliverable-account-owner@example.com', UserProfile.ROLE_CLIENT)
    project = _project(owner, 'Collection account target project')
    deliverable = Deliverable.objects.create(
        project=project,
        title='Target deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin,
    )
    other_deliverable = Deliverable.objects.create(
        project=project,
        title='Other deliverable',
        category=Deliverable.CATEGORY_DOCUMENTS,
        uploaded_by=admin,
    )
    other_project = _project(owner, 'Other collection project')
    document_type = _collection_document_type()
    other_type = DocumentType.objects.create(code='markdown-detail-budget', name='Markdown')
    _create_target_collection_accounts(deliverable, document_type)
    Document.objects.create(
        document_type=document_type,
        project=project,
        deliverable=other_deliverable,
        title='Other deliverable account',
        public_number='PA-OTHER-DELIVERABLE',
        commercial_status=Document.CommercialStatus.ISSUED,
    )
    Document.objects.create(
        document_type=document_type,
        project=other_project,
        deliverable=None,
        title='Other project account',
        public_number='PA-OTHER-PROJECT',
        commercial_status=Document.CommercialStatus.ISSUED,
    )
    Document.objects.create(
        document_type=other_type,
        project=project,
        deliverable=deliverable,
        title='Other type document',
        public_number='PA-OTHER-TYPE',
        commercial_status=Document.CommercialStatus.ISSUED,
    )

    response = _jwt_client(admin).get(_detail_url(project, deliverable))

    assert response.status_code == 200
    assert [item['public_number'] for item in response.json()['collection_accounts']] == [
        f'PA-TARGET-{number:02d}' for number in range(50, 0, -1)
    ]
