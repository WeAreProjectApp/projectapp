"""Only service terms can be supplied while changing the contract layout."""
from rest_framework import serializers

from content.serializers.service_contract_settings import ServiceTermField, StrictSettingsSerializer


class ModalityServiceParamsSerializer(StrictSettingsSerializer):
    service_initial_term = ServiceTermField(duration=True, required=False, allow_blank=True, max_length=100)
    service_renewal_notice_days = ServiceTermField(required=False, allow_blank=True, max_length=60)
    service_termination_notice_days = ServiceTermField(required=False, allow_blank=True, max_length=60)


class ContractModalitySerializer(StrictSettingsSerializer):
    contract_modality = serializers.ChoiceField(choices=['single', 'split'])
    change_note = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    contract_params = ModalityServiceParamsSerializer(required=False)
    conflict_resolution = serializers.ChoiceField(choices=['use_origin'], required=False)


class ContractRestoreSerializer(StrictSettingsSerializer):
    snapshot_id = serializers.IntegerField(min_value=1)
    change_note = serializers.CharField(max_length=4000, allow_blank=False)
