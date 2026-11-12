"""Online package checkout coverage at the Wompi provider boundary."""

from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest
import requests
from content.models import HourPackageSettings
from django.test import override_settings
from rest_framework.exceptions import ValidationError

from accounts.models_requirement_packages import (
    PackageMovement,
    PackageOrder,
    PackageProjectSettings,
)
from accounts.services import package_commerce as commerce

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.requirement_package_test_support',)


def online_order(context):
    """Create a reviewed online order through the real package commerce service."""
    quote = commerce.quote(context.package, context.project)
    created = commerce.create_order(
        context.project.pk,
        context.client,
        {
            'request_id': uuid4(),
            'package_id': context.package.pk,
            'method': 'online',
            'language': 'es',
            'conditions_accepted': True,
            'quote_digest': quote['quote_digest'],
        },
    )
    return PackageOrder.objects.get(pk=created['id'])


def literal_cop_online_order(context):
    """Create an online order with a real catalog price fixed at COP 25,000."""
    pricing = HourPackageSettings.load()
    pricing.xs_price_cop = Decimal(25000)
    pricing.save(update_fields=['xs_price_cop'])
    PackageProjectSettings.objects.update_or_create(
        project=context.project,
        defaults={'nationality': 'COL', 'tax_rate': Decimal('0.00')},
    )
    return online_order(context)


def unavailable_provider_post():
    """Return a provider boundary mock that fails before a payment link exists."""
    return Mock(side_effect=requests.RequestException('provider unavailable'))


def missing_link_provider_post():
    """Return a successful provider response without the required link identifier."""
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {'data': {}}
    return Mock(return_value=response)


@override_settings(
    WOMPI_PRIVATE_KEY='checkout-test-key',
    WOMPI_API_URL='https://wompi.example.test',
    FRONTEND_URL='https://platform.example.test',
)
def test_online_checkout_sends_a_single_use_cop_link_request(
    monkeypatch,
    package_context,
):
    """Fails if an online package checkout sends a non-COP or reusable provider link."""
    order = literal_cop_online_order(package_context)
    provider_response = Mock()
    provider_response.raise_for_status.return_value = None
    provider_response.json.return_value = {'data': {'id': 'wpl_checkout_001'}}
    provider_post = Mock(return_value=provider_response)
    monkeypatch.setattr(requests, 'post', provider_post)

    result = commerce.checkout(
        package_context.project.pk,
        package_context.client,
        order.pk,
        {'request_id': uuid4()},
    )

    order.refresh_from_db()
    sent = provider_post.call_args.kwargs['json']
    provider_post.assert_called_once()
    assert order.total == Decimal(25000)
    assert sent == {
        'name': order.snapshot['name'][:100],
        'description': f'Paquete {order.pk}',
        'single_use': True,
        'collect_shipping': False,
        'currency': 'COP',
        'amount_in_cents': 2500000,
        'redirect_url': (
            f'https://platform.example.test/es-co/platform/projects/{package_context.project.pk}/packages?order={order.pk}'
        ),
    }
    assert (
        result['checkout_url'],
        order.status,
        PackageMovement.objects.filter(order=order, kind='credit').count(),
    ) == ('https://checkout.wompi.co/l/wpl_checkout_001', 'processing', 0)


@override_settings(
    WOMPI_PRIVATE_KEY='checkout-test-key',
    WOMPI_API_URL='https://wompi.example.test',
    FRONTEND_URL='https://platform.example.test',
)
def test_online_checkout_reuses_the_provider_link_for_a_new_request_id(
    monkeypatch,
    package_context,
):
    """Fails if a checkout retry creates another provider link or credits capacity."""
    order = online_order(package_context)
    provider_response = Mock()
    provider_response.raise_for_status.return_value = None
    provider_response.json.return_value = {'data': {'id': 'wpl_checkout_retry'}}
    provider_post = Mock(return_value=provider_response)
    monkeypatch.setattr(requests, 'post', provider_post)

    first = commerce.checkout(
        package_context.project.pk,
        package_context.client,
        order.pk,
        {'request_id': uuid4()},
    )
    replay = commerce.checkout(
        package_context.project.pk,
        package_context.client,
        order.pk,
        {'request_id': uuid4()},
    )

    order.refresh_from_db()
    provider_post.assert_called_once()
    assert first['checkout_url'] == 'https://checkout.wompi.co/l/wpl_checkout_retry'
    assert replay['checkout_url'] == first['checkout_url']
    assert order.payment_link_id == 'wpl_checkout_retry'
    assert order.status == 'processing'
    assert PackageMovement.objects.filter(order=order, kind='credit').count() == 0


@pytest.mark.parametrize(
    ('provider_post_factory', 'message'),
    [
        (unavailable_provider_post, 'No se pudo preparar el pago. La compra sigue pendiente.'),
        (missing_link_provider_post, 'La pasarela no devolvió un enlace válido.'),
    ],
    ids=['request-exception', 'missing-link-id'],
)
@override_settings(
    WOMPI_PRIVATE_KEY='checkout-test-key',
    WOMPI_API_URL='https://wompi.example.test',
    FRONTEND_URL='https://platform.example.test',
)
def test_online_checkout_provider_failure_keeps_order_pending(
    monkeypatch,
    package_context,
    provider_post_factory,
    message,
):
    """Fails if a failed checkout response changes order state or credits capacity."""
    order = online_order(package_context)
    monkeypatch.setattr(requests, 'post', provider_post_factory())

    with pytest.raises(ValidationError) as error:
        commerce.checkout(
            package_context.project.pk,
            package_context.client,
            order.pk,
            {'request_id': uuid4()},
        )

    order.refresh_from_db()
    assert str(error.value.detail[0]) == message
    assert order.status == 'pending'
    assert order.payment_link_id is None
    assert PackageMovement.objects.filter(order=order, kind='credit').count() == 0
