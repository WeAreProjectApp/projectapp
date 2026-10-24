from content.serializers.editorial import EditorialModelSerializer
from django.utils import timezone
from rest_framework import serializers

from content.models import (
    DocumentNote,
    DocumentNoteEvent,
    DocumentState,
    DocumentStateEpisode,
    DocumentStateEpisodeEvent,
    DocumentStateGroup,
)
from content.models.document_state import normalize_document_state_name


def actor_display(user):
    if user is None:
        return None
    return user.get_full_name().strip() or user.get_username()


class DocumentStateGroupSerializer(EditorialModelSerializer):
    state_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = DocumentStateGroup
        fields = (
            'id', 'catalog', 'name', 'selection_mode', 'order', 'is_active',
            'state_count', 'created_at', 'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')


class DocumentStateSummarySerializer(EditorialModelSerializer):
    group_id = serializers.IntegerField(source='group.id', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    group_mode = serializers.CharField(
        source='group.selection_mode', read_only=True,
    )
    group_order = serializers.IntegerField(source='group.order', read_only=True)
    operational_effect_help = serializers.CharField(read_only=True)

    class Meta:
        model = DocumentState
        fields = (
            'id', 'catalog', 'name', 'description', 'slug', 'color',
            'system_key', 'operational_effect', 'operational_effect_help', 'order',
            'show_in_document_manager',
            'group_id', 'group_name', 'group_mode', 'group_order',
        )


class DocumentStateSerializer(DocumentStateSummarySerializer):
    SYSTEM_GROUP_MODES = {
        'draft': DocumentStateGroup.SelectionMode.EXCLUSIVE,
        'sent': DocumentStateGroup.SelectionMode.EXCLUSIVE,
        'in_review': DocumentStateGroup.SelectionMode.EXCLUSIVE,
        'bug_resolved': DocumentStateGroup.SelectionMode.EXCLUSIVE,
        'closed': DocumentStateGroup.SelectionMode.EXCLUSIVE,
        'needs_fix': DocumentStateGroup.SelectionMode.ADDITIVE,
    }
    incompatibility_ids = serializers.PrimaryKeyRelatedField(
        source='incompatibilities',
        queryset=DocumentState.objects.all(),
        many=True,
        required=False,
    )
    active_document_count = serializers.IntegerField(read_only=True, default=0)
    active_project_count = serializers.IntegerField(read_only=True, default=0)
    historical_episode_count = serializers.IntegerField(read_only=True, default=0)
    merged_into_name = serializers.CharField(
        source='merged_into.name', read_only=True, default=None,
    )

    class Meta(DocumentStateSummarySerializer.Meta):
        fields = DocumentStateSummarySerializer.Meta.fields + (
            'group', 'is_active', 'merged_into', 'merged_into_name',
            'incompatibility_ids', 'active_document_count',
            'active_project_count',
            'historical_episode_count', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'slug', 'system_key', 'show_in_document_manager', 'merged_into',
            'created_at', 'updated_at',
        )

    def validate_name(self, value):
        normalized = normalize_document_state_name(value)
        catalog = (
            self.initial_data.get('catalog')
            or getattr(self.instance, 'catalog', None)
            or DocumentStateGroup.Catalog.DOCUMENTS
        )
        queryset = DocumentState.objects.filter(
            catalog=catalog,
            normalized_name=normalized,
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('Ya existe un estado con ese nombre.')
        return ' '.join(value.strip().split())

    def validate_incompatibility_ids(self, states):
        if self.instance and any(state.pk == self.instance.pk for state in states):
            raise serializers.ValidationError(
                'Un estado no puede excluirse a sí mismo.',
            )
        return states

    def validate(self, attrs):
        attrs = super().validate(attrs)
        system_key = self.instance.system_key if self.instance else None
        expected_mode = self.SYSTEM_GROUP_MODES.get(system_key)
        group = attrs.get('group') or getattr(self.instance, 'group', None)
        catalog = (
            attrs.get('catalog')
            or getattr(self.instance, 'catalog', None)
            or (group.catalog if group else DocumentStateGroup.Catalog.DOCUMENTS)
        )
        if group and group.catalog != catalog:
            raise serializers.ValidationError({
                'group': 'El grupo pertenece a otro catálogo de estados.',
            })
        effect = attrs.get(
            'operational_effect',
            getattr(self.instance, 'operational_effect', ''),
        )
        if catalog == DocumentStateGroup.Catalog.PROJECTS and not effect:
            raise serializers.ValidationError({
                'operational_effect': (
                    'Cada estado de proyecto debe definir su efecto operativo.'
                ),
            })
        description = attrs.get(
            'description',
            getattr(self.instance, 'description', ''),
        )
        if catalog == DocumentStateGroup.Catalog.PROJECTS and not description.strip():
            raise serializers.ValidationError({
                'description': (
                    'Explica qué significa este estado para quien lo elige.'
                ),
            })
        if 'description' in attrs:
            attrs['description'] = ' '.join(description.strip().split())
        if catalog == DocumentStateGroup.Catalog.DOCUMENTS and effect:
            raise serializers.ValidationError({
                'operational_effect': (
                    'Los estados de documentos no tienen efecto de proyecto.'
                ),
            })
        visibility = attrs.get(
            'show_in_document_manager',
            getattr(self.instance, 'show_in_document_manager', False),
        )
        if catalog == DocumentStateGroup.Catalog.DOCUMENTS and visibility:
            raise serializers.ValidationError({
                'show_in_document_manager': (
                    'La visibilidad de carpetas sólo aplica a estados de proyecto.'
                ),
            })
        if expected_mode and group and group.selection_mode != expected_mode:
            label = 'exclusivo' if expected_mode == 'exclusive' else 'aditivo'
            raise serializers.ValidationError({
                'group': (
                    f'Este estado semilla conserva su función en un grupo {label}.'
                ),
            })
        return attrs


class DocumentNoteSerializer(EditorialModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()
    deleted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentNote
        fields = (
            'id', 'document', 'episode', 'title', 'content', 'order',
            'status', 'resolution_note', 'created_by', 'created_by_name',
            'resolved_by', 'resolved_by_name', 'resolved_at', 'created_at',
            'created_at_known', 'deleted_at', 'deleted_by',
            'deleted_by_name', 'updated_at',
        )
        read_only_fields = fields

    def get_created_by_name(self, obj):
        return actor_display(obj.created_by)

    def get_resolved_by_name(self, obj):
        return actor_display(obj.resolved_by)

    def get_deleted_by_name(self, obj):
        return actor_display(obj.deleted_by)


class DocumentNoteEventSerializer(EditorialModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentNoteEvent
        fields = (
            'id', 'note', 'event_type', 'actor', 'actor_name',
            'recorded_at', 'details',
        )
        read_only_fields = fields

    def get_actor_name(self, obj):
        return actor_display(obj.actor)


class DocumentStateEventSerializer(EditorialModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentStateEpisodeEvent
        fields = (
            'id', 'event_type', 'effective_at', 'recorded_at',
            'actor', 'actor_name', 'details',
        )

    def get_actor_name(self, obj):
        return actor_display(obj.actor)


class DocumentStateEpisodeSerializer(EditorialModelSerializer):
    state = DocumentStateSummarySerializer(read_only=True)
    opening_time_known = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    opened_by_name = serializers.SerializerMethodField()
    closed_by_name = serializers.SerializerMethodField()
    events = DocumentStateEventSerializer(many=True, read_only=True)
    notes = serializers.SerializerMethodField()

    class Meta:
        model = DocumentStateEpisode
        fields = (
            'id', 'document', 'project', 'state', 'opened_at', 'closed_at',
            'opening_time_known', 'duration_seconds', 'opened_by',
            'opened_by_name', 'closed_by', 'closed_by_name', 'outcome',
            'close_note', 'origin', 'created_at', 'updated_at',
            'events', 'notes',
        )

    def get_opening_time_known(self, obj):
        return obj.opened_at is not None

    def get_duration_seconds(self, obj):
        if obj.opened_at is None:
            return None
        end = obj.closed_at or timezone.now()
        return max(0, int((end - obj.opened_at).total_seconds()))

    def get_opened_by_name(self, obj):
        return actor_display(obj.opened_by)

    def get_closed_by_name(self, obj):
        return actor_display(obj.closed_by)

    def get_notes(self, obj):
        notes = getattr(obj, '_active_notes', None)
        if notes is None:
            notes = obj.notes.filter(deleted_at__isnull=True).select_related(
                'created_by', 'resolved_by', 'deleted_by',
            )
        return DocumentNoteSerializer(notes, many=True).data


class DocumentBrowseStateSerializer(EditorialModelSerializer):
    """Only the state fields rendered by a document row or card."""

    group_mode = serializers.CharField(
        source='group.selection_mode', read_only=True,
    )
    group_order = serializers.IntegerField(source='group.order', read_only=True)

    class Meta:
        model = DocumentState
        fields = (
            'id', 'name', 'color', 'system_key', 'order',
            'group_mode', 'group_order',
        )


class DocumentBrowseStateEpisodeSerializer(EditorialModelSerializer):
    """Compact active-state projection for the paginated document browser."""

    state = DocumentBrowseStateSerializer(read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = DocumentStateEpisode
        fields = ('id', 'state', 'opened_at', 'duration_seconds')

    def get_duration_seconds(self, obj):
        if obj.opened_at is None:
            return None
        return max(0, int(((obj.closed_at or timezone.now()) - obj.opened_at).total_seconds()))


class OpenDocumentStateSerializer(serializers.Serializer):
    state_id = serializers.PrimaryKeyRelatedField(
        source='state',
        queryset=DocumentState.objects.filter(
            catalog=DocumentStateGroup.Catalog.DOCUMENTS,
        ),
    )
    opened_at = serializers.DateTimeField(required=False)
    origin = serializers.ChoiceField(
        choices=DocumentStateEpisode.Origin.choices,
        required=False,
        default=DocumentStateEpisode.Origin.MANUAL,
    )


class CloseDocumentStateSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=(
            DocumentStateEpisode.Outcome.COMPLETED,
            DocumentStateEpisode.Outcome.REMOVED,
        ),
        default=DocumentStateEpisode.Outcome.COMPLETED,
        required=False,
    )
    note = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default='',
    )


class CorrectEpisodeOpeningSerializer(serializers.Serializer):
    opened_at = serializers.DateTimeField()


class CreateDocumentNoteSerializer(serializers.Serializer):
    text_formats = serializers.JSONField(required=False)
    title = serializers.CharField(
        max_length=120, required=False, allow_blank=True, default='',
    )
    content = serializers.CharField()
    mark_needs_fix = serializers.BooleanField(required=False, default=False)


class UpdateDocumentNoteSerializer(serializers.Serializer):
    text_formats = serializers.JSONField(required=False)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    content = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('No hay cambios para guardar.')
        return attrs


class FinishDocumentNoteSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=(DocumentNote.Status.RESOLVED, DocumentNote.Status.DISCARDED),
        default=DocumentNote.Status.RESOLVED,
        required=False,
    )
    resolution_note = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default='',
    )
    close_linked_state = serializers.BooleanField(required=False, default=False)
    move_cycle_to_bug_attended = serializers.BooleanField(
        required=False, default=False,
    )


class BulkDeleteDocumentNotesSerializer(serializers.Serializer):
    note_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_note_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                'La selección contiene observaciones repetidas.',
            )
        return value
