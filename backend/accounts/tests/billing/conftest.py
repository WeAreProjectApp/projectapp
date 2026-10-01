from datetime import date
from decimal import Decimal
import pytest
from accounts.models import HostingSubscription, Payment, ProjectContract
from content.models import Document, DocumentCollectionAccount, HostingRecord
from content.services.document_type_utils import get_collection_account_document_type
from accounts.tests.billing.mail_safety import LOCMEM_BACKEND, assert_billing_mailers_isolated


@pytest.fixture(scope='session', autouse=True)
def billing_mailer_isolation(django_test_environment):
    from django.conf import settings
    from django.test import override_settings
    aliases = {alias: {'BACKEND': LOCMEM_BACKEND} for alias in settings.MAILERS}
    aliases['default'] = {'BACKEND': LOCMEM_BACKEND}
    with override_settings(MAILERS=aliases):
        assert_billing_mailers_isolated()
        yield


@pytest.fixture(scope='session')
def django_db_setup(billing_mailer_isolation, django_db_setup):
    return django_db_setup


@pytest.fixture
def contract(project):
    document = Document.objects.create(title='Contrato A', project=project, client_user=project.client)
    return ProjectContract.objects.create(project=project, key='contract-a', title='Contrato A', document=document)


@pytest.fixture
def account(project):
    doc = Document.objects.create(title='Cobro histórico', project=project, client_user=project.client,
                                  document_type=get_collection_account_document_type(),
                                  commercial_status='issued', public_number='HIST-001',
                                  issue_date=date(2026, 1, 1),
                                  total=Decimal('150000'), notes='Nota contable privada',
                                  metadata={'private_note': 'interno'})
    DocumentCollectionAccount.objects.create(document=doc, customer_name='Snapshot legal', customer_project_name='Marca congelada')
    return doc


@pytest.fixture
def hosting_record(project):
    return HostingRecord.objects.create(project=project, client=project.client.profile,
                                       client_name='Titular', monthly_value=50000, payment_per_cycle=150000,
                                       valid_from=date(2026, 1, 1), valid_to=date(2026, 3, 31))


@pytest.fixture
def subscription(project):
    return HostingSubscription.objects.create(project=project, plan='quarterly', base_monthly_amount=50000,
                                             effective_monthly_amount=50000, billing_amount=150000,
                                             start_date=date(2026, 1, 1), status='active')


@pytest.fixture
def payment(subscription):
    return Payment.objects.create(subscription=subscription, amount=150000, status='paid',
                                  billing_period_start=date(2026, 1, 1), billing_period_end=date(2026, 3, 31),
                                  due_date=date(2026, 1, 1))
