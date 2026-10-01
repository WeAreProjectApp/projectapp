from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    Requirement,
    UserProfile,
)
from accounts.tests.wompi_event_helpers import signed_transaction_event

User = get_user_model()
MAX_SUBSCRIPTION_LIST_QUERIES = 6


def _create_subscription(project, *, start_date='2026-01-01'):
    subscription = HostingSubscription(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal('330000'),
        discount_percent=10,
        start_date=start_date,
        next_billing_date='2026-04-01',
        status=HostingSubscription.STATUS_ACTIVE,
    )
    subscription.calculate_amounts()
    subscription.save()
    return subscription


def _create_subscriptions_for_query_budget(client_user, count, *, add_pending_payments=False):
    projects = [
        Project(
            name=f'Budget subscription project {index}',
            client=client_user,
            status=Project.STATUS_ACTIVE,
            progress=0,
        )
        for index in range(count)
    ]
    persisted_projects = Project.objects.bulk_create(projects)
    subscriptions = [
        HostingSubscription(
            project=project,
            plan=HostingSubscription.PLAN_QUARTERLY,
            base_monthly_amount=Decimal('330000'),
            discount_percent=10,
            start_date='2026-01-01',
            next_billing_date='2026-04-01',
            status=HostingSubscription.STATUS_ACTIVE,
            effective_monthly_amount=Decimal('297000'),
            billing_amount=Decimal('891000'),
        )
        for project in persisted_projects
    ]
    persisted_subscriptions = HostingSubscription.objects.bulk_create(subscriptions)
    if add_pending_payments:
        Payment.objects.bulk_create([
            Payment(
                subscription=subscription,
                amount=subscription.billing_amount,
                billing_period_start=date(2026, 1, 1),
                billing_period_end=date(2026, 1, 31),
                due_date=date(2026, 1, 1),
                status=Payment.STATUS_PENDING,
            )
            for subscription in persisted_subscriptions
        ])


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    user = User.objects.create_user(
        username='admin@pay.com', email='admin@pay.com', password='adminpass1',
        first_name='Admin', last_name='User',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_ADMIN,
        is_onboarded=True, profile_completed=True,
    )
    return user


@pytest.fixture
def admin_headers(api_client, admin_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'admin@pay.com', 'password': 'adminpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def client_user(admin_user):
    user = User.objects.create_user(
        username='client@pay.com', email='client@pay.com', password='clientpass1',
        first_name='Carlos', last_name='López',
    )
    UserProfile.objects.create(
        user=user, role=UserProfile.ROLE_CLIENT,
        is_onboarded=True, profile_completed=True,
        company_name='PayCorp', created_by=admin_user,
    )
    return user


@pytest.fixture
def client_headers(api_client, client_user):
    resp = api_client.post('/api/accounts/login/', {
        'email': 'client@pay.com', 'password': 'clientpass1',
    })
    token = resp.json()['tokens']['access']
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


@pytest.fixture
def project(client_user):
    return Project.objects.create(
        name='Pay Project', client=client_user,
        status=Project.STATUS_ACTIVE, progress=0,
    )


@pytest.fixture
def subscription(project):
    return _create_subscription(project)


@pytest.fixture
def sample_payments(subscription):
    payments = []
    payments.append(Payment.objects.create(
        subscription=subscription,
        amount=subscription.billing_amount,
        description='Q1 Hosting',
        billing_period_start='2026-01-01',
        billing_period_end='2026-03-31',
        due_date='2026-01-01',
        status=Payment.STATUS_PAID,
    ))
    payments.append(Payment.objects.create(
        subscription=subscription,
        amount=subscription.billing_amount,
        description='Q2 Hosting',
        billing_period_start='2026-04-01',
        billing_period_end='2026-06-30',
        due_date='2026-04-01',
        status=Payment.STATUS_PENDING,
    ))
    payments.append(Payment.objects.create(
        subscription=subscription,
        amount=subscription.billing_amount,
        description='Q0 Overdue',
        billing_period_start='2025-10-01',
        billing_period_end='2025-12-31',
        due_date='2025-10-01',
        status=Payment.STATUS_OVERDUE,
    ))
    return payments


# =========================================================================
# HostingSubscription model
# =========================================================================


@pytest.mark.django_db
class TestHostingSubscriptionModel:
    def test_calculate_amounts_quarterly(self, project):
        sub = HostingSubscription(
            project=project, plan='quarterly',
            base_monthly_amount=Decimal('100000'), discount_percent=10,
            start_date='2026-01-01',
        )
        sub.calculate_amounts()

        assert sub.effective_monthly_amount == Decimal('90000')
        assert sub.billing_amount == Decimal('270000')

    def test_calculate_amounts_semiannual(self, project):
        sub = HostingSubscription(
            project=project, plan='semiannual',
            base_monthly_amount=Decimal('100000'), discount_percent=20,
            start_date='2026-01-01',
        )
        sub.calculate_amounts()

        assert sub.effective_monthly_amount == Decimal('80000')
        assert sub.billing_amount == Decimal('480000')

    def test_calculate_amounts_nine_month(self, project):
        sub = HostingSubscription(
            project=project, plan='nine_month',
            base_monthly_amount=Decimal('100000'), discount_percent=40,
            start_date='2026-01-01',
        )
        sub.calculate_amounts()

        assert sub.effective_monthly_amount == Decimal('60000')
        assert sub.billing_amount == Decimal('540000')

    def test_calculate_amounts_monthly_no_discount(self, project):
        sub = HostingSubscription(
            project=project, plan='monthly',
            base_monthly_amount=Decimal('100000'), discount_percent=0,
            start_date='2026-01-01',
        )
        sub.calculate_amounts()

        assert sub.effective_monthly_amount == Decimal('100000')
        assert sub.billing_amount == Decimal('100000')

    def test_billing_months_property(self, subscription):
        assert subscription.billing_months == 3


# =========================================================================
# Subscription Views
# =========================================================================


@pytest.mark.django_db
class TestSubscriptionList:
    def test_admin_lists_all_subscriptions(
        self, api_client, admin_headers, subscription,
    ):
        resp = api_client.get('/api/accounts/subscriptions/', **admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]['project_name'] == 'Pay Project'

    def test_client_lists_own_subscriptions(
        self, api_client, client_headers, subscription,
    ):
        resp = api_client.get('/api/accounts/subscriptions/', **client_headers)

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get('/api/accounts/subscriptions/')

        assert resp.status_code == 401

    def test_pending_payments_uses_inclusive_cutoff(
        self, api_client, admin_headers, subscription,
    ):
        """Fails if the pending payment aggregate excludes the seven-day cutoff date."""
        fixed_now = datetime(2026, 1, 15, tzinfo=datetime_timezone.utc)
        Payment.objects.create(
            subscription=subscription, amount=subscription.billing_amount,
            billing_period_start=date(2026, 1, 1), billing_period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 15), status=Payment.STATUS_PENDING,
        )
        Payment.objects.create(
            subscription=subscription, amount=subscription.billing_amount,
            billing_period_start=date(2026, 2, 1), billing_period_end=date(2026, 2, 28),
            due_date=date(2026, 1, 22), status=Payment.STATUS_FAILED,
        )
        Payment.objects.create(
            subscription=subscription, amount=subscription.billing_amount,
            billing_period_start=date(2026, 3, 1), billing_period_end=date(2026, 3, 31),
            due_date=date(2026, 1, 22), status=Payment.STATUS_PAID,
        )
        Payment.objects.create(
            subscription=subscription, amount=subscription.billing_amount,
            billing_period_start=date(2026, 4, 1), billing_period_end=date(2026, 4, 30),
            due_date=date(2026, 1, 22), status=Payment.STATUS_OVERDUE, is_archived=True,
        )
        Payment.objects.create(
            subscription=subscription, amount=subscription.billing_amount,
            billing_period_start=date(2026, 5, 1), billing_period_end=date(2026, 5, 31),
            due_date=date(2026, 1, 23), status=Payment.STATUS_OVERDUE,
        )

        with patch('accounts.views.timezone.now', return_value=fixed_now):
            response = api_client.get('/api/accounts/subscriptions/', **admin_headers)

        assert response.status_code == 200
        assert response.json()[0]['pending_payments'] == 2

    def test_subscription_list_query_budget_is_constant(
        self, api_client, admin_headers, client_user,
    ):
        """Fails if serializing each subscription restores a filtered payment COUNT query."""
        _create_subscriptions_for_query_budget(client_user, 1)

        with CaptureQueriesContext(connection) as one_subscription_queries:
            one_subscription_response = api_client.get('/api/accounts/subscriptions/', **admin_headers)

        _create_subscriptions_for_query_budget(client_user, 49, add_pending_payments=True)

        with CaptureQueriesContext(connection) as fifty_subscription_queries:
            fifty_subscription_response = api_client.get('/api/accounts/subscriptions/', **admin_headers)

        assert one_subscription_response.status_code == 200
        assert fifty_subscription_response.status_code == 200
        assert len(one_subscription_response.json()) == 1
        assert len(fifty_subscription_response.json()) == 50
        assert len(one_subscription_queries) == len(fifty_subscription_queries)
        assert len(fifty_subscription_queries) <= MAX_SUBSCRIPTION_LIST_QUERIES

    def test_subscription_list_orders_by_created_at(
        self, api_client, admin_headers, client_user,
    ):
        """Fails if the payment aggregate drops the subscription creation order."""
        oldest_project = Project.objects.create(
            name='Old subscription project', client=client_user, status=Project.STATUS_ACTIVE,
        )
        newest_project = Project.objects.create(
            name='New subscription project', client=client_user, status=Project.STATUS_ACTIVE,
        )
        oldest_subscription = _create_subscription(oldest_project)
        newest_subscription = _create_subscription(newest_project)
        HostingSubscription.objects.filter(pk=oldest_subscription.pk).update(
            created_at=datetime(2026, 1, 1, tzinfo=datetime_timezone.utc),
        )
        HostingSubscription.objects.filter(pk=newest_subscription.pk).update(
            created_at=datetime(2026, 1, 2, tzinfo=datetime_timezone.utc),
        )

        response = api_client.get('/api/accounts/subscriptions/', **admin_headers)

        assert response.status_code == 200
        assert [item['id'] for item in response.json()] == [
            newest_subscription.id,
            oldest_subscription.id,
        ]

    def test_client_does_not_receive_other_clients_subscription(
        self, api_client, admin_user, client_headers,
    ):
        """Fails if the subscription list exposes another client's project."""
        other_client = User.objects.create_user(
            username='other-pay@test.com', email='other-pay@test.com', password='pass12345',
        )
        UserProfile.objects.create(
            user=other_client, role=UserProfile.ROLE_CLIENT,
            is_onboarded=True, profile_completed=True, created_by=admin_user,
        )
        foreign_project = Project.objects.create(
            name='Other client project', client=other_client, status=Project.STATUS_ACTIVE, progress=0,
        )
        foreign_subscription = _create_subscription(foreign_project)

        response = api_client.get('/api/accounts/subscriptions/', **client_headers)

        assert response.status_code == 200
        assert foreign_subscription.id not in [item['id'] for item in response.json()]

@pytest.mark.django_db
class TestProjectSubscription:
    def test_get_subscription_with_payments(
        self, api_client, admin_headers, project, subscription, sample_payments,
    ):
        resp = api_client.get(
            f'/api/accounts/projects/{project.id}/subscription/', **admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data['plan'] == 'quarterly'
        assert 'payments' in data
        assert len(data['payments']) == 3

    def test_client_gets_own_subscription(
        self, api_client, client_headers, project, subscription,
    ):
        resp = api_client.get(
            f'/api/accounts/projects/{project.id}/subscription/', **client_headers,
        )

        assert resp.status_code == 200

    def test_no_subscription_returns_404(
        self, api_client, admin_headers, project,
    ):
        resp = api_client.get(
            f'/api/accounts/projects/{project.id}/subscription/', **admin_headers,
        )

        assert resp.status_code == 404

    def test_admin_updates_plan(
        self, api_client, admin_headers, project, subscription,
    ):
        resp = api_client.patch(
            f'/api/accounts/projects/{project.id}/subscription/',
            {'plan': 'semiannual'},
            format='json', **admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data['plan'] == 'semiannual'

    def test_client_can_change_plan(
        self, api_client, client_headers, project, subscription,
    ):
        # The client may change the frequency only while the subscription is
        # still pending (the first payment has not settled yet).
        subscription.status = HostingSubscription.STATUS_PENDING
        subscription.save(update_fields=['status'])

        resp = api_client.patch(
            f'/api/accounts/projects/{project.id}/subscription/',
            {'plan': 'nine_month'},
            format='json', **client_headers,
        )

        assert resp.status_code == 200
        assert resp.json()['plan'] == 'nine_month'

    def test_client_cannot_change_status(
        self, api_client, client_headers, project, subscription,
    ):
        resp = api_client.patch(
            f'/api/accounts/projects/{project.id}/subscription/',
            {'status': 'cancelled'},
            format='json', **client_headers,
        )

        assert resp.status_code == 403


# =========================================================================
# Project Payments
# =========================================================================


@pytest.mark.django_db
class TestProjectPayments:
    def test_list_payments_for_project(
        self, api_client, admin_headers, project, subscription, sample_payments,
    ):
        resp = api_client.get(
            f'/api/accounts/projects/{project.id}/payments/', **admin_headers,
        )

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_client_lists_payments(
        self, api_client, client_headers, project, subscription, sample_payments,
    ):
        resp = api_client.get(
            f'/api/accounts/projects/{project.id}/payments/', **client_headers,
        )

        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_no_subscription_returns_empty(
        self, api_client, admin_headers, project,
    ):
        resp = api_client.get(
            f'/api/accounts/projects/{project.id}/payments/', **admin_headers,
        )

        assert resp.status_code == 200
        assert resp.json() == []


# =========================================================================
# Generate Payment Link
# =========================================================================


@pytest.mark.django_db
class TestPaymentGenerateLink:
    @patch('accounts.services.wompi.requests.post')
    def test_admin_generates_link_for_pending_payment(
        self, mock_post, api_client, admin_headers, project, subscription, sample_payments,
    ):
        pending = sample_payments[1]
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json.return_value = {
            'data': {'id': 'link_abc123'},
        }

        resp = api_client.post(
            f'/api/accounts/projects/{project.id}/payments/{pending.id}/generate-link/',
            **admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data['wompi_payment_link_id'] == 'link_abc123'
        assert 'checkout.wompi.co' in data['wompi_payment_link_url']

    def test_cannot_generate_link_for_paid_payment(
        self, api_client, admin_headers, project, subscription, sample_payments,
    ):
        paid = sample_payments[0]

        resp = api_client.post(
            f'/api/accounts/projects/{project.id}/payments/{paid.id}/generate-link/',
            **admin_headers,
        )

        assert resp.status_code == 400

    def test_client_cannot_generate_link(
        self, api_client, client_headers, project, subscription, sample_payments,
    ):
        pending = sample_payments[1]

        resp = api_client.post(
            f'/api/accounts/projects/{project.id}/payments/{pending.id}/generate-link/',
            **client_headers,
        )

        assert resp.status_code == 403


# =========================================================================
# Wompi Webhook
# =========================================================================


@pytest.mark.django_db
class TestWompiWebhook:
    def test_approved_transaction_marks_payment_paid(
        self, api_client, subscription, sample_payments,
    ):
        pending = sample_payments[1]
        pending.wompi_payment_link_id = 'link_test_ref'
        pending.save(update_fields=['wompi_payment_link_id'])

        resp = api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': 'txn_123',
                'status': 'APPROVED',
                'reference': 'link_test_ref',
            }),
            format='json',
        )

        assert resp.status_code == 200
        pending.refresh_from_db()
        assert pending.status == Payment.STATUS_PAID
        assert pending.paid_at is not None
        assert pending.wompi_transaction_id == 'txn_123'

    def test_declined_transaction_marks_payment_failed(
        self, api_client, subscription, sample_payments,
    ):
        pending = sample_payments[1]
        pending.wompi_payment_link_id = 'link_declined'
        pending.save(update_fields=['wompi_payment_link_id'])

        resp = api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': 'txn_456',
                'status': 'DECLINED',
                'reference': 'link_declined',
            }),
            format='json',
        )

        assert resp.status_code == 200
        pending.refresh_from_db()
        assert pending.status == Payment.STATUS_FAILED

    def test_non_transaction_event_ignored(self, api_client):
        resp = api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({}, event='nequi_token.updated'),
            format='json',
        )

        assert resp.status_code == 200
        assert resp.json()['status'] == 'ignored'

    def test_unknown_reference_returns_404(self, api_client):
        resp = api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': 'txn_ghost',
                'status': 'APPROVED',
                'reference': 'nonexistent_ref',
            }),
            format='json',
        )

        assert resp.status_code == 404

    def test_approved_transaction_activates_pending_subscription(
        self, api_client, project,
    ):
        sub = HostingSubscription.objects.create(
            project=project, plan='monthly',
            base_monthly_amount=Decimal('100000'), discount_percent=0,
            effective_monthly_amount=Decimal('100000'), billing_amount=Decimal('100000'),
            start_date='2026-01-01', next_billing_date='2026-01-01',
            status=HostingSubscription.STATUS_PENDING,
        )
        payment = Payment.objects.create(
            subscription=sub, amount=Decimal('100000'),
            billing_period_start='2026-01-01', billing_period_end='2026-01-31',
            due_date='2026-01-01', status=Payment.STATUS_PENDING,
            wompi_payment_link_id='link_activate',
        )

        api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': 'txn_activate',
                'status': 'APPROVED',
                'reference': 'link_activate',
            }),
            format='json',
        )

        sub.refresh_from_db()
        assert sub.status == HostingSubscription.STATUS_ACTIVE


# =========================================================================
# Project creation with proposal link
# =========================================================================


@pytest.mark.django_db
class TestProjectCreationWithProposal:
    def test_create_project_with_proposal_links_but_no_subscription(
        self, api_client, admin_headers, client_user,
    ):
        from content.models import BusinessProposal

        proposal = BusinessProposal.objects.create(
            title='E-commerce proposal',
            client_name='Test Client',
            total_investment=Decimal('10000000'),
            hosting_percent=30,
            hosting_discount_quarterly=10,
            hosting_discount_semiannual=20,
            status='accepted',
        )

        resp = api_client.post('/api/accounts/projects/', {
            'name': 'E-commerce Project',
            'client_id': client_user.id,
            'proposal_id': proposal.id,
        }, format='json', **admin_headers)

        assert resp.status_code == 201
        data = resp.json()
        assert data['proposal_id'] == proposal.id

        project = Project.objects.get(id=data['id'])
        proposal.refresh_from_db()
        assert proposal.deliverable is not None
        assert proposal.deliverable.project_id == project.id
        assert not HostingSubscription.objects.filter(project=project).exists()

    def test_create_project_without_proposal(
        self, api_client, admin_headers, client_user,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Manual Project',
            'client_id': client_user.id,
        }, format='json', **admin_headers)

        assert resp.status_code == 201
        project = Project.objects.get(id=resp.json()['id'])
        assert project.linked_business_proposal() is None
        assert not HostingSubscription.objects.filter(project=project).exists()

    def test_create_project_with_invalid_proposal_fails(
        self, api_client, admin_headers, client_user,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Bad', 'client_id': client_user.id, 'proposal_id': 99999,
        }, format='json', **admin_headers)

        assert resp.status_code == 400


# =========================================================================
# Auto-create requirements from proposal
# =========================================================================


@pytest.fixture
def proposal_with_sections():
    from content.models import BusinessProposal, ProposalSection

    proposal = BusinessProposal.objects.create(
        title='Full Proposal',
        client_name='Test Corp',
        total_investment=Decimal('10000000'),
        hosting_percent=30,
        hosting_discount_quarterly=10,
        hosting_discount_semiannual=20,
        status='accepted',
    )

    ProposalSection.objects.create(
        proposal=proposal,
        section_type='functional_requirements',
        title='Requerimientos Funcionales',
        order=10,
        content_json={
            'groups': [
                {
                    'id': 'views',
                    'title': 'Vistas',
                    'is_visible': True,
                    'items': [
                        {'name': 'Landing Page', 'description': 'Main page'},
                        {'name': 'Catálogo', 'description': 'Product listing'},
                    ],
                },
                {
                    'id': 'features',
                    'title': 'Funcionalidades',
                    'is_visible': True,
                    'items': [
                        {'name': 'Responsive Design', 'description': 'Mobile support'},
                    ],
                },
                {
                    'id': 'hidden',
                    'title': 'Hidden Group',
                    'is_visible': False,
                    'items': [
                        {'name': 'Should Not Appear', 'description': 'Invisible'},
                    ],
                },
            ],
        },
    )

    ProposalSection.objects.create(
        proposal=proposal,
        section_type='investment',
        title='Inversión',
        order=4,
        content_json={
            'currency': 'COP',
            'paymentOptions': [
                {'label': '40% al firmar', 'description': '$4.000.000'},
                {'label': '30% al diseño', 'description': '$3.000.000'},
                {'label': '30% al deploy', 'description': '$3.000.000'},
            ],
            'hostingPlan': {
                'hostingPercent': 30,
                'billingTiers': [
                    {'frequency': 'semiannual', 'months': 6, 'discountPercent': 20, 'label': 'Semestral', 'badge': 'Mejor precio'},
                    {'frequency': 'quarterly', 'months': 3, 'discountPercent': 10, 'label': 'Trimestral', 'badge': '10% dcto'},
                    {'frequency': 'monthly', 'months': 1, 'discountPercent': 0, 'label': 'Mensual', 'badge': ''},
                ],
            },
        },
    )

    return proposal


@pytest.mark.django_db
class TestAutoCreateRequirements:
    def test_no_requirements_auto_created_from_proposal(
        self, api_client, admin_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Auto-Req Project',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        assert resp.status_code == 201
        project = Project.objects.get(id=resp.json()['id'])
        reqs = Requirement.objects.filter(stage__phase__scope__contract__project=project)

        assert reqs.count() == 0

    def test_project_from_proposal_has_no_hidden_requirements(
        self, api_client, admin_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Hidden Test',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project = Project.objects.get(id=resp.json()['id'])
        assert Requirement.objects.filter(stage__phase__scope__contract__project=project).count() == 0

    def test_project_from_proposal_stores_milestones(
        self, api_client, admin_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Milestones Check',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project = Project.objects.get(id=resp.json()['id'])
        assert project.payment_milestones is not None


# =========================================================================
# Payment milestones and hosting tiers extraction
# =========================================================================


@pytest.mark.django_db
class TestProposalFinancialExtraction:
    def test_payment_milestones_stored_on_project(
        self, api_client, admin_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Milestones Test',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project = Project.objects.get(id=resp.json()['id'])

        assert len(project.payment_milestones) == 3
        assert project.payment_milestones[0]['label'] == '40% al firmar'
        assert project.payment_milestones[2]['description'] == '$3.000.000'

    def test_hosting_tiers_stored_on_project(
        self, api_client, admin_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Tiers Test',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project = Project.objects.get(id=resp.json()['id'])

        assert len(project.hosting_tiers) == 3
        semi = next(t for t in project.hosting_tiers if t['frequency'] == 'semiannual')
        assert semi['discount_percent'] == 20
        assert semi['months'] == 6
        assert semi['base_monthly'] > 0

    def test_milestones_visible_to_admin_in_detail(
        self, api_client, admin_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Admin Visibility',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']
        detail = api_client.get(f'/api/accounts/projects/{project_id}/', **admin_headers)

        assert detail.status_code == 200
        assert len(detail.json()['payment_milestones']) == 3

    def test_milestones_hidden_from_client_in_detail(
        self, api_client, admin_headers, client_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Client Hidden',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']
        detail = api_client.get(f'/api/accounts/projects/{project_id}/', **client_headers)

        assert detail.status_code == 200
        assert detail.json()['payment_milestones'] == []

    def test_hosting_tiers_visible_to_both_roles(
        self, api_client, admin_headers, client_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Tiers Both Roles',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']

        admin_detail = api_client.get(f'/api/accounts/projects/{project_id}/', **admin_headers)
        client_detail = api_client.get(f'/api/accounts/projects/{project_id}/', **client_headers)

        assert len(admin_detail.json()['hosting_tiers']) == 3
        assert len(client_detail.json()['hosting_tiers']) == 3

    def test_project_without_proposal_has_empty_milestones(
        self, api_client, admin_headers, client_user,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'No Proposal',
            'client_id': client_user.id,
        }, format='json', **admin_headers)

        project = Project.objects.get(id=resp.json()['id'])

        assert project.payment_milestones == []
        assert project.hosting_tiers == []


# =========================================================================
# Auto-renewal: first payment created on subscription + next on approval
# =========================================================================


@pytest.mark.django_db
class TestAutoRenewal:
    def test_first_payment_created_when_client_chooses_plan(
        self, api_client, admin_headers, client_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'First Payment Test',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']

        sub_resp = api_client.post(
            f'/api/accounts/projects/{project_id}/subscription/',
            {'plan': 'quarterly'},
            format='json', **client_headers,
        )

        assert sub_resp.status_code == 201
        sub = HostingSubscription.objects.get(project_id=project_id)
        payments = Payment.objects.filter(subscription=sub)

        assert payments.count() == 1
        first = payments.first()
        assert first.status == Payment.STATUS_PENDING
        assert sub.plan == 'quarterly'

    def test_next_payment_generated_after_webhook_approval(
        self, api_client, project,
    ):
        sub = HostingSubscription.objects.create(
            project=project, plan='monthly',
            base_monthly_amount=Decimal('250000'), discount_percent=0,
            effective_monthly_amount=Decimal('250000'), billing_amount=Decimal('250000'),
            start_date='2026-01-01', next_billing_date='2026-01-01',
            status=HostingSubscription.STATUS_PENDING,
        )
        payment = Payment.objects.create(
            subscription=sub, amount=Decimal('250000'),
            billing_period_start='2026-01-01', billing_period_end='2026-01-31',
            due_date='2026-01-01', status=Payment.STATUS_PENDING,
            wompi_payment_link_id='link_renewal',
        )

        api_client.post(
            '/api/accounts/webhooks/wompi/',
            signed_transaction_event({
                'id': 'txn_renewal',
                'status': 'APPROVED',
                'reference': 'link_renewal',
            }),
            format='json',
        )

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_PAID

        hist = PaymentHistory.objects.filter(payment=payment).first()
        assert hist is not None
        assert hist.from_status == Payment.STATUS_PENDING
        assert hist.to_status == Payment.STATUS_PAID

        all_payments = Payment.objects.filter(subscription=sub).order_by('billing_period_start')
        assert all_payments.count() == 2

        next_pay = all_payments.last()
        assert next_pay.status == Payment.STATUS_PENDING
        assert next_pay.billing_period_start.isoformat() == '2026-02-01'

    def test_no_duplicate_pending_payment(
        self, api_client, project,
    ):
        sub = HostingSubscription.objects.create(
            project=project, plan='monthly',
            base_monthly_amount=Decimal('100000'), discount_percent=0,
            effective_monthly_amount=Decimal('100000'), billing_amount=Decimal('100000'),
            start_date='2026-01-01', next_billing_date='2026-02-01',
            status=HostingSubscription.STATUS_ACTIVE,
        )
        Payment.objects.create(
            subscription=sub, amount=Decimal('100000'),
            billing_period_start='2026-02-01', billing_period_end='2026-02-28',
            due_date='2026-02-01', status=Payment.STATUS_PENDING,
        )

        from accounts.views import _generate_next_payment
        result = _generate_next_payment(sub)

        assert result is None
        assert Payment.objects.filter(subscription=sub, status=Payment.STATUS_PENDING).count() == 1


# =========================================================================
# Client creates subscription via POST
# =========================================================================


@pytest.mark.django_db
class TestClientCreateSubscription:
    def test_client_creates_subscription_with_valid_plan(
        self, api_client, admin_headers, client_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Sub Create Test',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']

        sub_resp = api_client.post(
            f'/api/accounts/projects/{project_id}/subscription/',
            {'plan': 'semiannual'},
            format='json', **client_headers,
        )

        assert sub_resp.status_code == 201
        data = sub_resp.json()
        assert data['plan'] == 'semiannual'

    def test_duplicate_subscription_rejected(
        self, api_client, admin_headers, client_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Dup Sub Test',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']

        first = api_client.post(
            f'/api/accounts/projects/{project_id}/subscription/',
            {'plan': 'semiannual'},
            format='json', **client_headers,
        )
        assert first.status_code == 201

        second = api_client.post(
            f'/api/accounts/projects/{project_id}/subscription/',
            {'plan': 'quarterly'},
            format='json', **client_headers,
        )

        assert second.status_code == 400

    def test_no_proposal_project_rejected(
        self, api_client, admin_headers, client_headers, client_user,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'No Proposal Sub',
            'client_id': client_user.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']

        sub_resp = api_client.post(
            f'/api/accounts/projects/{project_id}/subscription/',
            {'plan': 'quarterly'},
            format='json', **client_headers,
        )

        assert sub_resp.status_code == 400

    def test_invalid_plan_rejected(
        self, api_client, admin_headers, client_headers, client_user, proposal_with_sections,
    ):
        resp = api_client.post('/api/accounts/projects/', {
            'name': 'Bad Plan',
            'client_id': client_user.id,
            'proposal_id': proposal_with_sections.id,
        }, format='json', **admin_headers)

        project_id = resp.json()['id']

        sub_resp = api_client.post(
            f'/api/accounts/projects/{project_id}/subscription/',
            {'plan': 'biennial'},
            format='json', **client_headers,
        )

        assert sub_resp.status_code == 400
