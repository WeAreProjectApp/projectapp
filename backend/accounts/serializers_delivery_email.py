"""Strict request contracts for manual delivery-stage closure emails."""
from rest_framework import serializers

from accounts.serializers_delivery import VersionedSerializer


class PrepareStageEmailSerializer(VersionedSerializer):
    request_id = serializers.CharField(max_length=100)
    message = serializers.CharField(required=False, allow_blank=True, max_length=20000)
    include_record_pdf = serializers.BooleanField(required=False, default=False)
    document_snapshot_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False,
        default=list, max_length=20,
    )


class SendStageEmailSerializer(VersionedSerializer):
    request_id = serializers.CharField(max_length=100)
    preview_sha256 = serializers.CharField(min_length=64, max_length=64)
    human_reviewed = serializers.BooleanField()

    def validate_human_reviewed(self, value):
        if value is not True:
            raise serializers.ValidationError('Confirma que revisaste el correo antes de enviarlo.')
        return value


class ResendStageEmailSerializer(VersionedSerializer):
    request_id = serializers.CharField(max_length=100)
