from decimal import Decimal

from rest_framework import serializers

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    DocumentPaymentMethod,
    DocumentType,
)
from content.services.collection_account_service import commercial_is_overdue


class DocumentTypeBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields = ('id', 'code', 'name')


class DocumentCollectionAccountSerializer(serializers.ModelSerializer):
    """Snapshot payer/customer fields are filled on issue; editable in draft: billing, terms, support."""

    class Meta:
        model = DocumentCollectionAccount
        fields = (
            'vat_rate',
            'billing_concept',
            'payment_term_type',
            'payment_term_days',
            'payer_name',
            'payer_identification',
            'payer_identification_type',
            'payer_address',
            'payer_phone',
            'payer_email',
            'customer_name',
            'customer_identification',
            'customer_identification_type',
            'customer_contact_name',
            'customer_email',
            'customer_address',
            'observations',
            'support_reference',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')


class DocumentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentItem
        fields = (
            'id',
            'position',
            'item_type',
            'description',
            'quantity',
            'unit_price',
            'discount_amount',
            'tax_amount',
            'line_total',
            'period_start',
            'period_end',
            'reference_type',
            'reference_id',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class DocumentItemWriteSerializer(serializers.ModelSerializer):
    """Payload for replacing line items on draft update (no id)."""

    class Meta:
        model = DocumentItem
        fields = (
            'position',
            'item_type',
            'description',
            'quantity',
            'unit_price',
            'discount_amount',
            'tax_amount',
            'line_total',
            'period_start',
            'period_end',
            'reference_type',
            'reference_id',
        )


class DocumentPaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPaymentMethod
        fields = (
            'id',
            'payment_method_type',
            'bank_name',
            'account_type',
            'account_number',
            'account_holder_name',
            'account_holder_identification',
            'payment_instructions',
            'is_primary',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class DocumentPaymentMethodWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentPaymentMethod
        fields = (
            'payment_method_type',
            'bank_name',
            'account_type',
            'account_number',
            'account_holder_name',
            'account_holder_identification',
            'payment_instructions',
            'is_primary',
        )


class CollectionAccountListSerializer(serializers.ModelSerializer):
    document_type = DocumentTypeBriefSerializer(read_only=True)
    is_overdue = serializers.SerializerMethodField()
    project_id = serializers.IntegerField(read_only=True)
    client_user_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Document
        fields = (
            'id',
            'uuid',
            'document_type',
            'title',
            'public_number',
            'commercial_status',
            'issue_date',
            'due_date',
            'currency',
            'total',
            'project_id',
            'client_user_id',
            'created_at',
            'updated_at',
            'is_overdue',
        )

    def get_is_overdue(self, obj):
        return commercial_is_overdue(obj)


class CollectionAccountDetailSerializer(serializers.ModelSerializer):
    vat_rate = serializers.DecimalField(source='collection_account.vat_rate', max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    document_type = DocumentTypeBriefSerializer(read_only=True)
    collection_account = serializers.SerializerMethodField()
    items = DocumentItemSerializer(many=True, read_only=True)
    payment_methods = DocumentPaymentMethodSerializer(many=True, read_only=True)
    is_overdue = serializers.SerializerMethodField()
    project_id = serializers.IntegerField(allow_null=True, required=False)
    client_user_id = serializers.IntegerField(allow_null=True, required=False)
    issuer_id = serializers.IntegerField(allow_null=True, read_only=True)

    class Meta:
        model = Document
        fields = (
            'id',
            'uuid',
            'document_type',
            'title',
            'public_number',
            'commercial_status',
            'issue_date',
            'due_date',
            'city',
            'currency',
            'vat_rate',
            'subtotal',
            'discount_total',
            'tax_total',
            'total',
            'notes',
            'terms_and_conditions',
            'template_version',
            'metadata',
            'project_id',
            'client_user_id',
            'issuer_id',
            'collection_account',
            'items',
            'payment_methods',
            'created_at',
            'updated_at',
            'is_overdue',
        )
        read_only_fields = (
            'uuid',
            'public_number',
            'commercial_status',
            'issue_date',
            'issuer_id',
            'created_at',
            'updated_at',
            'is_overdue',
        )

    def get_collection_account(self, obj):
        ext = DocumentCollectionAccount.objects.filter(document_id=obj.pk).first()
        if not ext:
            return None
        return DocumentCollectionAccountSerializer(ext).data

    def get_is_overdue(self, obj):
        return commercial_is_overdue(obj)


class CollectionAccountCreateSerializer(serializers.Serializer):
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), required=False, allow_null=True)
    title = serializers.CharField(max_length=255)
    project_id = serializers.IntegerField(required=False, allow_null=True)
    deliverable_id = serializers.IntegerField(required=False, allow_null=True)
    client_user_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, default='COP')
    city = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')
    discount_total = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True, default='')
    billing_concept = serializers.CharField(required=False, allow_blank=True, default='')
    payment_term_type = serializers.ChoiceField(
        choices=DocumentCollectionAccount.PaymentTermType.choices,
        default=DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE,
    )
    payment_term_days = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    support_reference = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if not attrs.get('project_id') and not attrs.get('client_user_id'):
            raise serializers.ValidationError(
                'Either project_id or client_user_id is required.',
            )
        pid = attrs.get('project_id')
        did = attrs.get('deliverable_id')
        if did is not None and pid is None:
            raise serializers.ValidationError(
                {'deliverable_id': 'deliverable_id requires project_id.'},
            )
        if did is not None:
            from accounts.models import Deliverable

            d = Deliverable.objects.filter(pk=did, project_id=pid).first()
            if not d:
                raise serializers.ValidationError(
                    {'deliverable_id': 'Entregable no encontrado en este proyecto.'},
                )
        return attrs


class CollectionAccountUpdateSerializer(serializers.Serializer):
    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False)
    project_id = serializers.IntegerField(required=False, allow_null=True)
    client_user_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    discount_total = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    due_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    terms_and_conditions = serializers.CharField(required=False, allow_blank=True)
    billing_concept = serializers.CharField(required=False, allow_blank=True)
    payment_term_type = serializers.ChoiceField(
        choices=DocumentCollectionAccount.PaymentTermType.choices,
        required=False,
    )
    payment_term_days = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    support_reference = serializers.CharField(required=False, allow_blank=True)
    observations = serializers.CharField(required=False, allow_blank=True)
    items = DocumentItemWriteSerializer(many=True, required=False)
    payment_methods = DocumentPaymentMethodWriteSerializer(many=True, required=False)
