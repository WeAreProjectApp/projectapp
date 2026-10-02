"""VAT capture rules shared by the income and expense write serializers."""
from decimal import Decimal

import pytest

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentType,
    IncomeRecord,
)
from content.serializers.accounting import (
    ExpenseRecordCreateUpdateSerializer,
    IncomeRecordCreateUpdateSerializer,
)


def income_payload(**overrides):
    payload = {
        'concept': 'Proyecto con IVA',
        'kind': IncomeRecord.Kind.EXPECTED,
        'period_date': '2026-10',
        'origin': IncomeRecord.Origin.DEVELOPMENT,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
class TestIncomeVatCapture:
    def test_new_company_income_defaults_to_nineteen_percent(self):
        """Falla si un ingreso nuevo de empresa deja de cobrar el IVA estándar."""
        serializer = IncomeRecordCreateUpdateSerializer(data=income_payload(
            amount='100.00', amount_mode='before_vat',
        ))

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['vat_rate'] == Decimal('19')
        assert serializer.validated_data['total_amount'] == Decimal('119.00')

    def test_historical_patch_preserves_unrecorded_vat(self, make_income):
        """Falla si editar una nota convierte un IVA histórico desconocido en 19%."""
        income = make_income(vat_rate=None)
        serializer = IncomeRecordCreateUpdateSerializer(
            income, data={'notes': 'Verificado'}, partial=True,
        )

        assert serializer.is_valid(), serializer.errors
        serializer.save()
        income.refresh_from_db()
        assert income.vat_rate is None

    def test_rejects_total_amount_with_vat_capture_amount(self):
        """Falla si una petición ambigua puede sobrescribir el total calculado."""
        serializer = IncomeRecordCreateUpdateSerializer(data=income_payload(
            amount='100.00', amount_mode='before_vat', total_amount='119.00',
        ))

        assert not serializer.is_valid()
        assert 'amount' in serializer.errors

    def test_rejects_tax_change_after_issuing_a_collection_account(
        self, make_income,
    ):
        """Falla si cambiar IVA altera un ingreso que ya se entregó al cliente."""
        income = make_income(vat_rate=Decimal('19.00'))
        document_type, _ = DocumentType.objects.get_or_create(
            code='collection_account', defaults={'name': 'Cuenta de cobro'},
        )
        document = Document.objects.create(
            title='Cuenta emitida',
            document_type=document_type,
            income_record=income,
            commercial_status=Document.CommercialStatus.ISSUED,
            total=income.total_amount,
        )
        DocumentCollectionAccount.objects.create(
            document=document, vat_rate=Decimal('19.00'),
        )
        serializer = IncomeRecordCreateUpdateSerializer(
            income, data={'vat_rate': '0.00'}, partial=True,
        )

        assert not serializer.is_valid()
        assert 'vat_rate' in serializer.errors

    def test_linked_payment_rejects_a_different_tax_rate(self, make_income):
        """Falla si un pago ligado puede usar un IVA distinto al ingreso esperado."""
        expected = make_income(vat_rate=Decimal('19.00'))
        serializer = IncomeRecordCreateUpdateSerializer(data=income_payload(
            kind=IncomeRecord.Kind.LIQUID,
            expected_income=expected.pk,
            total_amount='100.00',
            vat_rate='0.00',
        ))

        assert not serializer.is_valid()
        assert 'vat_rate' in serializer.errors


@pytest.mark.django_db
class TestExpenseVatCapture:
    def test_new_expense_defaults_to_zero_percent(self):
        """Falla si un gasto nuevo empieza a sumar IVA sin que el operador lo defina."""
        serializer = ExpenseRecordCreateUpdateSerializer(data={
            'concept': 'Suscripción',
            'period_date': '2026-10',
            'amount': '100.00',
            'amount_mode': 'before_vat',
            'register_in_pocket': False,
        })

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['vat_rate'] == Decimal('0')
        assert serializer.validated_data['total_amount'] == Decimal('100.00')

    def test_rejects_amount_mode_without_an_amount(self):
        """Falla si el modo de IVA puede llegar sin una cifra que normalizar."""
        serializer = ExpenseRecordCreateUpdateSerializer(data={
            'concept': 'Suscripción',
            'period_date': '2026-10',
            'amount_mode': 'vat_included',
            'total_amount': '100.00',
            'register_in_pocket': False,
        })

        assert not serializer.is_valid()
        assert 'amount' in serializer.errors
