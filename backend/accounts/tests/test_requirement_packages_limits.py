"""Boundary behavior for requirement package consent and allowance limits."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models_requirement_packages import PackageDecision, PackageMovement
from accounts.services import package_requests
from accounts.tests.requirement_package_test_support import (
    decision_data,
    offer_xs,
    paid_order,
    publish_calculator,
    request_row,
)

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.requirement_package_test_support',)


@pytest.fixture(autouse=True)
def package_limits_clock():
    """Freeze allowance expiry comparisons for each package limit scenario."""
    with freeze_time('2026-11-12 12:00:00+00:00'):
        yield


def test_warranty_xs_accepts_without_a_paid_allowance(package_context):
    """Fails if a warranty correction consumes a package allowance or requires a purchase."""
    publish_calculator(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row, warranty=True)
    row.refresh_from_db()

    result = package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                     decision_data(row, order_id=None))

    row.refresh_from_db()
    assert row.status == 'accepted'
    assert result['balances'] == {'XS': 0, 'S': 0, 'M': 0}
    assert PackageMovement.objects.filter(kind='debit').count() == 0


@pytest.mark.parametrize('size', ['L', 'XL', 'PROJECT'])
def test_non_package_size_rejects_allowance_consent(package_context, size):
    """Fails if a separately quoted size can be accepted as a package allowance."""
    publish_calculator(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row, size=size)
    row.refresh_from_db()

    with pytest.raises(ValidationError) as error:
        package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                decision_data(row, order_id=None))

    row.refresh_from_db()
    assert error.value.status_code == 400
    assert row.status == 'offered'
    assert PackageDecision.objects.count() == 0


@freeze_time('2026-11-12 12:00:00+00:00')
def test_expired_allowance_rejects_client_acceptance(package_context):
    """Fails if an expired purchase can still authorize a requirement debit."""
    publish_calculator(package_context)
    order = paid_order(package_context, expires_at=timezone.now() - timedelta(seconds=1))
    row = request_row(package_context)
    offer_xs(package_context, row)
    row.refresh_from_db()

    with pytest.raises(ValidationError) as error:
        package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                decision_data(row, order_id=order.pk))

    assert error.value.status_code == 400
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 0


def test_impersonated_client_jwt_cannot_accept_its_own_package_request(package_context, api_client):
    """Fails if an administrator impersonating the owner can record client consent."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)
    row.refresh_from_db()
    token = AccessToken.for_user(package_context.client)
    token['impersonated_by'] = package_context.admin.pk
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    payload = decision_data(row, order_id=order.pk)
    payload['request_id'] = str(payload['request_id'])
    payload['order_id'] = str(payload['order_id'])

    response = api_client.post(
        f'/api/requirement-packages/projects/{package_context.project.pk}/requests/{row.pk}/decide/',
        payload,
        format='json',
    )

    assert response.status_code == PermissionDenied.status_code
    assert PackageDecision.objects.count() == 0
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 0


def test_objection_requires_a_reoffer_before_new_package_consent(package_context):
    """Fails if objecting preserves a consumable offer or debits an allowance before a new response."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)
    row.refresh_from_db()
    objection = {
        'request_id': uuid4(), 'expected_version': row.version, 'proposal_id': row.current_proposal_id,
        'decision': 'object', 'message': 'Necesito ajustar el alcance.', 'order_id': None,
    }

    package_requests.decide(package_context.project.pk, package_context.client, row.pk, objection)
    row.refresh_from_db()
    with pytest.raises(ValidationError):
        package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                decision_data(row, order_id=order.pk))
    offer_xs(package_context, row)
    row.refresh_from_db()
    package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                            decision_data(row, order_id=order.pk))

    row.refresh_from_db()
    assert row.status == 'accepted'
    assert PackageDecision.objects.filter(decision='object').count() == 1
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 1


def test_second_request_cannot_spend_an_exhausted_last_allowance(package_context):
    """Fails if sequential requests can drive one remaining XS allowance below zero."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    first = request_row(package_context)
    second = request_row(package_context)
    second.ticket.title = 'Actualizar otro tablero'
    second.ticket.save(update_fields=['title', 'updated_at'])
    offer_xs(package_context, first)
    offer_xs(package_context, second)
    first.refresh_from_db()
    second.refresh_from_db()

    package_requests.decide(package_context.project.pk, package_context.client, first.pk,
                            decision_data(first, order_id=order.pk))
    with pytest.raises(ValidationError):
        package_requests.decide(package_context.project.pk, package_context.client, second.pk,
                                decision_data(second, order_id=order.pk))

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == 'accepted'
    assert second.status == 'offered'
    assert list(PackageMovement.objects.filter(order=order).order_by('pk').values_list('quantity', flat=True)) == [1, -1]
