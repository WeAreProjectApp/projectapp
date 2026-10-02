"""VAT capture normalization shared by panel and MCP serializers."""
from decimal import Decimal
from rest_framework import serializers
from content.services.accounting_vat import vat_breakdown


class VatReadMixin(serializers.Serializer):
    base_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)
    vat_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)


class VatWriteMixin(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False, write_only=True)
    amount_mode = serializers.ChoiceField(choices=('before_vat', 'vat_included'), required=False, write_only=True)
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), required=False, allow_null=True)
    vat_total_field = 'total_amount'
    vat_default = Decimal('0')

    def validate(self, data):
        total_field = self.vat_total_field
        if 'amount' in data and total_field in data:
            raise serializers.ValidationError({'amount': 'Envía un único importe.'})
        if 'amount_mode' in data and 'amount' not in data:
            raise serializers.ValidationError({'amount': 'Escribe el importe para el modo seleccionado.'})
        rate = data.get('vat_rate')
        if 'vat_rate' not in data:
            if data.get('expected_income') is not None:
                rate = data['expected_income'].vat_rate
                data['vat_rate'] = rate
            elif self.instance is not None:
                rate = self.instance.vat_rate
            elif self.context.get('settlement'):
                rate = None
            else:
                rate = self.vat_default if data.get('ledger', 'company') == 'company' else Decimal('0')
            if self.instance is None:
                data['vat_rate'] = rate
        expected = data.get(
            'expected_income', getattr(self.instance, 'expected_income', None),
        )
        if (
            expected is not None
            and ('vat_rate' in data or 'expected_income' in data)
            and rate != expected.vat_rate
        ):
            raise serializers.ValidationError({'vat_rate': 'El pago debe conservar el IVA del ingreso esperado.'})
        amount = data.pop('amount', None)
        mode = data.pop('amount_mode', 'vat_included')
        if amount is not None:
            try:
                data[total_field] = vat_breakdown(amount, rate, mode)[2]
            except ValueError as exc:
                raise serializers.ValidationError({'amount': str(exc)}) from exc
        if self.instance is None and total_field not in data and total_field == 'total_amount':
            raise serializers.ValidationError({total_field: 'Escribe el importe.'})
        validate_income_vat_change(self.instance, data, self.context.get('settlement'))
        return super().validate(data)


def validate_income_vat_change(instance, data, settlement=False):
    """Protect financial terms after emission or payment, including locked writes."""
    if instance is not None and instance._meta.model_name == 'incomerecord':
        financial_change = (
            ('vat_rate' in data and data['vat_rate'] != instance.vat_rate)
            or ('total_amount' in data and data['total_amount'] != instance.total_amount)
        )
        if financial_change and not settlement:
            if instance.collection_documents.exclude(commercial_status__in=('draft', 'cancelled')).exists():
                raise serializers.ValidationError({'vat_rate': 'Anula la cuenta emitida antes de cambiar el importe o el IVA del ingreso.'})
            if 'vat_rate' in data and data['vat_rate'] != instance.vat_rate and (instance.liquid_records.exists() or instance.deduction_records.exists()):
                raise serializers.ValidationError({'vat_rate': 'El IVA no puede cambiar después de registrar pagos o deducciones.'})
