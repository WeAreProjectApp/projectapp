from rest_framework import serializers


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError('Campos de entrada desconocidos.')
        return super().to_internal_value(data)


class ModeInput(ClosedSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    mode = serializers.ChoiceField(choices=['normal', 'suspended', 'banner'])


class ListInput(ClosedSerializer):
    project_id = serializers.IntegerField(min_value=1, required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    search = serializers.CharField(max_length=200, required=False, allow_blank=True)


class MessageInput(ClosedSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    message_mode = serializers.ChoiceField(choices=['suspended', 'banner'])
    title = serializers.CharField(max_length=200)
    text = serializers.CharField(max_length=2000)


class ReceiptInput(ClosedSerializer):
    target_key = serializers.SlugField(max_length=100)
    version = serializers.IntegerField(min_value=0)
    digest = serializers.RegexField(r'^[a-f0-9]{64}$')
    applied = serializers.BooleanField()
