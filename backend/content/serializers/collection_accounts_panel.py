"""Serializers for the panel (accounting) view of collection accounts."""
from decimal import Decimal

from rest_framework import serializers
from accounts.services.billing_context import context_data
from accounts.serializers_billing_context import BillingContextFields

from content.models import Document, DocumentItem, DocumentPaymentMethod
from content.services.collection_account_service import (
    collection_account_was_delivered,
    commercial_is_overdue,
)

STATUS_LABELS = {
    'draft': 'Borrador',
    'issued': 'Emitida',
    'paid': 'Pagada',
    'cancelled': 'Anulada',
}


class CollectionAccountPanelListSerializer(serializers.ModelSerializer):
    context = serializers.SerializerMethodField()
    vat_rate = serializers.DecimalField(source='collection_account.vat_rate', max_digits=5, decimal_places=2, read_only=True, allow_null=True)

    def get_context(self, obj):
        return context_data(getattr(obj, 'billing_context', None))

    customer_name = serializers.CharField(
        source='collection_account.customer_name', read_only=True, default='',
    )
    customer_email = serializers.CharField(
        source='collection_account.customer_email', read_only=True, default='',
    )
    billing_concept = serializers.CharField(
        source='collection_account.billing_concept', read_only=True, default='',
    )
    commercial_status_label = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    origin = serializers.SerializerMethodField()
    origin_label = serializers.SerializerMethodField()
    income_kind = serializers.SerializerMethodField()
    # The live client relation, which is what the Cliente column sorts and
    # filters on. `customer_name` stays alongside it as the FROZEN name the
    # PDF actually printed: the two can legitimately differ on a document
    # issued before this rule, and the panel shows that rather than hiding it.
    client = serializers.SerializerMethodField()
    client_display_name = serializers.SerializerMethodField()
    # Same contract as the Cliente column above: the LIVE relation answers —
    # it is what the project filter already matches on, so cell and filter
    # can no longer contradict each other. The frozen
    # `customer_project_name` snapshot remains the PDF's truth and the
    # fallback for FK-null rows (project deleted, or issued before the
    # relation existed). Reading only the snapshot kept every draft blank
    # and froze issued rows to whatever was true at issue time.
    project_name = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            'context',
            'id', 'uuid', 'public_number', 'title',
            'billing_concept', 'customer_name', 'customer_email',
            'client', 'client_display_name', 'project_name',
            'origin', 'origin_label', 'hosting_record_id', 'project_id',
            'income_record_id', 'income_kind',
            'subtotal', 'tax_total', 'vat_rate', 'total', 'currency',
            'issue_date', 'due_date',
            'commercial_status', 'commercial_status_label', 'is_overdue',
            # The delete rule, resolved server-side: the panel must not have to
            # re-derive "did this ever reach the client" from data it cannot see.
            'can_delete',
            # Internal-only: the operator's own note about the cuenta, never
            # rendered in the PDF nor the client email. It travels in the list
            # so the monitor can show it back without a detail round trip —
            # a field you fill and can never read again is a dead end.
            'notes',
            'created_at', 'updated_at',
        )

    def _client_profile(self, obj):
        if not obj.client_user_id:
            return None
        return getattr(obj.client_user, 'profile', None)

    def get_client(self, obj):
        profile = self._client_profile(obj)
        return profile.pk if profile else None

    def get_client_display_name(self, obj):
        """None keeps 'sin cliente' distinct from a blank name."""
        profile = self._client_profile(obj)
        if profile is None:
            return None
        from accounts.services.proposal_client_service import (
            build_client_display_name,
        )

        return build_client_display_name(profile)

    def get_project_name(self, obj):
        if obj.project_id:
            return obj.project.name
        extension = getattr(obj, 'collection_account', None)
        return extension.customer_project_name if extension else ''

    def get_commercial_status_label(self, obj):
        return STATUS_LABELS.get(obj.commercial_status, obj.commercial_status)

    def get_is_overdue(self, obj):
        return commercial_is_overdue(obj)

    def get_can_delete(self, obj):
        """Mirrors ``delete_collection_account``'s guards, one row at a time.

        Reads the ``was_delivered`` annotation the list view attaches, falling
        back to the per-object query for the detail endpoint (same technique as
        the income serializer's collection-account block): one row does not
        justify a second query, a hundred rows do.
        """
        if obj.commercial_status == Document.CommercialStatus.PAID:
            return False
        if obj.commercial_status == Document.CommercialStatus.CANCELLED:
            return True
        delivered = obj.__dict__.get('was_delivered')
        if delivered is None:
            delivered = collection_account_was_delivered(obj)
        return not delivered

    def get_income_kind(self, obj):
        if obj.income_record_id and obj.income_record:
            return obj.income_record.kind
        return None

    def get_origin(self, obj):
        """Which record the cuenta was raised from.

        `project` ranks LAST on purpose. It used to outrank `income`, which
        was harmless only while nothing populated `Document.project` from the
        panel; now that a cuenta inherits its income's project, that order
        would relabel every income-driven cuenta as project-originated and
        break the origin filter. A project is a dimension every origin
        carries — only a document with neither hosting nor income is
        genuinely project-originated, which is the platform/JWT flow.
        """
        if obj.hosting_record_id:
            return 'hosting'
        if obj.income_record_id:
            return 'income'
        if obj.project_id:
            return 'project'
        return 'other'

    def get_origin_label(self, obj):
        """The origin TYPE only.

        It used to append the hosting's client, the project or the income's
        concept — data that now has columns of its own, so repeating it here
        printed the client twice in every hosting row.
        """
        return {
            'hosting': 'Hosting',
            'income': 'Ingreso',
            'project': 'Proyecto',
        }.get(self.get_origin(obj), 'Otro')


class _PanelItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentItem
        fields = (
            'id', 'position', 'item_type', 'description', 'quantity',
            'unit_price', 'discount_amount', 'tax_amount', 'line_total',
            'period_start', 'period_end',
        )


class _PanelPaymentMethodSerializer(serializers.ModelSerializer):
    payment_method_type_label = serializers.CharField(
        source='get_payment_method_type_display', read_only=True,
    )

    class Meta:
        model = DocumentPaymentMethod
        fields = (
            'id', 'payment_method_type', 'payment_method_type_label',
            'bank_name', 'account_type', 'account_number',
            'account_holder_name', 'payment_instructions', 'is_primary',
        )


class CollectionAccountPanelDetailSerializer(CollectionAccountPanelListSerializer):
    items = _PanelItemSerializer(many=True, read_only=True)
    payment_methods = _PanelPaymentMethodSerializer(many=True, read_only=True)

    class Meta(CollectionAccountPanelListSerializer.Meta):
        fields = CollectionAccountPanelListSerializer.Meta.fields + (
            'items', 'payment_methods',
        )


class _CreateItemSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'), required=False)
    amount_mode = serializers.ChoiceField(choices=('before_vat', 'vat_included'), required=False)

    def validate(self, data):
        if ('amount' in data) == ('unit_price' in data):
            raise serializers.ValidationError({'amount': 'Envía un único importe por concepto.'})
        if 'amount_mode' in data and 'amount' not in data:
            raise serializers.ValidationError({'amount': 'Escribe el importe.'})
        return data
    # Unbounded on purpose: this is the "Descripción del concepto" the operator
    # writes in the form, several paragraphs long when the cuenta bills
    # attended requirements. Blank falls back to the concepto in the service.
    description = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'),
        required=False, default=Decimal('1'),
    )
    unit_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'), required=False,
    )
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)


class _CustomerOverrideSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
    identification = serializers.CharField(
        max_length=64, required=False, allow_blank=True,
    )
    identification_type = serializers.CharField(
        max_length=32, required=False, allow_blank=True,
    )
    email = serializers.EmailField(required=False, allow_blank=True)
    contact_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
    )
    address = serializers.CharField(
        max_length=512, required=False, allow_blank=True,
    )


class CollectionAccountCreateSerializer(BillingContextFields):
    """Shared payload of the panel create and preview endpoints."""

    vat_rate = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'), required=False, allow_null=True)
    # UserProfile pk — what ClientAutocomplete / the clients module handle.
    client_profile_id = serializers.IntegerField()
    income_record_id = serializers.IntegerField()
    # Sent ONLY when the operator edited the server suggestion; blank means
    # auto-allocate from the client's series.
    public_number = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default='',
    )
    billing_concept = serializers.CharField(
        max_length=512, required=False, allow_blank=True, default='',
    )
    items = _CreateItemSerializer(many=True, allow_empty=False)
    # 0 is a legitimate term: immediate payment against presentation, which
    # issues the cuenta with no due date at all. Negative days stay rejected.
    payment_term_days = serializers.IntegerField(
        min_value=0, max_value=120, required=False, allow_null=True,
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.CharField(
        max_length=3, required=False, allow_blank=True, default='COP',
    )
    city = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default='',
    )
    customer = _CustomerOverrideSerializer(required=False)
    observations = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')
