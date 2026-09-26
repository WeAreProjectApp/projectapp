from accounts.models import Project, UserProfile
from rest_framework import serializers

from .catalog import SECRET_TYPES, type_label
from .models import SecureLink, SecureLinkEvent
from .services import sender_label


class SecureLinkEventSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source='get_kind_display', read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = SecureLinkEvent
        fields = ('id', 'kind', 'kind_label', 'actor_name', 'ip_address', 'user_agent', 'details', 'created_at')

    def get_actor_name(self, obj):
        if obj.actor_id is None:
            return ''
        return obj.actor.get_full_name() or obj.actor.get_username()


class SecureLinkSerializer(serializers.ModelSerializer):
    """Panel projection. Never includes the token or the content."""

    status = serializers.CharField(read_only=True)
    type_label = serializers.SerializerMethodField()
    origin_label = serializers.CharField(source='get_origin_display', read_only=True)
    sender = serializers.SerializerMethodField()
    team_only = serializers.BooleanField(read_only=True)
    client_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SecureLink
        fields = (
            'id', 'title', 'secret_type', 'type_label', 'language', 'origin', 'origin_label',
            'sender', 'team_only', 'status', 'client', 'client_name', 'project', 'project_name',
            'created_by_name', 'creator_name', 'creator_email', 'validity_days', 'expires_at',
            'consumed_at', 'revoked_at', 'activation_count', 'created_at', 'updated_at',
        )

    def get_type_label(self, obj):
        return type_label(obj.secret_type)

    def get_sender(self, obj):
        return sender_label(obj)

    def get_client_name(self, obj):
        if obj.client_id is None:
            return ''
        user = obj.client.user
        return user.get_full_name() or obj.client.company_name or user.email

    def get_project_name(self, obj):
        return obj.project.name if obj.project_id else ''

    def get_created_by_name(self, obj):
        if obj.created_by_id is None:
            return ''
        return obj.created_by.get_full_name() or obj.created_by.get_username()


class _AssociationMixin(serializers.Serializer):
    client = serializers.PrimaryKeyRelatedField(
        queryset=UserProfile.objects.clients(), required=False, allow_null=True,
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True,
    )


class PanelCreateSerializer(_AssociationMixin):
    secret_type = serializers.ChoiceField(choices=list(SECRET_TYPES))
    title = serializers.CharField(max_length=160)
    fields = serializers.DictField()
    language = serializers.ChoiceField(choices=SecureLink.Language.choices, default=SecureLink.Language.ES)
    validity_days = serializers.IntegerField(required=False)


class PanelUpdateSerializer(_AssociationMixin):
    title = serializers.CharField(max_length=160, required=False)
    secret_type = serializers.ChoiceField(choices=list(SECRET_TYPES), required=False)
    fields = serializers.DictField(required=False)

    def validate(self, attrs):
        if 'secret_type' in attrs and 'fields' not in attrs:
            raise serializers.ValidationError({'fields': ['Envía el contenido al cambiar el tipo.']})
        return attrs


class ReactivateSerializer(serializers.Serializer):
    validity_days = serializers.IntegerField(required=False)
    rotate = serializers.BooleanField(default=False)


class FilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SecureLink.STATUSES, required=False)
    origin = serializers.ChoiceField(choices=SecureLink.Origin.choices, required=False)
    received = serializers.BooleanField(required=False)
    client = serializers.IntegerField(required=False, min_value=1)
    project = serializers.IntegerField(required=False, min_value=1)
    search = serializers.CharField(required=False, max_length=120)
    page = serializers.IntegerField(required=False, min_value=1, default=1)


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)


class PublicCreateSerializer(serializers.Serializer):
    secret_type = serializers.ChoiceField(choices=list(SECRET_TYPES))
    title = serializers.CharField(max_length=160, required=False, allow_blank=True)
    fields = serializers.DictField()
    creator_name = serializers.CharField(max_length=120)
    creator_email = serializers.EmailField(required=False, allow_blank=True)
    language = serializers.ChoiceField(choices=SecureLink.Language.choices, default=SecureLink.Language.ES)
    validity_days = serializers.IntegerField(required=False)
    recaptcha_token = serializers.CharField(required=False, allow_blank=True, max_length=4096)
    # Honeypot: humans never see it, so any value marks an automated post.
    website = serializers.CharField(required=False, allow_blank=True, max_length=200)
