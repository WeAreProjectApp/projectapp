"""
Serializers for the proposal admin panel's client management surface.

These wrap ``accounts.UserProfile`` (filtered to ``role='client'``) with the
shape expected by ``/panel/clients`` and the proposal create/edit autocomplete.
"""

from rest_framework import serializers

from accounts.models import Project, UserProfile
from accounts.services.proposal_client_service import build_client_display_name


class ClientBillingSnapshotMixin:
    def get_billing_customer(self, obj):
        from content.services.collection_account_create_service import (
            customer_snapshot_defaults,
        )
        customer = customer_snapshot_defaults(obj)
        if obj.is_email_placeholder:
            customer['email'] = ''
        return customer


class ClientBillingFieldsSerializer(serializers.Serializer):
    """Validate the profile's billing fields before any client write."""

    nit = serializers.CharField(max_length=32, required=False, allow_blank=True)
    cedula = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=512, required=False, allow_blank=True)


class ProposalClientSerializer(ClientBillingSnapshotMixin, serializers.ModelSerializer):
    """
    Full serializer for the proposal-side client (UserProfile + nested User).

    Read fields:
        - ``name``: derived from User.first_name + last_name, falling back to
          company_name or email.
        - ``email``: User.email (may be a placeholder ``cliente_<id>@temp.example.com``).
        - ``phone``: UserProfile.phone.
        - ``company``: UserProfile.company_name.
        - ``is_email_placeholder`` / ``is_onboarded``: status flags.
        - ``total_proposals`` / ``is_orphan``: read from queryset annotations
          when available, falling back to per-instance queries otherwise.

    Write fields (POST/PATCH):
        - ``name``, ``email``, ``phone``, ``company`` are accepted but the
          underlying writes are routed through ``proposal_client_service``
          (the views call ``get_or_create_client_for_proposal`` /
          ``update_client_profile`` instead of using ``serializer.save``).
    """

    name = serializers.CharField(required=False, allow_blank=True, max_length=311)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=30)
    company = serializers.CharField(
        source='company_name',
        required=False,
        allow_blank=True,
        max_length=200,
    )
    billing_customer = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    is_email_placeholder = serializers.BooleanField(read_only=True)
    total_proposals = serializers.SerializerMethodField()
    projects_count = serializers.SerializerMethodField()
    diagnostics_count = serializers.SerializerMethodField()
    incomes_count = serializers.SerializerMethodField()
    hostings_count = serializers.SerializerMethodField()
    active_hostings_count = serializers.SerializerMethodField()
    active_projects_count = serializers.SerializerMethodField()
    diagnostic_incomes_count = serializers.SerializerMethodField()
    diagnostics_without_proposal_count = serializers.SerializerMethodField()
    emails_sent_count = serializers.SerializerMethodField()
    emails_failed_count = serializers.SerializerMethodField()
    last_email_at = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()
    documents_no_project_count = serializers.SerializerMethodField()
    document_folders_count = serializers.SerializerMethodField()
    last_document_at = serializers.SerializerMethodField()
    communications_count = serializers.SerializerMethodField()
    open_communications_count = serializers.SerializerMethodField()
    last_communication_at = serializers.SerializerMethodField()
    is_orphan = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()
    archived_at = serializers.DateTimeField(read_only=True)
    accepted_count = serializers.SerializerMethodField()
    last_status = serializers.SerializerMethodField()
    last_sent_at = serializers.SerializerMethodField()
    project_types = serializers.SerializerMethodField()
    market_types = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            'id',
            'user_id',
            'name',
            'email',
            'phone',
            'company',
            'nit',
            'cedula',
            'address',
            'billing_customer',
            'billing_code',
            'is_onboarded',
            'is_email_placeholder',
            'total_proposals',
            'projects_count',
            'diagnostics_count',
            'incomes_count',
            'hostings_count',
            'active_hostings_count',
            'active_projects_count',
            'diagnostic_incomes_count',
            'diagnostics_without_proposal_count',
            'emails_sent_count',
            'emails_failed_count',
            'last_email_at',
            'documents_count',
            'documents_no_project_count',
            'document_folders_count',
            'last_document_at',
            'communications_count',
            'open_communications_count',
            'last_communication_at',
            'is_orphan',
            'is_archived',
            'archived_at',
            'accepted_count',
            'last_status',
            'last_sent_at',
            'project_types',
            'market_types',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'user_id',
            'is_onboarded',
            'is_email_placeholder',
            'total_proposals',
            'projects_count',
            'diagnostics_count',
            'incomes_count',
            'hostings_count',
            'active_hostings_count',
            'active_projects_count',
            'diagnostic_incomes_count',
            'diagnostics_without_proposal_count',
            'emails_sent_count',
            'emails_failed_count',
            'last_email_at',
            'documents_count',
            'documents_no_project_count',
            'document_folders_count',
            'last_document_at',
            'communications_count',
            'open_communications_count',
            'last_communication_at',
            'is_orphan',
            'is_archived',
            'archived_at',
            'accepted_count',
            'last_status',
            'last_sent_at',
            'project_types',
            'market_types',
            'created_at',
            'updated_at',
        )

    def validate_email(self, value):
        # Lazy import avoids a circular dependency with content.serializers.proposal,
        # which imports ProposalClientSerializer at module load time.
        from content.serializers.proposal import _validate_client_email_mx

        return _validate_client_email_mx(value)

    def get_total_proposals(self, obj):
        # Annotated alias `proposals_count` is preferred when the queryset
        # was annotated; fall back to a per-instance query otherwise.
        annotated = getattr(obj, 'proposals_count', None)
        if annotated is not None:
            return annotated
        return obj.proposals.count()

    def get_projects_count(self, obj):
        annotated = getattr(obj, 'projects_count', None)
        if annotated is not None:
            return annotated
        return obj.user.projects.count()

    def get_diagnostics_count(self, obj):
        annotated = getattr(obj, 'diagnostics_count', None)
        if annotated is not None:
            return annotated
        return obj.web_app_diagnostics.count()

    def get_incomes_count(self, obj):
        annotated = getattr(obj, 'incomes_count', None)
        if annotated is not None:
            return annotated
        return obj.income_records.count()

    def get_hostings_count(self, obj):
        annotated = getattr(obj, 'hostings_count', None)
        if annotated is not None:
            return annotated
        return obj.hosting_records.count()

    def get_active_hostings_count(self, obj):
        annotated = getattr(obj, 'active_hostings_count', None)
        if annotated is not None:
            return annotated
        return obj.hosting_records.filter(is_active=True).count()

    def get_diagnostic_incomes_count(self, obj):
        annotated = getattr(obj, 'diagnostic_incomes_count', None)
        if annotated is not None:
            return annotated
        from content.models import IncomeRecord
        return (
            obj.income_records
            .filter(origin=IncomeRecord.Origin.DIAGNOSTIC)
            .exclude(kind=IncomeRecord.Kind.LOST)
            .count()
        )

    def get_diagnostics_without_proposal_count(self, obj):
        annotated = getattr(obj, 'diagnostics_without_proposal_count', None)
        if annotated is not None:
            return annotated
        # The annotation minus its outer Subquery: with the diagnostics query
        # outermost, the Exists' OuterRefs bind to it directly, exactly as
        # they do one level down in `_base_queryset`.
        from django.db.models import Exists, OuterRef
        from django.db.models.functions import Coalesce

        from content.models import BusinessProposal, WebAppDiagnostic
        return (
            obj.web_app_diagnostics
            .exclude(status=WebAppDiagnostic.Status.DRAFT)
            .filter(~Exists(
                BusinessProposal.objects.filter(
                    client_id=OuterRef('client_id'),
                    created_at__gt=Coalesce(
                        OuterRef('initial_sent_at'), OuterRef('created_at'),
                    ),
                )
            ))
            .count()
        )

    def get_emails_sent_count(self, obj):
        annotated = getattr(obj, 'emails_sent_count', None)
        if annotated is not None:
            return annotated
        from content.models import EmailLog
        return obj.email_logs.filter(
            audience=EmailLog.Audience.CLIENT,
        ).count()

    def get_emails_failed_count(self, obj):
        annotated = getattr(obj, 'emails_failed_count', None)
        if annotated is not None:
            return annotated
        from content.models import EmailLog
        return obj.email_logs.filter(
            audience=EmailLog.Audience.CLIENT,
            status=EmailLog.Status.FAILED,
        ).count()

    def get_last_email_at(self, obj):
        annotated = getattr(obj, 'last_email_at', None)
        if annotated is not None:
            return annotated
        from content.models import EmailLog
        # EmailLog orders newest-first, so first() is the latest.
        return obj.email_logs.filter(
            audience=EmailLog.Audience.CLIENT,
        ).values_list('sent_at', flat=True).first()

    def get_documents_count(self, obj):
        annotated = getattr(obj, 'documents_count', None)
        if annotated is not None:
            return annotated
        return obj.user.client_documents.filter(is_archived=False).count()

    def get_documents_no_project_count(self, obj):
        annotated = getattr(obj, 'documents_no_project_count', None)
        if annotated is not None:
            return annotated
        return obj.user.client_documents.filter(
            is_archived=False, project__isnull=True,
        ).count()

    def get_document_folders_count(self, obj):
        annotated = getattr(obj, 'document_folders_count', None)
        if annotated is not None:
            return annotated
        return obj.user.client_document_folders.filter(
            is_archived=False,
        ).count()

    def get_last_document_at(self, obj):
        annotated = getattr(obj, 'last_document_at', None)
        if annotated is not None:
            return annotated
        return (
            obj.user.client_documents
            .filter(is_archived=False)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )

    def get_communications_count(self, obj):
        annotated = getattr(obj, 'communications_count', None)
        if annotated is not None:
            return annotated
        return obj.communication_threads.count()

    def get_open_communications_count(self, obj):
        annotated = getattr(obj, 'open_communications_count', None)
        if annotated is not None:
            return annotated
        from content.models import CommunicationThread
        return obj.communication_threads.filter(
            status=CommunicationThread.Status.OPEN,
        ).count()

    def get_last_communication_at(self, obj):
        annotated = getattr(obj, 'last_communication_at', None)
        if annotated is not None:
            return annotated
        return (
            obj.communication_threads
            .order_by('-last_activity_at')
            .values_list('last_activity_at', flat=True)
            .first()
        )

    def get_active_projects_count(self, obj):
        annotated = getattr(obj, 'active_projects_count', None)
        if annotated is not None:
            return annotated
        return obj.user.projects.filter(status=Project.STATUS_ACTIVE).count()

    def get_is_orphan(self, obj):
        if self.get_total_proposals(obj) > 0:
            return False
        projects_annotated = getattr(obj, 'projects_count', None)
        if projects_annotated is not None and projects_annotated > 0:
            return False
        if projects_annotated is None and obj.user.projects.exists():
            return False
        diagnostics_annotated = getattr(obj, 'diagnostics_count', None)
        if diagnostics_annotated is not None:
            if diagnostics_annotated > 0:
                return False
        elif obj.web_app_diagnostics.exists():
            return False
        if self.get_incomes_count(obj) > 0:
            return False
        if self.get_hostings_count(obj) > 0:
            return False
        return self.get_communications_count(obj) == 0

    def get_is_archived(self, obj):
        return obj.archived_at is not None

    def get_accepted_count(self, obj):
        annotated = getattr(obj, 'accepted_count', None)
        if annotated is not None:
            return annotated
        return obj.proposals.filter(status__in=['accepted', 'finished']).count()

    def get_last_status(self, obj):
        annotated = getattr(obj, 'last_status', None)
        if annotated is not None:
            return annotated
        latest = obj.proposals.order_by('-last_activity_at').values_list('status', flat=True).first()
        return latest

    def get_last_sent_at(self, obj):
        annotated = getattr(obj, 'last_sent_at', None)
        if annotated is not None:
            return annotated
        from django.db.models import Max
        return obj.proposals.aggregate(last=Max('sent_at'))['last']

    def get_project_types(self, obj):
        return list({p.project_type for p in obj.proposals.all() if p.project_type})

    def get_market_types(self, obj):
        return list({p.market_type for p in obj.proposals.all() if p.market_type})

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['name'] = build_client_display_name(instance)
        rep['email'] = instance.user.email or ''
        return rep


class ProposalNestedClientSerializer(serializers.ModelSerializer):
    """
    Client payload nested inside a proposal detail response.

    Same identity/contact/status fields as ``ProposalClientSerializer`` minus the
    cross-entity aggregates (``total_proposals``, ``projects_count``,
    ``diagnostics_count``, ``is_orphan``, ``accepted_count``, ``last_status``,
    ``last_sent_at``, ``project_types``, ``market_types``). Those are
    ``SerializerMethodField``s that fall back to a per-instance query whenever
    the queryset was not annotated -- which is the case for the proposal detail
    endpoint -- costing ~8-10 queries for numbers the proposal surfaces never
    read. ``/panel/clients`` still uses the full serializer.
    """

    name = serializers.CharField(required=False, allow_blank=True, max_length=311)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=30)
    company = serializers.CharField(
        source='company_name',
        required=False,
        allow_blank=True,
        max_length=200,
    )
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    is_email_placeholder = serializers.BooleanField(read_only=True)
    # Reads an already-loaded column, so it costs no extra query.
    is_archived = serializers.SerializerMethodField()
    archived_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            'id',
            'user_id',
            'name',
            'email',
            'phone',
            'company',
            'is_onboarded',
            'is_email_placeholder',
            'is_archived',
            'archived_at',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_is_archived(self, obj):
        return obj.archived_at is not None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['name'] = build_client_display_name(instance)
        rep['email'] = instance.user.email or ''
        return rep


class ProposalClientSearchSerializer(ClientBillingSnapshotMixin, serializers.ModelSerializer):
    """Lightweight payload for a client-picker page (up to 20 results)."""

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    company = serializers.CharField(source='company_name')
    billing_customer = serializers.SerializerMethodField()
    is_email_placeholder = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            'id', 'name', 'email', 'phone', 'company',
            'nit', 'cedula', 'address', 'billing_code', 'billing_customer', 'is_email_placeholder',
        )

    def get_name(self, obj):
        return build_client_display_name(obj)

    def get_email(self, obj):
        return obj.user.email or ''
