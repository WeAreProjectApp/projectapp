"""Hosting client filters, billing inheritance and bulk assignment."""
import re
from decimal import Decimal

import pytest

from accounts.services.proposal_client_service import build_client_display_name
from content.models import AccountingChangeLog, Document, HostingRecord

pytestmark = pytest.mark.django_db

BULK_URL = '/api/accounting/hostings/bulk-assign-client/'


@pytest.fixture(autouse=True)
def issuer(settings):
    from content.models import IssuerProfile

    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    profile = IssuerProfile.objects.order_by('pk').first()
    profile.default_payment_methods = [
        {'payment_method_type': 'bank_transfer', 'bank_name': 'Bancolombia'},
    ]
    profile.save()
    return profile


def make_hosting(**overrides):
    defaults = {
        'client_name': 'German - Kore',
        'domain_url': 'https://korehealths.com/',
        'monthly_value': Decimal('91667.00'),
        'payment_modality': 'semiannual',
        'payment_per_cycle': Decimal('550002.00'),
        'valid_to': '2026-07-20',
        'is_active': True,
    }
    defaults.update(overrides)
    return HostingRecord.objects.create(**defaults)


def _ids(response):
    return {row['id'] for row in response.data['results']}


class TestClientFilter:
    def test_filters_by_client_and_isolates_the_unassigned(
        self, super_client, make_client_profile,
    ):
        acme = make_client_profile(company='Acme SAS')
        linked = make_hosting(client=acme)
        orphan = make_hosting(client_name='Katerin Ruiz - Senses Candles')

        by_client = super_client.get(f'/api/accounting/hostings/?client={acme.pk}')
        without = super_client.get('/api/accounting/hostings/?client=none')

        assert _ids(by_client) == {linked.pk}
        assert _ids(without) == {orphan.pk}

    def test_invalid_client_param_returns_400(self, super_client):
        response = super_client.get('/api/accounting/hostings/?client=abc')

        assert response.status_code == 400
        assert 'client' in response.data['error']

    def test_meta_counts_the_pending_group(
        self, super_client, make_client_profile,
    ):
        make_hosting(client=make_client_profile())
        make_hosting(client_name='Sin vincular')

        meta = super_client.get('/api/accounting/hostings/').data['meta']

        assert meta['without_client_count'] == 1

    def test_search_reaches_the_linked_client(
        self, super_client, make_client_profile,
    ):
        linked = make_hosting(
            client=make_client_profile(company='Xpandia Global'),
            client_name='N - X',
        )
        make_hosting(client_name='Otro')

        response = super_client.get('/api/accounting/hostings/?q=Xpandia')

        assert _ids(response) == {linked.pk}

    def test_export_carries_the_linked_client_column(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile(company='Acme SAS')
        make_hosting(client=profile)

        response = super_client.get('/api/accounting/export/?section=hosting')

        body = response.content.decode('utf-8-sig')
        # Appended, so the historical column order is untouched.
        assert body.splitlines()[0].endswith(
            'Cliente vinculado,Proyecto,Valor antes de IVA,IVA (%),IVA',
        )
        assert build_client_display_name(profile) in body


class TestBillingInheritsTheClient:
    def test_a_hosting_without_email_is_billable_through_its_client(
        self, super_client, make_client_profile, mailoutbox,
    ):
        # The production shape: no client_email anywhere, so this used to be
        # unbillable outright.
        profile = make_client_profile(company='Acme SAS')
        hosting = make_hosting(client=profile, client_email='')

        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )

        assert response.status_code == 201, response.data
        assert response.data['email_sent'] is True
        assert mailoutbox[0].to == [profile.user.email]

    def test_the_hosting_email_overrides_the_client_one(
        self, super_client, make_client_profile, mailoutbox,
    ):
        hosting = make_hosting(
            client=make_client_profile(), client_email='pagos@kore.co',
        )

        super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )

        assert mailoutbox[0].to == ['pagos@kore.co']

    def test_a_linked_hosting_uses_the_per_client_series(
        self, super_client, make_client_profile,
    ):
        # NIT present, so the code derives from the company name. Without one
        # the same client would number under the person's name — the code
        # follows the identification, not company_name on its own.
        hosting = make_hosting(client=make_client_profile(
            company='Acme SAS', nit='900123456-7',
        ))

        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )

        number = response.data['document']['public_number']
        assert re.fullmatch(r'[A-Z]+-[A-Z0-9]+-\d{3}', number), number
        assert number.startswith('PA-ACMESAS-')

    def test_a_hosting_without_client_keeps_the_legacy_series(
        self, super_client,
    ):
        hosting = make_hosting(client_email='german@korehealths.com')

        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )

        number = response.data['document']['public_number']
        assert re.fullmatch(r'[A-Z]+-\d{4}-\d{4}', number), number

    def test_the_document_links_the_client_user(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        hosting = make_hosting(client=profile)

        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )

        document = Document.objects.get(pk=response.data['document']['id'])
        assert document.client_user_id == profile.user_id

    def test_without_any_recipient_the_error_says_what_to_do(
        self, super_client,
    ):
        hosting = make_hosting(client_email='')

        response = super_client.post(
            f'/api/accounting/hostings/{hosting.pk}/send-collection-account/',
        )

        assert response.status_code == 400
        assert 'vincula un cliente' in response.data['error']


class TestBulkAssignClient:
    def test_assigns_and_audits_one_row_per_hosting(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()
        first = make_hosting(client_name='Uno')
        second = make_hosting(client_name='Dos')

        response = super_client.post(
            BULK_URL,
            {'hosting_ids': [first.pk, second.pk], 'client': profile.pk},
            format='json',
        )

        assert response.status_code == 200
        assert response.data['updated'] == 2
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.client_id == profile.pk
        assert second.client_id == profile.pk
        logs = AccountingChangeLog.objects.filter(
            entity_type=AccountingChangeLog.EntityType.HOSTING,
            action=AccountingChangeLog.Action.UPDATED,
        )
        assert logs.count() == 2

    def test_null_unlinks_and_repeating_it_is_a_no_op(
        self, super_client, make_client_profile,
    ):
        hosting = make_hosting(client=make_client_profile())

        first = super_client.post(
            BULK_URL, {'hosting_ids': [hosting.pk], 'client': None},
            format='json',
        )
        second = super_client.post(
            BULK_URL, {'hosting_ids': [hosting.pk], 'client': None},
            format='json',
        )

        assert first.data['updated'] == 1
        assert second.data['updated'] == 0
        hosting.refresh_from_db()
        assert hosting.client_id is None

    def test_empty_list_is_rejected(self, super_client, make_client_profile):
        response = super_client.post(
            BULK_URL,
            {'hosting_ids': [], 'client': make_client_profile().pk},
            format='json',
        )

        assert response.status_code == 400

    def test_unknown_ids_are_rejected_and_nothing_is_written(
        self, super_client, make_client_profile,
    ):
        # Twin of the incomes contract: the two endpoints share one helper and
        # must not drift.
        profile = make_client_profile()
        hosting = make_hosting(domain_url='kore.com.co')

        response = super_client.post(
            BULK_URL,
            {'hosting_ids': [hosting.pk, 999999], 'client': profile.pk},
            format='json',
        )

        assert response.status_code == 409
        assert response.data['code'] == 'records_not_found'
        assert response.data['missing_ids'] == [999999]
        hosting.refresh_from_db()
        assert hosting.client_id is None

    def test_requires_superuser(self, admin_client, make_client_profile):
        response = admin_client.post(
            BULK_URL,
            {'hosting_ids': [make_hosting().pk], 'client': make_client_profile().pk},
            format='json',
        )

        assert response.status_code == 403


class TestClientDetailConsolidation:
    """The client card answers 'todo sobre este cliente' in one payload."""

    def test_nests_hostings_with_their_monthly_total_and_incomes(
        self, super_client, make_client_profile, make_income,
    ):
        profile = make_client_profile(company='Acme SAS')
        make_hosting(client=profile, monthly_value=Decimal('91667.00'))
        make_hosting(
            client=profile, monthly_value=Decimal('19000.00'), is_active=False,
        )
        make_income(concept='Acme - Inicio 40%', client=profile)
        make_hosting(client_name='De otro')

        response = super_client.get(
            f'/api/proposals/client-profiles/{profile.pk}/',
        )

        assert response.status_code == 200
        assert len(response.data['hostings']) == 2
        # Only the active one counts: an inactive hosting costs nothing.
        assert response.data['hostings_monthly_total'] == '91667.00'
        assert len(response.data['incomes']) == 1
        assert response.data['hostings_count'] == 2

    def test_a_client_without_accounting_gets_empty_sections(
        self, super_client, make_client_profile,
    ):
        profile = make_client_profile()

        response = super_client.get(
            f'/api/proposals/client-profiles/{profile.pk}/',
        )

        assert response.data['hostings'] == []
        assert response.data['incomes'] == []
        assert response.data['hostings_monthly_total'] == '0.00'


class TestSnapshotFollowsTheClient:
    """Reassigning the FK must refresh the billing snapshot: the old values
    are the PREVIOUS client's contact data, and billing_email prefers the
    stored override — a stale email routes the cuenta al buzón equivocado."""

    def test_reassigning_the_client_refreshes_the_billing_snapshot(
        self, super_client, make_client_profile,
    ):
        old = make_client_profile(company='Kore SAS', email='kore@example.co')
        new = make_client_profile(
            # NIT present: the billing name follows the identification, so a
            # company with a tax id is billed under its company name.
            company='Vastago SAS', nit='900987654-3',
            email='gerencia@vastago.com.co',
        )
        hosting = make_hosting(
            client=old, client_name='Kore SAS', client_email='kore@example.co',
        )

        response = super_client.patch(
            f'/api/accounting/hostings/{hosting.pk}/update/',
            {'client': new.pk},
            format='json',
        )

        assert response.status_code == 200, response.data
        hosting.refresh_from_db()
        assert hosting.client_id == new.pk
        assert hosting.client_name == 'Vastago SAS'
        assert hosting.client_email == 'gerencia@vastago.com.co'
        assert hosting.billing_email == 'gerencia@vastago.com.co'

    def test_an_override_in_the_same_request_wins(
        self, super_client, make_client_profile,
    ):
        old = make_client_profile(company='Kore SAS', email='kore@example.co')
        new = make_client_profile(
            # NIT present: the billing name follows the identification, so a
            # company with a tax id is billed under its company name.
            company='Vastago SAS', nit='900987654-3',
            email='gerencia@vastago.com.co',
        )
        hosting = make_hosting(
            client=old, client_name='Kore SAS', client_email='kore@example.co',
        )

        response = super_client.patch(
            f'/api/accounting/hostings/{hosting.pk}/update/',
            {'client': new.pk, 'client_email': 'facturacion@vastago.com.co'},
            format='json',
        )

        assert response.status_code == 200, response.data
        hosting.refresh_from_db()
        # The explicit contact survives; the rest still points at the new client.
        assert hosting.client_email == 'facturacion@vastago.com.co'
        assert hosting.client_name == 'Vastago SAS'

    def test_bulk_assign_refreshes_and_audits_the_snapshot(
        self, super_client, make_client_profile,
    ):
        old = make_client_profile(company='Kore SAS', email='kore@example.co')
        new = make_client_profile(
            # NIT present: the billing name follows the identification, so a
            # company with a tax id is billed under its company name.
            company='Vastago SAS', nit='900987654-3',
            email='gerencia@vastago.com.co',
        )
        hosting = make_hosting(
            client=old, client_name='Kore SAS', client_email='kore@example.co',
        )

        response = super_client.post(
            BULK_URL,
            {'hosting_ids': [hosting.pk], 'client': new.pk},
            format='json',
        )

        assert response.status_code == 200, response.data
        hosting.refresh_from_db()
        assert hosting.client_email == 'gerencia@vastago.com.co'
        assert hosting.client_name == 'Vastago SAS'
        log = AccountingChangeLog.objects.filter(
            entity_type='hosting', object_id=hosting.pk, action='updated',
        ).latest('pk')
        changed_fields = {change['field'] for change in log.changes}
        assert 'client_email' in changed_fields
