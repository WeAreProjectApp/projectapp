"""Explicit billing context input reused across authenticated entry points."""
from rest_framework import serializers

from accounts.serializers_delivery import StrictSerializer


class BillingContractLinkSerializer(StrictSerializer):
    source_type = serializers.ChoiceField(choices=('document', 'proposal_document'))
    source_id = serializers.IntegerField(min_value=1)
    expected_version = serializers.IntegerField(min_value=0)
    request_id = serializers.CharField(max_length=100)


class BillingContextFields(serializers.Serializer):
    billing_nature = serializers.ChoiceField(choices=('contract', 'hosting'), required=False)
    contract_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    amendment_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    project_hosting_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    hosting_payment_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class BillingContextAssignmentSerializer(BillingContextFields):
    billing_nature = serializers.ChoiceField(choices=('contract', 'hosting'))
    expected_version = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=2000, allow_blank=False)


class HostingReconciliationSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=2000, allow_blank=False)
    subscription_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    hosting_record_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    operational_record_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class HostingEvidenceSerializer(serializers.Serializer):
    group_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    expected_version = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=2000, allow_blank=False)
    label = serializers.CharField(max_length=200)
    payment_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)
    cycle_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)
    document_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)


class HostingAccountEmissionSerializer(serializers.Serializer):
    hosting_payment_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
