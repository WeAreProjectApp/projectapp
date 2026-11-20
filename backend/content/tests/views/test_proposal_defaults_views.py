"""Tests for proposal defaults API views (GET/PUT/RESET)."""
import pytest
from django.urls import reverse

from content.models import BusinessProposal, ProposalDefaultConfig

pytestmark = pytest.mark.django_db


SAMPLE_SECTIONS = [
    {
        'section_type': 'greeting',
        'title': 'Saludo',
        'order': 0,
        'is_wide_panel': False,
        'content_json': {'proposalTitle': '', 'clientName': ''},
    },
    {
        'section_type': 'executive_summary',
        'title': 'Resumen Ejecutivo',
        'order': 1,
        'is_wide_panel': True,
        'content_json': {'index': '02', 'title': 'Resumen'},
    },
]


# ---------------------------------------------------------------------------
# GET /api/proposals/defaults/
# ---------------------------------------------------------------------------


class TestGetProposalDefaults:
    def test_returns_hardcoded_defaults_when_no_db_config(self, admin_client):
        url = reverse('proposal-defaults')
        response = admin_client.get(url, {'lang': 'es'})
        assert response.status_code == 200
        data = response.json()
        assert data['language'] == 'es'
        assert data['id'] is None
        assert data['expiration_days'] == 21
        assert isinstance(data['sections_json'], list)
        assert len(data['sections_json']) > 0
        assert data['sections_json'][0]['section_type'] == 'greeting'

    def test_returns_db_config_when_exists(self, admin_client):
        ProposalDefaultConfig.objects.create(
            language='es', sections_json=SAMPLE_SECTIONS, expiration_days=28,
        )
        url = reverse('proposal-defaults')
        response = admin_client.get(url, {'lang': 'es'})
        assert response.status_code == 200
        data = response.json()
        assert data['id'] is not None
        assert data['expiration_days'] == 28
        assert len(data['sections_json']) == 2
        assert data['sections_json'][0]['section_type'] == 'greeting'

    def test_returns_english_hardcoded_defaults(self, admin_client):
        url = reverse('proposal-defaults')
        response = admin_client.get(url, {'lang': 'en'})
        assert response.status_code == 200
        data = response.json()
        assert data['language'] == 'en'
        assert isinstance(data['sections_json'], list)
        assert len(data['sections_json']) > 0

    def test_defaults_to_es_when_no_lang_param(self, admin_client):
        url = reverse('proposal-defaults')
        response = admin_client.get(url)
        assert response.status_code == 200
        assert response.json()['language'] == 'es'

    def test_rejects_invalid_language(self, admin_client):
        url = reverse('proposal-defaults')
        response = admin_client.get(url, {'lang': 'fr'})
        assert response.status_code == 400

    def test_requires_admin_auth(self, api_client):
        url = reverse('proposal-defaults')
        response = api_client.get(url)
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/proposals/defaults/
# ---------------------------------------------------------------------------


class TestPutProposalDefaults:
    @pytest.mark.parametrize('language', ['es', 'en'])
    def test_general_save_preserves_custom_sections_for_new_proposals(self, admin_client, language):
        custom = [{
            'section_type': 'greeting', 'title': f'Saludo propio {language}', 'order': 2,
            'content_json': {'clientName': '', 'proposalTitle': ''},
        }, {
            'section_type': 'executive_summary', 'title': f'Resumen propio {language}', 'order': 3,
            'content_json': {'index': '03', 'title': f'Resumen guardado {language}'},
        }]
        ProposalDefaultConfig.objects.update_or_create(language=language, defaults={'sections_json': custom})

        saved = admin_client.put(reverse('proposal-defaults'), {
            'language': language, 'reminder_days': 9,
        }, format='json')
        loaded = admin_client.get(reverse('proposal-defaults'), {'lang': language})
        created = admin_client.post(reverse('create-proposal'), {
            'title': 'Borrador de prueba', 'client_name': f'Cliente de prueba {language}', 'language': language,
        }, format='json')

        assert saved.status_code == 200
        assert loaded.data['sections_json'] == custom
        assert 'effective_sections_json' not in loaded.data
        assert created.status_code == 201
        proposal = BusinessProposal.objects.get(pk=created.data['id'])
        assert list(proposal.sections.values_list('title', 'order')) == [(item['title'], item['order']) for item in custom]
        assert proposal.sections.get(section_type='executive_summary').content_json == custom[1]['content_json']

    @pytest.mark.parametrize(('language', 'reminder', 'urgency'), [('es', 3, 7), ('en', 5, 11)])
    def test_general_save_exposes_effective_system_sections(self, admin_client, language, reminder, urgency):
        url = reverse('proposal-defaults')

        saved = admin_client.put(url, {
            'language': language, 'reminder_days': reminder, 'urgency_reminder_days': urgency,
        }, format='json')
        loaded = admin_client.get(url, {'lang': language})

        assert saved.status_code == 200
        assert loaded.data['reminder_days'] == reminder
        assert loaded.data['urgency_reminder_days'] == urgency
        assert saved.data['sections_json'] == loaded.data['sections_json'] == []
        assert saved.data['effective_sections_json'] == loaded.data['effective_sections_json']
        commercial = [
            section for section in loaded.data['effective_sections_json']
            if section['section_type'] != 'technical_document'
        ]
        assert len(commercial) == 17
        assert len(loaded.data['effective_sections_json']) == 18

    def test_creates_new_config(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'expiration_days': 21,
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 200
        data = response.json()
        assert data['id'] is not None
        assert data['language'] == 'es'
        assert data['expiration_days'] == 21
        assert len(data['sections_json']) == 2
        assert ProposalDefaultConfig.objects.filter(language='es').exists()

    def test_updates_existing_config(self, admin_client):
        ProposalDefaultConfig.objects.create(
            language='es', sections_json=SAMPLE_SECTIONS, expiration_days=21,
        )
        url = reverse('proposal-defaults')
        updated = [SAMPLE_SECTIONS[0]]
        payload = {'language': 'es', 'sections_json': updated, 'expiration_days': 14}
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 200
        assert len(response.json()['sections_json']) == 1
        assert response.json()['expiration_days'] == 14
        assert ProposalDefaultConfig.objects.filter(language='es').count() == 1

    def test_validates_sections_json_must_be_list(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {'language': 'es', 'sections_json': {'not': 'a list'}}
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_validates_section_required_keys(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {
            'language': 'es',
            'sections_json': [{'section_type': 'greeting'}],
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_validates_language_choices(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {'language': 'fr', 'sections_json': SAMPLE_SECTIONS}
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_validates_expiration_days_range(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'expiration_days': 0,
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400

    def test_requires_admin_auth(self, api_client):
        url = reverse('proposal-defaults')
        payload = {'language': 'es', 'sections_json': SAMPLE_SECTIONS}
        response = api_client.put(url, payload, format='json')
        assert response.status_code == 401

    def _put_full_payload(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'default_currency': 'USD',
            'default_total_investment': '1234.50',
            'hosting_percent': 45,
            'hosting_discount_semiannual': 25,
            'hosting_discount_quarterly': 12,
            'expiration_days': 30,
            'reminder_days': 5,
            'urgency_reminder_days': 10,
            'default_discount_percent': 15,
            'default_slug_pattern': 'Mi Propuesta Especial',
        }
        return admin_client.put(url, payload, format='json')

    def test_round_trip_persists_financial_fields(self, admin_client):
        put_resp = self._put_full_payload(admin_client)
        assert put_resp.status_code == 200, put_resp.content
        data = admin_client.get(reverse('proposal-defaults'), {'lang': 'es'}).json()
        assert data['default_currency'] == 'USD'
        assert float(data['default_total_investment']) == 1234.50
        assert data['hosting_percent'] == 45
        assert data['hosting_discount_semiannual'] == 25
        assert data['hosting_discount_quarterly'] == 12
        assert data['default_discount_percent'] == 15

    def test_round_trip_persists_deadline_and_slug_fields(self, admin_client):
        self._put_full_payload(admin_client)
        data = admin_client.get(reverse('proposal-defaults'), {'lang': 'es'}).json()
        assert data['expiration_days'] == 30
        assert data['reminder_days'] == 5
        assert data['urgency_reminder_days'] == 10
        assert data['default_slug_pattern'] == 'Mi Propuesta Especial'

    def test_rejects_hosting_percent_out_of_range(self, admin_client):
        url = reverse('proposal-defaults')
        payload = {
            'language': 'es',
            'sections_json': SAMPLE_SECTIONS,
            'hosting_percent': 150,
        }
        response = admin_client.put(url, payload, format='json')
        assert response.status_code == 400
        assert 'hosting_percent' in response.json()


# ---------------------------------------------------------------------------
# PUT /api/proposals/defaults/ — stale snapshot guard
# ---------------------------------------------------------------------------


class TestPutProposalDefaultsConcurrency:
    """The panel saves sections_json wholesale from the snapshot it loaded.

    A tab opened before a migration — or before another admin's save — would
    otherwise rewind the stored defaults, and every proposal created afterwards
    would inherit the rewound content.
    """

    def _config(self):
        return ProposalDefaultConfig.objects.create(
            language='es', sections_json=SAMPLE_SECTIONS, expiration_days=21,
        )

    def _put(self, admin_client, sections, base_updated_at=None, **extra):
        payload = {'language': 'es', 'sections_json': sections, **extra}
        if base_updated_at is not None:
            payload['base_updated_at'] = base_updated_at
        return admin_client.put(
            reverse('proposal-defaults'), payload, format='json',
        )

    def test_rejects_a_write_based_on_an_older_version(self, admin_client):
        config = self._config()
        stale_version = config.updated_at

        config.sections_json = [SAMPLE_SECTIONS[0]]
        config.save()

        response = self._put(
            admin_client, SAMPLE_SECTIONS, base_updated_at=stale_version.isoformat(),
        )

        assert response.status_code == 409
        assert response.json()['code'] == 'stale_defaults'

    def test_a_rejected_write_leaves_the_stored_defaults_alone(self, admin_client):
        config = self._config()
        stale_version = config.updated_at
        config.sections_json = [SAMPLE_SECTIONS[0]]
        config.save()

        self._put(
            admin_client, SAMPLE_SECTIONS, base_updated_at=stale_version.isoformat(),
        )

        config.refresh_from_db()
        assert config.sections_json == [SAMPLE_SECTIONS[0]]

    def test_accepts_a_write_based_on_the_current_version(self, admin_client):
        config = self._config()

        response = self._put(
            admin_client, [SAMPLE_SECTIONS[0]],
            base_updated_at=config.updated_at.isoformat(),
        )

        assert response.status_code == 200
        config.refresh_from_db()
        assert config.sections_json == [SAMPLE_SECTIONS[0]]

    def test_the_response_version_is_usable_as_the_next_base(self, admin_client):
        config = self._config()

        first = self._put(
            admin_client, [SAMPLE_SECTIONS[0]],
            base_updated_at=config.updated_at.isoformat(),
        )
        second = self._put(
            admin_client, SAMPLE_SECTIONS,
            base_updated_at=first.json()['updated_at'],
        )

        assert second.status_code == 200

    def test_rejects_an_unparsable_version(self, admin_client):
        self._config()

        response = self._put(
            admin_client, SAMPLE_SECTIONS, base_updated_at='ayer',
        )

        assert response.status_code == 400
        assert response.json()['code'] == 'invalid_base_updated_at'

    def test_a_write_without_a_version_still_goes_through(self, admin_client):
        # Programmatic callers (scripts, MCP) state no precondition.
        config = self._config()

        response = self._put(admin_client, [SAMPLE_SECTIONS[0]])

        assert response.status_code == 200
        config.refresh_from_db()
        assert config.sections_json == [SAMPLE_SECTIONS[0]]

    def test_a_general_fields_write_is_not_blocked_by_a_stale_version(
        self, admin_client,
    ):
        # The general form submits without sections_json, so it cannot rewind
        # them: the view keeps the stored ones.
        config = self._config()
        stale_version = config.updated_at
        config.sections_json = [SAMPLE_SECTIONS[0]]
        config.save()

        response = admin_client.put(
            reverse('proposal-defaults'),
            {
                'language': 'es',
                'expiration_days': 30,
                'base_updated_at': stale_version.isoformat(),
            },
            format='json',
        )

        assert response.status_code == 200
        config.refresh_from_db()
        assert config.expiration_days == 30
        assert config.sections_json == [SAMPLE_SECTIONS[0]]

    def test_a_first_save_needs_no_version(self, admin_client):
        # No row yet: there is nothing to rewind, so the guard must not fire.
        assert not ProposalDefaultConfig.objects.filter(language='en').exists()

        response = admin_client.put(
            reverse('proposal-defaults'),
            {
                'language': 'en',
                'sections_json': SAMPLE_SECTIONS,
                'base_updated_at': '2020-01-01T00:00:00Z',
            },
            format='json',
        )

        assert response.status_code == 200
        assert ProposalDefaultConfig.objects.filter(language='en').exists()


# ---------------------------------------------------------------------------
# POST /api/proposals/defaults/reset/
# ---------------------------------------------------------------------------


class TestResetProposalDefaults:
    def test_deletes_existing_config(self, admin_client):
        ProposalDefaultConfig.objects.create(
            language='es', sections_json=SAMPLE_SECTIONS,
        )
        url = reverse('reset-proposal-defaults')
        response = admin_client.post(url, {'language': 'es'}, format='json')
        assert response.status_code == 200
        assert response.json()['deleted'] is True
        assert not ProposalDefaultConfig.objects.filter(language='es').exists()

    def test_returns_false_when_no_config_to_delete(self, admin_client):
        url = reverse('reset-proposal-defaults')
        response = admin_client.post(url, {'language': 'es'}, format='json')
        assert response.status_code == 200
        assert response.json()['deleted'] is False

    def test_rejects_invalid_language(self, admin_client):
        url = reverse('reset-proposal-defaults')
        response = admin_client.post(url, {'language': 'fr'}, format='json')
        assert response.status_code == 400

    def test_requires_admin_auth(self, api_client):
        url = reverse('reset-proposal-defaults')
        response = api_client.post(url, {'language': 'es'}, format='json')
        assert response.status_code == 401

    def test_only_deletes_requested_language(self, admin_client):
        ProposalDefaultConfig.objects.create(language='es', sections_json=SAMPLE_SECTIONS)
        ProposalDefaultConfig.objects.create(language='en', sections_json=SAMPLE_SECTIONS)
        url = reverse('reset-proposal-defaults')
        admin_client.post(url, {'language': 'es'}, format='json')
        assert not ProposalDefaultConfig.objects.filter(language='es').exists()
        assert ProposalDefaultConfig.objects.filter(language='en').exists()
