"""The scope-of-work clause is owned by the defaults, not by the payload.

JSON/MCP payloads are routinely composed from stale snapshots — a downloaded
template, a previous proposal — and ``build_proposal_from_json`` used to copy
``commercialConditions`` wholesale. A brand-new proposal could therefore be born
with a superseded legal clause even with the stored defaults already repaired.

These tests pin that the clause is forced from the resolved defaults on both
JSON paths, that the rest of the section still belongs to the seller, and that
migration 0168 repairs drafts without touching delivered proposals.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from content.models import BusinessProposal, ProposalSection
from content.services.proposal_service import (
    DEFAULT_SECTIONS,
    DEFAULT_SECTIONS_EN,
    apply_proposal_json_update,
    build_proposal_from_json,
)

pytestmark = pytest.mark.django_db

STALE_CLAUSE = [
    'Cualquier solicitud que surja durante el proyecto no aplica.',
]

STALE_SECTION = {
    'title': 'Condiciones comerciales',
    'pricingModel': 'hours',
    'hourlyRate': 123456,
    'packages': [
        {'name': 'Paquete propio', 'hours': 7, 'discountPercent': 5, 'note': 'n'},
    ],
    'effortBadge': 'insignia propia',
    'scopeTitle': 'Alcance viejo',
    'scopeParagraphs': STALE_CLAUSE,
}


def _default_scope(lang='es'):
    defaults = DEFAULT_SECTIONS_EN if lang == 'en' else DEFAULT_SECTIONS
    section = next(
        s for s in defaults if s['section_type'] == 'commercial_conditions'
    )
    return section['content_json']


def _stale_payload_section():
    # Fresh copy per test: the enforcement mutates the dict it is handed.
    return {**STALE_SECTION, 'scopeParagraphs': list(STALE_CLAUSE)}


class TestCreationFromJson:
    def test_stale_clause_in_the_payload_is_overridden(self):
        proposal, _ = build_proposal_from_json({
            'title': 'Desde snapshot viejo', 'client_name': 'Cliente',
            'language': 'es',
            'sections': {'commercialConditions': _stale_payload_section()},
        })

        content = proposal.sections.get(
            section_type='commercial_conditions').content_json
        assert content['scopeParagraphs'] == _default_scope('es')['scopeParagraphs']
        assert content['scopeTitle'] == _default_scope('es')['scopeTitle']

    def test_the_enforced_clause_covers_requests_raised_before_the_project(self):
        proposal, _ = build_proposal_from_json({
            'title': 'Antes o durante', 'client_name': 'Cliente',
            'language': 'es',
            'sections': {'commercialConditions': _stale_payload_section()},
        })

        paragraphs = proposal.sections.get(
            section_type='commercial_conditions').content_json['scopeParagraphs']
        assert any('**antes o durante**' in p for p in paragraphs)
        assert any('correo electrónico' in p for p in paragraphs)

    def test_english_proposals_get_the_english_clause(self):
        proposal, _ = build_proposal_from_json({
            'title': 'From stale snapshot', 'client_name': 'Client',
            'language': 'en',
            'sections': {'commercialConditions': _stale_payload_section()},
        })

        paragraphs = proposal.sections.get(
            section_type='commercial_conditions').content_json['scopeParagraphs']
        assert any('**before or during**' in p for p in paragraphs)

    def test_the_rest_of_the_section_still_belongs_to_the_seller(self):
        proposal, _ = build_proposal_from_json({
            'title': 'Paquetes propios', 'client_name': 'Cliente',
            'language': 'es',
            'sections': {'commercialConditions': _stale_payload_section()},
        })

        content = proposal.sections.get(
            section_type='commercial_conditions').content_json
        assert content['hourlyRate'] == 123456
        assert content['effortBadge'] == 'insignia propia'
        assert [p['name'] for p in content['packages']] == ['Paquete propio']


class TestUpdateFromJson:
    def _proposal_with_stale_clause(self, status='draft'):
        proposal = BusinessProposal.objects.create(
            title='Propuesta', client_name='Cliente',
            client_email='c@example.com', language='es',
            total_investment=Decimal('9000000'), currency='COP',
            status=status,
            expires_at=timezone.now() + timezone.timedelta(days=14),
        )
        ProposalSection.objects.create(
            proposal=proposal, section_type='commercial_conditions',
            title='Condiciones', order=17, is_enabled=True,
            content_json={
                'title': 'Condiciones',
                'scopeTitle': 'Alcance viejo',
                'scopeParagraphs': list(STALE_CLAUSE),
            },
        )
        return proposal

    def test_a_payload_rewriting_the_section_cannot_downgrade_the_clause(self):
        proposal = self._proposal_with_stale_clause()

        apply_proposal_json_update(proposal, {
            'sections': {'commercialConditions': _stale_payload_section()},
        })

        content = proposal.sections.get(
            section_type='commercial_conditions').content_json
        assert content['scopeParagraphs'] == _default_scope('es')['scopeParagraphs']
        assert content['hourlyRate'] == 123456

    def test_a_payload_rewriting_the_section_keeps_the_manual_hour_rate(self):
        """The manual rate is panel-only, so no JSON payload ever carries it.

        Without the carry-over, one save from the JSON tab would silently
        return the proposal to catalog pricing.
        """
        proposal = self._proposal_with_stale_clause()
        section = proposal.sections.get(section_type='commercial_conditions')
        section.content_json = {
            **section.content_json,
            'hourPackagesMode': 'manual',
            'manualHourlyRate': 45000,
            'manualCurrency': 'COP',
            'manualPackageRates': [{'packageId': 7, 'hourlyRate': 52000}],
        }
        section.save(update_fields=['content_json'])

        apply_proposal_json_update(proposal, {
            'sections': {'commercialConditions': _stale_payload_section()},
        })

        content = proposal.sections.get(
            section_type='commercial_conditions').content_json
        assert content['hourPackagesMode'] == 'manual'
        assert content['manualHourlyRate'] == 45000
        assert content['manualCurrency'] == 'COP'
        assert content['manualPackageRates'] == [
            {'packageId': 7, 'hourlyRate': 52000},
        ]

    def test_a_payload_stating_the_mode_still_wins(self):
        proposal = self._proposal_with_stale_clause()
        section = proposal.sections.get(section_type='commercial_conditions')
        section.content_json = {
            **section.content_json, 'hourPackagesMode': 'manual',
        }
        section.save(update_fields=['content_json'])

        payload = {**_stale_payload_section(), 'hourPackagesMode': 'auto'}
        apply_proposal_json_update(proposal, {
            'sections': {'commercialConditions': payload},
        })

        content = proposal.sections.get(
            section_type='commercial_conditions').content_json
        assert content['hourPackagesMode'] == 'auto'

    def test_a_payload_omitting_the_section_leaves_it_untouched(self):
        proposal = self._proposal_with_stale_clause(status='sent')

        apply_proposal_json_update(proposal, {'sections': {}})

        content = proposal.sections.get(
            section_type='commercial_conditions').content_json
        assert content['scopeParagraphs'] == STALE_CLAUSE


class TestMigration0168:
    def _make_proposal(self, status):
        proposal = BusinessProposal.objects.create(
            title=f'Propuesta {status}', client_name='Cliente',
            client_email=f'{status}@example.com', language='es',
            total_investment=Decimal('15000000'), currency='COP',
            status=status,
            expires_at=timezone.now() + timezone.timedelta(days=14),
        )
        ProposalSection.objects.create(
            proposal=proposal, section_type='commercial_conditions',
            title='Condiciones', order=17, is_enabled=True,
            content_json={
                'title': 'Condiciones',
                'scopeTitle': 'Alcance del trabajo aprobado',
                'scopeParagraphs': list(STALE_CLAUSE),
                'hourlyRate': 30000,
            },
        )
        return proposal

    def _run_migration(self):
        import importlib

        from django.apps import apps as global_apps

        migration = importlib.import_module(
            'content.migrations.0168_repair_draft_scope_clause')
        migration.repair_draft_scope_clause(global_apps, None)

    def _clause(self, proposal):
        return proposal.sections.get(
            section_type='commercial_conditions').content_json

    def test_draft_scope_clause_is_repaired(self):
        proposal = self._make_proposal('draft')
        self._run_migration()

        content = self._clause(proposal)
        assert content['scopeParagraphs'] == _default_scope('es')['scopeParagraphs']
        # Commercial fields outside the legal clause are left alone.
        assert content['hourlyRate'] == 30000

    @pytest.mark.parametrize('status', ['sent', 'viewed', 'accepted', 'expired'])
    def test_delivered_proposals_keep_the_wording_they_were_sent_with(self, status):
        proposal = self._make_proposal(status)
        self._run_migration()

        assert self._clause(proposal)['scopeParagraphs'] == STALE_CLAUSE

    def test_migration_is_idempotent(self):
        proposal = self._make_proposal('draft')
        self._run_migration()
        first = self._clause(proposal)['scopeParagraphs']
        self._run_migration()

        assert self._clause(proposal)['scopeParagraphs'] == first
