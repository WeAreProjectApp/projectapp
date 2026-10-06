"""Project as a first-class relation of the accounting records.

Covers the ownership rule (a record's project must be its client's), what
happens when the client is reassigned, and the two endpoints the panel needs
to inspect an income and to pick a project.
"""
from decimal import Decimal

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied

from content.models import ExpenseRecord, HostingRecord, IncomeRecord, ProjectRetentionContext
from content.services.project_force_deletion import (
    force_delete_project,
    forced_deletion_preview,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_client(email, *, first='Ana', last='Pérez'):
    user = User.objects.create_user(
        username=email, email=email, password='pass12345',
        first_name=first, last_name=last,
    )
    return UserProfile.objects.create(user=user, cedula='1049654583')


def make_income(**overrides):
    fields = {
        'concept': 'Desarrollo módulo de reportes',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-08-01',
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


class TestProjectOwnershipRule:
    def test_a_project_of_another_client_is_rejected(self, super_client):
        owner = make_client('daniel@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)

        response = super_client.post('/api/accounting/incomes/create/', {
            'concept': 'Hosting trimestral',
            'kind': 'expected',
            'period_date': '2026-08',
            'total_amount': '233280.00',
            'origin': 'development',
            'client': other.pk,
            'project': project.pk,
        }, format='json')

        assert response.status_code == 400
        assert 'pertenece a otro cliente' in str(response.data['project'])

    def test_a_project_without_a_client_is_rejected(self, super_client):
        owner = make_client('daniel@example.com')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)

        response = super_client.post('/api/accounting/incomes/create/', {
            'concept': 'Hosting trimestral',
            'kind': 'expected',
            'period_date': '2026-08',
            'total_amount': '233280.00',
            'origin': 'development',
            'project': project.pk,
        }, format='json')

        assert response.status_code == 400
        assert 'Asigna primero el cliente' in str(response.data['project'])

    def test_the_clients_own_project_is_accepted(self, super_client):
        owner = make_client('daniel@example.com')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)

        response = super_client.post('/api/accounting/incomes/create/', {
            'concept': 'Hosting trimestral',
            'kind': 'expected',
            'period_date': '2026-08',
            'total_amount': '233280.00',
            'origin': 'development',
            'client': owner.pk,
            'project': project.pk,
        }, format='json')

        assert response.status_code == 201, response.data
        assert response.data['project'] == project.pk
        assert response.data['project_name'] == 'MIMITTOS'

    def test_reassigning_the_client_clears_a_project_that_is_now_foreign(
        self, super_client,
    ):
        owner = make_client('daniel@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)
        income = make_income(client=owner, project=project)

        response = super_client.patch(
            f'/api/accounting/incomes/{income.pk}/update/',
            {'client': other.pk}, format='json',
        )

        # Clearing beats keeping a record that points at someone else's
        # project — and beats rejecting an otherwise valid reassignment.
        assert response.status_code == 200, response.data
        assert response.data['project'] is None
        income.refresh_from_db()
        assert income.project_id is None


class TestIncomeDetailEndpoint:
    def test_returns_the_settlement_history_and_the_linked_cuenta(
        self, super_client,
    ):
        owner = make_client('daniel@example.com')
        expected = make_income(client=owner)
        IncomeRecord.objects.create(
            concept='Abono 1', kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-08-05', total_amount=Decimal('400000.00'),
            gustavo_amount=Decimal('200000.00'),
            carlos_amount=Decimal('200000.00'),
            expected_income=expected, client=owner,
        )
        ExpenseRecord.objects.create(
            concept='Comisión pasarela', period_date='2026-08-05',
            total_amount=Decimal('12000.00'),
            gustavo_amount=Decimal('6000.00'),
            carlos_amount=Decimal('6000.00'),
            deduction_type='gateway_fee', source_income=expected,
        )

        response = super_client.get(
            f'/api/accounting/incomes/{expected.pk}/detail/',
        )

        assert response.status_code == 200, response.data
        assert response.data['income']['id'] == expected.pk
        assert [r['concept'] for r in response.data['liquid']] == ['Abono 1']
        assert [r['concept'] for r in response.data['expenses']] == [
            'Comisión pasarela',
        ]
        assert response.data['collection_account'] is None
        # 400k liquid + 12k deduction credit the gross total.
        assert response.data['income']['paid_amount'] == '412000.00'

    def test_an_income_with_no_history_returns_empty_lists(self, super_client):
        income = make_income()

        response = super_client.get(
            f'/api/accounting/incomes/{income.pk}/detail/',
        )

        assert response.status_code == 200
        assert response.data['liquid'] == []
        assert response.data['expenses'] == []
        assert response.data['collection_account'] is None

    def test_requires_a_superuser(self, api_client):
        income = make_income()

        response = api_client.get(
            f'/api/accounting/incomes/{income.pk}/detail/',
        )

        assert response.status_code in (401, 403)


class TestProjectPickerEndpoint:
    def test_scopes_the_list_to_one_client(self, super_client):
        owner = make_client('daniel@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        Project.objects.create(name='MIMITTOS', client=owner.user)
        Project.objects.create(name='Xpandia', client=other.user)

        response = super_client.get(
            f'/api/accounting/projects/?client={owner.pk}',
        )

        assert response.status_code == 200
        assert [p['name'] for p in response.data['results']] == ['MIMITTOS']
        assert response.data['results'][0]['status_label'] == 'En desarrollo'

    def test_without_a_client_it_returns_them_all(self, super_client):
        owner = make_client('daniel@example.com')
        other = make_client('nestor@example.com', first='Néstor')
        Project.objects.create(name='MIMITTOS', client=owner.user)
        Project.objects.create(name='Xpandia', client=other.user)

        response = super_client.get('/api/accounting/projects/')

        assert [p['name'] for p in response.data['results']] == [
            'MIMITTOS', 'Xpandia',
        ]

    def test_rows_carry_their_owner_for_the_unscoped_picker(self, super_client):
        owner = make_client('daniel@example.com', first='Daniel', last='Ríos')
        Project.objects.create(name='MIMITTOS', client=owner.user)

        response = super_client.get('/api/accounting/projects/')

        row = response.data['results'][0]
        assert row['client_profile_id'] == owner.pk
        assert 'Daniel' in row['client_display_name']

    def test_a_staff_admin_can_use_the_picker(self, admin_client):
        owner = make_client('daniel@example.com')
        Project.objects.create(name='MIMITTOS', client=owner.user)

        response = admin_client.get('/api/accounting/projects/')

        assert response.status_code == 200
        assert response.data['results'][0]['name'] == 'MIMITTOS'


class TestWithoutProjectMeta:
    def test_incomes_meta_counts_only_client_linked_rows_without_project(
        self, super_client,
    ):
        """Same backlog definition as /panel/projects: a client-less row has
        no project to propose, so it lives in without_client_count instead
        and the two counters compose without overlap."""
        owner = make_client('daniel@example.com')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)
        make_income(client=owner)
        make_income(client=owner, project=project)
        make_income(concept='Sin dueño')

        response = super_client.get('/api/accounting/incomes/')

        assert response.status_code == 200
        assert response.data['meta']['without_project_count'] == 1
        assert response.data['meta']['without_client_count'] == 1

    def test_the_counter_follows_the_active_filters(self, super_client):
        owner = make_client('daniel@example.com')
        make_income(client=owner, period_date='2025-01-01')

        unfiltered = super_client.get('/api/accounting/incomes/')
        filtered = super_client.get(
            '/api/accounting/incomes/?date_from=2026-01-01',
        )

        assert unfiltered.data['meta']['without_project_count'] == 1
        assert filtered.data['meta']['without_project_count'] == 0

    def test_hostings_meta_counts_the_same_backlog(self, super_client):
        owner = make_client('daniel@example.com')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)
        HostingRecord.objects.create(
            client=owner, client_name='Daniel - Backlog',
            monthly_value=Decimal('77760.00'),
        )
        HostingRecord.objects.create(
            client=owner, project=project, client_name='Daniel - Mimittos',
            monthly_value=Decimal('77760.00'),
        )
        HostingRecord.objects.create(
            client_name='Sin dueño', monthly_value=Decimal('77760.00'),
        )

        response = super_client.get('/api/accounting/hostings/')

        assert response.status_code == 200
        assert response.data['meta']['without_project_count'] == 1


class TestExpectedIncomeFilter:
    def test_liquid_children_are_finally_queryable_from_the_list(
        self, super_client,
    ):
        """Before this filter the children of an expected income could not be
        reached from the panel at all."""
        expected = make_income()
        child = IncomeRecord.objects.create(
            concept='Abono 1', kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-08-05', total_amount=Decimal('400000.00'),
            gustavo_amount=Decimal('200000.00'),
            carlos_amount=Decimal('200000.00'),
            expected_income=expected,
        )
        make_income(concept='Ingreso ajeno')

        response = super_client.get(
            f'/api/accounting/incomes/?expected_income={expected.pk}',
        )

        assert [r['id'] for r in response.data['results']] == [child.pk]


class TestProjectDeletionDoesNotBlockTheLedger:
    def test_empty_force_selection_retains_ledger_records(self, superuser):
        """Fails if retaining ledger rows drops amounts or makes their former project editable."""
        from content.models import HostingRecord

        owner = make_client('daniel@example.com')
        project = Project.objects.create(name='MIMITTOS', client=owner.user)
        income = make_income(client=owner, project=project)
        hosting = HostingRecord.objects.create(
            client=owner, project=project, client_name='Daniel - Mimittos',
            monthly_value=Decimal('77760.00'),
        )
        preview = forced_deletion_preview(project, actor=superuser, delete_keys=[])

        force_delete_project(
            project.pk,
            actor=superuser,
            confirmation='DELETE',
            impact_token=preview['impact_token'],
            delete_keys=[],
        )

        income.refresh_from_db()
        hosting.refresh_from_db()
        context = ProjectRetentionContext.objects.get(pk=income.retention_context_id)
        assert (
            income.project_id, hosting.project_id,
            income.client_id, hosting.client_id,
            income.total_amount, hosting.monthly_value,
        ) == (None, None, owner.pk, owner.pk, Decimal('1000000.00'), Decimal('77760.00'))
        assert income.retention_context_id == hosting.retention_context_id == context.pk
        assert context.client_id == owner.user_id
        with pytest.raises(PermissionDenied, match='sólo permiten consulta'):
            income.save()
