"""Public account serializer deliberately excludes private financial metadata."""
from rest_framework import serializers
from accounts.services.billing_context import context_data
from content.models import Document
from content.services.collection_account_service import commercial_is_overdue


class BillingAccountListSerializer(serializers.ModelSerializer):
    context = serializers.SerializerMethodField()
    project_name = serializers.CharField(source='project.name', default='')
    project_id = serializers.IntegerField(read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ('id', 'title', 'public_number', 'commercial_status', 'issue_date', 'due_date',
                  'currency', 'total', 'project_id', 'project_name', 'context', 'is_overdue')

    def get_context(self, obj):
        if not obj.project_id:
            return {**context_data(None), 'status': 'not_applicable'}
        return context_data(getattr(obj, 'billing_context', None))

    def get_is_overdue(self, obj):
        return commercial_is_overdue(obj)


class BillingAccountDetailSerializer(BillingAccountListSerializer):
    collection_account = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    payment_methods = serializers.SerializerMethodField()

    class Meta(BillingAccountListSerializer.Meta):
        fields = BillingAccountListSerializer.Meta.fields + (
            'city', 'subtotal', 'discount_total', 'tax_total', 'terms_and_conditions',
            'collection_account', 'items', 'payment_methods',
        )

    def get_collection_account(self, obj):
        ext = getattr(obj, 'collection_account', None)
        if not ext:
            return None
        return {name: getattr(ext, name) for name in (
            'billing_concept', 'payment_term_type', 'payment_term_days', 'observations',
            'customer_name', 'customer_email', 'customer_identification', 'customer_identification_type',
            'customer_project_name', 'payer_name', 'payer_identification',
        )}

    def get_items(self, obj):
        return [{name: getattr(item, name) for name in (
            'id', 'description', 'quantity', 'unit_price', 'line_total', 'period_start', 'period_end',
        )} for item in obj.items.all()]

    def get_payment_methods(self, obj):
        return [{name: getattr(method, name) for name in (
            'id', 'payment_method_type', 'bank_name', 'account_type', 'account_number',
            'account_holder_name', 'payment_instructions', 'is_primary',
        )} for method in obj.payment_methods.all()]
