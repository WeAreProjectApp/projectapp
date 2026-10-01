"""Whitelisted client input and metadata projections, separate from Panel."""

from rest_framework import serializers

from .catalog import SECRET_TYPES, type_label
from .models import SecureLink, SecureLinkEvent


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError('La solicitud contiene campos no permitidos.')
        return super().to_internal_value(data)


class CreateInput(StrictInput):
    request_id = serializers.UUIDField()
    title = serializers.CharField(max_length=160)
    secret_type = serializers.ChoiceField(choices=list(SECRET_TYPES))
    fields = serializers.DictField()
    language = serializers.ChoiceField(choices=SecureLink.Language.choices, default='es')
    validity_days = serializers.ChoiceField(choices=(1, 3, 7), default=7)
    replaces = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class TitleInput(StrictInput):
    title = serializers.CharField(max_length=160)
    expected_updated_at = serializers.DateTimeField()


class ReactivateInput(StrictInput):
    validity_days = serializers.ChoiceField(choices=(1, 3, 7), default=7)
    expected_updated_at = serializers.DateTimeField()


class EmptyInput(StrictInput):
    pass


class ListInput(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    status = serializers.ChoiceField(choices=SecureLink.STATUSES, required=False)
    search = serializers.CharField(max_length=160, required=False, allow_blank=True)


class LinkMetadata(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    type_label = serializers.SerializerMethodField()
    replaces = serializers.IntegerField(source='replaces_id', read_only=True)
    replaced_by = serializers.SerializerMethodField()
    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = SecureLink
        fields = (
            'id', 'project', 'title', 'secret_type', 'type_label', 'language', 'audience',
            'status', 'validity_days', 'expires_at', 'consumed_at', 'revoked_at',
            'activation_count', 'created_at', 'updated_at', 'replaces', 'replaced_by', 'capabilities',
        )

    def get_type_label(self, obj):
        return type_label(obj.secret_type, obj.language)

    def get_replaced_by(self, obj):
        successor = getattr(obj, 'replaced_by', None)
        return successor.pk if successor else None

    def get_capabilities(self, obj):
        return {
            'copy_url': obj.status == 'active',
            'revoke': obj.revoked_at is None,
            'reactivate': obj.status != 'active' and self.get_replaced_by(obj) is None,
            'replace': obj.revoked_at is not None and self.get_replaced_by(obj) is None,
        }


class EventMetadata(serializers.ModelSerializer):
    actor_kind = serializers.SerializerMethodField()
    references = serializers.SerializerMethodField()

    class Meta:
        model = SecureLinkEvent
        fields = ('id', 'kind', 'created_at', 'actor_kind', 'references')

    def get_actor_kind(self, obj):
        if obj.actor_id is None:
            return 'system'
        return 'client' if obj.actor_id == self.context.get('owner_user_id') else 'team'

    def get_references(self, obj):
        value = obj.details.get('replacement_id')
        return {'replacement_id': value} if obj.kind == SecureLinkEvent.Kind.REPLACED and type(value) is int else {}
