"""Serializers for the panel Projects module (Plataforma space).

Read shape for ``/api/projects/``: the listing row speaks the panel's
language — the client travels as UserProfile id plus display name (the
model's FK points at ``auth.User``), and each row carries the counts of
accounting records hanging off the project.
"""

from rest_framework import serializers

from accounts.models import Project, UserProfile
from accounts.services.proposal_client_service import build_client_display_name
from content.models import DocumentState, DocumentStateGroup
from content.serializers.document_state import DocumentStateSummarySerializer
from content.services.project_state_service import (
    LEGACY_STATUS_BY_EFFECT,
    initialize_project_state,
    project_state_suggestion,
)


class DeletePanelProjectSerializer(serializers.Serializer):
    force = serializers.BooleanField(default=False)
    confirmation = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    impact_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['force'] and attrs.get('confirmation') != 'DELETE':
            raise serializers.ValidationError({
                'confirmation': 'Escribe exactamente DELETE en mayúsculas.',
            })
        if attrs['force'] and not attrs.get('impact_token'):
            raise serializers.ValidationError({'impact_token': 'Revisa las dependencias antes de confirmar.'})
        return attrs


class PanelProjectSerializer(serializers.ModelSerializer):
    """Listing row for ``/panel/projects``."""

    status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    current_state = DocumentStateSummarySerializer(read_only=True)
    state_suggestion = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    hostings_count = serializers.IntegerField(read_only=True)
    incomes_count = serializers.IntegerField(read_only=True)
    # The client's completion backlog (their records with no project yet) —
    # repeated on every project row of the same client on purpose.
    unlinked_hostings_count = serializers.IntegerField(read_only=True, default=0)
    unlinked_incomes_count = serializers.IntegerField(read_only=True, default=0)
    unlinked_documents_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'description', 'status', 'status_label',
            'current_state', 'state_review_required', 'state_suggestion',
            'created_at', 'client', 'hostings_count', 'incomes_count',
            'unlinked_hostings_count', 'unlinked_incomes_count',
            'unlinked_documents_count',
        ]
        read_only_fields = fields

    def get_client(self, project):
        profile = getattr(project.client, 'profile', None)
        if profile is None:
            # A client user without a profile row predates the platform
            # onboarding; the panel still needs something to render.
            return {
                'profile_id': None,
                'name': project.client.get_full_name() or project.client.email,
                'company': '',
            }
        return {
            'profile_id': profile.pk,
            'name': build_client_display_name(profile),
            'company': profile.company_name or '',
        }

    def get_status(self, project):
        state = project.current_state
        return (state.system_key or state.slug) if state else None

    def get_status_label(self, project):
        return project.current_state.name if project.current_state else 'Sin clasificar'

    def get_state_suggestion(self, project):
        return project_state_suggestion(project)


class CreatePanelProjectSerializer(serializers.Serializer):
    """Create payload: the PA-38 minimum — name and client, the rest optional.

    The client arrives as a UserProfile id (what the panel's autocomplete
    carries) and lands on the model's ``client`` User FK. A same-name project
    for the same client is legal: the duplicate warning lives client-side
    and never blocks.
    """

    name = serializers.CharField(max_length=200)
    client_profile_id = serializers.IntegerField()
    description = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    state_id = serializers.PrimaryKeyRelatedField(
        source='state',
        queryset=DocumentState.objects.filter(
            catalog=DocumentStateGroup.Catalog.PROJECTS,
            is_active=True,
            merged_into__isnull=True,
        ),
        required=False,
    )

    def validate_client_profile_id(self, value):
        profile = UserProfile.objects.clients().filter(pk=value).first()
        if profile is None:
            raise serializers.ValidationError(
                'Ese cliente no existe o no es un perfil de cliente.'
            )
        self.client_profile = profile
        return value

    def create(self, validated_data):
        state = validated_data.pop('state', None)
        if state is None:
            state = DocumentState.objects.get(
                catalog=DocumentStateGroup.Catalog.PROJECTS,
                system_key=Project.STATUS_DEVELOPMENT,
                is_active=True,
            )
        project = Project.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            client=self.client_profile.user,
            current_state=state,
            status=LEGACY_STATUS_BY_EFFECT[state.operational_effect],
        )
        request = self.context.get('request')
        initialize_project_state(
            project,
            state,
            actor=request.user if request else None,
        )
        return project


class ProjectAssignUnlinkedSerializer(serializers.Serializer):
    """Apply payload for ``projects/<id>/assign-unlinked/``.

    Explicit ids on purpose: what the operator confirmed is what runs, not
    "whatever is unlinked by the time the request lands". The view checks the
    ids against the project's unlinked set; this serializer only guards the
    shape and refuses an empty plan.
    """

    hosting_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    income_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    document_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )

    def validate(self, attrs):
        if (
            not attrs.get('hosting_ids')
            and not attrs.get('income_ids')
            and not attrs.get('document_ids')
        ):
            raise serializers.ValidationError(
                'Selecciona al menos un registro para asignar.'
            )
        return attrs


class UpdatePanelProjectSerializer(serializers.ModelSerializer):
    """Partial update with the platform's field semantics, panel-scoped.

    Same max lengths as the platform ``UpdateProjectSerializer``, restricted
    to what the panel edits. Client and lifecycle changes use their dedicated
    preview-and-apply flows.
    """

    class Meta:
        model = Project
        fields = ['name', 'description']


class ProjectTransitionPreviewSerializer(serializers.Serializer):
    state_id = serializers.PrimaryKeyRelatedField(
        source='state',
        queryset=DocumentState.objects.filter(
            catalog=DocumentStateGroup.Catalog.PROJECTS,
        ),
    )
    effective_at = serializers.DateTimeField(required=False)


class ProjectIncomeResolutionSerializer(serializers.Serializer):
    income_id = serializers.IntegerField()
    action = serializers.ChoiceField(
        choices=('keep_receivable', 'write_off'),
    )


class ProjectTransitionApplySerializer(ProjectTransitionPreviewSerializer):
    impact_token = serializers.CharField(min_length=64, max_length=64)
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        default='',
    )
    resolutions = ProjectIncomeResolutionSerializer(
        many=True,
        required=False,
        default=list,
    )


class ProjectChangeClientSerializer(serializers.Serializer):
    """Apply payload for ``projects/<id>/change-client/``.

    ``mode`` is a bare CharField on purpose: the view maps an unknown value
    to its own ``invalid_mode`` code (the operator must choose move/detach
    every time — there is no default to fall back to). The id lists are the
    staleness token, not a selection: they must equal the CURRENT linked
    sets or nothing runs.
    """

    client_profile_id = serializers.IntegerField()
    mode = serializers.CharField()
    hosting_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    income_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
    communication_thread_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
