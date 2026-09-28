from rest_framework import serializers


class VideoResourceWriteSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=0)
    action = serializers.ChoiceField(choices=['upload', 'remove', 'restore-default'])
    file = serializers.FileField(required=False, allow_empty_file=False)

    def validate(self, attrs):
        if attrs['action'] == 'upload' and 'file' not in attrs:
            raise serializers.ValidationError({'file': 'Selecciona un archivo MP4.'})
        return attrs
