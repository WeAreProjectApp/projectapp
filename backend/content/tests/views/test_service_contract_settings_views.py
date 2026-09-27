"""API contract for the global selectable terms of a service contract."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from content.models import CompanySettings

pytestmark = pytest.mark.django_db
User = get_user_model()

VALID_SETTINGS = {
    'duration_options': [3, 6, 9, 12],
    'notice_options': [30, 60, 90],
    'default_duration': 9,
    'default_renewal_notice': 60,
    'default_termination_notice': 60,
}


def _payload(settings=VALID_SETTINGS):
    return {'service_contract_settings': settings}


class TestServiceContractSettings:
    URL_NAME = 'get-company-settings'

    def _url(self):
        return reverse(self.URL_NAME)

    def test_admin_persists_sorted_term_catalog(self, admin_client, company_settings):
        """Fails if the API reports configurable terms but does not persist a sorted catalog."""
        submitted = {
            'duration_options': [12, 3, 9, 6],
            'notice_options': [90, 30, 60],
            'default_duration': 9,
            'default_renewal_notice': 60,
            'default_termination_notice': 90,
        }

        patched = admin_client.patch(self._url(), _payload(submitted), format='json')
        fetched = admin_client.get(self._url())
        company_settings.refresh_from_db()

        expected = {
            'duration_options': [3, 6, 9, 12],
            'notice_options': [30, 60, 90],
            'default_duration': 9,
            'default_renewal_notice': 60,
            'default_termination_notice': 90,
        }
        assert patched.status_code == 200
        assert patched.data['service_contract_settings'] == expected
        assert fetched.data['service_contract_settings'] == expected
        assert company_settings.service_contract_settings == expected

    @pytest.mark.parametrize(
        ('catalog', 'error_field'),
        [
            ({**VALID_SETTINGS, 'duration_options': [3, 3]}, 'duration_options'),
            ({**VALID_SETTINGS, 'notice_options': []}, 'notice_options'),
            ({**VALID_SETTINGS, 'duration_options': ['3']}, 'duration_options'),
            ({**VALID_SETTINGS, 'duration_options': [1.5]}, 'duration_options'),
            ({**VALID_SETTINGS, 'duration_options': [0]}, 'duration_options'),
            ({**VALID_SETTINGS, 'duration_options': [1000]}, 'duration_options'),
            ({**VALID_SETTINGS, 'duration_options': [True]}, 'duration_options'),
            ({**VALID_SETTINGS, 'default_duration': 8}, 'default_duration'),
            ({**VALID_SETTINGS, 'unexpected': 1}, 'unexpected'),
        ],
    )
    def test_invalid_catalog_is_rejected_without_changing_saved_settings(
        self, admin_client, company_settings, catalog, error_field,
    ):
        """Fails if malformed service-term catalogs overwrite a working saved configuration."""
        before = company_settings.service_contract_settings

        response = admin_client.patch(self._url(), _payload(catalog), format='json')
        company_settings.refresh_from_db()

        assert response.status_code == 400
        assert error_field in response.data['service_contract_settings']
        assert company_settings.service_contract_settings == before

    def test_unknown_top_level_setting_leaves_saved_catalog_intact(
        self, admin_client, company_settings,
    ):
        """Fails if this endpoint can write unrelated company configuration fields."""
        before = company_settings.service_contract_settings
        payload = {**_payload(), 'contractor_full_name': 'No permitido'}

        response = admin_client.patch(self._url(), payload, format='json')
        company_settings.refresh_from_db()

        assert response.status_code == 400
        assert 'contractor_full_name' in response.data
        assert company_settings.service_contract_settings == before

    def test_unauthenticated_patch_leaves_no_singleton(self, api_client):
        """Fails if an anonymous caller can alter the presets used in service contracts."""
        CompanySettings.objects.all().delete()

        response = api_client.patch(self._url(), _payload(), format='json')

        assert response.status_code == 401
        assert CompanySettings.objects.count() == 0

    def test_non_staff_user_cannot_change_the_service_term_catalog(self, api_client, company_settings):
        """Fails if a signed-in non-administrator can alter service-contract presets."""
        user = User.objects.create_user(username='settings-member', password='secret-pass')
        api_client.force_authenticate(user=user)
        before = company_settings.service_contract_settings

        response = api_client.patch(self._url(), _payload(), format='json')
        company_settings.refresh_from_db()

        assert response.status_code == 403
        assert company_settings.service_contract_settings == before

    def test_session_patch_without_csrf_leaves_catalog_intact(self, admin_user, company_settings):
        """Fails if a session-authenticated browser can overwrite presets without a CSRF token."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(admin_user)
        before = company_settings.service_contract_settings

        response = client.patch(
            self._url(), data=json.dumps(_payload()), content_type='application/json',
        )
        company_settings.refresh_from_db()

        assert response.status_code == 403
        assert company_settings.service_contract_settings == before
