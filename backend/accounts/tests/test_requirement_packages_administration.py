"""Administrative payment, allowance and evaluation behavior for requirement packages."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from content.models import HourPackageSettings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.exceptions import ValidationError

from accounts.models import ChangeRequest, Notification
from accounts.models_requirement_packages import (
    PackageMovement,
    PackageOrder,
    PackageProjectSettings,
)
from accounts.services import package_commerce as commerce
from accounts.services import package_requests
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.requirement_package_test_support import (
    decision_data,
    offer_xs,
    paid_order,
    publish_calculator,
    request_row,
)

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.requirement_package_test_support',)

PAID_AT = datetime(2026, 11, 10, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def administration_clock():
    """Freeze expiry and future-payment checks around each package operation."""
    with freeze_time('2026-11-12 12:00:00+00:00'):
        yield


def external_order(context):
    """Create one reviewed external order through the real commerce service."""
    quote = commerce.quote(context.package, context.project)
    created = commerce.create_order(
        context.project.pk,
        context.client,
        {
            'request_id': uuid4(),
            'package_id': context.package.pk,
            'method': 'external',
            'language': 'es',
            'conditions_accepted': True,
            'quote_digest': quote['quote_digest'],
        },
    )
    return PackageOrder.objects.get(pk=created['id'])


def external_payment_data(request_id=None):
    """Build one settled external-payment payload with a past payment timestamp."""
    return {
        'request_id': request_id or uuid4(),
        'paid_at': PAID_AT,
        'payment_reference': 'TRANSFER-2026-11-10-001',
    }


def debited_xs_order(context):
    """Create one paid XS order after explicit client consent consumes its allowance."""
    publish_calculator(context)
    order = paid_order(context)
    row = request_row(context)
    offer_xs(context, row)
    row.refresh_from_db()
    package_requests.decide(
        context.project.pk,
        context.client,
        row.pk,
        decision_data(row, order_id=order.pk),
    )
    return order, PackageMovement.objects.get(order=order, kind='debit')


def set_xs_catalog_price(amount):
    """Persist one known internal XS price for a real catalog quote."""
    settings = HourPackageSettings.load()
    settings.xs_price_cop = amount
    settings.save(update_fields=['xs_price_cop'])


def test_external_payment_activates_the_order_with_exact_credits_and_expiry(
    package_context,
    api_client,
):
    """Fails if an approved external payment does not activate the purchased XS allowance."""
    order = external_order(package_context)
    api_client.force_authenticate(user=package_context.admin)

    response = api_client.post(
        reverse(
            'package-order-action',
            args=[package_context.project.pk, order.pk, 'confirm-external'],
        ),
        {
            'request_id': str(uuid4()),
            'paid_at': '2026-11-10T15:00:00Z',
            'payment_reference': 'TRANSFER-2026-11-10-001',
        },
        format='json',
    )

    order.refresh_from_db()
    assert response.status_code == 200
    assert response.data['status'] == 'paid'
    assert order.payment_reference == 'TRANSFER-2026-11-10-001'
    assert order.paid_at == PAID_AT
    assert order.expires_at == datetime(2027, 11, 10, 15, 0, tzinfo=UTC)
    assert list(
        PackageMovement.objects.filter(order=order)
        .order_by('pk')
        .values_list('kind', 'size', 'quantity')
    ) == [('credit', 'XS', 1)]


def test_external_payment_replay_keeps_one_credit(package_context):
    """Fails if replaying one external payment receipt credits the package twice."""
    order = external_order(package_context)
    data = external_payment_data(uuid4())

    first = commerce.confirm_external(
        package_context.project.pk,
        package_context.admin,
        order.pk,
        data,
    )
    replay = commerce.confirm_external(
        package_context.project.pk,
        package_context.admin,
        order.pk,
        data,
    )

    order.refresh_from_db()
    assert replay == first
    assert order.status == 'paid'
    assert PackageMovement.objects.filter(order=order, kind='credit').count() == 1


def test_reverse_debit_restores_the_original_order_allowance(
    package_context,
    api_client,
):
    """Fails if reversing a consent debit changes the original paid order or expiry."""
    order, debit = debited_xs_order(package_context)
    original_expiry = order.expires_at
    api_client.force_authenticate(user=package_context.admin)

    response = api_client.post(
        reverse(
            'package-reverse',
            args=[package_context.project.pk, debit.pk],
        ),
        {'request_id': uuid4(), 'reason': 'El alcance aceptado fue corregido.'},
        format='json',
    )

    order.refresh_from_db()
    assert response.status_code == 200
    assert response.data['balances'] == {'XS': 1, 'S': 0, 'M': 0}
    assert order.status == 'paid'
    assert order.expires_at == original_expiry
    assert list(
        PackageMovement.objects.filter(order=order)
        .order_by('pk')
        .values_list('kind', 'quantity')
    ) == [('credit', 1), ('debit', -1), ('reversal', 1)]


def test_reverse_debit_rejects_a_second_credit_restoration(package_context):
    """Fails if a corrected requirement can restore the same XS allowance twice."""
    order, debit = debited_xs_order(package_context)
    commerce.reverse_movement(
        package_context.project.pk,
        package_context.admin,
        debit.pk,
        {'request_id': uuid4(), 'reason': 'Corrección administrativa.'},
    )

    with pytest.raises(ValidationError) as error:
        commerce.reverse_movement(
            package_context.project.pk,
            package_context.admin,
            debit.pk,
            {'request_id': uuid4(), 'reason': 'Intento duplicado.'},
        )

    assert str(error.value.detail[0]) == 'El consumo ya fue revertido.'
    assert PackageMovement.objects.filter(order=order, kind='reversal').count() == 1


def test_package_settings_rejects_a_stale_version(package_context):
    """Fails if a stale settings editor overwrites a newer package configuration."""
    first = commerce.update_settings(
        package_context.project.pk,
        package_context.admin,
        {
            'request_id': uuid4(),
            'expected_version': 0,
            'nationality': 'COL',
            'tax_rate': Decimal('7.00'),
        },
    )

    with pytest.raises(DeliveryConflict) as error:
        commerce.update_settings(
            package_context.project.pk,
            package_context.admin,
            {
                'request_id': uuid4(),
                'expected_version': 0,
                'nationality': 'COL',
                'tax_rate': Decimal('0.00'),
            },
        )

    settings = PackageProjectSettings.objects.get(project=package_context.project)
    assert first == {'nationality': 'COL', 'tax_rate': '7.00', 'version': 1}
    assert error.value.status_code == 409
    assert (settings.tax_rate, settings.version) == (Decimal('7.00'), 1)


def test_package_settings_leave_an_existing_order_snapshot_unchanged(
    package_context,
    api_client,
):
    """Fails if a tax update rewrites the quoted total preserved by an older order."""
    set_xs_catalog_price(Decimal('1000.00'))
    earlier = external_order(package_context)
    earlier_snapshot = earlier.snapshot.copy()
    api_client.force_authenticate(user=package_context.admin)

    response = api_client.post(
        reverse('package-settings', args=[package_context.project.pk]),
        {
            'request_id': str(uuid4()),
            'expected_version': 0,
            'nationality': 'COL',
            'tax_rate': '0.00',
        },
        format='json',
    )

    later = external_order(package_context)

    earlier.refresh_from_db()
    assert response.status_code == 200
    assert response.data == {'nationality': 'COL', 'tax_rate': '0.00', 'version': 1}
    assert earlier.snapshot == earlier_snapshot
    assert (earlier.total, earlier.snapshot['tax_rate']) == (Decimal(1190), '19')
    assert (later.total, later.snapshot['tax_rate']) == (Decimal(1000), '0.00')


def test_begin_evaluation_marks_the_request_without_a_debit(
    package_context,
    api_client,
):
    """Fails if beginning manual evaluation consumes a paid XS allowance."""
    order = paid_order(package_context)
    row = request_row(package_context)
    before = list(
        PackageMovement.objects.filter(order=order)
        .order_by('pk')
        .values_list('kind', 'size', 'quantity')
    )

    api_client.force_authenticate(user=package_context.admin)
    response = api_client.post(
        reverse(
            'package-request-action',
            args=[package_context.project.pk, row.pk, 'evaluate'],
        ),
        {'request_id': str(uuid4()), 'expected_version': 0},
        format='json',
    )

    row.refresh_from_db()
    notification = Notification.objects.get(
        user=package_context.client,
        project=package_context.project,
        related_object_type='package_request',
        related_object_id=row.pk,
    )
    after = list(
        PackageMovement.objects.filter(order=order)
        .order_by('pk')
        .values_list('kind', 'size', 'quantity')
    )
    assert response.status_code == 200
    assert (response.data['status'], row.status, row.version) == ('evaluating', 'evaluating', 1)
    assert row.ticket.status == ChangeRequest.STATUS_EVALUATING
    assert (notification.title, notification.message) == (
        'Estamos evaluando: Actualizar tablero',
        '',
    )
    assert after == before == [('credit', 'XS', 1)]


def test_external_payment_api_rejects_a_future_paid_at(package_context, api_client):
    """Fails if the external-payment API records a payment timestamp after today."""
    order = external_order(package_context)
    api_client.force_authenticate(user=package_context.admin)

    response = api_client.post(
        reverse(
            'package-order-action',
            args=[package_context.project.pk, order.pk, 'confirm-external'],
        ),
        {
            'request_id': str(uuid4()),
            'paid_at': '2026-11-13T12:00:00Z',
            'payment_reference': 'TRANSFER-FUTURE',
        },
        format='json',
    )

    order.refresh_from_db()
    assert response.status_code == 400
    assert response.data['paid_at'] == ['La fecha del pago no puede estar en el futuro.']
    assert order.status == 'pending'
    assert PackageMovement.objects.filter(order=order, kind='credit').count() == 0


def test_order_api_rejects_unaccepted_conditions(package_context, api_client):
    """Fails if an order can be created before the client accepts its quoted conditions."""
    quote = commerce.quote(package_context.package, package_context.project)
    api_client.force_authenticate(user=package_context.client)

    response = api_client.post(
        reverse('package-order-create', args=[package_context.project.pk]),
        {
            'request_id': str(uuid4()),
            'package_id': package_context.package.pk,
            'method': 'external',
            'language': 'es',
            'conditions_accepted': False,
            'quote_digest': quote['quote_digest'],
        },
        format='json',
    )

    assert response.status_code == 400
    assert response.data['conditions_accepted'] == [
        'Acepta las condiciones antes de crear la compra.',
    ]
    assert PackageOrder.objects.count() == 0
