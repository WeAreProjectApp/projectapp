from accounts.models import Project, UserProfile
from rest_framework import serializers
from .models import SecureLinkFolder


class FolderSerializer(serializers.ModelSerializer):
    folder_kind = serializers.SerializerMethodField()
    is_read_only = serializers.SerializerMethodField()
    class Meta:
        model = SecureLinkFolder
        fields = ('id', 'name', 'parent', 'order', 'client', 'project', 'managed_project',
                  'folder_kind', 'is_archived', 'archived_at', 'archived_via_folder',
                  'is_read_only', 'created_at', 'updated_at')

    def get_is_read_only(self, obj):
        return bool(obj.retention_context_id)

    def get_folder_kind(self, obj):
        return 'project' if obj.managed_project_id else 'manual'


class FolderWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    parent = serializers.PrimaryKeyRelatedField(queryset=SecureLinkFolder.objects.all(), required=False, allow_null=True)
    client = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.clients(), required=False, allow_null=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False, allow_null=True)
    expected_updated_at = serializers.DateTimeField(required=False)


class MoveLinkSerializer(serializers.Serializer):
    folder = serializers.PrimaryKeyRelatedField(queryset=SecureLinkFolder.objects.all(), allow_null=True)
    expected_updated_at = serializers.DateTimeField(required=False)


class RevisionSerializer(serializers.Serializer):
    expected_updated_at = serializers.DateTimeField(required=False)


class ReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)
    parent = serializers.PrimaryKeyRelatedField(queryset=SecureLinkFolder.objects.all(), allow_null=True, default=None)
