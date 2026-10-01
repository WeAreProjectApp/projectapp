"""Only the fixed visibility matrix is writable; grants bind server-side values."""
from rest_framework import serializers

from accounts.serializers_project_ideas import StrictSerializer, VersionField

ENVIRONMENTS = ('production', 'staging')
ACCESS_FIELDS = ('site_url', 'admin_url', 'admin_username', 'admin_password')


class AccessPermissionsSerializer(StrictSerializer):
    site_url = serializers.BooleanField()
    admin_url = serializers.BooleanField()
    admin_username = serializers.BooleanField()
    admin_password = serializers.BooleanField()

    def to_internal_value(self, data):
        if isinstance(data, dict) and any(type(value) is not bool for value in data.values()):
            raise serializers.ValidationError({'non_field_errors': ['Cada permiso debe ser verdadero o falso.']})
        return super().to_internal_value(data)


class AccessMatrixSerializer(StrictSerializer):
    production = AccessPermissionsSerializer()
    staging = AccessPermissionsSerializer()


class ClientAccessPolicySerializer(StrictSerializer):
    expected_version = VersionField(min_value=0)
    source_token = serializers.CharField(max_length=1000)
    permissions = AccessMatrixSerializer()


class EmptyAccessSerializer(StrictSerializer):
    pass
