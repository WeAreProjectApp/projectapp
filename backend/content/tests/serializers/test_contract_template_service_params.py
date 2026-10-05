"""Service defaults apply to default templates while negotiated contracts stay valid."""
import pytest
from content.serializers.proposal import ContractParamsSerializer

pytestmark = pytest.mark.django_db

def test_combined_contract_params_fill_service_defaults_without_overwriting_explicit_values(company_settings):
    """Falla si el contrato combinado omite defaults de servicio o pisa términos negociados."""
    company_settings.service_contract_settings = {
        'default_duration': 12,
        'default_renewal_notice': 30,
        'default_termination_notice': 60,
        'duration_options': [6, 12],
        'notice_options': [30, 60],
    }
    company_settings.save(update_fields=['service_contract_settings'])
    serializer = ContractParamsSerializer(
        data={
            'client_cedula': '123456789', 'contractor_nit': '900123456',
            'service_initial_term': '18 meses',
        },
        context={'modality': 'single', 'variant': 'combined'},
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['service_initial_term'] == '18 meses'
    assert serializer.validated_data['service_renewal_notice_days'] == 'treinta (30)'
    assert serializer.validated_data['service_termination_notice_days'] == 'sesenta (60)'


def test_custom_combined_contract_accepts_its_saved_terms_without_default_service_fields():
    """Falla si las nuevas validaciones bloquean un contrato combinado personalizado."""
    serializer = ContractParamsSerializer(
        data={'client_cedula': '123456789', 'contract_source': 'custom',
              'custom_contract_markdown': '# Texto contractual negociado'},
        context={'modality': 'single', 'variant': 'combined'},
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['custom_contract_markdown'] == '# Texto contractual negociado'
