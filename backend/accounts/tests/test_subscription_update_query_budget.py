"""Query-budget and data-preservation contracts for subscription PATCH requests."""
from datetime import date
from decimal import Decimal

import pytest
from content.models import BusinessProposal
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import (
    HostingSubscription,
    Payment,
    PaymentHistory,
    Project,
    ProjectPhase,
    UserProfile,
)

User = get_user_model()
MAX_SUBSCRIPTION_STATUS_PATCH_QUERIES = 8


def _subscription_url(project_id):
    return f'/api/accounts/projects/{project_id}/subscription/'


def _subscription(project, *, status=HostingSubscription.STATUS_ACTIVE):
    subscription = HostingSubscription(
        project=project,
        plan=HostingSubscription.PLAN_QUARTERLY,
        base_monthly_amount=Decimal(300000),
        discount_percent=0,
        start_date=date(2026, 1, 1),
        next_billing_date=date(2026, 4, 1),
        status=status,
    )
    subscription.calculate_amounts()
    subscription.save()
    return subscription


def _payments_with_history(subscription, count, *, start=0):
    payments = Payment.objects.bulk_create([
        Payment(
            subscription=subscription,
            amount=subscription.billing_amount,
            description=f'Hosting payment {index}',
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 3, 31),
            due_date=date(2026, 1, 1),
            status=Payment.STATUS_PENDING,
        )
        for index in range(start, start + count)
    ])
    PaymentHistory.objects.bulk_create([
        PaymentHistory(
            payment=payment,
            from_status=Payment.STATUS_PENDING,
            to_status=Payment.STATUS_PENDING,
            source=PaymentHistory.SOURCE_SYSTEM,
        )
        for payment in payments
    ])


def _payment_selects(queries):
    payment_tables = (Payment._meta.db_table.lower(), PaymentHistory._meta.db_table.lower())
    return [
        query['sql'] for query in queries
        if query['sql'].lstrip().upper().startswith('SELECT')
        and any(table in query['sql'].lower() for table in payment_tables)
    ]


def _pending_subscription_with_archived_payment(project):
    proposal = BusinessProposal.objects.create(
        title='Subscription billing proposal',
        client_name='Subscription budget client',
        total_investment=Decimal(12000000),
        hosting_percent=30,
        hosting_discount_semiannual=20,
    )
    ProjectPhase.objects.create(
        project=project,
        business_proposal=proposal,
        order=1,
        hosting_activated_at=date(2026, 1, 1),
    )
    subscription = _subscription(project, status=HostingSubscription.STATUS_PENDING)
    archived = Payment.objects.create(
        subscription=subscription,
        amount=Decimal(900000),
        description='Archived pending payment',
        billing_period_start=date(2025, 10, 1),
        billing_period_end=date(2025, 12, 31),
        due_date=date(2025, 10, 1),
        status=Payment.STATUS_PENDING,
        is_archived=True,
    )
    active = Payment.objects.create(
        subscription=subscription,
        amount=Decimal(900000),
        description='Active pending payment',
        billing_period_start=date(2026, 1, 1),
        billing_period_end=date(2026, 3, 31),
        due_date=date(2026, 1, 1),
        status=Payment.STATUS_PENDING,
    )
    PaymentHistory.objects.create(
        payment=active,
        from_status=Payment.STATUS_PENDING,
        to_status=Payment.STATUS_PENDING,
        source=PaymentHistory.SOURCE_SYSTEM,
    )
    return subscription, archived, active


@pytest.fixture
def api_client():
    """Provide an API client for JWT-authenticated request contracts."""
    return APIClient()


@pytest.fixture
def users_and_headers(api_client):
    """Create administrator and client actors with real JWT credentials."""
    admin = User.objects.create_user(
        username='subscription-budget-admin@example.com',
        email='subscription-budget-admin@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=admin,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
        profile_completed=True,
    )
    client = User.objects.create_user(
        username='subscription-budget-client@example.com',
        email='subscription-budget-client@example.com',
        password='pass12345',
    )
    UserProfile.objects.create(
        user=client,
        role=UserProfile.ROLE_CLIENT,
        is_onboarded=True,
        profile_completed=True,
        created_by=admin,
    )
    admin_login = api_client.post('/api/accounts/login/', {
        'email': admin.email,
        'password': 'pass12345',
    })
    client_login = api_client.post('/api/accounts/login/', {
        'email': client.email,
        'password': 'pass12345',
    })
    admin_headers = {'HTTP_AUTHORIZATION': f"Bearer {admin_login.json()['tokens']['access']}"}
    client_headers = {'HTTP_AUTHORIZATION': f"Bearer {client_login.json()['tokens']['access']}"}
    return admin, client, admin_headers, client_headers


@pytest.fixture
def project(users_and_headers):
    """Create the client-owned project targeted by subscription requests."""
    _, client, _, _ = users_and_headers
    return Project.objects.create(name='Subscription budget project', client=client)


@pytest.mark.django_db
def test_status_patch_keeps_payment_history_queries_constant(
    api_client, users_and_headers, project,
):
    """Fails if a status PATCH reintroduces payment or history reads per payment."""
    _, _, admin_headers, _ = users_and_headers
    subscription = _subscription(project)
    _payments_with_history(subscription, 1)

    with CaptureQueriesContext(connection) as one_payment_queries:
        one_response = api_client.patch(
            _subscription_url(project.id),
            {'status': HostingSubscription.STATUS_SUSPENDED},
            format='json',
            **admin_headers,
        )

    _payments_with_history(subscription, 49, start=1)
    with CaptureQueriesContext(connection) as fifty_payment_queries:
        fifty_response = api_client.patch(
            _subscription_url(project.id),
            {'status': HostingSubscription.STATUS_ACTIVE},
            format='json',
            **admin_headers,
        )

    one_body = one_response.json()
    fifty_body = fifty_response.json()

    assert (one_response.status_code, fifty_response.status_code) == (400, 400)
    assert (one_body['code'], fifty_body['code']) == (
        'subscription_lifecycle_required', 'subscription_lifecycle_required',
    )
    subscription.refresh_from_db()
    assert subscription.status == HostingSubscription.STATUS_ACTIVE
    assert _payment_selects(one_payment_queries.captured_queries) == []
    assert _payment_selects(fifty_payment_queries.captured_queries) == []
    assert len(one_payment_queries) == len(fifty_payment_queries)
    assert len(fifty_payment_queries) <= MAX_SUBSCRIPTION_STATUS_PATCH_QUERIES


@pytest.mark.django_db
def test_pending_plan_patch_updates_the_earliest_active_payment(
    api_client, users_and_headers, project,
):
    """Fails if a pending plan change rewrites an archived payment instead of the active one."""
    _, _, _, client_headers = users_and_headers
    _, archived, active = _pending_subscription_with_archived_payment(project)

    response = api_client.patch(
        _subscription_url(project.id),
        {'plan': HostingSubscription.PLAN_SEMIANNUAL},
        format='json',
        **client_headers,
    )

    archived.refresh_from_db()
    active.refresh_from_db()
    assert response.status_code == 200
    assert (
        active.amount,
        active.billing_period_end,
        active.description,
    ) == (
        Decimal('1440000.00'),
        date(2026, 6, 30),
        'Hosting Semestral — 2026-01-01 a 2026-06-30',
    )
    assert (archived.amount, archived.description) == (Decimal(900000), 'Archived pending payment')


@pytest.mark.django_db
def test_pending_plan_patch_returns_active_payment_history(
    api_client, users_and_headers, project,
):
    """Fails if a successful pending plan change omits active payment history from its response."""
    _, _, _, client_headers = users_and_headers
    _, _, active = _pending_subscription_with_archived_payment(project)

    response = api_client.patch(
        _subscription_url(project.id),
        {'plan': HostingSubscription.PLAN_SEMIANNUAL},
        format='json',
        **client_headers,
    )

    body = response.json()
    assert (response.status_code, body['plan']) == (200, HostingSubscription.PLAN_SEMIANNUAL)
    assert [payment['id'] for payment in body['payments']] == [active.id]
    assert [item['to_status'] for item in body['payments'][0]['history']] == [Payment.STATUS_PENDING]


@pytest.mark.django_db
def test_client_status_patch_rejects_without_loading_payment_collections(
    api_client, users_and_headers, project,
):
    """Fails if a rejected client status PATCH prefetches payments or payment history."""
    _, _, _, client_headers = users_and_headers
    subscription = _subscription(project)
    _payments_with_history(subscription, 1)

    with CaptureQueriesContext(connection) as rejected_queries:
        response = api_client.patch(
            _subscription_url(project.id),
            {'status': HostingSubscription.STATUS_CANCELLED},
            format='json',
            **client_headers,
        )

    subscription.refresh_from_db()
    assert response.status_code == 400
    assert response.json()['code'] == 'subscription_lifecycle_required'
    assert _payment_selects(rejected_queries.captured_queries) == []
    assert subscription.status == HostingSubscription.STATUS_ACTIVE


@pytest.mark.django_db
def test_invalid_status_patch_rejects_without_loading_payment_collections(
    api_client, users_and_headers, project,
):
    """Fails if an invalid status PATCH prefetches payments before validation rejects it."""
    _, _, admin_headers, _ = users_and_headers
    subscription = _subscription(project)
    _payments_with_history(subscription, 1)

    with CaptureQueriesContext(connection) as rejected_queries:
        response = api_client.patch(
            _subscription_url(project.id),
            {'status': 'not-a-subscription-status'},
            format='json',
            **admin_headers,
        )

    subscription.refresh_from_db()
    assert response.status_code == 400
    assert _payment_selects(rejected_queries.captured_queries) == []
    assert subscription.status == HostingSubscription.STATUS_ACTIVE


@pytest.mark.django_db
def test_status_patch_returns_404_when_subscription_is_missing(
    api_client, users_and_headers, project,
):
    """Fails if optimized reverse-relation loading changes the missing-subscription response."""
    _, _, admin_headers, _ = users_and_headers

    response = api_client.patch(
        _subscription_url(project.id),
        {'status': HostingSubscription.STATUS_SUSPENDED},
        format='json',
        **admin_headers,
    )

    assert response.status_code == 404
    assert response.json() == {
        'detail': 'No hay suscripción de hosting para este proyecto.',
    }
