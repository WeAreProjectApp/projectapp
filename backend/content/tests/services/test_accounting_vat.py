"""VAT arithmetic and the client-facing collection-account boundary."""
import io
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from accounts.models import Project
from pypdf import PdfReader

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    DocumentType,
    HostingRecord,
    IncomeRecord,
    IssuerProfile,
)
from content.services import accounting_service, accounting_settlement_service
from content.services.accounting_vat import MAX_MONEY, vat_breakdown
from content.services.collection_account_create_service import (
    create_income_collection_account,
    create_income_collection_account_draft,
)
from content.services.hosting_billing_service import (
    create_hosting_collection_account,
)
from content.services.collection_account_email_service import (
    build_collection_account_email,
)
from content.services.collection_account_pdf_service import CollectionAccountPdfService
from content.services.collection_account_service import CollectionAccountError
from content.services.document_type_utils import get_collection_account_document_type

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def issuer_profile():
    """The no-migrations database has no catalog seed for the panel issuer."""
    issuer = IssuerProfile.objects.get_or_create(
        name='ProjectApp', defaults={'legal_name': 'ProjectApp SAS'},
    )[0]
    DocumentType.objects.get_or_create(
        code='collection_account', defaults={'name': 'Cuenta de cobro'},
    )
    return issuer


@pytest.mark.parametrize(
    ('amount', 'rate', 'mode', 'expected'),
    [
        (Decimal('100.01'), Decimal('19'), 'before_vat', (Decimal('100.01'), Decimal('19.00'), Decimal('119.01'))),
        (Decimal('119.01'), Decimal('19'), 'vat_included', (Decimal('100.01'), Decimal('19.00'), Decimal('119.01'))),
        (Decimal('100.00'), Decimal('19'), 'vat_included', (Decimal('84.03'), Decimal('15.97'), Decimal('100.00'))),
        (Decimal('100.00'), Decimal('0'), 'vat_included', (Decimal('100.00'), Decimal('0.00'), Decimal('100.00'))),
    ],
)
def test_vat_breakdown_keeps_money_totals_exactly(amount, rate, mode, expected):
    """Falla si redondear IVA deja de conservar el total que se cobra."""
    assert vat_breakdown(amount, rate, mode) == expected


@pytest.mark.parametrize(
    ('amount', 'rate', 'mode', 'message'),
    [
        (Decimal('-0.01'), Decimal('19'), 'vat_included', 'importe'),
        (Decimal('100.00'), Decimal('100.01'), 'vat_included', 'porcentaje'),
        (Decimal('100.00'), None, 'before_vat', 'porcentaje'),
        (MAX_MONEY, Decimal('19'), 'before_vat', 'total con IVA'),
    ],
)
def test_vat_breakdown_rejects_invalid_financial_inputs(amount, rate, mode, message):
    """Falla si un importe o porcentaje imposible alcanza los registros contables."""
    with pytest.raises(ValueError, match=message):
        vat_breakdown(amount, rate, mode)


def test_vat_breakdown_keeps_unknown_historical_tax_unclassified():
    """Falla si los totales históricos se hacen pasar por registros sin IVA."""
    assert vat_breakdown(Decimal('100.00'), None) == (
        None, None, Decimal('100.00'),
    )


@pytest.mark.django_db
def test_income_vat_read_properties_do_not_query_per_row(
    make_income, django_assert_num_queries,
):
    """Falla si el desglose de IVA vuelve N+1 los listados de ingresos."""
    income = make_income(
        total_amount=Decimal('119.00'), vat_rate=Decimal('19.00'),
    )

    with django_assert_num_queries(0):
        breakdown = (income.base_amount, income.vat_amount)

    assert breakdown == (Decimal('100.00'), Decimal('19.00'))


@pytest.mark.django_db
def test_collection_preview_updates_the_response_without_persisting_the_income(
    super_client, make_client_profile, make_income,
):
    """Falla si previsualizar una cuenta cambia el ingreso antes de confirmarla."""
    client = make_client_profile(company='IVA Preview SAS', nit='900123456')
    income = make_income(
        client=client,
        total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
        vat_rate=None,
    )
    documents_before = Document.objects.count()

    response = super_client.post(
        '/api/accounting/collection-accounts/preview/',
        {
            'client_profile_id': client.pk,
            'income_record_id': income.pk,
            'vat_rate': '19.00',
            'items': [{
                'description': income.concept,
                'amount': '100.00',
                'amount_mode': 'before_vat',
            }],
        },
        format='json',
    )

    assert response.status_code == 200, response.data
    assert response.data['income_total'] == '119.00'
    assert response.data['tax_total'] == '19.00'
    assert response.data['vat_rate'] == '19.00'
    income.refresh_from_db()
    assert income.total_amount == Decimal('100.00')
    assert income.vat_rate is None
    assert Document.objects.count() == documents_before


@pytest.mark.django_db
def test_collection_account_rejects_tax_change_after_a_partial_payment(
    make_client_profile, make_income,
):
    """Falla si una cuenta puede reescribir IVA cuando ya hay dinero aplicado."""
    client = make_client_profile(company='Cobro Parcial SAS', nit='900123457')
    income = make_income(
        client=client,
        total_amount=Decimal('119.00'),
        gustavo_amount=Decimal('59.50'),
        carlos_amount=Decimal('59.50'),
        vat_rate=Decimal('19.00'),
    )
    IncomeRecord.objects.create(
        concept=income.concept,
        kind=IncomeRecord.Kind.LIQUID,
        period_date=date(2026, 10, 2),
        total_amount=Decimal('20.00'),
        gustavo_amount=Decimal('10.00'),
        carlos_amount=Decimal('10.00'),
        vat_rate=Decimal('19.00'),
        expected_income=income,
    )

    with pytest.raises(CollectionAccountError, match='pagos o deducciones'):
        create_income_collection_account(
            {
                'client_profile_id': client.pk,
                'income_record_id': income.pk,
                'vat_rate': Decimal('0'),
                'items': [{
                    'description': income.concept,
                    'amount': Decimal('99.00'),
                    'amount_mode': 'vat_included',
                }],
            },
            persist_snapshot=False,
        )

    income.refresh_from_db()
    assert income.vat_rate == Decimal('19.00')
    assert income.total_amount == Decimal('119.00')
    assert not Document.objects.filter(income_record=income).exists()


@pytest.mark.django_db
def test_legacy_item_price_syncs_an_uncollected_income_with_known_tax_rate(
    make_client_profile, make_income,
):
    """Falla si una cuenta legado deja su total distinto al ingreso con IVA."""
    client = make_client_profile(company='Cuenta Legado SAS', nit='900123458')
    income = make_income(
        client=client,
        total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
        vat_rate=Decimal('19.00'),
    )

    document = create_income_collection_account_draft(
        {
            'client_profile_id': client.pk,
            'income_record_id': income.pk,
            'items': [{
                'description': income.concept,
                'unit_price': Decimal('100.00'),
            }],
        },
    )

    income.refresh_from_db()
    assert income.total_amount == Decimal('119.00')
    assert document.items.get().line_total == Decimal('119.00')


@pytest.mark.django_db
def test_collection_pdf_and_email_publish_the_same_vat_breakdown(
    make_client_profile,
):
    """Falla si PDF y correo dejan de explicar la misma base, IVA y total."""
    client = make_client_profile(company='Factura IVA SAS')
    project = Project.objects.create(
        name='Proyecto IVA', client=client.user, status=Project.STATUS_ACTIVE,
    )
    issuer = IssuerProfile.objects.create(name='ProjectApp', legal_name='ProjectApp SAS')
    document = Document.objects.create(
        title='Cuenta de cobro — IVA',
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.ISSUED,
        client_user=client.user,
        project=project,
        issuer=issuer,
        public_number='PA-IVA-001',
        issue_date=date(2026, 10, 1),
        subtotal=Decimal('1000000.00'),
        tax_total=Decimal('190000.00'),
        total=Decimal('1190000.00'),
        currency='COP',
    )
    DocumentCollectionAccount.objects.create(
        document=document, customer_name='Factura IVA SAS',
        customer_email='pagos@factura-iva.co', billing_concept='Servicio',
        vat_rate=Decimal('19.00'),
    )
    DocumentItem.objects.create(
        document=document, position=0, description='Servicio',
        quantity=Decimal('1'), unit_price=Decimal('1000000.00'),
        tax_amount=Decimal('190000.00'), line_total=Decimal('1190000.00'),
    )

    pdf = CollectionAccountPdfService.generate(document)
    pdf_text = ''.join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    email = build_collection_account_email(document)

    assert 'Valor antes de IVA: $1.000.000' in pdf_text
    assert 'IVA (19 %): $190.000' in pdf_text
    assert 'Total (COP): $1.190.000' in pdf_text
    assert 'Valor antes de IVA: $1\'000.000 COP.' in email['text_body']
    assert 'IVA (19 %): $190.000 COP.' in email['text_body']
    assert 'Valor a pagar: $1\'190.000 COP.' in email['text_body']


@pytest.mark.django_db
def test_hosting_collection_account_splits_the_gross_cycle_amount():
    """Falla si un ciclo de hosting con IVA factura la base como total bruto."""
    hosting = HostingRecord.objects.create(
        client_name='Hosting IVA SAS',
        client_email='pagos@hosting-iva.co',
        domain_url='hosting-iva.co',
        monthly_value=Decimal('100.00'),
        payment_modality=HostingRecord.LEGACY_MONTHLY,
        payment_per_cycle=Decimal('119.00'),
        valid_from=date(2026, 10, 1),
        valid_to=date(2026, 11, 1),
        vat_rate=Decimal('19.00'),
        is_active=True,
    )

    document = create_hosting_collection_account(hosting)
    item = document.items.get()

    assert document.collection_account.vat_rate == Decimal('19.00')
    assert item.unit_price == Decimal('100.00')
    assert item.tax_amount == Decimal('19.00')
    assert item.line_total == Decimal('119.00')


@pytest.mark.django_db
def test_settlement_children_inherit_the_expected_income_tax_rate(
    superuser, make_income,
):
    """Falla si una liquidación separa sus hijos del IVA del cobro original."""
    income = make_income(
        total_amount=Decimal('100.00'),
        gustavo_amount=Decimal('50.00'),
        carlos_amount=Decimal('50.00'),
        vat_rate=Decimal('19.00'),
    )

    with patch.object(accounting_service, '_notify'):
        result = accounting_settlement_service.settle_expected_income(
            income,
            {
                'concept': income.concept,
                'period_date': date(2026, 10, 2),
                'destination': IncomeRecord.Destination.PARTNERS,
                'total_amount': Decimal('60.00'),
                'notes': '',
                'deductions': [],
                'expected_incomes': [{
                    'concept': 'Saldo IVA',
                    'period_date': date(2026, 11, 1),
                    'amount': Decimal('40.00'),
                }],
            },
            superuser,
        )

    assert result['liquid'].vat_rate == Decimal('19.00')
    assert result['expected_incomes'][0].vat_rate == Decimal('19.00')
