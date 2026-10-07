from rest_framework import serializers

from accounts.serializers_delivery import VersionedSerializer


class RetryDeliveryNoticeSerializer(VersionedSerializer):
    request_id = serializers.CharField(max_length=100)
    preview_sha256 = serializers.RegexField(r'^[0-9a-f]{64}$')
