from rest_framework import serializers

from accounts.models import UserProfile
from accounts.services import proposal_client_service
from content.services.proposal_module_links import (
    ensure_functional_requirements_item_ids,
    normalize_technical_document_module_links,
)
from content.services.section_content_schemas import validate_section_content
from content.models import (
    BusinessProposal,
    EmailTemplateConfig,
    Nationality,
    ProposalAlert,
    ProposalProjectStage,
    ProposalSection,
    ProposalShareLink,
    ProposalDefaultConfig,
)
from content.serializers.proposal_clients import (
    ProposalClientSerializer,
    ProposalNestedClientSerializer,
)
from content.utils import validate_editable_slug, validate_email_domain_mx


def _validate_client_email_mx(value):
    """Shared field validator: reject emails whose domain has no MX/A records."""
    if value and not validate_email_domain_mx(value):
        raise serializers.ValidationError(
            'El dominio de este correo no puede recibir emails (sin registros MX).'
        )
    return value


class ProposalProjectStageSerializer(serializers.ModelSerializer):
    """
    Serializer for ProposalProjectStage — internal project execution tracking.

    Exposes the stage dates + completion + alert timestamps. Used by the
    admin Cronograma tab to read stage state. Writes go through the
    dedicated update_project_stage / complete_project_stage endpoints,
    not through ProposalDetailSerializer (which is read-only for stages).
    """
    stage_label = serializers.CharField(source='get_stage_key_display', read_only=True)

    class Meta:
        model = ProposalProjectStage
        fields = (
            'id', 'stage_key', 'stage_label', 'order',
            'start_date', 'end_date', 'completed_at',
            'warning_sent_at', 'last_overdue_reminder_at',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'stage_label', 'completed_at',
            'warning_sent_at', 'last_overdue_reminder_at',
            'created_at', 'updated_at',
        )

    def validate(self, attrs):
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start and end and start > end:
            raise serializers.ValidationError({
                'end_date': 'La fecha fin debe ser igual o posterior a la fecha de inicio.',
            })
        return attrs


class ProposalSectionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing proposal sections in admin views.
    """

    class Meta:
        model = ProposalSection
        fields = ('id', 'section_type', 'title', 'order', 'is_enabled', 'is_wide_panel')


class ProposalSectionDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for proposal sections, including content_json.
    """

    class Meta:
        model = ProposalSection
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # The investment section's hostingPlan mirrors fields that live on
        # BusinessProposal (hosting_percent, hosting_discount_*). Normalize
        # here so every consumer — public UI, PDF renderer, platform
        # onboarding — reads the same numbers without re-implementing the
        # override locally.
        if (instance.section_type == 'investment'
                and isinstance(data.get('content_json'), dict)):
            from content.services.proposal_service import normalize_hosting_plan
            cj = data['content_json']
            if isinstance(cj.get('hostingPlan'), dict):
                cj['hostingPlan'] = normalize_hosting_plan(
                    instance.proposal, cj['hostingPlan']
                )
        return data


class ProposalListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing proposals in admin views.
    Includes computed fields for expiration status.
    """
    days_remaining = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    available_transitions = serializers.SerializerMethodField()
    client = ProposalClientSerializer(read_only=True)

    class Meta:
        model = BusinessProposal
        fields = (
            'id', 'uuid', 'title', 'client_name', 'client_email', 'status',
            'total_investment', 'currency', 'nationality', 'expires_at',
            'view_count', 'created_at', 'days_remaining', 'is_expired',
            'is_active', 'show_contract_terms', 'automations_paused',
            'responded_at', 'last_activity_at',
            'project_type', 'market_type', 'client_phone',
            'project_type_custom', 'market_type_custom',
            'cached_heat_score', 'engagement_declining',
            'available_transitions', 'language', 'sent_at',
            'email_intro',
            'client',
        )

    def get_days_remaining(self, obj):
        return obj.days_remaining

    def get_is_expired(self, obj):
        return obj.is_expired

    def get_available_transitions(self, obj):
        return obj.available_transitions


class ProposalDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for a business proposal, used by both client and admin detail views.

    Includes nested sections (filtered by is_enabled for client, all for admin),
    nested requirement groups with items, and computed properties.
    """

    # The public payload is readable by anyone holding the proposal link, and
    # the public page reads none of these. contract_params alone carries the
    # client's cédula and email and the contractor's NIT and bank account.
    PUBLIC_HIDDEN_FIELDS = (
        'contract_params', 'change_logs', 'client', 'client_email', 'client_phone',
        'automations_paused', 'reminder_days', 'urgency_reminder_days',
        'reminder_sent_at', 'urgency_email_sent_at',
        'email_intro', 'email_features', 'email_method_phases', 'email_signed_by',
        'view_count', 'first_viewed_at', 'last_activity_at', 'responded_at',
        'available_transitions', 'proposal_documents',
        'platform_onboarding_completed_at', 'platform_onboarding_status',
        'first_view_notification',
    )

    sections = serializers.SerializerMethodField()
    # project_stages is internal-only execution tracking; the model docstring
    # explicitly says it must never be rendered to the client. Gate by is_admin.
    project_stages = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    validity_text = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()
    discounted_investment = serializers.SerializerMethodField()
    effective_total_investment = serializers.SerializerMethodField()
    has_confirmed_module_selection = serializers.ReadOnlyField()
    available_transitions = serializers.SerializerMethodField()
    proposal_documents = serializers.SerializerMethodField()
    first_view_notification = serializers.SerializerMethodField()
    # Slim on purpose: the client aggregates cost ~8-10 unannotated queries and
    # no proposal surface reads them. See ProposalNestedClientSerializer.
    client = ProposalNestedClientSerializer(read_only=True)

    change_logs = serializers.SerializerMethodField()

    class Meta:
        model = BusinessProposal
        fields = (
            'id', 'uuid', 'title', 'client_name', 'client_email', 'slug',
            'language', 'total_investment', 'currency', 'nationality',
            'hosting_percent',
            'hosting_discount_nine_month',
            'hosting_discount_semiannual', 'hosting_discount_quarterly',
            'status', 'expires_at',
            'reminder_days', 'urgency_reminder_days', 'discount_percent',
            'is_active', 'show_contract_terms', 'automations_paused',
            'reminder_sent_at', 'urgency_email_sent_at',
            'project_type', 'market_type', 'client_phone',
            'project_type_custom', 'market_type_custom',
            'last_activity_at',
            'view_count', 'first_viewed_at', 'sent_at', 'responded_at',
            'created_at', 'updated_at',
            'email_intro', 'email_features', 'email_method_phases', 'email_signed_by',
            'sections', 'project_stages', 'change_logs',
            'days_remaining', 'is_expired', 'validity_text', 'public_url',
            'discounted_investment', 'effective_total_investment',
            'selected_modules', 'has_confirmed_module_selection',
            'contract_params', 'available_transitions', 'proposal_documents',
            'platform_onboarding_completed_at',
            'platform_onboarding_status',
            'first_view_notification',
            'client',
        )

    def get_fields(self):
        # Dropping the fields here, not in to_representation, also skips
        # computing them (change logs, documents, transitions) for the public.
        fields = super().get_fields()
        if not self.context.get('is_admin', False):
            for name in self.PUBLIC_HIDDEN_FIELDS:
                fields.pop(name, None)
        return fields

    def get_project_stages(self, obj):
        """Return project_stages only for admin requests; empty for public."""
        if not self.context.get('is_admin', False):
            return []
        stages = obj.project_stages.all()
        return ProposalProjectStageSerializer(stages, many=True).data

    def get_sections(self, obj):
        """
        Return sections ordered by 'order'.
        For public (client) requests, only enabled sections are returned.
        For admin requests, all sections are returned.
        """
        is_admin = self.context.get('is_admin', False)
        # Plain .all() reuses the view's prefetch cache (Meta ordering is
        # already ['order']); chaining .filter()/.order_by() would issue a
        # fresh query per proposal.
        sections = list(obj.sections.all())
        if not is_admin:
            sections = [s for s in sections if s.is_enabled]
        serialized = list(ProposalSectionDetailSerializer(sections, many=True).data)
        if not is_admin:
            from content.services.proposal_service import normalize_hosting_plan

            for section in serialized:
                if section.get('section_type') != 'investment':
                    continue
                content = dict(section.get('content_json') or {})
                content['hostingPlan'] = normalize_hosting_plan(
                    obj, content.get('hostingPlan') or {},
                )
                section['content_json'] = content
        return serialized

    def get_validity_text(self, obj):
        """Server-computed validity sentence shared verbatim with the PDF."""
        from content.services.proposal_service import ProposalService
        return ProposalService.compute_validity_text(obj)

    def get_days_remaining(self, obj):
        return obj.days_remaining

    def get_is_expired(self, obj):
        return obj.is_expired

    def get_public_url(self, obj):
        return obj.public_url

    def get_change_logs(self, obj):
        """Return change logs only for admin requests."""
        is_admin = self.context.get('is_admin', False)
        if not is_admin:
            return []
        # Meta ordering is ['-created_at']. Slicing the queryset (not a
        # materialized list) serves from the prefetch cache when one exists and
        # emits a LIMIT 50 query otherwise — the log table grows unboundedly
        # with proposal age, so loading every row just to keep 50 is not ok.
        logs = obj.change_logs.all()[:50]
        return [
            {
                'id': log.id,
                'change_type': log.change_type,
                'description': log.description,
                'field_name': log.field_name,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'actor_type': log.actor_type,
                'created_at': log.created_at.isoformat(),
            }
            for log in logs
        ]

    def get_discounted_investment(self, obj):
        """Return discounted price when discount_percent > 0."""
        if not obj.discount_percent or obj.discount_percent <= 0:
            return None
        from decimal import Decimal
        factor = (Decimal(100) - Decimal(obj.discount_percent)) / Decimal(100)
        return str(round(obj.total_investment * factor, 2))

    def get_effective_total_investment(self, obj):
        """
        Client-facing total: base ``total_investment`` plus the price of
        the additional calculator modules in the client's selection, with
        a fallback to admin-marked defaults when the client hasn't
        confirmed the calculator yet. Same rule as the PDF and the admin
        metrics map so every consumer sees the same number.
        """
        from content.services.proposal_totals_service import (
            effective_total_for_proposal,
        )
        return str(effective_total_for_proposal(obj))

    def get_available_transitions(self, obj):
        return obj.available_transitions

    def get_proposal_documents(self, obj):
        is_admin = self.context.get('is_admin', False)
        if not is_admin:
            return []
        # Meta ordering is ['-created_at']; plain .all() keeps prefetch warm.
        docs = list(obj.proposal_documents.all())
        return [serialize_proposal_document(d) for d in docs]

    def get_first_view_notification(self, obj):
        """Expose operational delivery details only inside the admin panel."""
        if not self.context.get('is_admin', False):
            return None
        return {
            'status': obj.first_view_notification_status,
            'attempts': obj.first_view_notification_attempts,
            'attempted_at': (
                obj.first_view_notification_attempted_at.isoformat()
                if obj.first_view_notification_attempted_at else None
            ),
            'sent_at': (
                obj.first_view_notification_sent_at.isoformat()
                if obj.first_view_notification_sent_at else None
            ),
            'last_error': obj.first_view_notification_last_error,
            'can_retry': (
                obj.first_view_notification_status
                == BusinessProposal.FirstViewNotificationStatus.FAILED
            ),
        }


class ContractParamsSerializer(serializers.Serializer):
    """Validate contract_params before saving to the JSONField."""

    CONTRACT_SOURCE_CHOICES = ('default', 'custom')

    contract_source = serializers.ChoiceField(
        choices=CONTRACT_SOURCE_CHOICES, default='default',
    )
    client_full_name = serializers.CharField(max_length=255, required=False, default='')
    client_cedula = serializers.CharField(max_length=30)
    client_email = serializers.EmailField(required=False, default='')
    contractor_full_name = serializers.CharField(max_length=255, required=False, default='')
    contractor_nit = serializers.CharField(
        max_length=30, required=False, default='', allow_blank=True,
    )
    contractor_cedula = serializers.CharField(
        max_length=30, required=False, default='', allow_blank=True,
    )
    contractor_email = serializers.EmailField(required=False, default='')
    bank_name = serializers.CharField(max_length=100, required=False, default='')
    bank_account_type = serializers.ChoiceField(
        choices=('Ahorros', 'Corriente'), default='Ahorros', required=False,
    )
    bank_account_number = serializers.CharField(max_length=50, required=False, default='')
    contract_city = serializers.CharField(max_length=100, required=False, default='Medellín')
    contract_date = serializers.CharField(max_length=20, required=False, default='')
    custom_contract_markdown = serializers.CharField(required=False, default='')

    def validate(self, data):
        if data.get('contract_source') == 'custom' and not data.get('custom_contract_markdown'):
            raise serializers.ValidationError(
                {'custom_contract_markdown': 'Required when contract_source is "custom".'}
            )
        # The contract names EL CONTRATISTA by whichever document is on file,
        # so exactly one of the two has to be there. Scoped to the default
        # template, matching where the other required fields are enforced.
        if data.get('contract_source', 'default') == 'default' and not (
            (data.get('contractor_nit') or '').strip()
            or (data.get('contractor_cedula') or '').strip()
        ):
            raise serializers.ValidationError(
                {'contractor_nit': 'Indica el NIT o la cédula del contratista (al menos uno).'}
            )
        return data


def serialize_proposal_document(d):
    """Serialize a ProposalDocument instance to a dict. Used by views and serializers."""
    display = (
        d.custom_type_label
        if d.document_type == 'other' and d.custom_type_label
        else d.get_document_type_display()
    )
    return {
        'id': d.id,
        'document_type': d.document_type,
        'document_type_display': display,
        'custom_type_label': d.custom_type_label,
        'title': d.title,
        'file': d.file.url if d.file else None,
        'is_generated': d.is_generated,
        'created_at': d.created_at.isoformat(),
    }


class ProposalCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating business proposal metadata.

    Client identity is canonical on ``BusinessProposal.client`` (FK to
    ``accounts.UserProfile``). The legacy ``client_name``/``client_email``/
    ``client_phone`` fields remain as write-through snapshots, kept in sync
    via ``proposal_client_service.sync_snapshot()``.

    Write contract:
        - ``client_id``: optional FK to an existing ``UserProfile``
          (role=client). When provided, that profile is used as-is and the
          inline ``client_name``/``client_email``/``client_phone``/``client_company``
          values are ignored — the snapshot is rebuilt from the profile.
        - When ``client_id`` is omitted/null, the service is asked to
          ``get_or_create`` a profile from the inline fields. Empty email
          triggers placeholder generation.
        - ``propagate_client_updates``: write-only boolean. When ``true``
          AND a client is being updated inline, the service propagates the
          new values to the ``UserProfile`` (cascading to all linked
          proposals). Default ``false``.
    """

    client_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        source='client',
        write_only=True,
        required=False,
        allow_null=True,
    )
    client_company = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=200, default='',
    )
    propagate_client_updates = serializers.BooleanField(
        write_only=True, required=False, default=False,
    )
    create_new_client = serializers.BooleanField(
        write_only=True, required=False, default=False,
    )
    client = ProposalClientSerializer(read_only=True)

    class Meta:
        model = BusinessProposal
        fields = (
            'title', 'client_name', 'client_email', 'slug',
            'language', 'total_investment', 'currency', 'nationality',
            'hosting_percent',
            'hosting_discount_nine_month',
            'hosting_discount_semiannual', 'hosting_discount_quarterly',
            'status', 'expires_at', 'reminder_days', 'urgency_reminder_days',
            'discount_percent', 'is_active', 'show_contract_terms',
            'automations_paused',
            'project_type', 'market_type', 'client_phone',
            'project_type_custom', 'market_type_custom',
            'email_intro', 'email_features', 'email_method_phases', 'email_signed_by',
            'client_id', 'client_company', 'propagate_client_updates',
            'create_new_client', 'client',
        )

    def validate_client_email(self, value):
        return _validate_client_email_mx(value)

    def validate_slug(self, value):
        return validate_editable_slug(
            value, BusinessProposal, self.instance, conflict_phrase='otra propuesta',
        )

    def validate_expires_at(self, value):
        """Ensure expiration date is in the future when actually being changed.

        Allow re-saving a proposal with its existing (possibly past) ``expires_at``
        unchanged so admins can edit other fields on an expired proposal.
        """
        if value is None:
            return value
        from django.utils import timezone
        existing = getattr(self.instance, 'expires_at', None)
        if existing is not None and existing == value:
            return value
        if value < timezone.now():
            raise serializers.ValidationError(
                'Expiration date must be in the future.'
            )
        return value

    def validate(self, attrs):
        """Ensure client_email is set when status is SENT."""
        status = attrs.get('status', getattr(self.instance, 'status', None))
        client_email = attrs.get(
            'client_email',
            getattr(self.instance, 'client_email', ''),
        )
        if status == BusinessProposal.Status.SENT and not client_email:
            raise serializers.ValidationError({
                'client_email': 'Client email is required when sending a proposal.',
            })
        return attrs

    # ------------------------------------------------------------------
    # client FK resolution + snapshot sync
    # ------------------------------------------------------------------

    def _pop_client_inputs(self, validated_data):
        """Strip client-related inputs from validated_data; return as dict."""
        return {
            'client': validated_data.pop('client', None),
            'name': validated_data.get('client_name', ''),
            'email': validated_data.get('client_email', ''),
            'phone': validated_data.get('client_phone', ''),
            'company': validated_data.pop('client_company', ''),
            'propagate': validated_data.pop('propagate_client_updates', False),
            'create_new': validated_data.pop('create_new_client', False),
        }

    def create(self, validated_data):
        client_inputs = self._pop_client_inputs(validated_data)
        profile = client_inputs['client']
        if profile is None:
            profile = proposal_client_service.get_or_create_client_for_proposal(
                name=client_inputs['name'],
                email=client_inputs['email'],
                phone=client_inputs['phone'],
                company=client_inputs['company'],
            )
        validated_data['client'] = profile
        proposal = super().create(validated_data)
        proposal_client_service.sync_snapshot(proposal)
        return proposal

    def update(self, instance, validated_data):
        client_inputs = self._pop_client_inputs(validated_data)
        explicit_profile = client_inputs['client']

        # Caller explicitly asked to create a brand-new client from the inline
        # fields (and did not pick an existing one). Resolve/create the profile
        # and (re)assign it WITHOUT touching the previously linked client.
        if client_inputs['create_new'] and explicit_profile is None:
            new_profile = proposal_client_service.get_or_create_client_for_proposal(
                name=client_inputs['name'],
                email=client_inputs['email'],
                phone=client_inputs['phone'],
                company=client_inputs['company'],
            )
            validated_data['client'] = new_profile
            proposal = super().update(instance, validated_data)
            proposal_client_service.sync_snapshot(proposal)
            return proposal

        # If caller passed a client_id, switch the FK and skip auto-create.
        if explicit_profile is not None:
            validated_data['client'] = explicit_profile
        # Otherwise: keep the current FK; the snapshot fields may still be
        # edited inline (overrides for THIS proposal only).

        # Optional propagation: when the admin opted in via the checkbox,
        # push the inline edits up to the canonical UserProfile so all other
        # proposals stay in sync.
        if client_inputs['propagate']:
            target = explicit_profile or instance.client
            if target is not None:
                proposal_client_service.update_client_profile(
                    target,
                    name=client_inputs['name'] or None,
                    email=client_inputs['email'] or None,
                    phone=client_inputs['phone'] or None,
                    company=client_inputs['company'] or None,
                )

        proposal = super().update(instance, validated_data)

        # When we just switched FK or propagated upstream, reset the snapshot
        # so this proposal mirrors the canonical client identity.
        if explicit_profile is not None or client_inputs['propagate']:
            proposal_client_service.sync_snapshot(proposal)

        return proposal


class ProposalSectionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating a proposal section's content and metadata.
    """

    class Meta:
        model = ProposalSection
        fields = ('title', 'order', 'is_enabled', 'is_wide_panel', 'content_json')

    def validate_content_json(self, value):
        """Ensure content_json is a dictionary and matches the section schema."""
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'content_json must be a JSON object (dict).'
            )
        if self.instance is not None:
            schema_errors = validate_section_content(
                self.instance.section_type, value,
            )
            if schema_errors:
                raise serializers.ValidationError(schema_errors)
        if (
            self.instance
            and self.instance.section_type == ProposalSection.SectionType.TECHNICAL_DOCUMENT
        ):
            sections = [
                {
                    'section_type': section.section_type,
                    'content_json': value if section.pk == self.instance.pk else section.content_json,
                }
                for section in self.instance.proposal.sections.all()
            ]
            return normalize_technical_document_module_links(value, sections)
        if (
            self.instance
            and self.instance.section_type == ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS
        ):
            return ensure_functional_requirements_item_ids(value)
        return value


# ---------------------------------------------------------------------------
# JSON key → section_type mapping
# ---------------------------------------------------------------------------
SECTION_KEY_MAP = {
    'general': 'greeting',
    'executiveSummary': 'executive_summary',
    'contextDiagnostic': 'context_diagnostic',
    'conversionStrategy': 'conversion_strategy',
    'designUX': 'design_ux',
    'creativeSupport': 'creative_support',
    'developmentStages': 'development_stages',
    'processMethodology': 'process_methodology',
    'functionalRequirements': 'functional_requirements',
    'timeline': 'timeline',
    'investment': 'investment',
    'proposalSummary': 'proposal_summary',
    'finalNote': 'final_note',
    'nextSteps': 'next_steps',
    'technicalDocument': 'technical_document',
    'valueAddedModules': 'value_added_modules',
    'roiProjection': 'roi_projection',
    'commercialConditions': 'commercial_conditions',
}

SECTION_TYPE_TO_KEY = {v: k for k, v in SECTION_KEY_MAP.items()}


class ProposalFromJSONSerializer(serializers.Serializer):
    """
    Serializer for creating a proposal from a complete JSON payload.

    Accepts proposal metadata at the top level and a ``sections`` dict
    whose keys are camelCase section names mapped to content_json dicts.
    """

    title = serializers.CharField(max_length=255)
    client_name = serializers.CharField(max_length=255)
    # Optional FK to an existing client UserProfile. When provided, that
    # profile is used as-is and the inline client_* fields are ignored
    # (the snapshot is rebuilt from the profile via sync_snapshot).
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
        source='client',
        write_only=True,
        required=False,
        allow_null=True,
    )
    client_email = serializers.EmailField(required=False, default='', allow_blank=True)
    client_phone = serializers.CharField(max_length=30, required=False, default='', allow_blank=True)
    client_company = serializers.CharField(max_length=200, required=False, default='', allow_blank=True)
    project_type = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    market_type = serializers.CharField(max_length=20, required=False, default='', allow_blank=True)
    project_type_custom = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    market_type_custom = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    language = serializers.ChoiceField(
        choices=BusinessProposal.Language.choices, default='es',
    )
    total_investment = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0,
    )
    currency = serializers.ChoiceField(
        choices=BusinessProposal.Currency.choices, default='COP',
    )
    nationality = serializers.ChoiceField(
        choices=Nationality.choices, default='COL',
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    reminder_days = serializers.IntegerField(required=False, default=10)
    urgency_reminder_days = serializers.IntegerField(required=False, default=15)
    discount_percent = serializers.IntegerField(required=False, default=0)
    show_contract_terms = serializers.BooleanField(required=False, default=True)
    email_intro = serializers.CharField(required=False, default='', allow_blank=True)
    sections = serializers.DictField(child=serializers.DictField(), required=True)

    def validate_client_email(self, value):
        return _validate_client_email_mx(value)

    def validate_expires_at(self, value):
        """Allow keeping the existing expires_at unchanged when re-importing JSON.

        Bound proposal is passed via context so we can compare against the
        currently stored value and skip the future-only check when nothing
        is actually being changed.
        """
        if value is None:
            return value
        from django.utils import timezone
        proposal = self.context.get('proposal')
        existing = getattr(proposal, 'expires_at', None) if proposal else None
        if existing is not None and existing == value:
            return value
        if value < timezone.now():
            raise serializers.ValidationError(
                'Expiration date must be in the future.'
            )
        return value

    def validate_sections(self, value):
        if 'general' not in value:
            raise serializers.ValidationError(
                'The sections dict must include a "general" key with at least clientName.'
            )
        general = value['general']
        if not isinstance(general, dict) or not general.get('clientName'):
            raise serializers.ValidationError(
                'sections.general must contain a non-empty "clientName".'
            )
        # Strip _meta helper key if present (template download artifact)
        value.pop('_meta', None)
        # Per-section-type schema validation: each camelCase key maps to a
        # section_type and its dict becomes that section's content_json.
        schema_errors = {}
        for key, content in value.items():
            section_type = SECTION_KEY_MAP.get(key)
            if section_type is None or not isinstance(content, dict):
                continue
            section_errors = validate_section_content(section_type, content)
            if section_errors:
                schema_errors[key] = section_errors
        if schema_errors:
            raise serializers.ValidationError(schema_errors)
        return value


class ProposalResendSerializer(serializers.Serializer):
    """Optional editable message submitted by the individual resend modal."""

    email_intro = serializers.CharField(required=False, allow_blank=True)


class ProposalAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and listing manual proposal alerts.
    """
    client_name = serializers.CharField(source='proposal.client_name', read_only=True)
    proposal_title = serializers.CharField(source='proposal.title', read_only=True)

    class Meta:
        model = ProposalAlert
        fields = (
            'id', 'proposal', 'alert_type', 'message', 'alert_date',
            'is_dismissed', 'created_at', 'client_name', 'proposal_title',
        )
        read_only_fields = ('id', 'created_at', 'client_name', 'proposal_title')


class ProposalShareLinkSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and displaying proposal share links.
    """

    class Meta:
        model = ProposalShareLink
        fields = (
            'id', 'uuid', 'shared_by_name', 'shared_by_email',
            'recipient_name', 'recipient_email',
            'view_count', 'first_viewed_at', 'created_at',
        )
        read_only_fields = (
            'id', 'uuid', 'view_count', 'first_viewed_at', 'created_at',
        )


class ProposalDefaultConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving and updating proposal default configurations.
    """

    class Meta:
        model = ProposalDefaultConfig
        fields = (
            'id',
            'language',
            'sections_json',
            'default_currency',
            'default_total_investment',
            'hosting_percent',
            'hosting_discount_nine_month',
            'hosting_discount_semiannual',
            'hosting_discount_quarterly',
            'expiration_days',
            'reminder_days',
            'urgency_reminder_days',
            'default_discount_percent',
            'default_slug_pattern',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            'hosting_percent': {'min_value': 0, 'max_value': 100},
            'hosting_discount_nine_month': {'min_value': 0, 'max_value': 100},
            'hosting_discount_semiannual': {'min_value': 0, 'max_value': 100},
            'hosting_discount_quarterly': {'min_value': 0, 'max_value': 100},
            'default_discount_percent': {'min_value': 0, 'max_value': 100},
            'reminder_days': {'min_value': 0, 'max_value': 365},
            'urgency_reminder_days': {'min_value': 0, 'max_value': 365},
            'default_total_investment': {'min_value': 0},
        }

    def validate_language(self, value):
        if value not in ('es', 'en'):
            raise serializers.ValidationError(
                'Language must be "es" or "en".'
            )
        return value

    def validate_sections_json(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'sections_json must be a JSON array (list).'
            )
        required_keys = {'section_type', 'title', 'order', 'content_json'}
        for i, section in enumerate(value):
            if not isinstance(section, dict):
                raise serializers.ValidationError(
                    f'Each section must be a dict (index {i}).'
                )
            missing = required_keys - set(section.keys())
            if missing:
                raise serializers.ValidationError(
                    f'Section at index {i} is missing keys: {missing}'
                )
        normalized_sections = []
        technical_content = None
        schema_errors = []
        for section in value:
            cloned = dict(section)
            content_json = cloned.get('content_json')
            cloned['content_json'] = content_json if isinstance(content_json, dict) else {}
            schema_errors.extend(
                validate_section_content(
                    cloned.get('section_type'), cloned['content_json'],
                )
            )
            if cloned.get('section_type') == ProposalSection.SectionType.FUNCTIONAL_REQUIREMENTS:
                cloned['content_json'] = ensure_functional_requirements_item_ids(cloned['content_json'])
            if cloned.get('section_type') == ProposalSection.SectionType.TECHNICAL_DOCUMENT:
                technical_content = cloned['content_json']
            normalized_sections.append(cloned)

        if schema_errors:
            raise serializers.ValidationError(schema_errors)

        if technical_content is not None:
            canonical_technical = normalize_technical_document_module_links(
                technical_content,
                normalized_sections,
            )
            normalized_sections = [
                {
                    **section,
                    'content_json': canonical_technical
                    if section.get('section_type') == ProposalSection.SectionType.TECHNICAL_DOCUMENT
                    else section['content_json'],
                }
                for section in normalized_sections
            ]
        return normalized_sections

    def validate_expiration_days(self, value):
        if value < 1 or value > 365:
            raise serializers.ValidationError(
                'expiration_days must be between 1 and 365.'
            )
        return value


class EmailTemplateConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for retrieving and updating email template configurations.
    """

    class Meta:
        model = EmailTemplateConfig
        fields = (
            'id', 'template_key', 'content_overrides', 'is_active',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'template_key', 'created_at', 'updated_at')

    def validate_content_overrides(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'content_overrides must be a JSON object (dict).'
            )
        return value
