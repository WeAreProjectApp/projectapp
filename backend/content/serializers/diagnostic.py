from content.serializers.editorial import EditorialModelSerializer
"""Serializers for the WebAppDiagnostic feature."""

from rest_framework import serializers

from accounts.models import UserProfile
from accounts.services.proposal_client_service import (
    build_client_display_name,
    sync_diagnostic_snapshot,
)
from content.models import (
    DiagnosticAttachment,
    DiagnosticChangeLog,
    DiagnosticDefaultConfig,
    DiagnosticSection,
    WebAppDiagnostic,
)
from content.services import diagnostic_service
from content.services.editorial_format import validate_nested_formats
from content.utils import validate_editable_slug

# Whitelist of render_context keys that are safe to expose on the public
# client-facing endpoint. Everything else (e.g. controllers_disconnected,
# *_count raw numbers used only for admin-facing hints) stays admin-only.
PUBLIC_RENDER_CONTEXT_KEYS = frozenset({
    'client_name',
    'investment_amount',
    'currency',
    'payment_initial_pct',
    'payment_final_pct',
    'duration_label',
    'size_category_label',
    'stack_backend_name',
    'stack_backend_version',
    'stack_frontend_name',
    'stack_frontend_version',
    'entities_count', 'entities_size',
    'routes_total', 'routes_size',
    'frontend_routes_count', 'frontend_routes_size',
    'components_count', 'components_size',
    'external_integrations', 'integrations_size',
    'modules_count', 'modules_size', 'modules_list',
})


def _render_context_for(serializer, diagnostic):
    """Build-or-reuse the render_context dict scoped to one serializer instance.

    Avoids recomputing ``build_render_context`` for multiple SerializerMethodFields
    on the same detail response.
    """
    cached = getattr(serializer, '_cached_render_context', None)
    if cached is None:
        cached = diagnostic_service.build_render_context(diagnostic)
        serializer._cached_render_context = cached
    return cached


class _ClientSummarySerializer(EditorialModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    company = serializers.CharField(source='company_name')
    is_email_placeholder = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'name', 'email', 'company', 'is_email_placeholder']

    def get_name(self, profile):
        return build_client_display_name(profile)

    def get_email(self, profile):
        return profile.user.email or ''


class DiagnosticSectionSerializer(EditorialModelSerializer):
    class Meta:
        model = DiagnosticSection
        fields = [
            'id', 'section_type', 'title', 'order', 'is_enabled',
            'visibility', 'content_json',
        ]
        read_only_fields = ['section_type']


class DiagnosticSectionUpdateSerializer(EditorialModelSerializer):
    class Meta:
        model = DiagnosticSection
        fields = ['title', 'order', 'is_enabled', 'visibility', 'content_json']
        extra_kwargs = {
            'title': {'required': False},
            'order': {'required': False},
            'is_enabled': {'required': False},
            'visibility': {'required': False},
            'content_json': {'required': False},
        }


class DiagnosticChangeLogSerializer(EditorialModelSerializer):
    class Meta:
        model = DiagnosticChangeLog
        fields = [
            'id', 'change_type', 'field_name', 'old_value', 'new_value',
            'description', 'actor_type', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


def serialize_diagnostic_attachment(att):
    display = (
        att.custom_type_label
        if att.document_type == DiagnosticAttachment.DOC_TYPE_OTHER
        and att.custom_type_label
        else att.get_document_type_display()
    )
    return {
        'id': att.id,
        'document_type': att.document_type,
        'document_type_display': display,
        'custom_type_label': att.custom_type_label,
        'title': att.title,
        'file': att.file.url if att.file else None,
        'is_generated': att.is_generated,
        'uploaded_by_name': (
            att.uploaded_by.get_full_name() or att.uploaded_by.username
            if att.uploaded_by else ''
        ),
        'created_at': att.created_at.isoformat(),
    }


class DiagnosticListSerializer(EditorialModelSerializer):
    client = _ClientSummarySerializer(read_only=True)
    public_url = serializers.CharField(read_only=True)

    class Meta:
        model = WebAppDiagnostic
        fields = [
            'id', 'uuid', 'slug', 'title', 'status', 'language',
            'client', 'public_url',
            'client_name', 'client_email', 'client_phone', 'client_company',
            'investment_amount', 'currency', 'duration_label',
            'size_category',
            'view_count', 'last_viewed_at',
            'initial_sent_at', 'final_sent_at', 'responded_at',
            'expires_at', 'is_expired', 'days_remaining',
            'created_at', 'updated_at',
        ]


class DiagnosticDetailSerializer(DiagnosticListSerializer):
    sections = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    change_logs = serializers.SerializerMethodField()
    payment_terms = serializers.JSONField()
    radiography = serializers.JSONField()
    confidentiality_params = serializers.JSONField()
    render_context = serializers.SerializerMethodField()
    available_transitions = serializers.SerializerMethodField()

    class Meta(DiagnosticListSerializer.Meta):
        fields = DiagnosticListSerializer.Meta.fields + [
            'payment_terms', 'radiography', 'confidentiality_params',
            'sections', 'attachments', 'change_logs', 'render_context',
            'available_transitions',
        ]

    def get_sections(self, diagnostic):
        # Model Meta.ordering = ['order'] already sorts; use list() to consume
        # the prefetched cache.
        return DiagnosticSectionSerializer(
            list(diagnostic.sections.all()), many=True,
        ).data

    def get_attachments(self, diagnostic):
        return [
            serialize_diagnostic_attachment(att)
            for att in diagnostic.attachments.all()
        ]

    def get_change_logs(self, diagnostic):
        # Slice the prefetched list in Python to keep the cache intact; an
        # upstream `RelatedManager[:60]` would issue a fresh SQL query.
        return DiagnosticChangeLogSerializer(
            list(diagnostic.change_logs.all())[:60], many=True,
        ).data

    def get_render_context(self, diagnostic):
        return _render_context_for(self, diagnostic)

    def get_available_transitions(self, diagnostic):
        return sorted(
            t.value for t in WebAppDiagnostic.ALLOWED_TRANSITIONS.get(
                diagnostic.status, frozenset(),
            )
        )


class DiagnosticUpdateSerializer(EditorialModelSerializer):
    """Admin update payload — pricing/radiography/client edits."""

    client_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        source='client',
        write_only=True,
        required=False,
        allow_null=False,
    )
    propagate_client_updates = serializers.BooleanField(
        write_only=True, required=False, default=False,
    )

    class Meta:
        model = WebAppDiagnostic
        fields = [
            'title', 'language', 'slug',
            'investment_amount', 'currency', 'payment_terms',
            'duration_label', 'size_category', 'radiography',
            'expires_at',
            'client_id',
            'client_name', 'client_email', 'client_phone', 'client_company',
            'propagate_client_updates',
        ]
        extra_kwargs = {
            'title': {'required': False},
            'language': {'required': False},
            'expires_at': {'required': False, 'allow_null': True},
            'slug': {'required': False, 'allow_blank': True},
            'client_name': {'required': False, 'allow_blank': True},
            'client_email': {'required': False, 'allow_blank': True},
            'client_phone': {'required': False, 'allow_blank': True},
            'client_company': {'required': False, 'allow_blank': True},
        }

    def validate_slug(self, value):
        return validate_editable_slug(
            value, WebAppDiagnostic, self.instance, conflict_phrase='otro diagnóstico',
        )

    def update(self, instance, validated_data):
        validated_data.pop('propagate_client_updates', None)
        new_client = validated_data.get('client')
        client_changed = new_client is not None and new_client.pk != instance.client_id
        diagnostic = super().update(instance, validated_data)
        if client_changed:
            # Reassignment: rebuild the snapshot from the new profile so the
            # list views show the new client, mirroring proposals'
            # sync_snapshot behavior on client_id switches.
            sync_diagnostic_snapshot(diagnostic)
        return diagnostic


class PublicDiagnosticSerializer(EditorialModelSerializer):
    client_name = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()
    render_context = serializers.SerializerMethodField()

    class Meta:
        model = WebAppDiagnostic
        fields = [
            'uuid', 'slug', 'title', 'status', 'language',
            'client_name', 'investment_amount', 'currency',
            'duration_label', 'size_category',
            'initial_sent_at', 'final_sent_at', 'responded_at',
            'expires_at', 'is_expired', 'days_remaining',
            'sections', 'render_context',
        ]

    def get_client_name(self, diagnostic):
        return build_client_display_name(diagnostic.client)

    def get_sections(self, diagnostic):
        return DiagnosticSectionSerializer(
            diagnostic_service.visible_sections(diagnostic),
            many=True,
        ).data

    def get_render_context(self, diagnostic):
        full = _render_context_for(self, diagnostic)
        return {k: v for k, v in full.items() if k in PUBLIC_RENDER_CONTEXT_KEYS}


class ConfidentialityParamsSerializer(serializers.Serializer):
    """Validate the params dict that fills the NDA template placeholders.

    Client-side fields are optional; missing/empty values render as
    ``_______________`` in the generated PDF, so the document can be printed
    and completed by hand. The contractor's identification is the exception:
    the NDA has to name EL CONSULTOR by NIT or by cédula, so at least one of
    the two is required.
    """

    client_full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    client_cedula = serializers.CharField(required=False, allow_blank=True, max_length=64)
    client_legal_representative = serializers.CharField(required=False, allow_blank=True, max_length=255)
    client_email = serializers.CharField(required=False, allow_blank=True, max_length=255)
    contractor_full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    contractor_nit = serializers.CharField(required=False, allow_blank=True, max_length=64)
    contractor_cedula = serializers.CharField(required=False, allow_blank=True, max_length=64)
    contractor_email = serializers.CharField(required=False, allow_blank=True, max_length=255)
    contract_city = serializers.CharField(required=False, allow_blank=True, max_length=120)
    contract_day = serializers.CharField(required=False, allow_blank=True, max_length=8)
    contract_month = serializers.CharField(required=False, allow_blank=True, max_length=20)
    contract_year = serializers.CharField(required=False, allow_blank=True, max_length=8)
    penal_clause_value = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, data):
        if not (
            (data.get('contractor_nit') or '').strip()
            or (data.get('contractor_cedula') or '').strip()
        ):
            raise serializers.ValidationError(
                {'contractor_nit': 'Indica el NIT o la cédula del contratista (al menos uno).'}
            )
        return data


class DiagnosticDefaultConfigSerializer(EditorialModelSerializer):
    """Serializer for the per-language diagnostic defaults singleton."""

    class Meta:
        model = DiagnosticDefaultConfig
        fields = (
            'id',
            'language',
            'sections_json',
            'payment_initial_pct',
            'payment_final_pct',
            'default_currency',
            'default_investment_amount',
            'default_duration_label',
            'expiration_days',
            'reminder_days',
            'urgency_reminder_days',
            'default_slug_pattern',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_sections_json(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'sections_json must be a JSON array (list).'
            )
        validate_nested_formats(value)
        required_keys = {'section_type', 'title', 'order', 'content_json'}
        normalized = []
        for i, section in enumerate(value):
            if not isinstance(section, dict):
                raise serializers.ValidationError(
                    f'Each section must be a dict (index {i}).'
                )
            missing = required_keys - set(section.keys())
            if missing:
                raise serializers.ValidationError(
                    f'Section at index {i} is missing keys: {sorted(missing)}'
                )
            cloned = dict(section)
            content_json = cloned.get('content_json')
            cloned['content_json'] = content_json if isinstance(content_json, dict) else {}
            normalized.append(cloned)
        return normalized

    def validate(self, attrs):
        initial = attrs.get(
            'payment_initial_pct',
            getattr(self.instance, 'payment_initial_pct', 60),
        )
        final = attrs.get(
            'payment_final_pct',
            getattr(self.instance, 'payment_final_pct', 40),
        )
        if (initial or 0) + (final or 0) != 100:
            raise serializers.ValidationError({
                'payment_initial_pct': (
                    'payment_initial_pct + payment_final_pct must equal 100.'
                ),
            })
        return attrs
