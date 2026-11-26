"""Tests for build_collection_account_email: what preview and send both show.

First coverage of this module — sibling of test_collection_account_service.py /
test_collection_account_pdf_service.py / test_collection_account_numbering.py.
Until now this was only verified indirectly, via a loose HTML substring check
on the create endpoint (test_collection_account_create_views.py).
"""
from decimal import Decimal

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from content.models import CompanySettings, Document, IncomeRecord, IssuerProfile
from content.services.collection_account_email_service import (
    build_collection_account_email,
)

User = get_user_model()
pytestmark = pytest.mark.django_db

CREATE_URL = '/api/accounting/collection-accounts/create/'


@pytest.fixture(autouse=True)
def issuer(settings):
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }
    profile = IssuerProfile.objects.order_by('pk').first()
    # Emptied on purpose: the bank data now comes from CompanySettings, and a
    # leftover here would mask a regression that stopped reading it.
    profile.default_payment_methods = []
    profile.save()
    return profile


@pytest.fixture(autouse=True)
def company_settings():
    """The single source of the payment data, set explicitly.

    A data migration seeds real values into the test database; pinning them
    here keeps these assertions from drifting when that seed changes.
    """
    company = CompanySettings.load()
    company.contractor_full_name = 'GUSTAVO ADOLFO PEREZ PEREZ'
    company.contractor_nit = '1021513348-7'
    company.contractor_cedula = ''
    company.bank_name = 'Bancolombia'
    company.bank_account_type = 'Ahorros'
    company.bank_account_number = '00774149350'
    company.save()
    return company


def make_client(email='ana@acme.co', company='Acme Soluciones'):
    user = User.objects.create_user(
        username=email, email=email, password='pass12345',
        first_name='Ana', last_name='Pérez',
    )
    UserProfile.objects.create(user=user, company_name=company)
    return user


def make_income(**overrides):
    fields = {
        'concept': 'Desarrollo módulo de reportes',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-08-01',
        'total_amount': Decimal('1490000.00'),
        'gustavo_amount': Decimal('745000.00'),
        'carlos_amount': Decimal('745000.00'),
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def payload(client_user, income, **overrides):
    data = {
        'client_profile_id': client_user.profile.pk,
        'income_record_id': income.pk,
        'items': [{
            'description': 'Desarrollo módulo de reportes',
            'quantity': '1',
            'unit_price': '1490000.00',
        }],
    }
    data.update(overrides)
    return data


def create_document(super_client, **payload_overrides):
    client = make_client()
    income = make_income()
    response = super_client.post(
        CREATE_URL, payload(client, income, **payload_overrides), format='json',
    )
    assert response.status_code == 201, response.data
    return Document.objects.get(pk=response.data['document']['id'])


PERIOD_ITEMS = [{
    'description': 'Desarrollo módulo de reportes',
    'quantity': '1',
    'unit_price': '1490000.00',
    'period_start': '2026-08-01',
    'period_end': '2026-08-31',
}]


class TestBuildCollectionAccountEmail:
    def test_renders_period_valor_and_payment_methods_from_a_real_document(
        self, super_client,
    ):
        """Fails if a regression corrupts what the preview modal AND the real client email show (the only function both share)."""
        document = create_document(super_client, items=PERIOD_ITEMS)

        email = build_collection_account_email(document)

        assert email['subject'] == (
            f'Cuenta de cobro {document.public_number} — ProjectApp'
        )
        assert 'Período facturado: 01/08/2026 a 31/08/2026.' in email['sections']
        valor = next(s for s in email['sections'] if s.startswith('Valor a pagar'))
        # startswith (not `in`) so a doubled-$ formatter regression is caught too.
        assert valor.startswith("Valor a pagar: $1'490.000 COP")
        methods = next(
            s for s in email['sections'] if s.startswith('Formas de pago')
        )
        assert 'Transferencia bancaria' in methods
        assert 'Entidad: Bancolombia' in methods
        assert email['greeting'] == 'Hola Ana Pérez'

    def test_omits_period_and_payment_methods_sections_when_absent(
        self, super_client, issuer, company_settings,
    ):
        """Fails if a dropped/inverted guard ships a blank or broken section."""
        # Both sources have to go quiet: an unconfigured bank account must not
        # print a payment block with labels and nothing beside them.
        company_settings.bank_name = ''
        company_settings.bank_account_number = ''
        company_settings.save()
        document = create_document(super_client)

        email = build_collection_account_email(document)

        assert not any('Período facturado' in s for s in email['sections'])
        assert not any(s.startswith('Formas de pago') for s in email['sections'])

    def test_emphasises_the_figures_the_client_has_to_act_on(self, super_client):
        """Fails if the amount, deadline or account number lose their emphasis and sink back into running text."""
        document = create_document(super_client, items=PERIOD_ITEMS)

        html = build_collection_account_email(document)['html_body']

        # The label stays plain and the datum carries the weight.
        assert 'Período facturado: <strong style="font-weight:500;">' in html
        assert 'Valor a pagar: <strong style="font-weight:500;">' in html
        assert 'Fecha límite de pago: <strong style="font-weight:500;">' in html
        assert '<strong style="font-weight:500;">00774149350</strong>' in html

    @freeze_time('2026-08-11 12:00:00-05:00')
    def test_gives_the_payment_deadline_a_line_of_its_own(self, super_client):
        """Fails if the deadline goes back to riding along on the amount's line, where it was invisible."""
        # Frozen because the deadline is issue date + PAYMENT_TERM_DAYS: the
        # assertion below is a literal date, so without this the test starts
        # failing the day after it was written.
        document = create_document(super_client, items=PERIOD_ITEMS)

        sections = build_collection_account_email(document)['sections']

        valor = next(s for s in sections if s.startswith('Valor a pagar'))
        assert 'Fecha límite' not in valor
        deadline = next(
            s for s in sections if s.startswith('Fecha límite de pago')
        )
        # The house weekday format, not 19/08/2026.
        assert deadline == 'Fecha límite de pago: Mié, 19 ago 2026.'

    def test_omits_the_deadline_when_the_term_is_immediate_payment(
        self, super_client,
    ):
        """Fails if a zero-day cuenta puts the deadline line back: with no due
        date it could only restate the issue date the client already read."""
        document = create_document(
            super_client, items=PERIOD_ITEMS, payment_term_days=0,
        )

        email = build_collection_account_email(document)

        assert document.due_date is None
        assert not any('Fecha límite' in s for s in email['sections'])
        assert 'Fecha límite' not in email['html_body']
        assert 'Fecha límite' not in email['text_body']

    def test_paid_explicitly_dated_account_keeps_its_deadline_in_the_notice(
        self, super_client,
    ):
        """A paid account created under the new dated mode still tells the
        client which deadline governed it; suppressing it hides the record."""
        document = create_document(
            super_client,
            due_date_mode='dated',
            due_date='2026-08-21',
        )
        document.commercial_status = Document.CommercialStatus.PAID
        document.save(update_fields=['commercial_status'])

        email = build_collection_account_email(document)

        assert 'Fecha límite de pago: Vie, 21 ago 2026.' in email['sections']
        assert 'Fecha límite de pago' in email['html_body']
        assert 'Fecha límite de pago' in email['text_body']

    def test_paid_historical_account_keeps_its_deadline_hidden(self, super_client):
        """A paid legacy row keeps the historical client-facing notice shape
        even when an old fixed due date remains stored on the document."""
        document = create_document(
            super_client,
            due_date_mode='legacy',
            due_date='2026-08-21',
        )
        document.commercial_status = Document.CommercialStatus.PAID
        document.save(update_fields=['commercial_status'])

        email = build_collection_account_email(document)

        assert not any('Fecha límite de pago' in section for section in email['sections'])
        assert 'Fecha límite de pago' not in email['html_body']
        assert 'Fecha límite de pago' not in email['text_body']

    def test_text_alternative_carries_no_markdown_markers(self, super_client):
        """Fails if the plain-text part ships raw ** and ### to whoever reads without HTML."""
        document = create_document(super_client, items=PERIOD_ITEMS)

        email = build_collection_account_email(document)

        assert '**' not in email['text_body']
        assert '###' not in email['text_body']
        assert "Valor a pagar: $1'490.000 COP." in email['text_body']

    def test_payment_block_names_bank_account_and_holder(self, super_client):
        """Fails if the block drops a field the client needs to actually transfer the money."""
        document = create_document(super_client, items=PERIOD_ITEMS)

        methods = next(
            s for s in build_collection_account_email(document)['sections']
            if s.startswith('Formas de pago')
        )

        assert 'Entidad: Bancolombia' in methods
        assert 'Tipo de cuenta: Ahorros' in methods
        assert 'Número de cuenta: 00774149350' in methods
        assert 'Titular: GUSTAVO ADOLFO PEREZ PEREZ (NIT 1021513348-7)' in methods
