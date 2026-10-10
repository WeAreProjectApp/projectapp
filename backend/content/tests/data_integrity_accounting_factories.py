"""Accounting rows for the data-integrity rule tests: incomes, hostings, cycles, recurring payments, cuentas."""
from datetime import date
from decimal import Decimal

from accounts.billing_models import CollectionAccountContext, ProjectHosting
from content.models import Document, HostingCycle, HostingRecord, IncomeRecord, RecurringPayment
from content.services.document_type_utils import get_collection_account_document_type


def make_income(profile=None, project=None, **overrides):
    fields = {
        'concept': 'Kore - Fase 1',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': date(2026, 7, 1),
        'total_amount': Decimal('1000000.00'),
        'gustavo_amount': Decimal('500000.00'),
        'carlos_amount': Decimal('500000.00'),
        'client': profile,
        'project': project,
    }
    fields.update(overrides)
    return IncomeRecord.objects.create(**fields)


def make_liquid(expected, profile=None, project=None, **overrides):
    """A payment settling ``expected``; client and project are given explicitly, as legacy rows had them."""
    fields = {'kind': IncomeRecord.Kind.LIQUID, 'expected_income': expected, 'concept': f'{expected.concept} (pago)'}
    fields.update(overrides)
    return make_income(profile, project, **fields)


def make_hosting(profile=None, project=None, **overrides):
    fields = {
        'client': profile,
        'project': project,
        'client_name': 'Ana - Kore',
        'domain_url': 'kore.example.com',
        'monthly_value': Decimal('120000.00'),
    }
    fields.update(overrides)
    return HostingRecord.objects.create(**fields)


def make_cycle(hosting, amount='300000.00', **overrides):
    """A paid cycle written directly, without the service that keeps the hosting totals in sync."""
    fields = {
        'hosting_record': hosting,
        'modality': HostingRecord.Modality.QUARTERLY,
        'amount': Decimal(amount),
        'paid_at': date(2026, 7, 1),
    }
    fields.update(overrides)
    return HostingCycle.objects.create(**fields)


def make_recurring(name='Servidor Kore', **overrides):
    fields = {
        'name': name,
        'price': Decimal('250000.00'),
        'currency': RecurringPayment.Currency.COP,
        'frequency': RecurringPayment.Frequency.MONTHLY,
    }
    fields.update(overrides)
    return RecurringPayment.objects.create(**fields)


def make_cuenta(profile, project, *, status=Document.CommercialStatus.ISSUED, **overrides):
    fields = {
        'title': 'Cuenta de cobro Kore',
        'document_type': get_collection_account_document_type(),
        'commercial_status': status,
        'client_user': profile.user,
        'project': project,
        'public_number': 'PA-KORE-001',
    }
    fields.update(overrides)
    return Document.objects.create(**fields)


def associate_hosting_context(document):
    """The explicit billing context of a cuenta: the project's single hosting."""
    hosting, _ = ProjectHosting.objects.get_or_create(project=document.project)
    return CollectionAccountContext.objects.create(
        document=document, nature=CollectionAccountContext.Nature.HOSTING, hosting=hosting,
    )
