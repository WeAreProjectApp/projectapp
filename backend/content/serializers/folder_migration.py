"""Closed, JSON-serializable inputs for a reviewed folder migration."""

from rest_framework import serializers

from content.serializers.panel_projects import CreatePanelProjectSerializer
from content.serializers.strict_input import StrictInputMixin
from content.services.document_ownership_planner import (
    CLIENT_POLICIES,
    PORTAL_POLICIES,
    DocumentDecisionSerializer,
)


class MigrationProjectSerializer(StrictInputMixin, CreatePanelProjectSerializer):
    def to_representation(self, instance):
        # The panel resolves state_id to a model; signed tokens contain only JSON.
        result = {key: value for key, value in instance.items() if key != 'state'}
        if 'state' in instance:
            result['state_id'] = instance['state'].pk
        return result


class MigrationTargetSerializer(StrictInputMixin, serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1, required=False)
    create_project = MigrationProjectSerializer(required=False)

    def validate(self, attrs):
        if len(attrs) != 1:
            raise serializers.ValidationError('Elige exactamente project_id o create_project.')
        return attrs


class FolderMigrationSerializer(StrictInputMixin, serializers.Serializer):
    source_folder_id = serializers.IntegerField(min_value=1)
    strategy = serializers.ChoiceField(choices=('adopt_source', 'move_contents'))
    target = MigrationTargetSerializer()
    include_folder_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, max_length=100,
    )
    include_document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, max_length=100,
    )
    document_decisions = DocumentDecisionSerializer(many=True, required=False, default=list, max_length=100)
    client_policy = serializers.ChoiceField(choices=CLIENT_POLICIES, default='abort_on_conflict')
    portal_policy = serializers.ChoiceField(choices=PORTAL_POLICIES, default='abort')
    archive_source_when_empty = serializers.BooleanField(required=False)
    source_rename_to = serializers.CharField(max_length=120, required=False)

    def validate(self, attrs):
        move_only = {'include_folder_ids', 'include_document_ids', 'archive_source_when_empty'}
        if attrs['strategy'] != 'move_contents' and move_only.intersection(attrs):
            raise serializers.ValidationError('Los filtros y el archivado sólo se usan con move_contents.')
        for key in ('include_folder_ids', 'include_document_ids'):
            if key in attrs:
                if len(set(attrs[key])) != len(attrs[key]):
                    raise serializers.ValidationError({key: 'No repitas identificadores.'})
                attrs[key] = sorted(attrs[key])
        decisions = attrs['document_decisions']
        if len(decisions) != len({row['document_id'] for row in decisions}):
            raise serializers.ValidationError({'document_decisions': 'No repitas decisiones para un documento.'})
        attrs['document_decisions'] = sorted(decisions, key=lambda row: row['document_id'])
        return attrs

    def to_representation(self, instance):
        result = dict(instance)
        target = dict(result['target'])
        if 'create_project' in target:
            target['create_project'] = MigrationProjectSerializer().to_representation(target['create_project'])
        result['target'] = target
        return result


class MigrationApplySerializer(StrictInputMixin, serializers.Serializer):
    plan_token = serializers.CharField()
    reason = serializers.CharField(min_length=3, max_length=2000)
    request_id = serializers.CharField(max_length=100)


class MigrationUndoSerializer(StrictInputMixin, serializers.Serializer):
    migration_id = serializers.IntegerField(min_value=1)
    expected_impact_hash = serializers.RegexField(r'^[a-f0-9]{64}$')
    reason = serializers.CharField(min_length=3, max_length=2000)
    request_id = serializers.CharField(max_length=100)
