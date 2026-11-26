from decimal import Decimal

from rest_framework import serializers

from content.serializers.accounting import HostingCycleCreateSerializer
from content.serializers.hosting_receipts import HostingReceiptSerializer


class NextIncomeInput(serializers.Serializer):
    reference_income_id = serializers.IntegerField(min_value=1, required=False)
    version = serializers.CharField(max_length=64, required=False)


class CycleReceiptInput(HostingCycleCreateSerializer):
    income_id = serializers.IntegerField(min_value=1)
    request_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    paid_at = serializers.DateField()
    hosting_receipt = HostingReceiptSerializer()
    preview_hash = serializers.CharField(max_length=64, required=False)
    destination = serializers.ChoiceField(choices=('pocket', 'partners'), default='pocket')
