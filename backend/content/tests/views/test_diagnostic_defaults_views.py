"""Tests for the diagnostic defaults API views (GET/PUT/RESET)."""
import pytest
from django.urls import reverse

from content.models import DiagnosticDefaultConfig

pytestmark = pytest.mark.django_db


SAMPLE_SECTIONS = [
    {
        'section_type': 'purpose',
        'title': 'Propósito',
        'order': 0,
        'is_enabled': True,
        'visibility': 'both',
        'content_json': {'heading': 'Hola'},
    },
    {
        'section_type': 'cost',
        'title': 'Inversión',
        'order': 1,
        'is_enabled': True,
        'visibility': 'final',
        'content_json': {'amount': 1000},
    },
]


# ── GET ────────────────────────────────────────────────────────────────────

class TestGetDiagnosticDefaults:
    @pytest.mark.parametrize(('language', 'first_title'), [('es', 'Propósito'), ('en', 'Purpose')])
    def test_empty_config_exposes_the_system_sections(self, admin_client, language, first_title):
        config = DiagnosticDefaultConfig.objects.create(language=language, sections_json=[])

        result = admin_client.get(reverse('diagnostic-defaults'), {'lang': language})

        assert result.status_code == 200
        assert result.data['sections_json'] == []
        assert len(result.data['effective_sections_json']) == 8
        assert result.data['effective_sections_json'][0]['title'] == first_title
        config.refresh_from_db()
        assert config.sections_json == []

    def test_fallback_returns_correct_identity_fields(self, admin_client):
        url = reverse('diagnostic-defaults')
        response = admin_client.get(url, {'lang': 'es'})
        assert response.status_code == 200
        data = response.json()
        assert data['id'] is None
        assert data['language'] == 'es'
        assert data['default_currency'] == 'COP'

    def test_fallback_returns_correct_deadline_fields(self, admin_client):
        url = reverse('diagnostic-defaults')
        response = admin_client.get(url, {'lang': 'es'})
        data = response.json()
        assert data['payment_initial_pct'] == 60
        assert data['payment_final_pct'] == 40
        assert data['expiration_days'] == 21
        assert isinstance(data['sections_json'], list)
        assert len(data['sections_json']) > 0

    def test_returns_db_config_identity_fields(self, admin_client):
        DiagnosticDefaultConfig.objects.create(
            language='es',
            sections_json=SAMPLE_SECTIONS,
            payment_initial_pct=70,
            payment_final_pct=30,
            default_currency='USD',
            default_duration_label='4 semanas',
            expiration_days=30,
        )
        url = reverse('diagnostic-defaults')
        response = admin_client.get(url, {'lang': 'es'})
        assert response.status_code == 200
        data = response.json()
        assert data['id'] is not None
        assert data['default_currency'] == 'USD'
        assert data['default_duration_label'] == '4 semanas'

    def test_returns_db_config_deadline_fields(self, admin_client):
        DiagnosticDefaultConfig.objects.create(
            language='es',
            sections_json=SAMPLE_SECTIONS,
            payment_initial_pct=70,
            payment_final_pct=30,
            default_currency='USD',
            expiration_days=30,
        )
        url = reverse('diagnostic-defaults')
        response = admin_client.get(url, {'lang': 'es'})
        data = response.json()
        assert data['payment_initial_pct'] == 70
        assert data['payment_final_pct'] == 30
        assert data['expiration_days'] == 30
        assert len(data['sections_json']) == len(SAMPLE_SECTIONS)

    def test_defaults_to_es_when_no_lang(self, admin_client):
        url = reverse('diagnostic-defaults')
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json()['language'] == 'es'

    def test_rejects_invalid_language(self, admin_client):
        url = reverse('diagnostic-defaults')
        response = admin_client.get(url, {'lang': 'fr'})
        assert response.status_code == 400

    def test_requires_admin(self, api_client):
        url = reverse('diagnostic-defaults')
        response = api_client.get(url)
        assert response.status_code in (401, 403)


# ── PUT ────────────────────────────────────────────────────────────────────

class TestPutDiagnosticDefaults:
    def test_general_save_preserves_the_empty_system_configuration(self, admin_client):
        DiagnosticDefaultConfig.objects.create(language='en', sections_json=[])

        response = admin_client.put(reverse('diagnostic-defaults'), {
            'language': 'en', 'default_currency': 'USD',
        }, format='json')

        assert response.status_code == 200
        assert response.data['effective_sections_json'][1]['title'] == 'Application Overview'
        assert DiagnosticDefaultConfig.objects.get(language='en').sections_json == []

    def test_initial_defaults_write_stores_system_template_for_language(self, admin_client):
        url = reverse('diagnostic-defaults')
        initial = admin_client.get(url, {'lang': 'en'})

        response = admin_client.put(url, {'language': 'en', 'default_currency': 'USD'}, format='json')

        assert response.status_code == 200
        assert DiagnosticDefaultConfig.objects.get(language='en').sections_json == initial.data['sections_json']

    def test_creates_new_config(self, admin_client):
        url = reverse('diagnostic-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'payment_initial_pct': 60,
            'payment_final_pct': 40,
            'default_currency': 'COP',
            'default_investment_amount': '1500000.00',
            'default_duration_label': '4 semanas',
            'expiration_days': 21,
            'reminder_days': 7,
            'urgency_reminder_days': 14,
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 200, response.json()
        data = response.json()
        assert data['id'] is not None
        assert data['payment_initial_pct'] == 60
        assert data['default_duration_label'] == '4 semanas'
        assert DiagnosticDefaultConfig.objects.filter(language='es').exists()

    def test_updates_existing_config(self, admin_client):
        DiagnosticDefaultConfig.objects.create(
            language='es', sections_json=SAMPLE_SECTIONS,
        )
        url = reverse('diagnostic-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS[:1],
            'payment_initial_pct': 50,
            'payment_final_pct': 50,
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 200
        assert response.json()['payment_initial_pct'] == 50
        assert DiagnosticDefaultConfig.objects.filter(language='es').count() == 1

    def test_keeps_existing_sections_when_payload_omits_them(self, admin_client):
        DiagnosticDefaultConfig.objects.create(
            language='es', sections_json=SAMPLE_SECTIONS,
        )
        url = reverse('diagnostic-defaults')
        payload = {'language': 'es', 'payment_initial_pct': 80, 'payment_final_pct': 20}
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 200
        assert len(response.json()['sections_json']) == len(SAMPLE_SECTIONS)

    def test_rejects_unbalanced_payments(self, admin_client):
        url = reverse('diagnostic-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'payment_initial_pct': 70,
            'payment_final_pct': 40,
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_rejects_invalid_currency(self, admin_client):
        url = reverse('diagnostic-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'default_currency': 'EUR',
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_rejects_invalid_sections_shape(self, admin_client):
        url = reverse('diagnostic-defaults')
        payload = {'language': 'es', 'sections_json': [{'section_type': 'purpose'}]}
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_requires_admin(self, api_client):
        url = reverse('diagnostic-defaults')
        response = api_client.put(url, {'language': 'es'}, format='json')
        assert response.status_code in (401, 403)


# ── RESET ──────────────────────────────────────────────────────────────────

class TestResetDiagnosticDefaults:
    def test_deletes_existing_config(self, admin_client):
        DiagnosticDefaultConfig.objects.create(language='es', sections_json=SAMPLE_SECTIONS)
        url = reverse('reset-diagnostic-defaults')
        response = admin_client.post(url, {'language': 'es'}, format='json')
        assert response.status_code == 200
        assert response.json()['deleted'] is True
        assert not DiagnosticDefaultConfig.objects.filter(language='es').exists()

    def test_returns_false_when_nothing_to_delete(self, admin_client):
        url = reverse('reset-diagnostic-defaults')
        response = admin_client.post(url, {'language': 'es'}, format='json')
        assert response.status_code == 200
        assert response.json()['deleted'] is False

    def test_only_affects_requested_language(self, admin_client):
        DiagnosticDefaultConfig.objects.create(language='es', sections_json=SAMPLE_SECTIONS)
        DiagnosticDefaultConfig.objects.create(language='en', sections_json=SAMPLE_SECTIONS)
        url = reverse('reset-diagnostic-defaults')
        admin_client.post(url, {'language': 'es'}, format='json')
        assert not DiagnosticDefaultConfig.objects.filter(language='es').exists()
        assert DiagnosticDefaultConfig.objects.filter(language='en').exists()

    def test_requires_admin(self, api_client):
        url = reverse('reset-diagnostic-defaults')
        response = api_client.post(url, {'language': 'es'}, format='json')
        assert response.status_code in (401, 403)
