"""Shared Panel/MCP validation for explicit proposal project review."""
from rest_framework import serializers


class NewApprovalClientSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=311)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    company = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    nit = serializers.CharField(max_length=32, required=False, allow_blank=True, default='')
    billing_code = serializers.CharField(max_length=12, required=False, allow_blank=True, allow_null=True, default=None)

    def validate_billing_code(self, value):
        from accounts.services.billing_code import normalize_billing_code
        from accounts.services.billing_code import billing_code_error
        code = normalize_billing_code(value) if value else None
        if code and billing_code_error(code):
            raise serializers.ValidationError(billing_code_error(code))
        from accounts.models import UserProfile
        if code and UserProfile.objects.filter(billing_code=code).exists():
            raise serializers.ValidationError('Ese código de facturación ya pertenece a un cliente.')
        return code


class ApprovalCustomDocumentSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=300)
    document_type = serializers.ChoiceField(choices=['contract', 'legal_annex', 'amendment', 'other'])


class ProposalApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['confirm', 'defer', 'retry'])
    accept_proposal = serializers.BooleanField(default=True)
    request_id = serializers.CharField(max_length=100, required=False)
    source_hash = serializers.CharField(max_length=64, required=False)
    client_profile_id = serializers.IntegerField(min_value=1, required=False)
    new_client = NewApprovalClientSerializer(required=False)
    project_id = serializers.IntegerField(min_value=1, required=False)
    new_project = serializers.DictField(required=False)
    use_proposal_contracts = serializers.BooleanField(default=True)
    selected_document_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list)
    custom_documents = ApprovalCustomDocumentSerializer(many=True, default=list)

    def validate(self, data):
        if data['action'] == 'confirm':
            for field in ('source_hash', 'request_id'):
                if not data.get(field):
                    raise serializers.ValidationError({field: 'Este dato es obligatorio para confirmar.'})
            if bool(data.get('client_profile_id')) == bool(data.get('new_client')):
                raise serializers.ValidationError({'client_profile_id': 'Selecciona un cliente o crea uno nuevo.'})
            if bool(data.get('project_id')) == bool(data.get('new_project')):
                raise serializers.ValidationError({'project_id': 'Selecciona un proyecto o crea uno nuevo.'})
        return data
