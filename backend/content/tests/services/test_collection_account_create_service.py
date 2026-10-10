"""create_income_collection_account: guards, snapshot, numbering, terms."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from content.models import (
    AccountingChangeLog,
    Document,
    IncomeRecord,
    IssuerProfile,
    PocketMovement,
)
from content.services.collection_account_create_service import (
    create_income_collection_account,
    create_income_collection_account_draft,
)
from content.services.collection_account_snapshot_service import (
    CollectionAccountSnapshotError,
)
from content.services.collection_account_service import (
    CollectionAccountError,
    mark_collection_account_cancelled,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def issuer():
    profile = IssuerProfile.objects.order_by('pk').first()
    profile.city = 'Bogotá'
    profile.identification_number = '901000000'
    profile.identification_type = 'NIT'
    profile.default_payment_methods = [
        {'payment_method_type': 'bank_transfer', 'bank_name': 'Bancolombia'},
    ]
    profile.save()
    return profile


def make_client(email='ana@acme.co', company='Acme Soluciones', **profile_kwargs):
    user = User.objects.create_user(
        username=email, email=email, password='pass12345',
        first_name='Ana', last_name='Pérez',
    )
    UserProfile.objects.create(user=user, company_name=company, **profile_kwargs)
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
            'quantity': Decimal('1'),
            'unit_price': Decimal('1490000.00'),
        }],
    }
    data.update(overrides)
    return data


class TestHappyPath:
    def test_draft_creation_does_not_cross_the_issuance_boundary(self):
        document = create_income_collection_account_draft(
            payload(make_client(), make_income()),
        )

        assert document.commercial_status == Document.CommercialStatus.DRAFT
        assert document.public_number == ''
        assert document.issue_date is None
        assert not document.generated_file

    def test_explicit_issue_date_is_used_for_seeded_history(self):
        issue_date = date(2026, 6, 15)

        document = create_income_collection_account(
            payload(make_client(), make_income()),
            persist_snapshot=False,
            issued_on=issue_date,
        )

        assert document.issue_date == issue_date

    def test_account_created_after_full_payment_uses_original_total_as_paid(self):
        """Falla si facturar después del abono crea una cuenta por saldo cero o vuelve a cobrarla."""
        client = make_client()
        income = make_income()
        IncomeRecord.objects.create(
            concept='Abono completo', kind=IncomeRecord.Kind.LIQUID,
            period_date='2026-08-02', total_amount=income.total_amount,
            gustavo_amount=income.gustavo_amount, carlos_amount=income.carlos_amount,
            expected_income=income,
        )
        movements_before = PocketMovement.objects.count()

        document = create_income_collection_account(
            payload(client, income), persist_snapshot=False,
        )

        assert document.total == income.total_amount
        assert document.commercial_status == Document.CommercialStatus.PAID
        assert PocketMovement.objects.count() == movements_before

    def test_issues_with_per_client_number_and_nit_snapshot(self):
        client = make_client(nit='901234567')
        income = make_income()

        document = create_income_collection_account(
            payload(client, income),
        )

        assert document.commercial_status == Document.CommercialStatus.ISSUED
        assert document.public_number == 'PA-ACMESOLU-001'
        assert document.income_record_id == income.pk
        assert document.client_user_id == client.pk
        assert document.total == Decimal('1490000.00')
        assert document.city == 'Bogotá'
        ext = document.collection_account
        assert ext.customer_name == 'Acme Soluciones'
        assert ext.customer_identification == '901234567'
        assert ext.customer_identification_type == 'NIT'
        assert ext.customer_email == 'ana@acme.co'
        # The CompanySettings bank account plus the issuer's own extra channel.
        assert document.payment_methods.count() == 2
        assert document.payment_methods.filter(is_primary=True).count() == 1

    def test_cedula_when_no_nit_and_concept_defaults_from_income(self):
        client = make_client(cedula='12345678')
        income = make_income()

        document = create_income_collection_account(payload(client, income))

        ext = document.collection_account
        assert ext.customer_identification == '12345678'
        assert ext.customer_identification_type == 'CC'
        assert ext.billing_concept == 'Desarrollo módulo de reportes'

    def test_customer_overrides_win(self):
        client = make_client(nit='901234567')
        income = make_income()

        document = create_income_collection_account(payload(
            client, income,
            customer={
                'email': 'pagos@acme.co',
                'identification': '999999',
                'identification_type': 'CC',
            },
        ))

        ext = document.collection_account
        assert ext.customer_email == 'pagos@acme.co'
        assert ext.customer_identification == '999999'
        assert ext.customer_identification_type == 'CC'

    @freeze_time('2026-08-05 12:00:00-05:00')
    def test_days_after_issue_default_term(self):
        document = create_income_collection_account(
            payload(make_client(), make_income()),
        )
        assert document.due_date == date(2026, 8, 13)

    def test_fixed_due_date_term(self):
        document = create_income_collection_account(payload(
            make_client(), make_income(), due_date=date(2026, 9, 1),
        ))
        assert document.due_date == date(2026, 9, 1)
        assert document.collection_account.payment_term_type == 'fixed_date'

    def test_manual_public_number(self):
        document = create_income_collection_account(payload(
            make_client(), make_income(), public_number='PA-ACMESOLU-044',
        ))
        assert document.public_number == 'PA-ACMESOLU-044'

    def test_terms_are_present_when_the_snapshot_is_archived(self):
        terms = 'Pago dentro de los quince días calendario.'
        archived_terms = []

        def capture_snapshot(document):
            archived_terms.append(document.terms_and_conditions)

        with patch(
            'content.services.collection_account_snapshot_service'
            '.persist_collection_account_pdf',
            side_effect=capture_snapshot,
        ):
            document = create_income_collection_account(payload(
                make_client(), make_income(), terms_and_conditions=terms,
            ))

        assert document.terms_and_conditions == terms
        assert archived_terms == [terms]


class TestGuards:
    def test_lost_income_rejected(self):
        income = make_income(kind=IncomeRecord.Kind.LOST)
        with pytest.raises(CollectionAccountError) as exc:
            create_income_collection_account(payload(make_client(), income))
        assert 'perdido' in str(exc.value)

    def test_income_with_active_cuenta_rejected(self):
        client = make_client()
        income = make_income()
        create_income_collection_account(payload(client, income))

        with pytest.raises(CollectionAccountError) as exc:
            create_income_collection_account(payload(client, income))
        assert 'ya tiene una cuenta de cobro' in str(exc.value)

    def test_cancelled_cuenta_frees_the_income(self):
        client = make_client()
        income = make_income()
        first = create_income_collection_account(payload(client, income))
        mark_collection_account_cancelled(first)

        second = create_income_collection_account(payload(client, income))

        # The code comes from the legal holder, not from company_name: this
        # client has no NIT, so the series belongs to the person (Ana Pérez),
        # not to the brand stored in company_name.
        assert second.public_number == 'PA-ANAPEREZ-002'
        assert second.income_record_id == income.pk

    def test_placeholder_email_rejected(self):
        client = make_client(email='cliente@temp.example.com')
        with pytest.raises(CollectionAccountError) as exc:
            create_income_collection_account(payload(client, make_income()))
        assert 'email real' in str(exc.value)

    def test_snapshot_failure_rolls_back_the_issuance(self):
        client = make_client()
        income = make_income()

        with patch(
            'content.services.collection_account_snapshot_service'
            '.persist_collection_account_pdf',
            side_effect=CollectionAccountSnapshotError('storage unavailable'),
        ):
            with pytest.raises(CollectionAccountError, match='storage unavailable'):
                create_income_collection_account(payload(client, income))

        assert not Document.objects.filter(income_record=income).exists()
        income.refresh_from_db()
        assert income.client_id is None


class TestClientOwnershipSync:
    def test_adopts_the_client_when_the_income_has_none(self):
        """Issuing the cuenta claims the orphan income for its client."""
        client = make_client(nit='901234567')
        income = make_income()

        create_income_collection_account(payload(client, income))

        income.refresh_from_db()
        assert income.client_id == client.profile.pk
        # Audited through the shared assignment pathway.
        log = AccountingChangeLog.objects.get(
            entity_type='income', object_id=income.pk, action='updated',
        )
        assert log.changes[0]['field'] == 'client'

    def test_rejects_an_income_owned_by_another_client(self):
        owner = make_client(email='owner@acme.co', company='Dueno SAS')
        other = make_client(email='other@acme.co', company='Otro SAS')
        income = make_income(client=owner.profile)

        with pytest.raises(CollectionAccountError) as exc:
            create_income_collection_account(payload(other, income))

        assert 'pertenece a otro cliente' in str(exc.value)
        assert not Document.objects.filter(income_record=income).exists()
        income.refresh_from_db()
        assert income.client_id == owner.profile.pk
