"""Additive ticket payloads shared by existing REST serializers and MCP."""
from rest_framework import serializers

from accounts.serializers_delivery import (
    ReplyClassificationSerializer, ReplyPayloadSerializer, SourceReferenceSerializer, StrictSerializer,
)
from accounts.services.delivery_access import is_admin
from accounts.services.issue_context import original_context


class IssueWriteFields(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0, required=False)
    request_id = serializers.UUIDField(required=False)


class IssueCreateFields(IssueWriteFields):
    source_publication_id = serializers.IntegerField(min_value=1, required=False)
    source_requirement_version = serializers.IntegerField(min_value=0, required=False)


class IssueMessageFields(IssueWriteFields):
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), max_length=10, required=False, default=list,
    )


class IssueContractReplyFields(StrictSerializer):
    context_id = serializers.UUIDField()
    expected_version = serializers.IntegerField(min_value=0)
    expected_ticket_version = serializers.IntegerField(min_value=0)
    human_reviewed = serializers.BooleanField()
    classifications = ReplyClassificationSerializer(many=True, allow_empty=False, max_length=100)
    source_references = SourceReferenceSerializer(many=True, max_length=100)


class IssueReplyPreviewFields(StrictSerializer):
    expected_version = serializers.IntegerField(min_value=0)
    expected_ticket_version = serializers.IntegerField(min_value=0)
    payload = ReplyPayloadSerializer()


class IssueEvaluationFields(IssueMessageFields):
    is_internal = serializers.BooleanField(default=False)
    contract_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    contract_reply = IssueContractReplyFields(required=False)


class IssueCommentFields(IssueMessageFields):
    reopen = serializers.BooleanField(default=False)


class IssueContextOptionsFields(serializers.Serializer):
    kind = serializers.ChoiceField(choices=['bug', 'change'], required=False)
    ticket_id = serializers.IntegerField(min_value=1, required=False)
    contract_id = serializers.IntegerField(min_value=1, required=False)
    source_requirement_id = serializers.IntegerField(min_value=1, required=False)
    source_publication_id = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if attrs.get('ticket_id') and not attrs.get('kind'):
            raise serializers.ValidationError({'kind': 'Indica el tipo de ticket.'})
        if attrs.get('source_publication_id') and not attrs.get('source_requirement_id'):
            raise serializers.ValidationError({'source_requirement_id': 'Indica el requerimiento original.'})
        return attrs


def _actor(context):
    request = context.get('request')
    return request.user if request else context.get('actor')


def attachment_data(item):
    return {
        'id': item.pk, 'document_id': item.document_id, 'title': item.title,
        'sha256': item.sha256,
        'download_url': f'/api/accounts/issue-reports/attachments/{item.pk}/',
    }


class IssueReadFields(serializers.Serializer):
    origin_context = serializers.SerializerMethodField()
    version = serializers.IntegerField(read_only=True)

    def get_origin_context(self, obj):
        return original_context(obj)


class IssueDetailFields(IssueReadFields):
    responses = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    def get_responses(self, obj):
        from accounts.services.issue_contract_reply import public_review_evidence
        admin = bool(_actor(self.context) and is_admin(_actor(self.context)))
        rows = getattr(obj, '_issue_responses', None)
        if rows is None:
            rows = obj.issue_responses.select_related('actor').prefetch_related('attachments')
        return [{
            'id': row.pk, 'message': row.message, 'status': row.status,
            'is_internal': row.is_internal, 'actor_name': row.actor.get_full_name() or row.actor.email,
            'contract_id': row.contract_id, 'scope_result': row.scope_result,
            'review_evidence': public_review_evidence(row.review_evidence),
            **({'review_context_id': row.review_evidence.get('private', {}).get('context_id')}
               if admin and isinstance(row.review_evidence, dict) else {}),
            'created_at': row.created_at.isoformat(),
            'attachments': [attachment_data(item) for item in row.attachments.all()],
        } for row in rows if admin or not row.is_internal]

    def get_history(self, obj):
        admin = bool(_actor(self.context) and is_admin(_actor(self.context)))
        rows = getattr(obj, '_issue_events', None)
        if rows is None:
            rows = obj.issue_events.select_related('actor')
        return [{
            'id': row.pk, 'action': row.action, 'previous_status': row.previous_status,
            'status': row.status, 'actor_name': row.actor.get_full_name() or row.actor.email,
            'created_at': row.created_at.isoformat(),
        } for row in rows if admin or not row.is_internal]


class IssueCommentReadFields(serializers.Serializer):
    attachments = serializers.SerializerMethodField()

    def get_attachments(self, obj):
        return [attachment_data(item) for item in obj.issue_attachments.all()]
