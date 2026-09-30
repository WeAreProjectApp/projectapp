"""Serializers for the credit-card statement sub-module (extractos)."""

from decimal import Decimal

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from content.models import (
    CreditCardStatement,
    CreditCardTransaction,
    MerchantAlias,
    normalize_descriptor,
)

from .accounting import MonthPeriodField, PeriodReadMixin


class CreditCardTransactionSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(
        source='get_category_display', read_only=True,
    )
    installment_label = serializers.SerializerMethodField()

    class Meta:
        model = CreditCardTransaction
        fields = (
            'id', 'statement', 'transaction_date', 'raw_description',
            'merchant_name', 'category', 'category_label', 'amount',
            'original_amount', 'original_currency',
            'installment_number', 'installments_total', 'installment_label',
            'is_identified', 'is_reversal', 'notes', 'created_at',
            'updated_at',
        )

    def get_installment_label(self, obj):
        if obj.installment_number and obj.installments_total:
            return f'{obj.installment_number}/{obj.installments_total}'
        return ''


class CreditCardTransactionWriteSerializer(serializers.ModelSerializer):
    # Negatives allowed on purpose: refunds/reversals appear on statements.
    class Meta:
        model = CreditCardTransaction
        fields = (
            'transaction_date', 'raw_description', 'merchant_name',
            'category', 'amount', 'original_amount', 'original_currency',
            'installment_number', 'installments_total', 'is_identified',
            'is_reversal', 'notes',
        )
        extra_kwargs = {
            'merchant_name': {'required': False},
            'category': {'required': False},
            'original_amount': {'required': False},
            'original_currency': {'required': False},
            'installment_number': {'required': False},
            'installments_total': {'required': False},
            'is_identified': {'required': False},
            'is_reversal': {'required': False},
            'notes': {'required': False},
        }

    def validate(self, attrs):
        def current(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None) if self.instance else None

        number = current('installment_number')
        total = current('installments_total')
        if (number is None) != (total is None):
            raise serializers.ValidationError(
                'Las cuotas requieren número y total (ambos o ninguno).'
            )
        if number is not None and total is not None and number > total:
            raise serializers.ValidationError(
                'El número de cuota no puede superar el total de cuotas.'
            )

        original_amount = current('original_amount')
        original_currency = current('original_currency') or ''
        if (original_amount is None) != (original_currency == ''):
            raise serializers.ValidationError(
                'El valor original requiere monto y moneda (ambos o ninguno).'
            )
        return attrs


class CreditCardStatementSerializer(PeriodReadMixin, serializers.ModelSerializer):
    status_label = serializers.CharField(
        source='get_status_display', read_only=True,
    )
    transactions_count = serializers.SerializerMethodField()
    transactions_sum = serializers.SerializerMethodField()
    pdf_file_url = serializers.SerializerMethodField()

    class Meta:
        model = CreditCardStatement
        fields = (
            'id', 'card_name', 'period', 'period_label', 'period_date',
            'status', 'status_label', 'purchases_total', 'previous_balance',
            'payments_total', 'interest_and_fees', 'closing_balance',
            'minimum_payment', 'due_date', 'notes', 'source_ref',
            'transactions_count', 'transactions_sum', 'pdf_file_url',
            'created_at', 'updated_at',
        )

    def get_transactions_count(self, obj):
        if hasattr(obj, '_transactions_count'):
            return obj._transactions_count if obj._transactions_count is not None else 0
        return obj.transactions.count()

    def get_transactions_sum(self, obj):
        if hasattr(obj, '_transactions_sum'):
            if obj._transactions_sum is None:
                return '0'
            return str(obj._transactions_sum.quantize(Decimal('0.01')))
        total = sum((tx.amount for tx in obj.transactions.all()), start=0)
        return str(total)

    def get_pdf_file_url(self, obj):
        return obj.pdf_file.url if obj.pdf_file else None


class CreditCardStatementDetailSerializer(CreditCardStatementSerializer):
    transactions = CreditCardTransactionSerializer(many=True, read_only=True)
    category_totals = serializers.SerializerMethodField()

    class Meta(CreditCardStatementSerializer.Meta):
        fields = CreditCardStatementSerializer.Meta.fields + (
            'transactions', 'category_totals',
        )

    def get_category_totals(self, obj):
        from content.services.accounting_statement_service import (
            statement_category_totals,
        )

        return statement_category_totals(obj)


class CreditCardStatementWriteSerializer(serializers.ModelSerializer):
    """Header write serializer. ``status`` is excluded on purpose: the
    lifecycle only moves through the finalize/reopen endpoints."""

    period_date = MonthPeriodField()

    class Meta:
        model = CreditCardStatement
        fields = (
            'card_name', 'period_date', 'purchases_total',
            'previous_balance', 'payments_total', 'interest_and_fees',
            'closing_balance', 'minimum_payment', 'due_date',
            'notes', 'source_ref',
        )
        extra_kwargs = {
            'previous_balance': {'required': False},
            'payments_total': {'required': False},
            'interest_and_fees': {'required': False},
            'closing_balance': {'required': False},
            'minimum_payment': {'required': False},
            'due_date': {'required': False},
            'notes': {'required': False},
            'source_ref': {'required': False},
        }
        validators = [
            UniqueTogetherValidator(
                queryset=CreditCardStatement.objects.all(),
                fields=('card_name', 'period_date'),
                message='Ya existe un extracto de esa tarjeta para ese mes.',
            ),
        ]


class MerchantAliasSerializer(serializers.ModelSerializer):
    default_category_label = serializers.CharField(
        source='get_default_category_display', read_only=True,
    )

    class Meta:
        model = MerchantAlias
        fields = (
            'id', 'match_text', 'merchant_name', 'default_category',
            'default_category_label', 'is_gateway', 'notes', 'created_at',
            'updated_at',
        )


class MerchantAliasWriteSerializer(serializers.ModelSerializer):
    # Uniqueness is validated here on the NORMALIZED text (the field's own
    # UniqueValidator would only see the raw input).
    match_text = serializers.CharField(max_length=255)

    class Meta:
        model = MerchantAlias
        fields = (
            'match_text', 'merchant_name', 'default_category', 'is_gateway',
            'notes',
        )
        extra_kwargs = {
            'default_category': {'required': False},
            'is_gateway': {'required': False},
            'notes': {'required': False},
        }

    def validate_match_text(self, value):
        normalized = normalize_descriptor(value)
        if not normalized:
            raise serializers.ValidationError(
                'El texto a mapear no puede quedar vacío.'
            )
        queryset = MerchantAlias.objects.filter(match_text=normalized)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                'Ya existe un alias para ese texto.'
            )
        return normalized
