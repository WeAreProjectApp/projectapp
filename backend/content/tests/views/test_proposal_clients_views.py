"""End-to-end tests for the proposal-side client management endpoints.

Covers ``/api/proposals/client-profiles/`` (list, search, retrieve, create,
update, delete) plus the integration with proposal create/update via
``client_id``.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from freezegun import freeze_time
from accounts.models import (
    BugReport,
    ChangeRequest,
    Deliverable,
    HostingSubscription,
    Project,
    ProjectPhase,
    UserProfile,
)
from accounts.services import proposal_client_service
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from content.models import Document, DocumentFolder, HostingRecord
from content.models.business_proposal import BusinessProposal
from content.serializers.proposal_clients import ProposalClientSerializer

pytestmark = pytest.mark.django_db
User = get_user_model()


def _bulk_create_client_profiles(count, prefix):
    users = [
        User(
            username=f'{prefix}-{index}@example.com',
            email=f'{prefix}-{index}@example.com',
            is_active=False,
        )
        for index in range(count)
    ]
    User.objects.bulk_create(users)
    created_users = list(
        User.objects.filter(username__startswith=f'{prefix}-').order_by('id')
    )
    UserProfile.objects.bulk_create([
        UserProfile(user=user, role=UserProfile.ROLE_CLIENT)
        for user in created_users
    ])


def _create_nested_project_aggregates(profile):
    project = Project.objects.create(name='Client detail project', client=profile.user)
    deliverable = Deliverable.objects.create(
        project=project,
        title='Client detail deliverable',
        category=Deliverable.CATEGORY_OTHER,
        uploaded_by=profile.user,
    )
    proposal = BusinessProposal.objects.create(
        title='Client detail proposal',
        client=profile,
        client_name='Client detail',
        total_investment=Decimal('765432.10'),
        deliverable=deliverable,
    )
    ProjectPhase.objects.create(project=project, business_proposal=proposal, order=1)
    BugReport.objects.create(
        project=project,
        reported_by=profile.user,
        title='Client detail open bug',
        status=BugReport.STATUS_REPORTED,
    )
    ChangeRequest.objects.create(
        project=project,
        created_by=profile.user,
        title='Client detail pending change',
        status=ChangeRequest.STATUS_PENDING,
    )
    HostingSubscription.objects.create(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('41152.00'),
        effective_monthly_amount=Decimal('41152.00'),
        billing_amount=Decimal('123456.00'),
        status=HostingSubscription.STATUS_ACTIVE,
        start_date=date(2026, 10, 1),
        next_billing_date=date(2026, 11, 15),
    )
    return project, proposal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def real_client_with_proposal(db):
    """Active client with one proposal — should never be considered orphan."""
    profile = proposal_client_service.get_or_create_client_for_proposal(
        name='Activa Mendoza', email='activa@gmail.com', company='ActivaCo',
    )
    BusinessProposal.objects.create(
        title='Active proposal', client_name='Activa Mendoza',
        client_email='activa@gmail.com', client=profile, total_investment=1000,
    )
    return profile


@pytest.fixture
def orphan_client(db):
    """Client with zero proposals and zero projects — eligible for delete."""
    return proposal_client_service.get_or_create_client_for_proposal(
        name='Huerfano Solo', email='huerfano@gmail.com',
    )


@pytest.fixture
def diagnostic_only_client(db):
    """Client whose only linked object is a WebAppDiagnostic — NOT an orphan."""
    profile = proposal_client_service.get_or_create_client_for_proposal(
        name='Diagnostico Cliente', email='diag@gmail.com',
    )
    from content.models.web_app_diagnostic import WebAppDiagnostic
    WebAppDiagnostic.objects.create(client=profile, status='draft')
    return profile


@pytest.fixture
def placeholder_client(db):
    """Client created with empty email — placeholder, no proposals."""
    return proposal_client_service.get_or_create_client_for_proposal(
        name='Placeholder Client', email='',
    )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListProposalClients:
    def test_returns_all_clients_for_admin(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(reverse('list-proposal-clients'))
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_search_filters_by_company_name_icontains(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'search': 'activa'},
        )
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['id'] == real_client_with_proposal.pk

    def test_orphans_filter_true_excludes_clients_with_proposals(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': 'true'},
        )
        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert orphan_client.pk in ids
        assert real_client_with_proposal.pk not in ids

    def test_orphans_filter_false_excludes_orphan_clients(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': 'false'},
        )
        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert real_client_with_proposal.pk in ids
        assert orphan_client.pk not in ids

    def test_orphans_filter_true_excludes_client_with_only_diagnostic(
        self, admin_client, orphan_client, diagnostic_only_client,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': 'true'},
        )
        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert orphan_client.pk in ids
        assert diagnostic_only_client.pk not in ids

    def test_orphans_filter_false_includes_client_with_only_diagnostic(
        self, admin_client, orphan_client, diagnostic_only_client,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': 'false'},
        )
        assert response.status_code == 200
        rows = {c['id']: c for c in response.data}
        assert diagnostic_only_client.pk in rows
        assert rows[diagnostic_only_client.pk]['is_orphan'] is False
        assert orphan_client.pk not in rows

    def test_unauthenticated_user_is_rejected(self, api_client):
        response = api_client.get(reverse('list-proposal-clients'))
        assert response.status_code in (401, 403)

    @pytest.mark.parametrize('orphans_value', ['1', 'yes', 'on'])
    def test_orphans_filter_accepts_truthy_variants(
        self, admin_client, real_client_with_proposal, orphan_client, orphans_value,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': orphans_value},
        )

        assert response.status_code == 200
        ids = [client['id'] for client in response.data]
        assert orphan_client.pk in ids
        assert real_client_with_proposal.pk not in ids

    def test_invalid_limit_falls_back_to_default_100(self, admin_client):
        prefix = f'limit-default-{uuid4().hex}'
        _bulk_create_client_profiles(101, prefix)

        response = admin_client.get(
            reverse('list-proposal-clients'), {'limit': 'not-a-number'},
        )

        assert response.status_code == 200
        assert len(response.data) == 100

    def test_limit_is_capped_at_500(self, admin_client):
        prefix = f'limit-cap-{uuid4().hex}'
        _bulk_create_client_profiles(505, prefix)

        response = admin_client.get(
            reverse('list-proposal-clients'), {'limit': 999},
        )

        assert response.status_code == 200
        assert len(response.data) == 500


class TestWithoutProjectsFilter:
    """``without_projects`` feeds the Projects module indicator: clients the
    operator still has to register a project for. Weaker than ``orphans`` —
    a client with proposals but no project must appear here."""

    def test_without_projects_true_returns_only_uncovered_clients(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        Project.objects.create(
            name='Cubierto', client=real_client_with_proposal.user,
        )

        response = admin_client.get(
            reverse('list-proposal-clients'), {'without_projects': 'true'},
        )

        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert orphan_client.pk in ids
        assert real_client_with_proposal.pk not in ids

    def test_a_client_with_proposals_but_no_project_counts_as_uncovered(
        self, admin_client, real_client_with_proposal,
    ):
        response = admin_client.get(
            reverse('list-proposal-clients'), {'without_projects': 'true'},
        )

        assert response.status_code == 200
        assert [c['id'] for c in response.data] == [real_client_with_proposal.pk]

    def test_without_projects_false_returns_the_covered_inverse(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        Project.objects.create(
            name='Cubierto', client=real_client_with_proposal.user,
        )

        response = admin_client.get(
            reverse('list-proposal-clients'), {'without_projects': 'false'},
        )

        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert ids == [real_client_with_proposal.pk]
        assert orphan_client.pk not in ids


# ---------------------------------------------------------------------------
# Preset annotations (hosting vigente / proyecto activo)
# ---------------------------------------------------------------------------

def _row_for(response, profile):
    return next(row for row in response.data if row['id'] == profile.pk)


class TestPresetAnnotations:
    """The two aggregates behind the 'Con hosting cobrado' / 'Con proyecto
    activo' predefined filters in /panel/clients."""

    def test_active_hostings_count_ignores_the_inactive_ones(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Hosting SAS')
        HostingRecord.objects.create(
            client=profile, client_name='Hosting SAS - Vigente',
            monthly_value=Decimal('90000.00'), is_active=True,
        )
        HostingRecord.objects.create(
            client=profile, client_name='Hosting SAS - Caido',
            monthly_value=Decimal('50000.00'), is_active=False,
        )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['hostings_count'] == 2
        assert row['active_hostings_count'] == 1

    def test_client_without_hostings_reports_zero(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Sin Hosting SAS')

        response = admin_client.get(reverse('list-proposal-clients'))

        assert _row_for(response, profile)['active_hostings_count'] == 0

    def test_active_projects_count_ignores_the_archived_ones(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Proyectos SAS')
        Project.objects.create(
            name='En curso', client=profile.user, status=Project.STATUS_ACTIVE,
        )
        Project.objects.create(
            name='Guardado', client=profile.user, status=Project.STATUS_ARCHIVED,
        )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['projects_count'] == 2
        assert row['active_projects_count'] == 1

    def test_hosting_of_one_client_does_not_leak_into_another(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile(company='Dueno SAS')
        stranger = make_client_profile(company='Ajeno SAS')
        HostingRecord.objects.create(
            client=owner, client_name='Dueno SAS - Web',
            monthly_value=Decimal('70000.00'), is_active=True,
        )

        response = admin_client.get(reverse('list-proposal-clients'))

        assert _row_for(response, owner)['active_hostings_count'] == 1
        assert _row_for(response, stranger)['active_hostings_count'] == 0

    @freeze_time('2026-08-13 12:00:00')
    def test_archived_client_stays_out_even_holding_a_live_hosting(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Pausado SAS')
        HostingRecord.objects.create(
            client=profile, client_name='Pausado SAS - Web',
            monthly_value=Decimal('60000.00'), is_active=True,
        )
        profile.archived_at = timezone.now()
        profile.save(update_fields=['archived_at'])

        response = admin_client.get(reverse('list-proposal-clients'))

        assert profile.pk not in {row['id'] for row in response.data}

    def test_serializer_falls_back_when_the_queryset_is_not_annotated(
        self, make_client_profile,
    ):
        profile = make_client_profile(company='Sin Anotar SAS')
        HostingRecord.objects.create(
            client=profile, client_name='Sin Anotar SAS - Web',
            monthly_value=Decimal('80000.00'), is_active=True,
        )
        Project.objects.create(
            name='Vivo', client=profile.user, status=Project.STATUS_ACTIVE,
        )

        raw = UserProfile.objects.get(pk=profile.pk)
        data = ProposalClientSerializer(raw).data

        assert data['active_hostings_count'] == 1
        assert data['active_projects_count'] == 1


class TestDocumentsModuleAnnotations:
    """Los agregados detrás del módulo Documentos de /panel/clients."""

    def test_folders_count_reads_the_folders_of_the_client(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Carpetas SAS')
        DocumentFolder.objects.create(name='Kore', client_user=profile.user)
        DocumentFolder.objects.create(name='Kore - Diseño', client_user=profile.user)
        DocumentFolder.objects.create(name='De nadie')

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['document_folders_count'] == 2

    def test_folders_count_excludes_the_archived_ones(
        self, admin_client, make_client_profile,
    ):
        """Espeja a documents_count: archivar es el eje de visibilidad del módulo."""
        profile = make_client_profile(company='Archivo SAS')
        DocumentFolder.objects.create(name='Viva', client_user=profile.user)
        DocumentFolder.objects.create(
            name='Guardada', client_user=profile.user, is_archived=True,
        )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['document_folders_count'] == 1

    def test_folders_of_one_client_do_not_leak_into_another(
        self, admin_client, make_client_profile,
    ):
        mine = make_client_profile(company='Mío SAS')
        other = make_client_profile(company='Ajeno SAS')
        DocumentFolder.objects.create(name='Ajena', client_user=other.user)

        response = admin_client.get(reverse('list-proposal-clients'))

        assert _row_for(response, mine)['document_folders_count'] == 0
        assert _row_for(response, other)['document_folders_count'] == 1

    def test_documents_count_excludes_the_archived_ones(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Docs SAS')
        Document.objects.create(title='Contrato', client_user=profile.user)
        Document.objects.create(
            title='Acta vieja', client_user=profile.user, is_archived=True,
        )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['documents_count'] == 1

    def test_documents_no_project_count_reads_the_half_linked(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Medio SAS')
        project = Project.objects.create(name='Kore', client=profile.user)
        Document.objects.create(
            title='Con proyecto', client_user=profile.user, project=project,
        )
        Document.objects.create(title='Sin proyecto', client_user=profile.user)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['documents_count'] == 2
        assert row['documents_no_project_count'] == 1

    def test_last_document_at_is_the_newest_active_one(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Fechas SAS')
        with freeze_time('2026-08-01 10:00:00'):
            Document.objects.create(title='Viejo', client_user=profile.user)
        with freeze_time('2026-08-10 10:00:00'):
            Document.objects.create(title='Nuevo', client_user=profile.user)
        with freeze_time('2026-08-14 10:00:00'):
            Document.objects.create(
                title='Archivado después', client_user=profile.user,
                is_archived=True,
            )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert str(row['last_document_at']).startswith('2026-08-10')

    def test_documents_of_one_client_do_not_leak_into_another(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile(company='Dueno Docs SAS')
        stranger = make_client_profile(company='Ajeno Docs SAS')
        Document.objects.create(title='Contrato', client_user=owner.user)

        response = admin_client.get(reverse('list-proposal-clients'))

        assert _row_for(response, owner)['documents_count'] == 1
        assert _row_for(response, stranger)['documents_count'] == 0

    def test_detail_nests_the_recent_documents_with_total(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Ficha SAS')
        project = Project.objects.create(name='Kore', client=profile.user)
        for index in range(6):
            Document.objects.create(
                title=f'Doc {index}', client_user=profile.user,
                project=project if index == 5 else None,
            )

        response = admin_client.get(
            reverse('retrieve-proposal-client', args=[profile.pk]),
        )

        assert response.status_code == 200
        assert response.data['documents_total'] == 6
        assert len(response.data['documents']) == 5
        newest = response.data['documents'][0]
        assert newest['title'] == 'Doc 5'
        assert newest['project_name'] == 'Kore'

    def test_serializer_falls_back_without_annotations(self, make_client_profile):
        profile = make_client_profile(company='Fallback Docs SAS')
        Document.objects.create(title='Suelto', client_user=profile.user)
        DocumentFolder.objects.create(name='Suya', client_user=profile.user)

        raw = UserProfile.objects.get(pk=profile.pk)
        data = ProposalClientSerializer(raw).data

        assert data['documents_count'] == 1
        assert data['documents_no_project_count'] == 1
        assert data['document_folders_count'] == 1


# ---------------------------------------------------------------------------
# Search (autocomplete)
# ---------------------------------------------------------------------------

class TestSearchProposalClients:
    def test_search_matches_email_substring(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(
            reverse('search-proposal-clients'), {'q': 'huerfano'},
        )
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['id'] == orphan_client.pk

    def test_empty_query_returns_all_clients_capped(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(reverse('search-proposal-clients'), {'q': ''})
        assert response.status_code == 200
        assert len(response.data) == 2

    def test_empty_query_orders_clients_by_display_name(
        self, admin_client, make_client_profile,
    ):
        zulu = make_client_profile(first_name='Zoé', last_name='Zulu')
        alpha = make_client_profile(first_name='Amanda', last_name='Alba')

        response = admin_client.get(reverse('search-proposal-clients'), {'q': ''})

        assert [row['id'] for row in response.data] == [alpha.pk, zulu.pk]

    def test_search_orders_clients_by_display_name_descending(
        self, admin_client, make_client_profile,
    ):
        zulu = make_client_profile(first_name='Zoé', last_name='Zulu')
        alpha = make_client_profile(first_name='Amanda', last_name='Alba')

        response = admin_client.get(
            reverse('search-proposal-clients'),
            {'q': '', 'order': '-name'},
        )

        assert [row['id'] for row in response.data] == [zulu.pk, alpha.pk]

    def test_search_uses_name_ascending_for_unknown_order(
        self, admin_client, make_client_profile,
    ):
        zulu = make_client_profile(first_name='Zoé', last_name='Zulu')
        alpha = make_client_profile(first_name='Amanda', last_name='Alba')

        response = admin_client.get(
            reverse('search-proposal-clients'),
            {'q': '', 'order': 'recent'},
        )

        assert [row['id'] for row in response.data] == [alpha.pk, zulu.pk]

    def test_search_returns_the_requested_result_page(
        self, admin_client, make_client_profile,
    ):
        make_client_profile(first_name='Amanda', last_name='Alba')
        second = make_client_profile(first_name='Beatriz', last_name='Bravo')
        third = make_client_profile(first_name='Carolina', last_name='Cano')

        response = admin_client.get(
            reverse('search-proposal-clients'),
            {'q': '', 'limit': 2, 'offset': 1},
        )

        assert [row['id'] for row in response.data] == [second.pk, third.pk]

    def test_search_exposes_the_filtered_total(
        self, admin_client, make_client_profile,
    ):
        make_client_profile(first_name='Amanda', last_name='Alba')
        make_client_profile(first_name='Beatriz', last_name='Bravo')
        make_client_profile(first_name='Carolina', last_name='Cano')

        response = admin_client.get(
            reverse('search-proposal-clients'),
            {'q': 'a', 'limit': 1},
        )

        assert response.headers['X-Total-Count'] == '3'

    @pytest.mark.parametrize(
        ('query', 'first_name', 'last_name', 'company_name'),
        [
            ('marcela', 'Marcela', 'Lopez', ''),
            ('lopez', 'Marcela', 'Lopez', ''),
            ('spectra', 'Marcela', 'Lopez', 'Spectra Labs'),
        ],
    )
    def test_search_matches_name_and_company_fields(
        self, admin_client, query, first_name, last_name, company_name,
    ):
        identity = uuid4().hex
        user = User.objects.create_user(
            username=f'{identity}@example.com',
            email=f'{identity}@example.com',
            password='pass12345',
            first_name=first_name,
            last_name=last_name,
        )
        profile = UserProfile.objects.create(
            user=user,
            role=UserProfile.ROLE_CLIENT,
            company_name=company_name,
        )

        response = admin_client.get(
            reverse('search-proposal-clients'), {'q': query},
        )

        assert response.status_code == 200
        assert response.data[0]['id'] == profile.pk

    def test_search_returns_the_complete_billing_profile(
        self, admin_client, make_client_profile,
    ):
        """Fails if the client picker loses billing data before a cuenta de cobro edit."""
        profile = make_client_profile(
            first_name='Laura',
            last_name='Ramírez',
            email='picker-laura@example.com',
            cedula='1049654583',
            address='Carrera 7 # 72-41, Bogotá',
            billing_code='LAURARAM',
        )

        response = admin_client.get(
            reverse('search-proposal-clients'), {'q': 'picker-laura'},
        )

        assert response.status_code == 200
        row = response.data[0]
        assert row['id'] == profile.pk
        assert row['billing_code'] == 'LAURARAM'
        assert row['billing_customer'] == {
            'name': 'Laura Ramírez',
            'email': 'picker-laura@example.com',
            'identification': '1049654583',
            'identification_type': 'CC',
            'contact_name': 'Laura Ramírez',
            'address': 'Carrera 7 # 72-41, Bogotá',
        }


# ---------------------------------------------------------------------------
# Retrieve detail
# ---------------------------------------------------------------------------

class TestRetrieveProposalClient:
    def test_detail_includes_nested_project_aggregates(self, admin_client, make_client_profile):
        """Fails if client detail drops project aggregates used by the panel."""
        profile = make_client_profile(company='Aggregate Co')
        project, proposal = _create_nested_project_aggregates(profile)

        response = admin_client.get(
            reverse('retrieve-proposal-client', args=[profile.pk]),
        )

        assert response.status_code == 200
        row = next(item for item in response.json()['projects'] if item['id'] == project.pk)
        assert {
            'proposal_id': row['proposal_id'],
            'proposal_title': row['proposal_title'],
            'bugs_open_count': row['bugs_open_count'],
            'changes_pending_count': row['changes_pending_count'],
            'phases_total_amount': Decimal(str(row['phases_total_amount'])),
            'next_hosting_payment': {
                'date': row['next_hosting_payment']['date'],
                'amount': Decimal(str(row['next_hosting_payment']['amount'])),
                'plan': row['next_hosting_payment']['plan'],
            },
        } == {
            'proposal_id': proposal.pk,
            'proposal_title': 'Client detail proposal',
            'bugs_open_count': 1,
            'changes_pending_count': 1,
            'phases_total_amount': Decimal('765432.10'),
            'next_hosting_payment': {
                'date': '2026-11-15',
                'amount': Decimal('123456.00'),
                'plan': HostingSubscription.PLAN_QUARTERLY,
            },
        }

    def test_detail_includes_nested_proposals(
        self, admin_client, real_client_with_proposal,
    ):
        response = admin_client.get(
            reverse('retrieve-proposal-client', args=[real_client_with_proposal.pk]),
        )
        assert response.status_code == 200
        assert response.data['id'] == real_client_with_proposal.pk
        assert 'proposals' in response.data
        assert len(response.data['proposals']) == 1
        assert response.data['proposals'][0]['title'] == 'Active proposal'

    def test_returns_404_for_unknown_client(self, admin_client):
        response = admin_client.get(reverse('retrieve-proposal-client', args=[999999]))
        assert response.status_code == 404
        assert response.data['error'] == 'client_not_found'

    def test_detail_orders_nested_proposals_by_created_at_desc(
        self, admin_client, real_client_with_proposal,
    ):
        BusinessProposal.objects.create(
            title='Newest proposal',
            client=real_client_with_proposal,
            client_name='Activa Mendoza',
            client_email='activa@gmail.com',
            total_investment=1200,
        )

        response = admin_client.get(
            reverse('retrieve-proposal-client', args=[real_client_with_proposal.pk]),
        )

        assert response.status_code == 200
        assert response.data['proposals'][0]['title'] == 'Newest proposal'

    def test_nested_income_queries_do_not_scale_with_rows(
        self, admin_client, make_client_profile, make_income,
    ):
        """The nested incomes reuse the list annotations + select_related;
        without them the serializer falls back to ~3 queries PER row."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        profile = make_client_profile(company='Vastago SAS')
        make_income(concept='Cuota 1', client=profile)
        url = reverse('retrieve-proposal-client', args=[profile.pk])

        admin_client.get(url)  # warm caches (content types, auth)
        with CaptureQueriesContext(connection) as baseline:
            assert admin_client.get(url).status_code == 200

        for n in range(2, 8):
            make_income(concept=f'Cuota {n}', client=profile)
        with CaptureQueriesContext(connection) as grown:
            response = admin_client.get(url)

        assert response.status_code == 200
        assert len(response.data['incomes']) == 7
        assert len(grown) == len(baseline)


# ---------------------------------------------------------------------------
# Create (standalone)
# ---------------------------------------------------------------------------

class TestCreateProposalClient:
    def test_create_with_email_returns_persisted_profile(self, admin_client):
        response = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'New Standalone', 'email': 'standalone@gmail.com', 'company': 'StandCo'},
            format='json',
        )
        assert response.status_code == 201
        assert response.data['email'] == 'standalone@gmail.com'
        assert response.data['company'] == 'StandCo'
        assert response.data['is_email_placeholder'] is False
        assert UserProfile.objects.filter(pk=response.data['id']).exists()

    def test_create_without_email_generates_placeholder(self, admin_client):
        response = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'No Email Person'},
            format='json',
        )
        assert response.status_code == 201
        assert response.data['is_email_placeholder'] is True
        assert response.data['email'].endswith('@temp.example.com')

    def test_create_persists_the_billing_identity(self, admin_client):
        # Parity with the edit form: the pair used to be dropped in silence, so
        # a client had to be created and then immediately edited.
        response = admin_client.post(
            reverse('create-proposal-client'),
            {
                'name': 'G&M', 'email': 'gym@example.com',
                'nit': '901234567-1', 'billing_code': 'g&m',
            },
            format='json',
        )

        assert response.status_code == 201
        profile = UserProfile.objects.get(pk=response.data['id'])
        assert profile.nit == '901234567-1'
        assert profile.billing_code == 'G&M'

    def test_create_returns_the_canonical_billing_customer(self, admin_client):
        """Fails if a created client's billing projection loses its C.C. or address."""
        request_data = {
            'name': 'Laura Ramírez',
            'email': 'laura.ramirez@example.com',
            'cedula': '1049654583',
            'address': 'Carrera 7 # 72-41, Bogotá',
        }

        response = admin_client.post(
            reverse('create-proposal-client'), request_data, format='json',
        )

        assert response.status_code == 201
        profile = UserProfile.objects.get(pk=response.data['id'])
        assert profile.cedula == '1049654583'
        assert profile.address == 'Carrera 7 # 72-41, Bogotá'
        assert response.data['billing_customer'] == {
            'name': 'Laura Ramírez',
            'email': 'laura.ramirez@example.com',
            'identification': '1049654583',
            'identification_type': 'CC',
            'contact_name': 'Laura Ramírez',
            'address': 'Carrera 7 # 72-41, Bogotá',
        }

    def test_create_rejects_an_address_longer_than_the_billing_limit(
        self, admin_client,
    ):
        """Fails if an overlong address reaches a profile after API validation rejects it."""
        request_data = {
            'name': 'Dirección Muy Larga',
            'email': 'direccion-larga@example.com',
            'address': 'A' * 513,
        }

        response = admin_client.post(
            reverse('create-proposal-client'), request_data, format='json',
        )

        assert response.status_code == 400
        assert 'address' in response.data
        assert not UserProfile.objects.filter(
            user__email='direccion-larga@example.com',
        ).exists()

    def test_create_without_a_code_stores_null_not_blank(self, admin_client):
        # `billing_code` is unique, so a second '' would hit the constraint.
        first = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'Sin Codigo Uno', 'email': 'uno@example.com'},
            format='json',
        )
        second = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'Sin Codigo Dos', 'email': 'dos@example.com'},
            format='json',
        )

        assert (first.status_code, second.status_code) == (201, 201)
        assert UserProfile.objects.get(pk=first.data['id']).billing_code is None
        assert UserProfile.objects.get(pk=second.data['id']).billing_code is None

    def test_create_rejects_a_code_that_would_break_the_document_chain(
        self, admin_client,
    ):
        response = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'Barra', 'email': 'barra@example.com', 'billing_code': 'G/M'},
            format='json',
        )

        assert response.status_code == 400
        assert response.data['error'] == 'invalid_billing_code'
        assert not UserProfile.objects.filter(user__email='barra@example.com').exists()

    def test_create_rejects_a_code_another_client_already_holds(self, admin_client):
        admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'Primero', 'email': 'primero@example.com', 'billing_code': 'G&M'},
            format='json',
        )

        response = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'Segundo', 'email': 'segundo@example.com', 'billing_code': 'G&M'},
            format='json',
        )

        # A clean 400, not the IntegrityError the unique column would raise.
        assert response.status_code == 400
        assert response.data['error'] == 'billing_code_taken'

    def test_create_rejects_completely_empty_payload(self, admin_client):
        response = admin_client.post(
            reverse('create-proposal-client'), {}, format='json',
        )
        assert response.status_code == 400
        assert response.data['error'] == 'name_or_email_required'

    @patch('content.views.proposal_clients.proposal_client_service.get_or_create_client_for_proposal')
    def test_create_returns_service_validation_error_payload(self, mock_get_or_create, admin_client):
        mock_get_or_create.side_effect = ValueError('Email already used by another client.')

        response = admin_client.post(
            reverse('create-proposal-client'),
            {'name': 'Conflicted', 'email': 'conflict@example.com'},
            format='json',
        )

        assert response.status_code == 400
        assert response.data['error'] == 'invalid_client_data'
        assert response.data['message'] == 'Email already used by another client.'


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdateProposalClient:
    def test_update_cascades_snapshot_to_linked_proposals(
        self, admin_client, real_client_with_proposal,
    ):
        response = admin_client.patch(
            reverse('update-proposal-client', args=[real_client_with_proposal.pk]),
            {'phone': '+57 311 9999'},
            format='json',
        )
        assert response.status_code == 200
        proposal = real_client_with_proposal.proposals.first()
        proposal.refresh_from_db()
        assert proposal.client_phone == '+57 311 9999'

    def test_update_returns_existing_representation_for_empty_payload(
        self, admin_client, real_client_with_proposal,
    ):
        response = admin_client.patch(
            reverse('update-proposal-client', args=[real_client_with_proposal.pk]),
            {},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['id'] == real_client_with_proposal.pk
        assert response.data['phone'] == real_client_with_proposal.phone

    def test_update_refreshes_the_canonical_billing_customer(
        self, admin_client, real_client_with_proposal,
    ):
        """Fails if editing a client leaves its next cuenta de cobro with old details."""
        request_data = {
            'cedula': '1049654583',
            'address': 'Avenida 19 # 103-22, Bogotá',
        }

        response = admin_client.patch(
            reverse('update-proposal-client', args=[real_client_with_proposal.pk]),
            request_data,
            format='json',
        )

        assert response.status_code == 200
        real_client_with_proposal.refresh_from_db()
        assert real_client_with_proposal.cedula == '1049654583'
        assert real_client_with_proposal.address == 'Avenida 19 # 103-22, Bogotá'
        assert response.data['billing_customer'] == {
            'name': 'Activa Mendoza',
            'email': 'activa@gmail.com',
            'identification': '1049654583',
            'identification_type': 'CC',
            'contact_name': 'Activa Mendoza',
            'address': 'Avenida 19 # 103-22, Bogotá',
        }

    def test_update_keeps_billing_identity_when_the_new_email_conflicts(
        self, admin_client, real_client_with_proposal,
    ):
        """Fails if a rejected email change partially saves the new billing identity."""
        User.objects.create_user(
            username='ocupado@example.com',
            email='ocupado@example.com',
            password='pass12345',
        )
        request_data = {
            'email': 'ocupado@example.com',
            'cedula': '1049654583',
            'address': 'Avenida 19 # 103-22, Bogotá',
        }

        response = admin_client.patch(
            reverse('update-proposal-client', args=[real_client_with_proposal.pk]),
            request_data,
            format='json',
        )

        assert response.status_code == 400
        assert response.data['error'] == 'update_conflict'
        real_client_with_proposal.refresh_from_db()
        assert real_client_with_proposal.cedula == ''
        assert real_client_with_proposal.address == ''

    @patch('content.views.proposal_clients.proposal_client_service.update_client_profile')
    def test_update_returns_conflict_payload_when_service_rejects_change(
        self, mock_update_client_profile, admin_client, real_client_with_proposal,
    ):
        mock_update_client_profile.side_effect = ValueError('Otro usuario ya está usando el email.')

        response = admin_client.patch(
            reverse('update-proposal-client', args=[real_client_with_proposal.pk]),
            {'email': 'used@example.com'},
            format='json',
        )

        assert response.status_code == 400
        assert response.data['error'] == 'update_conflict'

    def test_update_returns_404_for_unknown_client(self, admin_client):
        response = admin_client.patch(
            reverse('update-proposal-client', args=[999999]),
            {'phone': '+57 300 0000'},
            format='json',
        )

        assert response.status_code == 404
        assert response.data['error'] == 'client_not_found'


# ---------------------------------------------------------------------------
# Archived clients
# ---------------------------------------------------------------------------

class TestArchivedClients:
    @freeze_time('2026-01-15 12:00:00')
    def test_default_list_excludes_archived_client(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        from django.utils import timezone
        orphan_client.archived_at = timezone.now()
        orphan_client.save(update_fields=['archived_at'])

        response = admin_client.get(reverse('list-proposal-clients'))

        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert real_client_with_proposal.pk in ids
        assert orphan_client.pk not in ids

    @freeze_time('2026-01-15 12:00:00')
    def test_archived_true_returns_only_archived_clients(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        from django.utils import timezone
        orphan_client.archived_at = timezone.now()
        orphan_client.save(update_fields=['archived_at'])

        response = admin_client.get(
            reverse('list-proposal-clients'), {'archived': 'true'},
        )

        assert response.status_code == 200
        ids = [c['id'] for c in response.data]
        assert ids == [orphan_client.pk]
        assert response.data[0]['is_archived'] is True

    @freeze_time('2026-01-15 12:00:00')
    def test_the_pre_rename_inactive_spelling_still_filters(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        # The panel shipped with ?inactive=1 before the word became
        # "archivado". A bookmarked URL or a saved tab that still says
        # ``inactive`` must not silently fall back to the ACTIVE list, which
        # is what a dropped param would do here.
        from django.utils import timezone
        orphan_client.archived_at = timezone.now()
        orphan_client.save(update_fields=['archived_at'])

        response = admin_client.get(
            reverse('list-proposal-clients'), {'inactive': 'true'},
        )

        assert response.status_code == 200
        assert [c['id'] for c in response.data] == [orphan_client.pk]

    # Archivar y desarchivar ya no pasan por este PATCH: suspenden los
    # proyectos del cliente y cancelan su facturación futura, así que viven en
    # su propio par preview/apply. El rechazo del PATCH y la cascada se prueban
    # en content/tests/views/test_client_archive_views.py y
    # accounts/tests/test_client_archive_service.py.


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteProposalClient:
    def test_delete_orphan_returns_204(self, admin_client, orphan_client):
        response = admin_client.delete(
            reverse('delete-proposal-client', args=[orphan_client.pk]),
        )
        assert response.status_code == 204
        assert not UserProfile.objects.filter(pk=orphan_client.pk).exists()

    def test_delete_with_proposals_returns_400_with_error_code(
        self, admin_client, real_client_with_proposal,
    ):
        response = admin_client.delete(
            reverse('delete-proposal-client', args=[real_client_with_proposal.pk]),
        )
        assert response.status_code == 400
        assert response.data['error'] == 'client_has_proposals'
        assert response.data['count'] == 1

    def test_delete_with_platform_project_returns_400(
        self, admin_client, orphan_client,
    ):
        Project.objects.create(
            name='Live Project', client=orphan_client.user, status=Project.STATUS_ACTIVE,
        )
        response = admin_client.delete(
            reverse('delete-proposal-client', args=[orphan_client.pk]),
        )
        assert response.status_code == 400
        assert response.data['error'] == 'client_has_projects'

    def test_delete_returns_404_for_unknown_client(self, admin_client):
        response = admin_client.delete(
            reverse('delete-proposal-client', args=[999999]),
        )

        assert response.status_code == 404
        assert response.data['error'] == 'client_not_found'


# ---------------------------------------------------------------------------
# Proposal create/update wiring (client_id resolution)
# ---------------------------------------------------------------------------

class TestProposalCreateWithClientId:
    def test_proposal_create_with_client_id_reuses_existing_profile(
        self, admin_client, real_client_with_proposal,
    ):
        response = admin_client.post(
            reverse('create-proposal'),
            {
                'title': 'Second proposal for same client',
                'client_id': real_client_with_proposal.pk,
                'client_name': 'ignored',
                'client_email': 'ignored@gmail.com',
                'total_investment': 5000,
                'currency': 'COP',
            },
            format='json',
        )
        assert response.status_code == 201
        proposal = BusinessProposal.objects.get(pk=response.data['id'])
        assert proposal.client_id == real_client_with_proposal.pk
        # Snapshot was rebuilt from the canonical profile, not the inline data.
        assert proposal.client_email == 'activa@gmail.com'

    def test_proposal_create_without_client_id_auto_creates_profile_from_email(
        self, admin_client,
    ):
        response = admin_client.post(
            reverse('create-proposal'),
            {
                'title': 'Auto-create test',
                'client_name': 'Brand New',
                'client_email': 'brandnew@gmail.com',
                'total_investment': 1000,
                'currency': 'COP',
            },
            format='json',
        )
        assert response.status_code == 201
        proposal = BusinessProposal.objects.get(pk=response.data['id'])
        assert proposal.client is not None
        assert proposal.client.user.email == 'brandnew@gmail.com'

    def test_proposal_create_without_email_generates_placeholder_client(
        self, admin_client,
    ):
        response = admin_client.post(
            reverse('create-proposal'),
            {
                'title': 'No email proposal',
                'client_name': 'Email Pending',
                'client_email': '',
                'total_investment': 1000,
                'currency': 'COP',
            },
            format='json',
        )
        assert response.status_code == 201
        proposal = BusinessProposal.objects.get(pk=response.data['id'])
        assert proposal.client.is_email_placeholder is True

    def test_proposal_update_with_client_id_switches_profile_and_resyncs_snapshot(
        self, admin_client, real_client_with_proposal,
    ):
        replacement = proposal_client_service.get_or_create_client_for_proposal(
            name='Nueva Cuenta',
            email='nueva@gmail.com',
            phone='+57 320 555 0000',
            company='NuevaCo',
        )
        proposal = real_client_with_proposal.proposals.first()

        response = admin_client.patch(
            reverse('update-proposal', args=[proposal.pk]),
            {
                'client_id': replacement.pk,
                'client_name': 'ignorado',
                'client_email': 'ignorado@gmail.com',
                'client_phone': '000',
            },
            format='json',
        )

        assert response.status_code == 200
        proposal.refresh_from_db()
        assert proposal.client_id == replacement.pk
        assert proposal.client_name == 'Nueva Cuenta'
        assert proposal.client_email == 'nueva@gmail.com'
        assert proposal.client_phone == '+57 320 555 0000'

    def test_proposal_update_rejects_unknown_client_id(
        self, admin_client, real_client_with_proposal,
    ):
        proposal = real_client_with_proposal.proposals.first()

        response = admin_client.patch(
            reverse('update-proposal', args=[proposal.pk]),
            {'client_id': 999999},
            format='json',
        )

        assert response.status_code == 400
        assert 'client_id' in response.data


# ---------------------------------------------------------------------------
# Edge cases — proposal/client lifecycle interactions
# ---------------------------------------------------------------------------

class TestProposalUpdatePropagatesClientChanges:
    def test_propagate_client_updates_cascades_to_other_proposals(
        self, admin_client, real_client_with_proposal,
    ):
        # Add a second proposal to the same client so we can verify cascade.
        BusinessProposal.objects.create(
            title='Sibling proposal',
            client=real_client_with_proposal,
            client_name='Activa Mendoza',
            client_email='activa@gmail.com',
            total_investment=2000,
        )
        original = real_client_with_proposal.proposals.first()

        response = admin_client.patch(
            reverse('update-proposal', args=[original.pk]),
            {
                'client_phone': '+57 311 0000',
                'propagate_client_updates': True,
            },
            format='json',
        )
        assert response.status_code == 200

        sibling = BusinessProposal.objects.exclude(pk=original.pk).get(
            client=real_client_with_proposal,
        )
        assert sibling.client_phone == '+57 311 0000'

    def test_inline_client_update_without_propagate_does_not_cascade(
        self, admin_client, real_client_with_proposal,
    ):
        # Capture the original (fixture) proposal id before creating the sibling.
        original_pk = real_client_with_proposal.proposals.values_list('pk', flat=True).first()
        sibling = BusinessProposal.objects.create(
            title='Sibling no-cascade',
            client=real_client_with_proposal,
            client_name='Activa Mendoza',
            client_email='activa@gmail.com',
            client_phone='untouched',
            total_investment=3000,
        )

        admin_client.patch(
            reverse('update-proposal', args=[original_pk]),
            {'client_phone': '+57 999 8888'},
            format='json',
        )

        # Sibling stays at 'untouched' because propagate flag was not set.
        sibling.refresh_from_db()
        assert sibling.client_phone == 'untouched'


class TestOrphanFlagTransitionsAfterProposalDelete:
    def test_client_becomes_orphan_after_last_proposal_is_deleted(
        self, admin_client, real_client_with_proposal,
    ):
        # First confirm: client is NOT orphan while it has a proposal.
        list_response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': 'false'},
        )
        ids = [c['id'] for c in list_response.data]
        assert real_client_with_proposal.pk in ids

        # Delete the only proposal.
        proposal = real_client_with_proposal.proposals.first()
        proposal.delete()

        # Client should now appear in the orphans filter.
        list_response = admin_client.get(
            reverse('list-proposal-clients'), {'orphans': 'true'},
        )
        ids = [c['id'] for c in list_response.data]
        assert real_client_with_proposal.pk in ids

    def test_orphan_can_be_deleted_after_last_proposal_removal(
        self, admin_client, real_client_with_proposal,
    ):
        proposal = real_client_with_proposal.proposals.first()
        proposal.delete()
        response = admin_client.delete(
            reverse('delete-proposal-client', args=[real_client_with_proposal.pk]),
        )
        assert response.status_code == 204


@pytest.mark.django_db
class TestClientStatusCounts:
    """
    The status cut runs server-side, so the selector cannot count the options it
    is not showing. These pin the counts against the lists they describe: a
    number that disagrees with what pressing it returns is worse than none.
    """

    def test_counts_match_the_list_each_status_returns(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(reverse('proposal-client-status-counts'))

        assert response.status_code == 200
        for status, params in (
            ('all', {}),
            ('active', {'orphans': 'false'}),
            ('orphans', {'orphans': 'true'}),
            ('archived', {'archived': 'true'}),
        ):
            listed = admin_client.get(reverse('list-proposal-clients'), params)
            assert response.data[status] == len(listed.data), status

    @freeze_time('2026-01-15 12:00:00')
    def test_archived_client_only_counts_under_archived(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        from django.utils import timezone
        orphan_client.archived_at = timezone.now()
        orphan_client.save(update_fields=['archived_at'])

        response = admin_client.get(reverse('proposal-client-status-counts'))

        assert response.data['archived'] == 1
        assert response.data['all'] == 1
        assert response.data['orphans'] == 0

    def test_counts_honour_the_search_term(
        self, admin_client, real_client_with_proposal, orphan_client,
    ):
        response = admin_client.get(
            reverse('proposal-client-status-counts'),
            {'search': real_client_with_proposal.user.email},
        )

        assert response.data['all'] == 1
        assert response.data['active'] == 1
        assert response.data['orphans'] == 0

    def test_requires_admin(self, client):
        response = client.get(reverse('proposal-client-status-counts'))

        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------

def _diagnostic(profile, status=None, **kwargs):
    """A WebAppDiagnostic with only what these annotations read."""
    from content.models import WebAppDiagnostic
    return WebAppDiagnostic.objects.create(
        client=profile,
        status=status or WebAppDiagnostic.Status.SENT,
        **kwargs,
    )


class TestDiagnosticModuleAnnotations:
    """The two aggregates behind the Diagnóstico subfilters. The billed cut
    reads the income; the unconverted cut reads the entity against whatever
    proposals followed it."""

    def test_a_billed_diagnostic_counts_without_any_diagnostic_entity(
        self, admin_client, make_client_profile, make_income,
    ):
        """The decision this module rests on, as an executable statement:
        'facturado' is the money, so a diagnostic that was charged for
        without its entity ever being created is still a billed one."""
        from content.models import IncomeRecord
        profile = make_client_profile(company='Diag SAS')
        make_income(client=profile, origin=IncomeRecord.Origin.DIAGNOSTIC)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostic_incomes_count'] == 1
        assert row['diagnostics_count'] == 0

    def test_a_legacy_income_without_origin_is_not_a_billed_diagnostic(
        self, admin_client, make_client_profile, make_income,
    ):
        profile = make_client_profile(company='Legado SAS')
        make_income(client=profile)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['incomes_count'] == 1
        assert row['diagnostic_incomes_count'] == 0

    def test_a_written_off_diagnostic_income_does_not_count_as_billed(
        self, admin_client, make_client_profile, make_income,
    ):
        from content.models import IncomeRecord
        profile = make_client_profile(company='Perdido SAS')
        make_income(
            client=profile, origin=IncomeRecord.Origin.DIAGNOSTIC,
            kind=IncomeRecord.Kind.LOST,
        )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostic_incomes_count'] == 0

    def test_a_written_off_row_does_not_hide_a_real_one(
        self, admin_client, make_client_profile, make_income,
    ):
        from content.models import IncomeRecord
        profile = make_client_profile(company='Mixto SAS')
        make_income(
            client=profile, origin=IncomeRecord.Origin.DIAGNOSTIC,
            kind=IncomeRecord.Kind.LOST,
        )
        make_income(client=profile, origin=IncomeRecord.Origin.DIAGNOSTIC)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostic_incomes_count'] == 1

    def test_a_draft_only_diagnostic_is_never_a_missed_opportunity(
        self, admin_client, make_client_profile,
    ):
        """A draft never left the building, so 'no proposal followed it' is
        trivially true and would flood the cut with work in progress."""
        from content.models import WebAppDiagnostic
        profile = make_client_profile(company='Borrador SAS')
        _diagnostic(profile, status=WebAppDiagnostic.Status.DRAFT)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_count'] == 1
        assert row['diagnostics_without_proposal_count'] == 0

    def test_a_sent_diagnostic_with_no_proposal_at_all_counts(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Enfriado SAS')
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(profile, initial_sent_at=timezone.now())

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 1

    def test_a_proposal_created_later_the_same_day_converts_it(
        self, admin_client, make_client_profile,
    ):
        """'Posterior' is a timestamp, not a date: same-day still converts."""
        profile = make_client_profile(company='Convertido SAS')
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(profile, initial_sent_at=timezone.now())
        with freeze_time('2026-03-10 17:00:00'):
            BusinessProposal.objects.create(
                title='Propuesta', client=profile,
                client_name='Ana', client_email='ana@example.com',
            )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 0

    def test_a_proposal_created_at_the_same_instant_does_not_convert_it(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Empate SAS')
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(profile, initial_sent_at=timezone.now())
            BusinessProposal.objects.create(
                title='Propuesta', client=profile,
                client_name='Ana', client_email='ana@example.com',
            )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 1

    def test_a_proposal_created_before_it_leaves_it_unconverted(
        self, admin_client, make_client_profile,
    ):
        """The headline false negative: an older proposal must not absolve a
        diagnostic that came after it."""
        profile = make_client_profile(company='Anterior SAS')
        with freeze_time('2026-01-05 09:00:00'):
            BusinessProposal.objects.create(
                title='Propuesta vieja', client=profile,
                client_name='Ana', client_email='ana@example.com',
            )
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(profile, initial_sent_at=timezone.now())

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 1

    def test_the_anchor_is_the_send_not_the_draft(
        self, admin_client, make_client_profile,
    ):
        """Drafted in January, proposal in February, sent in June: that
        proposal cannot be the outcome of something the client had not
        received yet, so the diagnostic is still unconverted."""
        profile = make_client_profile(company='Ancla SAS')
        with freeze_time('2026-01-05 09:00:00'):
            diag = _diagnostic(profile)
        with freeze_time('2026-02-01 09:00:00'):
            BusinessProposal.objects.create(
                title='Propuesta', client=profile,
                client_name='Ana', client_email='ana@example.com',
            )
        with freeze_time('2026-06-01 09:00:00'):
            diag.initial_sent_at = timezone.now()
            diag.save(update_fields=['initial_sent_at'])

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 1

    def test_a_non_draft_diagnostic_never_sent_falls_back_to_created_at(
        self, admin_client, make_client_profile,
    ):
        """Without the Coalesce the comparison would go NULL and the row
        would count as unconverted forever, whatever followed it."""
        profile = make_client_profile(company='Sin envio SAS')
        from content.models import WebAppDiagnostic
        with freeze_time('2026-01-05 09:00:00'):
            _diagnostic(
                profile, status=WebAppDiagnostic.Status.ACCEPTED,
                initial_sent_at=None,
            )
        with freeze_time('2026-02-01 09:00:00'):
            BusinessProposal.objects.create(
                title='Propuesta', client=profile,
                client_name='Ana', client_email='ana@example.com',
            )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 0

    def test_it_counts_each_unconverted_diagnostic(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Varios SAS')
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(profile, initial_sent_at=timezone.now())
            _diagnostic(profile, initial_sent_at=timezone.now())

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['diagnostics_without_proposal_count'] == 2

    def test_another_clients_proposal_does_not_convert_this_diagnostic(
        self, admin_client, make_client_profile,
    ):
        """The only test that catches a mis-bound OuterRef."""
        owner = make_client_profile(company='Dueno SAS')
        stranger = make_client_profile(company='Ajeno SAS')
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(owner, initial_sent_at=timezone.now())
        with freeze_time('2026-04-01 09:00:00'):
            BusinessProposal.objects.create(
                title='Propuesta ajena', client=stranger,
                client_name='Otro', client_email='otro@example.com',
            )

        response = admin_client.get(reverse('list-proposal-clients'))

        assert _row_for(response, owner)['diagnostics_without_proposal_count'] == 1
        assert _row_for(response, stranger)['diagnostics_without_proposal_count'] == 0

    def test_the_serializer_falls_back_when_the_queryset_is_not_annotated(
        self, make_client_profile, make_income,
    ):
        from content.models import IncomeRecord
        profile = make_client_profile(company='Sin anotar SAS')
        make_income(client=profile, origin=IncomeRecord.Origin.DIAGNOSTIC)
        with freeze_time('2026-03-10 09:00:00'):
            _diagnostic(profile, initial_sent_at=timezone.now())

        raw = UserProfile.objects.get(pk=profile.pk)
        data = ProposalClientSerializer(raw).data

        assert data['diagnostic_incomes_count'] == 1
        assert data['diagnostics_without_proposal_count'] == 1


class TestEmailModuleAnnotations:
    """The three aggregates behind the Emails subfilters and the row column.
    All of them read what went TO the client: an internal notice about their
    income is in their trail, but it is not contact with them."""

    def _log(self, profile, **kwargs):
        from content.models import EmailLog
        defaults = {
            'template_key': 'collection_account_sent',
            'recipient': 'ana@example.com',
            'subject': 'Cuenta de cobro',
            'status': EmailLog.Status.SENT,
            'audience': EmailLog.Audience.CLIENT,
            'client': profile,
        }
        defaults.update(kwargs)
        return EmailLog.objects.create(**defaults)

    def test_it_counts_only_what_was_addressed_to_the_client(
        self, admin_client, make_client_profile,
    ):
        from content.models import EmailLog
        profile = make_client_profile(company='Contacto SAS')
        self._log(profile)
        self._log(
            profile, template_key='accounting_change',
            audience=EmailLog.Audience.INTERNAL,
        )

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['emails_sent_count'] == 1

    def test_failed_sends_are_counted_apart(
        self, admin_client, make_client_profile,
    ):
        from content.models import EmailLog
        profile = make_client_profile(company='Fallido SAS')
        self._log(profile)
        self._log(profile, status=EmailLog.Status.FAILED)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['emails_sent_count'] == 2
        assert row['emails_failed_count'] == 1

    def test_last_email_at_is_the_most_recent_one(
        self, admin_client, make_client_profile,
    ):
        profile = make_client_profile(company='Fecha SAS')
        with freeze_time('2026-01-05 09:00:00'):
            self._log(profile)
        with freeze_time('2026-06-01 09:00:00'):
            self._log(profile)

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['last_email_at'].date().isoformat() == '2026-06-01'

    def test_a_client_who_never_got_anything_reads_zero_and_null(
        self, admin_client, make_client_profile,
    ):
        """What 'Sin ningún correo' and 'Sin contacto en 30 días' both read."""
        profile = make_client_profile(company='Silencio SAS')

        response = admin_client.get(reverse('list-proposal-clients'))
        row = _row_for(response, profile)

        assert row['emails_sent_count'] == 0
        assert row['emails_failed_count'] == 0
        assert row['last_email_at'] is None

    def test_another_clients_email_does_not_leak_into_this_count(
        self, admin_client, make_client_profile,
    ):
        owner = make_client_profile(company='Dueno mail SAS')
        stranger = make_client_profile(company='Ajeno mail SAS')
        self._log(owner)

        response = admin_client.get(reverse('list-proposal-clients'))

        assert _row_for(response, owner)['emails_sent_count'] == 1
        assert _row_for(response, stranger)['emails_sent_count'] == 0

    def test_the_serializer_falls_back_when_the_queryset_is_not_annotated(
        self, make_client_profile,
    ):
        from content.models import EmailLog
        profile = make_client_profile(company='Sin anotar mail SAS')
        self._log(profile)
        self._log(profile, status=EmailLog.Status.FAILED)

        raw = UserProfile.objects.get(pk=profile.pk)
        data = ProposalClientSerializer(raw).data

        assert data['emails_sent_count'] == 2
        assert data['emails_failed_count'] == 1
        assert data['last_email_at'] is not None
