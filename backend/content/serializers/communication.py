from content.serializers.editorial import EditorialModelSerializer
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Project, UserProfile
from accounts.services.proposal_client_service import build_client_display_name
from content.models import (
    CommunicationFolder,
    CommunicationMessage,
    CommunicationMessageDateCorrection,
    CommunicationMessageRevision,
    CommunicationThread,
    Document,
)


class CommunicationDocumentSerializer(EditorialModelSerializer):
    class Meta:
        model = Document
        fields = ('id', 'title', 'status', 'project_id', 'client_user_id')


class CommunicationDateCorrectionSerializer(EditorialModelSerializer):
    corrected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CommunicationMessageDateCorrection
        fields = (
            'id',
            'previous_occurred_at',
            'corrected_occurred_at',
            'reason',
            'corrected_by_name',
            'corrected_at',
        )

    def get_corrected_by_name(self, obj):
        if not obj.corrected_by:
            return ''
        return obj.corrected_by.get_full_name() or obj.corrected_by.username


class CommunicationMessageRevisionSerializer(EditorialModelSerializer):
    edited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CommunicationMessageRevision
        fields = ('id', 'changes', 'edited_by_name', 'edited_at')

    def get_edited_by_name(self, obj):
        if not obj.edited_by:
            return ''
        return obj.edited_by.get_full_name() or obj.edited_by.username


class CommunicationMessageSerializer(EditorialModelSerializer):
    documents = CommunicationDocumentSerializer(many=True, read_only=True)
    date_corrections = CommunicationDateCorrectionSerializer(many=True, read_only=True)
    revisions = CommunicationMessageRevisionSerializer(many=True, read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_reply = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CommunicationMessage
        fields = (
            'id',
            'thread_id',
            'channel',
            'channel_display',
            'direction',
            'direction_display',
            'status',
            'status_display',
            'subject',
            'content',
            'occurred_at',
            'recorded_at',
            'updated_at',
            'source',
            'reply_to_id',
            'has_reply',
            'documents',
            'date_corrections',
            'revisions',
            'created_by_name',
            'voided_at',
            'void_reason',
        )

    def get_has_reply(self, obj):
        annotated = getattr(obj, 'has_reply', None)
        if annotated is not None:
            return annotated
        return obj.replies.filter(voided_at__isnull=True).exists()

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.username


class CommunicationMessageCreateSerializer(EditorialModelSerializer):
    status = serializers.ChoiceField(
        choices=CommunicationMessage.Status.choices,
        required=False,
    )
    occurred_at = serializers.DateTimeField(required=False, default=timezone.now)
    reply_to = serializers.PrimaryKeyRelatedField(
        queryset=CommunicationMessage.objects.all(),
        required=False,
        allow_null=True,
    )
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = CommunicationMessage
        fields = (
            'channel', 'direction', 'status', 'subject', 'content',
            'occurred_at', 'reply_to', 'document_ids',
        )

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El contenido es obligatorio.')
        return value

    def validate_subject(self, value):
        return value.strip()

    def validate(self, attrs):
        direction = attrs.get('direction')
        if 'status' not in attrs:
            attrs['status'] = (
                CommunicationMessage.Status.RECEIVED
                if direction == CommunicationMessage.Direction.INCOMING
                else CommunicationMessage.Status.DRAFT
            )
        return attrs


class CommunicationDraftUpdateSerializer(EditorialModelSerializer):
    reply_to = serializers.PrimaryKeyRelatedField(
        queryset=CommunicationMessage.objects.all(),
        required=False,
        allow_null=True,
    )
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = CommunicationMessage
        fields = (
            'channel', 'direction', 'subject', 'content', 'occurred_at',
            'reply_to', 'document_ids',
        )
        extra_kwargs = {
            'channel': {'required': False},
            'direction': {'required': False},
            'subject': {'required': False},
            'content': {'required': False},
            'occurred_at': {'required': False},
        }

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El contenido es obligatorio.')
        return value

    def validate_subject(self, value):
        return value.strip()


class CommunicationThreadListSerializer(EditorialModelSerializer):
    client_name = serializers.SerializerMethodField()
    client_email = serializers.EmailField(source='client.user.email', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    messages_count = serializers.IntegerField(read_only=True)
    draft_count = serializers.IntegerField(read_only=True)
    latest_message = serializers.SerializerMethodField()
    channels = serializers.SerializerMethodField()
    thread_kind = serializers.CharField(read_only=True)
    folder_name = serializers.CharField(source='folder.name', read_only=True, default='')

    class Meta:
        model = CommunicationThread
        fields = (
            'id', 'title', 'status', 'client_id', 'client_name', 'client_email',
            'project_id', 'project_name', 'messages_count', 'draft_count',
            'channels', 'latest_message', 'last_activity_at', 'closed_at',
            'thread_kind', 'is_archived', 'archived_at', 'folder_id', 'folder_name',
            'created_at', 'updated_at',
        )
        # `is_archived`/`archived_at` son read-only por el mismo motivo que en
        # carpetas: el PATCH del hilo usa este serializer, y dejarlos escribibles
        # permitiría archivar saltándose la guarda de la comunicación madre.
        read_only_fields = ('is_archived', 'archived_at')

    def get_client_name(self, obj):
        return build_client_display_name(obj.client)

    def _messages(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', {})
        return list(cache.get('messages', obj.messages.all()))

    def get_latest_message(self, obj):
        messages = [message for message in self._messages(obj) if not message.voided_at]
        if not messages:
            return None
        message = max(messages, key=lambda item: (item.occurred_at, item.id))
        return {
            'id': message.id,
            'direction': message.direction,
            'status': message.status,
            'content': message.content[:180],
            'occurred_at': message.occurred_at,
        }

    def get_channels(self, obj):
        return sorted({message.channel for message in self._messages(obj)})


class CommunicationThreadDetailSerializer(CommunicationThreadListSerializer):
    messages = CommunicationMessageSerializer(many=True, read_only=True)

    class Meta(CommunicationThreadListSerializer.Meta):
        fields = CommunicationThreadListSerializer.Meta.fields + ('messages',)


class CommunicationThreadWriteSerializer(EditorialModelSerializer):
    folder = serializers.PrimaryKeyRelatedField(
        queryset=CommunicationFolder.objects.all(), required=False, allow_null=True,
    )
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(),
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = CommunicationThread
        fields = ('client', 'project', 'title', 'folder')

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El título es obligatorio.')
        return value

    def validate(self, attrs):
        instance = self.instance
        client = attrs.get('client', getattr(instance, 'client', None))
        project = attrs.get('project', getattr(instance, 'project', None))
        if project and client and project.client_id != client.user_id:
            raise serializers.ValidationError({
                'project': 'El proyecto no pertenece al cliente seleccionado.',
            })
        return attrs


class CommunicationMarkSentSerializer(serializers.Serializer):
    occurred_at = serializers.DateTimeField(required=False)


class CommunicationVoidSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class CommunicationDateCorrectionWriteSerializer(serializers.Serializer):
    occurred_at = serializers.DateTimeField()
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
