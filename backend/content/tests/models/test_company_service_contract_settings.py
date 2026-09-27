"""Defaults that make service-contract term choices usable on a fresh install."""
import pytest

from content.models import CompanySettings

pytestmark = pytest.mark.django_db


def test_fresh_singleton_exposes_agreed_service_contract_term_defaults():
    """Fails if a new deployment opens the contract modal without the agreed presets."""
    CompanySettings.objects.all().delete()

    settings = CompanySettings.load()

    assert settings.service_contract_settings == {
        'duration_options': [3, 6, 9, 12],
        'notice_options': [30, 60, 90],
        'default_duration': 9,
        'default_renewal_notice': 60,
        'default_termination_notice': 60,
    }
