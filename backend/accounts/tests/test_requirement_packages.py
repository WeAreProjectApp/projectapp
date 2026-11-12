"""Behavior coverage for project-owned requirement package purchases and consent."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from content.services import client_merge
from content.services.project_force_deletion import forced_deletion_preview
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Notification, UserProfile
from accounts.models_requirement_packages import (
    PackageDecision,
    PackageExampleRevision,
    PackageMovement,
    PackageOrder,
)
from accounts.services import package_commerce as commerce
from accounts.services import package_examples, package_requests
from accounts.services.delivery_access import DeliveryConflict
from accounts.services.delivery_client_transfer import (
    assert_delivery_client_transfer_safe,
)
from accounts.tests.requirement_package_test_support import (
    decision_data,
    offer_xs,
    paid_order,
    publish_calculator,
    request_row,
)

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.requirement_package_test_support',)
User = get_user_model()


@pytest.fixture(autouse=True)
def package_clock():
    """Freeze expiry and payment timestamps used by package lifecycle assertions."""
    with freeze_time('2026-11-12 12:00:00+00:00'):
        yield


def example_source(catalog, size):
    """Return the displayed source label for one size from a public catalog."""
    return next(row['source'] for row in catalog['sizes'] if row['size'] == size)


def examples_for_size(catalog, size):
    """Return the public examples displayed for one size from a catalog."""
    return next(row['examples'] for row in catalog['sizes'] if row['size'] == size)


def has_blocking_package_ownership(plan, relation):
    """Report whether a merge plan blocks one retained package ownership relation."""
    return any(
        row['relation'] == relation and row['policy'] == 'blocks_merge'
        for row in plan['relations']
    )


def test_client_request_notifies_the_project_team(package_context):
    """Fails if a client package request is created without an in-app team notification."""
    result = package_requests.create_request(package_context.project.pk, package_context.client, {
        'request_id': uuid4(),
        'title': 'Actualizar tablero',
        'description': 'Mostrar una métrica.',
    })

    notification = Notification.objects.filter(
        user=package_context.admin,
        project=package_context.project,
        type=Notification.TYPE_GENERAL,
        related_object_type='package_request',
        related_object_id=result['id'],
    )

    assert list(notification.values_list('title', 'message', 'is_read')) == [
        ('Nueva solicitud: Actualizar tablero', '', False),
    ]


def test_order_rejects_a_quote_digest_that_changed_after_review(package_context):
    """Fails if a purchase can use catalog conditions the client did not review."""
    current = commerce.quote(package_context.package, package_context.project)
    package_context.package.discount_percent = 10
    package_context.package.save(update_fields=['discount_percent'])

    with pytest.raises(DeliveryConflict) as error:
        commerce.create_order(package_context.project.pk, package_context.client, {
            'request_id': uuid4(), 'package_id': package_context.package.pk, 'method': 'external',
            'language': 'es', 'conditions_accepted': True, 'quote_digest': current['quote_digest'],
        })

    assert error.value.status_code == 409
    assert PackageOrder.objects.count() == 0


@pytest.mark.parametrize('transaction_change', [
    {'payment_link_id': 'foreign-link'}, {'amount_in_cents': 10001}, {'currency': 'USD'},
], ids=['foreign-link', 'foreign-amount', 'foreign-currency'])
@freeze_time('2026-11-12 12:00:00+00:00')
def test_online_payment_rejects_a_transaction_from_another_order(package_context, transaction_change, api_client, monkeypatch):
    """Fails if a foreign Wompi transaction can credit this project's allowances."""
    order = PackageOrder.objects.create(
        project=package_context.project, client=package_context.client, package=package_context.package,
        snapshot={'counts': {'XS': 1, 'S': 0, 'M': 0}, 'validity_months': 12}, currency='COP',
        subtotal=Decimal(100), tax_rate=Decimal(0), total=Decimal(100), method='online',
        payment_link_id='expected-link', recorded_by=package_context.client,
    )
    transaction = {
        'id': 'transaction-001', 'payment_link_id': 'expected-link', 'amount_in_cents': 10000,
        'currency': 'COP', 'status': 'APPROVED', 'created_at': timezone.now().isoformat(),
    } | transaction_change

    monkeypatch.setattr('accounts.services.wompi.verify_transaction', lambda _transaction_id: transaction)
    api_client.force_authenticate(user=package_context.client)
    response = api_client.post(
        reverse('package-order-action', args=[package_context.project.pk, order.pk, 'verify']),
        {'request_id': str(uuid4()), 'transaction_id': 'transaction-001'}, format='json',
    )

    order.refresh_from_db()
    assert response.status_code == 400
    assert order.status == 'pending'
    assert PackageMovement.objects.filter(order=order, kind='credit').count() == 0


@freeze_time('2026-11-12 12:00:00+00:00')
def test_repeated_approved_transaction_credits_each_size_once(package_context):
    """Fails if a callback retry duplicates the paid package's allowance credit."""
    order = PackageOrder.objects.create(
        project=package_context.project, client=package_context.client, package=package_context.package,
        snapshot={'counts': {'XS': 1, 'S': 0, 'M': 0}, 'validity_months': 12}, currency='COP',
        subtotal=Decimal(100), tax_rate=Decimal(0), total=Decimal(100), method='online',
        payment_link_id='retry-link', recorded_by=package_context.client,
    )
    transaction = {
        'id': 'transaction-retry', 'payment_link_id': 'retry-link', 'amount_in_cents': 10000,
        'currency': 'COP', 'status': 'APPROVED', 'created_at': timezone.now().isoformat(),
    }

    commerce.apply_transaction(package_context.project.pk, package_context.client, order.pk,
                               {'request_id': uuid4(), 'transaction_id': 'transaction-retry'}, transaction)
    commerce.apply_transaction(package_context.project.pk, package_context.client, order.pk,
                               {'request_id': uuid4(), 'transaction_id': 'transaction-retry'}, transaction)

    order.refresh_from_db()
    assert order.status == 'paid'
    assert PackageOrder.objects.filter(pk=order.pk, status='paid').count() == 1
    assert list(PackageMovement.objects.filter(order=order, kind='credit').values_list('size', 'quantity')) == [('XS', 1)]


def test_pending_request_offer_defers_xs_debit_until_client_consent(package_context):
    """Fails if manual sizing debits an allowance before the owner accepts it."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)

    offer_xs(package_context, row)
    row.refresh_from_db()
    before = package_requests.request_payload(row)
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 0
    result = package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                     decision_data(row, order_id=before['suggested_order_id']))

    row.refresh_from_db()
    assert row.status == 'accepted'
    assert result['balances']['XS'] == 0
    assert PackageDecision.objects.filter(proposal=row.current_proposal, decision='accept').count() == 1
    assert list(PackageMovement.objects.filter(order=order, kind='debit').values_list('size', 'quantity')) == [('XS', -1)]


def test_stale_proposal_acceptance_preserves_the_available_allowance(package_context):
    """Fails if an outdated client screen can consume the last XS allowance."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)

    with pytest.raises(DeliveryConflict) as error:
        package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                decision_data(row, order_id=order.pk, version=0))

    row.refresh_from_db()
    assert error.value.status_code == 409
    assert row.status == 'offered'
    assert PackageDecision.objects.count() == 0
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 0


def test_other_client_cannot_accept_a_project_package_request(package_context):
    """Fails if a client outside the project can consent to another client's purchase."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)
    outsider = User.objects.create_user('package-outsider', email='package-outsider@example.test')
    UserProfile.objects.create(user=outsider, role=UserProfile.ROLE_CLIENT)

    with pytest.raises(NotFound) as error:
        package_requests.decide(package_context.project.pk, outsider, row.pk, decision_data(row, order_id=order.pk))

    row.refresh_from_db()
    assert error.value.status_code == 404
    assert row.status == 'offered'
    assert PackageDecision.objects.count() == 0
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 0


def test_revised_offer_replaces_an_accepted_debit_only_after_new_consent(package_context):
    """Fails if a revision changes allowance consumption without a fresh customer decision."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)
    row.refresh_from_db()
    package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                            decision_data(row, order_id=order.pk))
    row.refresh_from_db()

    offer_xs(package_context, row)
    row.refresh_from_db()
    after_offer = list(PackageMovement.objects.filter(order=order).order_by('pk').values_list('kind', 'quantity'))
    package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                            decision_data(row, order_id=package_requests.request_payload(row)['suggested_order_id']))

    row.refresh_from_db()
    assert row.status == 'accepted'
    assert after_offer == [('credit', 1), ('debit', -1)]
    assert PackageMovement.objects.filter(order=order, kind='reversal', quantity=1).count() == 1
    assert PackageMovement.objects.filter(order=order, kind='debit', reversal__isnull=True).count() == 1


@freeze_time('2026-11-12 12:00:00+00:00')
def test_revised_offer_keeps_previous_debit_when_no_replacement_allowance_exists(package_context):
    """Fails if a rejected replacement reverses a prior accepted allowance outside its transaction."""
    publish_calculator(package_context)
    order = paid_order(package_context)
    row = request_row(package_context)
    offer_xs(package_context, row)
    row.refresh_from_db()
    package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                            decision_data(row, order_id=order.pk))
    order.expires_at = timezone.now() - timedelta(seconds=1)
    order.save(update_fields=['expires_at'])
    row.refresh_from_db()
    offer_xs(package_context, row)
    row.refresh_from_db()

    with pytest.raises(ValidationError):
        package_requests.decide(package_context.project.pk, package_context.client, row.pk,
                                decision_data(row, order_id=order.pk))

    row.refresh_from_db()
    assert row.status == 'offered'
    assert PackageMovement.objects.filter(order=order, kind='debit').count() == 1
    assert PackageMovement.objects.filter(order=order, kind='reversal').count() == 0


def test_project_examples_fall_back_per_size(package_context):
    """Fails if a partial project override hides the generic example for another size."""
    first_request = uuid4()
    payload = {'request_id': first_request, 'expected_revision': 0, 'examples': {'XS': ['Cambiar una etiqueta propia.']},
               'note': 'Ejemplo del proyecto'}
    before = package_examples.example_catalog(package_context.project.pk)

    first = package_examples.publish_examples(package_context.admin, payload, project_id=package_context.project.pk)

    assert example_source(first, 'XS') == 'project'
    assert example_source(first, 'S') == 'generic'
    assert examples_for_size(first, 'S') == examples_for_size(before, 'S')
    assert PackageExampleRevision.objects.filter(project=package_context.project).count() == 1


def test_project_examples_replay_keeps_one_revision(package_context):
    """Fails if retrying a published examples request duplicates its immutable history row."""
    payload = {'request_id': uuid4(), 'expected_revision': 0, 'examples': {'XS': ['Cambiar una etiqueta propia.']},
               'note': 'Ejemplo del proyecto'}

    first = package_examples.publish_examples(package_context.admin, payload, project_id=package_context.project.pk)
    replay = package_examples.publish_examples(package_context.admin, payload, project_id=package_context.project.pk)

    assert replay['project_revision'] == first['project_revision']
    assert PackageExampleRevision.objects.filter(project=package_context.project).count() == 1


def test_project_examples_reject_a_stale_expected_revision(package_context):
    """Fails if an older examples editor overwrites the published project explanation."""
    package_examples.publish_examples(package_context.admin, {
        'request_id': uuid4(), 'expected_revision': 0, 'examples': {'XS': ['Primera explicación.']}, 'note': 'Primera versión',
    }, project_id=package_context.project.pk)

    with pytest.raises(DeliveryConflict) as error:
        package_examples.publish_examples(package_context.admin, {
            'request_id': uuid4(), 'expected_revision': 0, 'examples': {'XS': ['Explicación vieja.']}, 'note': 'Versión vieja',
        }, project_id=package_context.project.pk)

    assert error.value.status_code == 409
    assert PackageExampleRevision.objects.filter(project=package_context.project).count() == 1


def _jwt_client(api_client, user):
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api_client


def test_platform_jwt_profile_admin_can_open_package_queue_without_staff(api_client):
    """Fails if a valid Platform administrator is rejected because Django staff is false."""
    user = User.objects.create_user('jwt-profile-admin', email='jwt-profile-admin@example.test', is_staff=False)
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN)

    response = _jwt_client(api_client, user).get(reverse('package-admin-queue'))

    assert response.status_code == 200
    assert response.data['pending_count'] == 0


def test_platform_jwt_profile_admin_can_open_package_example_history_without_staff(api_client):
    """Fails if a valid Platform administrator cannot review the immutable examples history."""
    user = User.objects.create_user('jwt-history-admin', email='jwt-history-admin@example.test', is_staff=False)
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_ADMIN)

    response = _jwt_client(api_client, user).get(reverse('package-examples-general-history'))

    assert response.status_code == 200
    assert response.data['count'] == 0


@pytest.mark.parametrize('route_name', ['package-admin-queue', 'package-examples-general-history'])
def test_platform_jwt_staff_with_client_profile_cannot_open_package_admin_view(api_client, route_name):
    """Fails if stale Django staff grants access to a Platform administrative package view."""
    user = User.objects.create_user('jwt-staff-client', email='jwt-staff-client@example.test', is_staff=True)
    UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)

    response = _jwt_client(api_client, user).get(reverse(route_name))

    assert response.status_code == 403


@pytest.mark.parametrize(
    ('record_factory', 'relation'),
    [(paid_order, 'accounts.PackageOrder.client'), (request_row, 'accounts.PackageRequest.client')],
    ids=['package-order', 'package-request'],
)
def test_package_history_blocks_client_transfer(package_context, record_factory, relation):
    """Fails if retained package client ownership can move to another client automatically."""
    record = record_factory(package_context)
    destination = User.objects.create_user('package-destination', email='package-destination@example.test')
    UserProfile.objects.create(user=destination, role=UserProfile.ROLE_CLIENT)

    with pytest.raises(ValidationError) as error:
        assert_delivery_client_transfer_safe(package_context.project, destination, actor=package_context.admin)

    package_context.project.refresh_from_db()
    record.refresh_from_db()
    assert error.value.detail['code'] == 'package_client_transfer_blocked'
    assert package_context.project.client_id == package_context.client.pk
    assert record.client_id == package_context.client.pk


@pytest.mark.parametrize(
    ('record_factory', 'relation'),
    [(paid_order, 'accounts.PackageOrder.client'), (request_row, 'accounts.PackageRequest.client')],
    ids=['package-order', 'package-request'],
)
def test_package_history_blocks_client_merge_ownership_rewrite(package_context, record_factory, relation):
    """Fails if a client merge treats retained package ownership as relinkable data."""
    record = record_factory(package_context)
    destination = User.objects.create_user('package-merge-destination', email='package-merge-destination@example.test')
    destination_profile = UserProfile.objects.create(user=destination, role=UserProfile.ROLE_CLIENT)
    source_profile = package_context.client.profile
    source_profile.user.is_active = False
    source_profile.user.save(update_fields=['is_active'])

    merge = client_merge.plan_client_merge(destination_profile, source_profile)

    record.refresh_from_db()
    assert has_blocking_package_ownership(merge, relation)
    assert record.client_id == package_context.client.pk


def test_force_delete_preview_names_requirement_package_history_as_a_blocker(package_context):
    """Fails if force deletion hides protected package purchases behind a generic relation error."""
    paid_order(package_context)
    operator = User.objects.create_superuser('package-superuser', email='package-superuser@example.test')

    preview = forced_deletion_preview(package_context.project, actor=operator)

    assert preview['can_delete'] is False
    assert {'key': 'accounts.packageorder', 'id': str(PackageOrder.objects.get().pk),
            'message': 'El historial de paquetes por tallas, compras y consentimiento se conserva y bloquea la eliminación automática.'} in preview['blockers']
