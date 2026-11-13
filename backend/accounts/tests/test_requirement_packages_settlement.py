"""Settlement boundaries for requirement package orders after account closure."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Project
from accounts.models_requirement_packages import (
    PackageDecision,
    PackageMovement,
    PackageOrder,
)
from accounts.services import package_commerce as commerce
from accounts.services import package_requests
from accounts.tests.requirement_package_test_support import (
    decision_data,
    offer_xs,
    paid_order,
    publish_calculator,
    request_row,
)
from accounts.tests.wompi_event_helpers import signed_transaction_event

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.requirement_package_test_support',)


@pytest.fixture(autouse=True)
def package_settlement_clock():
    """Freeze canonical transaction timestamps used in settlement assertions."""
    with freeze_time('2026-11-12 12:00:00+00:00'):
        yield


def online_order(context, *, payment_link_id):
    """Create a pending online order bound to a deterministic Wompi payment link."""
    return PackageOrder.objects.create(
        project=context.project,
        client=context.client,
        package=context.package,
        snapshot={'counts': {'XS': 1, 'S': 0, 'M': 0}, 'validity_months': 12, 'language': 'es'},
        currency='COP',
        subtotal=Decimal(100),
        tax_rate=Decimal(0),
        total=Decimal(100),
        method='online',
        payment_link_id=payment_link_id,
        recorded_by=context.client,
    )


@freeze_time('2026-11-12 12:00:00+00:00')
def test_signed_webhook_credits_existing_order_after_client_archive(package_context, api_client, monkeypatch):
    """Fails if a canonical paid package is abandoned after its client is archived."""
    order = online_order(package_context, payment_link_id='late-settlement-link')
    transaction = {
        'id': 'late-settlement-transaction',
        'payment_link_id': 'late-settlement-link',
        'amount_in_cents': 10000,
        'currency': 'COP',
        'status': 'APPROVED',
        'created_at': timezone.now().isoformat(),
    }
    package_context.project.status = Project.STATUS_SUSPENDED
    package_context.project.save(update_fields=['status', 'updated_at'])
    package_context.client.profile.archived_at = timezone.now()
    package_context.client.profile.save(update_fields=['archived_at', 'updated_at'])
    package_context.client.is_active = False
    package_context.client.save(update_fields=['is_active'])
    monkeypatch.setattr('accounts.services.wompi.verify_transaction', lambda _transaction_id: transaction)
    event = signed_transaction_event(transaction)

    response = api_client.post('/api/accounts/webhooks/wompi/', event, format='json')
    replay = api_client.post('/api/accounts/webhooks/wompi/', event, format='json')

    order.refresh_from_db()
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert replay.status_code == 200
    assert replay.json() == {'status': 'ok'}
    assert order.status == 'paid'
    assert order.transaction_id == 'late-settlement-transaction'
    assert list(PackageMovement.objects.filter(order=order, kind='credit').order_by('pk').values_list('size', 'quantity')) == [('XS', 1)]


def test_suspended_project_rejects_new_package_order(package_context):
    """Fails if the settlement exception lets a suspended project start another purchase."""
    quote = commerce.quote(package_context.package, package_context.project)
    package_context.project.status = Project.STATUS_SUSPENDED
    package_context.project.save(update_fields=['status', 'updated_at'])

    with pytest.raises(ValidationError) as error:
        commerce.create_order(package_context.project.pk, package_context.client, {
            'request_id': 'a37cd7b9-0259-4d64-ae6a-2b46edba6f12',
            'package_id': package_context.package.pk,
            'method': 'external',
            'language': 'es',
            'conditions_accepted': True,
            'quote_digest': quote['quote_digest'],
        })

    assert error.value.status_code == 400
    assert PackageOrder.objects.count() == 0


@freeze_time('2026-11-12 12:00:00+00:00')
def test_suspended_order_rejects_authenticated_payment_verification(package_context, api_client, monkeypatch):
    """Fails if the webhook exception lets an authenticated client settle a suspended project."""
    order = online_order(package_context, payment_link_id='normal-verification-link')
    transaction = {
        'id': 'normal-verification-transaction',
        'payment_link_id': 'normal-verification-link',
        'amount_in_cents': 10000,
        'currency': 'COP',
        'status': 'APPROVED',
        'created_at': timezone.now().isoformat(),
    }
    package_context.project.status = Project.STATUS_SUSPENDED
    package_context.project.save(update_fields=['status', 'updated_at'])
    monkeypatch.setattr('accounts.services.wompi.verify_transaction', lambda _transaction_id: transaction)
    api_client.force_authenticate(user=package_context.client)

    response = api_client.post(
        reverse('package-order-action', args=[package_context.project.pk, order.pk, 'verify']),
        {'request_id': 'f7d58cc5-139d-4ef3-ac6e-65ced334acb3', 'transaction_id': transaction['id']},
        format='json',
    )

    order.refresh_from_db()
    assert response.status_code == 400
    assert order.status == 'pending'
    assert order.transaction_id is None
    assert PackageMovement.objects.filter(order=order, kind='credit').count() == 0


@freeze_time('2026-11-12 12:00:00+00:00')
def test_archived_inactive_client_rejects_package_consent(package_context):
    """Fails if the trusted webhook path lets an archived client record new consent."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)
    row.refresh_from_db()
    package_context.client.profile.archived_at = timezone.now()
    package_context.client.profile.save(update_fields=['archived_at', 'updated_at'])
    package_context.client.is_active = False
    package_context.client.save(update_fields=['is_active'])

    with pytest.raises(PermissionDenied) as error:
        package_requests.decide(
            package_context.project.pk,
            package_context.client,
            row.pk,
            decision_data(row, order_id=order.pk),
        )

    assert error.value.status_code == 403
    assert PackageDecision.objects.count() == 0
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 0
