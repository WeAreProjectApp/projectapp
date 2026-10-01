"""Tests for the value_added_modules section and manual_module group."""
import pytest

from content.services.proposal_service import ProposalService

pytestmark = pytest.mark.django_db


class TestManualModule:
    def test_manual_module_present_in_es_functional_requirements(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        manual = next(g for g in fr['content_json']['groups'] if g['id'] == 'manual_module')
        assert 'price_percent' not in manual
        assert manual['selected'] is True
        assert manual.get('is_calculator_module', False) is False
        assert len(manual['items']) >= 4

    def test_manual_module_present_in_en_functional_requirements(self):
        sections = ProposalService.get_default_sections('en')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        manual = next(g for g in fr['content_json']['groups'] if g['id'] == 'manual_module')
        assert 'price_percent' not in manual
        assert manual['selected'] is True
        assert 'Interactive User Manual' in manual['title']


class TestValueAddedModulesSection:
    @pytest.mark.parametrize('language', ['es', 'en'])
    def test_section_present(self, language):
        sections = ProposalService.get_default_sections(language)
        section = next(s for s in sections if s['section_type'] == 'value_added_modules')
        assert section['title']
        cj = section['content_json']
        assert cj['module_ids'] == [
            'admin_module', 'manual_module', 'kpi_dashboard_module', 'analytics_dashboard',
            'ai_automation_module',
        ]
        assert set(cj['justifications'].keys()) == set(cj['module_ids'])
        for value in cj['justifications'].values():
            assert isinstance(value, str)
            assert len(value) > 0
        assert cj['footer_note']

    def test_section_order_is_after_functional_requirements(self):
        sections = ProposalService.get_default_sections('es')
        vam = next(s for s in sections if s['section_type'] == 'value_added_modules')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        assert vam['order'] > fr['order']

    def test_orders_are_contiguous_after_shift(self):
        """functional_requirements sits at order 10 and value_added_modules at 11.

        The value-added summary intentionally appears AFTER the full functional
        requirements block so the client first sees everything included, then
        the no-cost reinforcement.
        """
        sections = ProposalService.get_default_sections('es')
        by_type = {s['section_type']: s['order'] for s in sections}
        assert by_type['functional_requirements'] == 10
        assert by_type['value_added_modules'] == 11
        assert by_type['development_stages'] == 12
        assert by_type['proposal_summary'] == 13
        assert by_type['technical_document'] == 16

    @pytest.mark.parametrize('language', ['es', 'en'])
    def test_content_json_index_matches_order(self, language):
        sections = ProposalService.get_default_sections(language)
        for section_type in ('functional_requirements', 'value_added_modules'):
            section = next(s for s in sections if s['section_type'] == section_type)
            assert section['content_json']['index'] == str(section['order']), (
                f"{section_type} ({language}): content_json.index must match order"
            )
