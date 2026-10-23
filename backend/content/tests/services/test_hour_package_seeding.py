"""Tests for seeding proposal commercial conditions from the hour-package catalog."""
from copy import deepcopy

import pytest
from django.urls import reverse

from content.models import BusinessProposal, HourPackage
from content.services.hour_package_service import (
    seed_commercial_conditions_from_catalog,
)
from content.services.proposal_service import (
    build_proposal_from_json,
    create_section_for_proposal,
)

pytestmark = pytest.mark.django_db

BASE_CONTENT = {
    'index': '17',
    'title': 'Condiciones comerciales',
    'packagesTitle': 'Paquetes de horas',
    'packagesIntro': 'intro',
    'hourlyRate': 90000,
    'pricingModel': 'hours',
    'currency': 'COP',
    'packages': [
        {'name': 'Default', 'hours': 20, 'discountPercent': 0, 'note': 'n'},
    ],
    'effortBadge': 'badge',
    'scopeTitle': 'Alcance',
    'scopeParagraphs': ['p1'],
}


def _ext_packages():
    # Migration 0160 seeds EXT defaults; clear them so assertions on exact
    # package lists stay deterministic.
    HourPackage.objects.filter(nationality='EXT').delete()
    HourPackage.objects.create(
        nationality='EXT', pricing_model='hours', name_es='Ágil MX', name_en='Agile MX',
        note_es='nota es', note_en='note en',
        hours=20, hourly_rate=45, discount_percent=0, order=2,
    )
    HourPackage.objects.create(
        nationality='EXT', pricing_model='hours', name_es='Pro MX', name_en='Pro MX',
        hours=60, hourly_rate=40, discount_percent=10, order=1,
    )


def _ext_requirement_packages():
    """Seed the catalog used by newly created proposals after the size migration."""
    HourPackage.objects.filter(nationality='EXT').delete()
    HourPackage.objects.create(
        nationality='EXT', pricing_model='requirements', name_es='Ágil MX', name_en='Agile MX',
        xs_count=30, s_count=0, m_count=0, discount_percent=10, order=2,
    )
    HourPackage.objects.create(
        nationality='EXT', pricing_model='requirements', name_es='Pro MX', name_en='Pro MX',
        xs_count=30, s_count=20, m_count=0, discount_percent=15, order=1,
    )


class TestSeedService:
    def test_empty_catalog_returns_input_untouched(self):
        HourPackage.objects.all().delete()
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='COL', language='es',
        )
        assert result is BASE_CONTENT

    def test_seeds_spanish_names_and_notes(self):
        _ext_packages()
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='EXT', language='es',
        )
        assert [p['name'] for p in result['packages']] == ['Pro MX', 'Ágil MX']
        assert result['packages'][1]['note'] == 'nota es'

    def test_seeds_english_names_and_notes(self):
        _ext_packages()
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='EXT', language='en',
        )
        assert result['packages'][1]['name'] == 'Agile MX'
        assert result['packages'][1]['note'] == 'note en'

    def test_derives_currency_and_per_package_rate(self):
        _ext_packages()
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='EXT', language='es',
        )
        assert result['currency'] == 'USD'
        # Section-level rate keeps the first package's rate as baseline.
        assert result['hourlyRate'] == 40.0
        assert [p['hourlyRate'] for p in result['packages']] == [40.0, 45.0]
        assert [p['discountPercent'] for p in result['packages']] == [10, 0]

    def test_excludes_inactive_packages(self):
        _ext_packages()
        HourPackage.objects.create(
            nationality='EXT', name_es='Inactivo', name_en='Inactive',
            hours=100, hourly_rate=30, is_active=False, order=0,
        )
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='EXT', language='es',
        )
        assert all(p['name'] != 'Inactivo' for p in result['packages'])

    def test_does_not_touch_scope_texts(self):
        _ext_packages()
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='EXT', language='es',
        )
        assert result['scopeParagraphs'] == ['p1']
        assert result['effortBadge'] == 'badge'
        assert result['packagesTitle'] == 'Paquetes de horas'


class TestProposalCreationSeeding:
    def test_panel_create_seeds_from_catalog(self, admin_client):
        _ext_requirement_packages()
        payload = {
            'title': 'Propuesta MX', 'client_name': 'Cliente',
            'client_email': 'c@test.com', 'language': 'es',
            'total_investment': '5000.00', 'currency': 'USD',
            'nationality': 'EXT',
        }
        response = admin_client.post(
            reverse('create-proposal'), payload, format='json'
        )
        assert response.status_code == 201
        assert response.data['nationality'] == 'EXT'
        section = next(
            s for s in response.data['sections']
            if s['section_type'] == 'commercial_conditions'
        )
        content = section['content_json']
        assert content['currency'] == 'USD'
        assert [p['name'] for p in content['packages']] == ['Pro MX', 'Ágil MX']
        assert [(p['xsCount'], p['sCount'], p['mCount']) for p in content['packages']] == [
            (30, 20, 0), (30, 0, 0),
        ]

    def test_panel_create_with_empty_catalog_has_no_packages(self, admin_client):
        HourPackage.objects.all().delete()
        payload = {
            'title': 'Propuesta COL', 'client_name': 'Cliente',
            'client_email': 'c@test.com', 'language': 'es',
            'total_investment': '5000.00', 'currency': 'COP',
        }
        response = admin_client.post(
            reverse('create-proposal'), payload, format='json'
        )
        assert response.status_code == 201
        section = next(
            s for s in response.data['sections']
            if s['section_type'] == 'commercial_conditions'
        )
        content = section['content_json']
        assert content['currency'] == 'COP'
        assert content['pricingModel'] == 'requirements'
        assert content['packages'] == []

    def test_from_json_seeds_when_section_not_in_payload(self):
        _ext_requirement_packages()
        proposal, _ = build_proposal_from_json({
            'title': 'JSON MX', 'client_name': 'Cliente',
            'nationality': 'EXT', 'language': 'es',
            'sections': {},
        })
        section = proposal.sections.get(section_type='commercial_conditions')
        assert section.content_json['currency'] == 'USD'
        assert section.content_json['packages'][0]['name'] == 'Pro MX'
        assert section.content_json['packages'][0]['sCount'] == 20

    def test_from_json_respects_explicit_section_payload(self):
        _ext_packages()
        explicit = {
            'title': 'Custom', 'hourlyRate': 123, 'currency': 'COP',
            'pricingModel': 'hours',
            'packages': [{'name': 'Custom Pack', 'hours': 5,
                          'discountPercent': 0, 'note': ''}],
        }
        proposal, _ = build_proposal_from_json({
            'title': 'JSON explicit', 'client_name': 'Cliente',
            'nationality': 'EXT', 'language': 'es',
            'sections': {'commercialConditions': explicit},
        })
        section = proposal.sections.get(section_type='commercial_conditions')
        assert section.content_json['packages'][0]['name'] == 'Custom Pack'
        assert section.content_json['hourlyRate'] == 123

    def test_create_section_for_proposal_seeds(self):
        _ext_requirement_packages()
        proposal = BusinessProposal.objects.create(
            title='Sin sección', client_name='Cliente', nationality='EXT',
        )
        section = create_section_for_proposal(proposal, 'commercial_conditions')
        assert section.content_json['currency'] == 'USD'
        assert section.content_json['packages'][0]['xsCount'] == 30


class TestBaseRatePropagationReachesNewProposals:
    def test_new_proposal_seeds_with_propagated_rate(self):
        from content.services.hour_package_service import (
            apply_base_rates_to_catalog,
        )
        _ext_packages()
        apply_base_rates_to_catalog({'EXT': 55})
        result = seed_commercial_conditions_from_catalog(
            BASE_CONTENT, nationality='EXT', language='es',
        )
        assert result['hourlyRate'] == 55.0
        assert [p['hourlyRate'] for p in result['packages']] == [55.0, 55.0]

    def test_existing_proposal_snapshot_survives_propagation(self):
        # The stored snapshot is intentionally untouched by propagation;
        # the PDF nevertheless shows current rates via the live re-seed at
        # generation time (see TestPdfLiveReseed).
        from content.services.hour_package_service import (
            apply_base_rates_to_catalog,
        )
        _ext_packages()
        proposal, _ = build_proposal_from_json({
            'title': 'Snapshot MX', 'client_name': 'Cliente',
            'nationality': 'EXT', 'language': 'es',
            'sections': {},
        })
        section = proposal.sections.get(section_type='commercial_conditions')
        snapshot = section.content_json
        assert snapshot['hourlyRate'] == 40.0

        apply_base_rates_to_catalog({'EXT': 55})
        section.refresh_from_db()
        assert section.content_json == snapshot
        assert section.content_json['hourlyRate'] == 40.0


class TestPdfLiveReseed:
    """The PDF re-seeds hour packages from the catalog on every generation."""

    def _generate_and_capture(self, proposal, monkeypatch):
        from content.services import proposal_pdf_service as pdf_mod

        captured = {}

        def spy(c, data, prop, ps=None, y=None):
            captured.update(data)
            return y

        monkeypatch.setitem(
            pdf_mod.SECTION_RENDERERS, 'commercial_conditions', spy)
        assert pdf_mod.ProposalPdfService.generate(proposal) is not None
        return captured

    def _proposal_with_snapshot(self, **overrides):
        payload = {
            'title': 'Live MX', 'client_name': 'Cliente',
            'nationality': 'EXT', 'language': 'es', 'sections': {},
        }
        payload.update(overrides)
        proposal, _ = build_proposal_from_json(payload)
        return proposal

    def test_pdf_uses_current_catalog_rate_not_snapshot(self, monkeypatch):
        from content.services.hour_package_service import (
            apply_base_rates_to_catalog,
        )
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        apply_base_rates_to_catalog({'EXT': 55})  # snapshot keeps 40

        data = self._generate_and_capture(proposal, monkeypatch)
        assert data['hourlyRate'] == 55.0
        assert [p['hourlyRate'] for p in data['packages']] == [55.0, 55.0]

    def test_pdf_overrides_manual_package_edits_keeps_titles(self, monkeypatch):
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        section = proposal.sections.get(section_type='commercial_conditions')
        content = dict(section.content_json)
        content['packagesTitle'] = 'Título editado'
        content['packages'] = [
            {'name': 'Manual', 'hours': 5, 'discountPercent': 0,
             'note': '', 'hourlyRate': 999},
        ]
        section.content_json = content
        section.save(update_fields=['content_json'])

        data = self._generate_and_capture(proposal, monkeypatch)
        assert [p['name'] for p in data['packages']] == ['Pro MX', 'Ágil MX']
        assert [p['hourlyRate'] for p in data['packages']] == [40.0, 45.0]
        assert data['packagesTitle'] == 'Título editado'

    def _set_content(self, proposal, **fields):
        section = proposal.sections.get(section_type='commercial_conditions')
        content = dict(section.content_json)
        content.update(fields)
        section.content_json = content
        section.save(update_fields=['content_json'])
        return section

    def test_pdf_manual_mode_keeps_the_proposals_own_packages(self, monkeypatch):
        """Manual proposals own their list, so the catalog must not touch it.

        The panel lets manual proposals rename packages and add or remove rows.
        If the catalog kept re-seeding, a removed row would come back and a
        rename would be undone on the next generation.
        """
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        self._set_content(proposal, hourPackagesMode='manual', packages=[
            {'name': 'A medida', 'hours': 5, 'discountPercent': 0,
             'note': 'sólo de esta propuesta', 'hourlyRate': 120},
        ])

        data = self._generate_and_capture(proposal, monkeypatch)
        assert [p['name'] for p in data['packages']] == ['A medida']
        assert data['packages'][0]['hourlyRate'] == 120

    def test_pdf_manual_mode_ignores_later_catalog_edits(self, monkeypatch):
        from content.services.hour_package_service import (
            apply_base_rates_to_catalog,
        )
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        self._set_content(proposal, hourPackagesMode='manual', packages=[
            {'name': 'Propio', 'hours': 10, 'discountPercent': 0,
             'note': '', 'hourlyRate': 99},
        ])
        apply_base_rates_to_catalog({'EXT': 55})

        data = self._generate_and_capture(proposal, monkeypatch)
        assert [p['name'] for p in data['packages']] == ['Propio']
        assert data['packages'][0]['hourlyRate'] == 99

    def test_pdf_manual_legacy_base_rate_still_prices_the_snapshot(
            self, monkeypatch):
        """Proposals saved before manual owned its packages must not change price.

        They carry `manualHourlyRate` with packages that have no rate of their
        own — the exact shape of the one manual proposal in production.
        """
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        self._set_content(proposal, hourPackagesMode='manual', manualHourlyRate=77,
                          packages=[
                              {'name': 'Viejo', 'hours': 20,
                               'discountPercent': 10, 'note': ''},
                          ])

        data = self._generate_and_capture(proposal, monkeypatch)
        assert [p['name'] for p in data['packages']] == ['Viejo']
        assert data['packages'][0]['hourlyRate'] == 77

    def test_pdf_manual_legacy_per_package_override_still_applies(self, monkeypatch):
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        self._set_content(
            proposal,
            hourPackagesMode='manual',
            manualHourlyRate=77,
            manualPackageRates=[{'packageId': 7, 'hourlyRate': 120}],
            packages=[
                {'id': 7, 'name': 'Con override', 'hours': 20,
                 'discountPercent': 0, 'note': ''},
                {'id': 8, 'name': 'Sin override', 'hours': 40,
                 'discountPercent': 0, 'note': ''},
            ],
        )

        data = self._generate_and_capture(proposal, monkeypatch)
        by_name = {p['name']: p['hourlyRate'] for p in data['packages']}
        assert by_name == {'Con override': 120, 'Sin override': 77}

    def test_pdf_manual_without_any_rate_keeps_the_stored_rates(self, monkeypatch):
        """An empty manual rate must never render $0 packages."""
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        self._set_content(proposal, hourPackagesMode='manual', manualHourlyRate=0,
                          packages=[
                              {'name': 'Propio', 'hours': 20,
                               'discountPercent': 0, 'note': '', 'hourlyRate': 42},
                          ])

        data = self._generate_and_capture(proposal, monkeypatch)
        assert data['packages'][0]['hourlyRate'] == 42

    def test_pdf_manual_mode_does_not_mutate_stored_section(self, monkeypatch):
        """Generating a PDF must never write back into content_json."""
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        section = self._set_content(
            proposal, hourPackagesMode='manual', manualHourlyRate=77)
        before = deepcopy(section.content_json)

        self._generate_and_capture(proposal, monkeypatch)
        section.refresh_from_db()
        assert section.content_json == before

    @pytest.mark.parametrize('mode', ['auto', 'unexpected'])
    def test_pdf_explicit_auto_mode_still_reseeds(self, monkeypatch, mode):
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        section = proposal.sections.get(section_type='commercial_conditions')
        content = dict(section.content_json)
        content['hourPackagesMode'] = mode
        content['packagesTitle'] = 'Título editado'
        content['packages'] = [
            {'name': 'Manual', 'hours': 5, 'discountPercent': 0,
             'note': '', 'hourlyRate': 999},
        ]
        section.content_json = content
        section.save(update_fields=['content_json'])

        data = self._generate_and_capture(proposal, monkeypatch)
        assert [p['name'] for p in data['packages']] == ['Pro MX', 'Ágil MX']
        assert data['packagesTitle'] == 'Título editado'

    def test_pdf_falls_back_to_snapshot_when_catalog_empty(self, monkeypatch):
        _ext_packages()
        proposal = self._proposal_with_snapshot()
        HourPackage.objects.all().delete()

        data = self._generate_and_capture(proposal, monkeypatch)
        assert data['hourlyRate'] == 40.0
        assert [p['name'] for p in data['packages']] == ['Pro MX', 'Ágil MX']

    def test_pdf_localizes_reseeded_packages_in_english(self, monkeypatch):
        _ext_packages()
        proposal = self._proposal_with_snapshot(
            title='Live EN', language='en')

        data = self._generate_and_capture(proposal, monkeypatch)
        assert [p['name'] for p in data['packages']] == ['Pro MX', 'Agile MX']
        assert data['packages'][1]['note'] == 'note en'
