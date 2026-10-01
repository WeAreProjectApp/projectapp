"""Tests for ProposalService.

Covers: get_default_sections() for ES and EN languages,
send_proposal() happy path and error cases.
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_tz
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from content.api_errors import ProposalActionError
from content.models import BusinessProposal, ProposalChangeLog, ProposalDefaultConfig
from content.services.proposal_service import (
    ProposalService,
    normalize_hosting_plan,
)
from content.tests.constants import EXPECTED_DEFAULT_SECTION_COUNT

pytestmark = pytest.mark.django_db

# Module-level constants for reusable payloads
CALCULATOR_MODULE_IDS = (
    'pwa_module', 'corporate_branding_module', 'ai_module', 'reports_alerts_module',
    'behavior_tracking_module',
    'email_marketing_module',
    'qr_generator_module', 'content_generator_module',
    'i18n_module',
    'integration_international_payments', 'integration_regional_payments',
    'integration_electronic_invoicing', 'integration_conversion_tracking',
    'biometric_verification_module',
    'dark_mode_module', 'live_chat_module',
)

EXPECTED_GROUP_ORDER = [
    'views', 'components', 'features', 'cross_cutting_features',
    'admin_module', 'analytics_dashboard', 'kpi_dashboard_module', 'manual_module',
    'ai_automation_module',
]

EXPECTED_ADDITIONAL_MODULE_ORDER = [
    'integration_electronic_invoicing',
    'integration_regional_payments',
    'integration_international_payments',
    'pwa_module', 'corporate_branding_module', 'ai_module',
    'integration_conversion_tracking',
    'biometric_verification_module',
    'behavior_tracking_module',
    'reports_alerts_module', 'email_marketing_module',
    'qr_generator_module', 'content_generator_module',
    'i18n_module',
    'live_chat_module', 'dark_mode_module',
    'gift_cards_module',
]


class TestGetDefaultSections:
    def test_returns_expected_default_section_count_for_es(self):
        """Verify ES defaults length matches EXPECTED_DEFAULT_SECTION_COUNT."""
        sections = ProposalService.get_default_sections('es')
        assert len(sections) == EXPECTED_DEFAULT_SECTION_COUNT

    def test_returns_expected_default_section_count_for_en(self):
        """Verify EN defaults length matches EXPECTED_DEFAULT_SECTION_COUNT."""
        sections = ProposalService.get_default_sections('en')
        assert len(sections) == EXPECTED_DEFAULT_SECTION_COUNT

    def test_all_sections_have_required_keys(self):
        sections = ProposalService.get_default_sections('es')
        required_keys = {'section_type', 'title', 'order', 'is_wide_panel', 'content_json'}
        for section in sections:
            assert required_keys.issubset(section.keys()), (
                f"Section {section.get('section_type')} missing keys: "
                f"{required_keys - section.keys()}"
            )

    def test_sections_have_unique_order_values(self):
        """Verify each section has an order field and no duplicate orders (except co-located pairs)."""
        sections = ProposalService.get_default_sections('es')
        orders = [s['order'] for s in sections]
        assert len(orders) == EXPECTED_DEFAULT_SECTION_COUNT
        assert all(isinstance(o, int) for o in orders)

    def test_section_types_cover_all_default_types(self):
        """Verify all default section types are present (count = EXPECTED_DEFAULT_SECTION_COUNT)."""
        expected_types = {
            'greeting', 'executive_summary', 'context_diagnostic',
            'conversion_strategy', 'roi_projection',
            'design_ux', 'creative_support',
            'development_stages', 'process_methodology',
            'value_added_modules',
            'functional_requirements',
            'timeline', 'investment', 'proposal_summary',
            'final_note', 'next_steps', 'technical_document',
            'commercial_conditions',
        }
        sections = ProposalService.get_default_sections('es')
        actual_types = {s['section_type'] for s in sections}
        assert actual_types == expected_types

    def test_en_sections_have_english_titles(self):
        sections = ProposalService.get_default_sections('en')
        greeting = next(s for s in sections if s['section_type'] == 'greeting')
        assert 'Greeting' in greeting['title']

    def test_es_sections_have_spanish_content(self):
        """Verify ES executive_summary section has Spanish content in its content_json."""
        sections = ProposalService.get_default_sections('es')
        es_section = next(s for s in sections if s['section_type'] == 'executive_summary')
        assert 'Resumen' in es_section['content_json']['title']

    def test_functional_requirements_has_default_groups(self):
        """Verify ES functional_requirements has 9 groups and 17 additionalModules."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        groups = fr['content_json']['groups']
        additional = fr['content_json']['additionalModules']
        assert len(groups) == 9
        assert len(additional) == 17
        group_ids = {g['id'] for g in groups}
        assert group_ids == {
            'views', 'components', 'features', 'cross_cutting_features',
            'admin_module', 'analytics_dashboard', 'kpi_dashboard_module', 'manual_module',
            'ai_automation_module',
        }
        additional_ids = {m['id'] for m in additional}
        assert additional_ids == {
            'integration_international_payments', 'integration_regional_payments',
            'integration_electronic_invoicing', 'integration_conversion_tracking',
            'biometric_verification_module', 'behavior_tracking_module',
            'pwa_module', 'corporate_branding_module', 'ai_module', 'reports_alerts_module',
            'email_marketing_module',
            'qr_generator_module', 'content_generator_module',
            'i18n_module', 'gift_cards_module',
            'dark_mode_module', 'live_chat_module',
        }

    def test_views_group_has_13_default_items(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        views = next(g for g in fr['content_json']['groups'] if g['id'] == 'views')
        assert len(views['items']) == 13

    def test_components_group_has_5_default_items(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        components = next(g for g in fr['content_json']['groups'] if g['id'] == 'components')
        assert len(components['items']) == 5

    def test_features_group_has_6_default_items(self):
        """Google registration and sign-in are two atomic items, not one composite."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        features = next(g for g in fr['content_json']['groups'] if g['id'] == 'features')
        assert len(features['items']) == 6
        assert all(item['name'] != 'Diseño Responsive' for item in features['items'])
        names = [i['name'] for i in features['items']]
        assert 'Registro con Google' in names
        assert 'Inicio de Sesión con Google' in names
        assert 'Registro e Inicio de Sesión con Google' not in names

    def test_cross_cutting_features_has_contextual_default_catalog(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        group = next(
            g for g in fr['content_json']['groups']
            if g['id'] == 'cross_cutting_features'
        )

        assert group['title'] == 'Funcionalidades Transversales'
        assert 'punto de partida' in group['description']
        assert len(group['items']) == 7
        assert group['items'][0]['name'] == 'Diseño Responsive'

    def test_cross_cutting_features_assigns_stable_item_ids(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        group = next(
            g for g in fr['content_json']['groups']
            if g['id'] == 'cross_cutting_features'
        )

        assert all(item['id'].startswith('item-cross_cutting_features-') for item in group['items'])

    def test_features_group_items_parity_es_en(self):
        """ES and EN features groups carry the same number of items, split included."""
        by_lang = {}
        for lang in ('es', 'en'):
            sections = ProposalService.get_default_sections(lang)
            fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
            features = next(g for g in fr['content_json']['groups'] if g['id'] == 'features')
            by_lang[lang] = [i['name'] for i in features['items']]
        assert len(by_lang['es']) == len(by_lang['en']) == 6
        assert 'Google Registration' in by_lang['en']
        assert 'Google Sign-In' in by_lang['en']

    def test_integration_international_payments_group(self):
        """Verify integration_international_payments: calculator module, 20%, not invite."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        intl = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'integration_international_payments')
        assert len(intl['items']) == 2
        assert intl['is_calculator_module'] is True
        assert intl['default_selected'] is False
        assert 'price_percent' not in intl
        assert intl['is_invite'] is False

    def test_integration_regional_payments_group(self):
        """Verify integration_regional_payments: calculator module, 20%, not invite."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        reg = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'integration_regional_payments')
        assert len(reg['items']) == 3
        assert reg['is_calculator_module'] is True
        assert reg['default_selected'] is False
        assert 'price_percent' not in reg
        assert reg['is_invite'] is False

    def test_integration_electronic_invoicing_group(self):
        """Verify integration_electronic_invoicing: 60%, not invite."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        inv = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'integration_electronic_invoicing')
        assert len(inv['items']) == 5
        assert inv['is_calculator_module'] is True
        assert inv['default_selected'] is False
        assert 'price_percent' not in inv
        assert inv['is_invite'] is False

    def test_integration_conversion_tracking_group(self):
        """Verify integration_conversion_tracking: 0%, is_invite, has invite_note."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        ct = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'integration_conversion_tracking')
        assert len(ct['items']) == 6
        assert ct['is_calculator_module'] is True
        assert ct['default_selected'] is False
        assert 'price_percent' not in ct
        assert ct['is_invite'] is True
        assert ct['invite_note']

    def test_biometric_verification_module_is_invite_with_zero_percent(self):
        """Verify biometric_verification_module: 6 items, 0%, is_invite, has invite_note (provider-billed integration)."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        bio = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'biometric_verification_module')
        assert bio['icon'] == '🪪'
        assert len(bio['items']) == 6
        assert bio['is_visible'] is True
        assert bio['is_calculator_module'] is True

    def test_biometric_verification_module_flags_and_invite(self):
        """Verify biometric_verification_module selection defaults and invite status."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        bio = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'biometric_verification_module')
        assert bio['default_selected'] is False
        assert bio['selected'] is False
        assert 'price_percent' not in bio
        assert bio['is_invite'] is True
        assert bio['invite_note']

    def test_qr_generator_module_has_25_percent(self):
        """Verify qr_generator_module: calculator module, 25%, not invite, 6 items."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        qr = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'qr_generator_module')
        assert qr['icon'] == '🔳'
        assert len(qr['items']) == 6
        assert qr['is_visible'] is True
        assert qr['is_calculator_module'] is True

    def test_qr_generator_module_price_and_no_invite(self):
        """Verify qr_generator_module selection defaults and non-invite status."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        qr = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'qr_generator_module')
        assert qr['default_selected'] is False
        assert qr['selected'] is False
        assert 'price_percent' not in qr
        assert qr.get('is_invite', False) is False
        assert 'invite_note' not in qr

    def test_content_generator_module_has_30_percent_and_calendar(self):
        """Verify content_generator_module: calculator module, 30%, not invite, mentions editorial calendar and scheduling."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        cg = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'content_generator_module')
        assert cg['icon'] == '✍️'
        assert len(cg['items']) == 7
        assert cg['is_visible'] is True
        assert cg['is_calculator_module'] is True
        assert cg['default_selected'] is False
        assert cg['selected'] is False
        assert 'price_percent' not in cg

    def test_content_generator_module_no_invite_and_calendar_copy(self):
        """Verify content_generator_module has no invite flag and contains editorial calendar content."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        cg = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'content_generator_module')
        assert cg.get('is_invite', False) is False
        assert 'invite_note' not in cg
        assert 'Calendario' in cg['title']
        haystack = ' '.join(i['name'] + ' ' + i['description'] for i in cg['items']).lower()
        assert 'calendario' in haystack
        assert 'programaci' in haystack  # programación / programar

    def test_greeting_title_has_emoji(self):
        sections = ProposalService.get_default_sections('es')
        greeting = next(s for s in sections if s['section_type'] == 'greeting')
        assert greeting['title'].startswith('\U0001f44b')

    def test_pwa_module_has_6_items_and_is_calculator_module(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        pwa = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'pwa_module')
        assert len(pwa['items']) == 6
        assert pwa['is_calculator_module'] is True
        assert pwa['default_selected'] is False
        assert 'price_percent' not in pwa

    def test_corporate_branding_module_has_5_items_and_35_percent(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        cb = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'corporate_branding_module')
        assert len(cb['items']) == 5
        assert cb['is_calculator_module'] is True
        # Pre-selected by default for every new proposal.
        assert cb['default_selected'] is True
        assert cb['selected'] is True
        assert 'price_percent' not in cb
        assert cb.get('is_invite', False) is False
        assert cb['is_visible'] is True

    def test_ai_module_has_11_items_and_is_invite(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        ai = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'ai_module')
        assert len(ai['items']) == 11
        assert ai['is_calculator_module'] is True
        assert ai['is_invite'] is True
        assert 'price_percent' not in ai

    def test_reports_alerts_module_is_priced_calculator_module(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        reports = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'reports_alerts_module')
        assert len(reports['items']) == 5
        assert reports['is_calculator_module'] is True
        assert reports['default_selected'] is False
        assert 'price_percent' not in reports

    def test_reports_alerts_module_offers_whatsapp_not_telegram(self):
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        reports = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'reports_alerts_module')
        assert 'WhatsApp' in reports['title']
        # Telegram is no longer offered as a notification channel.
        assert 'Telegram' not in reports['title']
        item_names = [i['name'] for i in reports['items']]
        assert 'Integración con WhatsApp' in item_names
        assert all('Telegram' not in n for n in item_names)

    def test_behavior_tracking_module_is_priced_calculator_module(self):
        """Verify behavior_tracking_module: calculator module at 30%, not invite."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        bt = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'behavior_tracking_module')
        assert bt['is_calculator_module'] is True
        assert bt['default_selected'] is False
        assert bt['selected'] is False
        assert 'price_percent' not in bt
        assert bt.get('is_invite', False) is False
        assert 'invite_note' not in bt

    def test_behavior_tracking_module_copy_and_items(self):
        """Verify behavior_tracking_module presentation: icon, title, closed scope copy."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        bt = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'behavior_tracking_module')
        assert bt['icon'] == '👣'
        assert 'Rastreo' in bt['title']
        assert bt['is_visible'] is True
        assert len(bt['items']) == 7
        assert 'hasta 15 vistas' in bt['description']

    @pytest.mark.parametrize('lang', ['es', 'en'])
    def test_behavior_tracking_module_position_before_reports_alerts(self, lang):
        """Verify behavior_tracking_module sits immediately before reports_alerts_module in both languages."""
        sections = ProposalService.get_default_sections(lang)
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        ids = [m['id'] for m in fr['content_json']['additionalModules']]
        assert ids.index('behavior_tracking_module') + 1 == ids.index('reports_alerts_module')

    def test_en_calculator_modules_mirror_es(self):
        """EN additional modules match ES in item count, calculator flag, and price percent."""
        es = ProposalService.get_default_sections('es')
        en = ProposalService.get_default_sections('en')
        es_fr = next(s for s in es if s['section_type'] == 'functional_requirements')
        en_fr = next(s for s in en if s['section_type'] == 'functional_requirements')
        for mod_id in CALCULATOR_MODULE_IDS:
            es_g = next(g for g in es_fr['content_json']['additionalModules'] if g['id'] == mod_id)
            en_g = next(g for g in en_fr['content_json']['additionalModules'] if g['id'] == mod_id)
            assert len(es_g['items']) == len(en_g['items'])
            assert es_g['is_calculator_module'] == en_g['is_calculator_module']
            assert 'price_percent' not in es_g
            assert 'price_percent' not in en_g

    def test_en_functional_requirements_has_complete_catalog(self):
        """Verify the complete EN functional-requirements catalog."""
        sections = ProposalService.get_default_sections('en')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        groups = fr['content_json']['groups']
        additional = fr['content_json']['additionalModules']
        assert len(groups) == 9
        assert len(additional) == 17
        group_ids = {g['id'] for g in groups}
        assert group_ids == {
            'views', 'components', 'features', 'cross_cutting_features',
            'admin_module', 'analytics_dashboard', 'kpi_dashboard_module', 'manual_module',
            'ai_automation_module',
        }
        additional_ids = {m['id'] for m in additional}
        assert additional_ids == {
            'integration_international_payments', 'integration_regional_payments',
            'integration_electronic_invoicing', 'integration_conversion_tracking',
            'biometric_verification_module', 'behavior_tracking_module',
            'pwa_module', 'corporate_branding_module', 'ai_module', 'reports_alerts_module',
            'email_marketing_module',
            'qr_generator_module', 'content_generator_module',
            'i18n_module', 'gift_cards_module',
            'dark_mode_module', 'live_chat_module',
        }

    def test_kpi_dashboard_module_is_not_calculator_module(self):
        """Verify kpi_dashboard_module is a regular group (selected by default, not a calculator module)."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        kpi = next(g for g in fr['content_json']['groups'] if g['id'] == 'kpi_dashboard_module')
        assert 'is_calculator_module' not in kpi
        assert kpi['selected'] is True
        assert 'price_percent' not in kpi
        assert len(kpi['items']) == 4
        assert any('CSV' in i['description'] for i in kpi['items'] if i['name'] == 'Exportación de reportes')

    def test_all_regular_groups_have_selected_true(self):
        """Verify all 9 regular groups have selected=True and price_percent=0."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        regular_groups = fr['content_json']['groups']
        assert len(regular_groups) == 9
        for g in regular_groups:
            assert g['selected'] is True, f"Group {g['id']} should have selected=True"
            assert 'price_percent' not in g, f"Group {g['id']} exposes retired pricing"

    def test_all_additional_modules_have_selected_false(self):
        """Verify additional modules default to selected=False.

        Exception: corporate_branding_module is pre-selected by default for
        every new proposal.
        """
        always_selected = {'corporate_branding_module'}
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        for g in fr['content_json']['additionalModules']:
            expected = g['id'] in always_selected
            assert g['selected'] is expected, (
                f"Additional module {g['id']} should have selected={expected}")

    def test_en_regular_groups_match_es_selected_and_price_percent(self):
        """Verify EN regular groups have same selected and price_percent values as ES."""
        es = ProposalService.get_default_sections('es')
        en = ProposalService.get_default_sections('en')
        es_fr = next(s for s in es if s['section_type'] == 'functional_requirements')
        en_fr = next(s for s in en if s['section_type'] == 'functional_requirements')
        for es_g, en_g in zip(es_fr['content_json']['groups'], en_fr['content_json']['groups']):
            assert es_g['id'] == en_g['id'], f"group order mismatch: {es_g['id']} vs {en_g['id']}"
            assert es_g['selected'] == en_g['selected'], f"selected mismatch for {es_g['id']}"
            assert 'price_percent' not in es_g, f"ES group {es_g['id']} exposes retired pricing"
            assert 'price_percent' not in en_g, f"EN group {en_g['id']} exposes retired pricing"

    def test_i18n_module_has_5_items_and_15_percent(self):
        """Verify i18n_module: 5 items, price_percent 15."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        i18n = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'i18n_module')
        assert len(i18n['items']) == 5
        assert i18n['is_calculator_module'] is True
        assert i18n['default_selected'] is False
        assert 'price_percent' not in i18n

    def test_gift_cards_module_has_5_items_and_20_percent(self):
        """Verify gift_cards_module: 5 items, price_percent 20, is_visible False."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        gc = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'gift_cards_module')
        assert len(gc['items']) == 5
        assert gc['is_calculator_module'] is False
        assert gc['default_selected'] is False
        assert 'price_percent' not in gc
        assert gc['is_visible'] is False

    def test_all_groups_have_is_visible(self):
        """Verify every group and additional module has an is_visible attribute."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        all_entries = fr['content_json']['groups'] + fr['content_json']['additionalModules']
        for group in all_entries:
            assert 'is_visible' in group, f"Group {group['id']} missing is_visible"

    def test_gift_cards_is_only_hidden_module(self):
        """Verify gift_cards_module is the only entry with is_visible=False."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        all_entries = fr['content_json']['groups'] + fr['content_json']['additionalModules']
        hidden = [g['id'] for g in all_entries if g['is_visible'] is False]
        assert hidden == ['gift_cards_module']

    def test_en_groups_have_is_visible_matching_es(self):
        """Verify EN groups and additional modules have the same is_visible values as ES."""
        es = ProposalService.get_default_sections('es')
        en = ProposalService.get_default_sections('en')
        es_fr = next(s for s in es if s['section_type'] == 'functional_requirements')
        en_fr = next(s for s in en if s['section_type'] == 'functional_requirements')
        es_all = es_fr['content_json']['groups'] + es_fr['content_json']['additionalModules']
        en_all = en_fr['content_json']['groups'] + en_fr['content_json']['additionalModules']
        for es_g in es_all:
            en_g = next(g for g in en_all if g['id'] == es_g['id'])
            assert es_g['is_visible'] == en_g['is_visible'], (
                f"is_visible mismatch for {es_g['id']}: ES={es_g['is_visible']}, EN={en_g['is_visible']}"
            )

    def test_ai_module_has_invite_note(self):
        """Verify ai_module has an invite_note field and uses is_invite (not is_ai_invite)."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        ai = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'ai_module')
        assert ai['invite_note']
        assert 'is_ai_invite' not in ai
        assert ai['is_invite'] is True

    def test_development_stages_has_current_stage(self):
        sections = ProposalService.get_default_sections('es')
        ds = next(s for s in sections if s['section_type'] == 'development_stages')
        stages = ds['content_json']['stages']
        current_stages = [s for s in stages if s.get('current')]
        assert len(current_stages) == 1

    def test_groups_are_in_expected_order(self):
        """Verify ES groups and additionalModules follow the specified order."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        group_ids = [g['id'] for g in fr['content_json']['groups']]
        assert group_ids == EXPECTED_GROUP_ORDER
        additional_ids = [g['id'] for g in fr['content_json']['additionalModules']]
        assert additional_ids == EXPECTED_ADDITIONAL_MODULE_ORDER

    def test_en_groups_match_es_order(self):
        """Verify EN groups and additionalModules are in the same order as ES."""
        es = ProposalService.get_default_sections('es')
        en = ProposalService.get_default_sections('en')
        es_fr = next(s for s in es if s['section_type'] == 'functional_requirements')
        en_fr = next(s for s in en if s['section_type'] == 'functional_requirements')
        es_ids = [g['id'] for g in es_fr['content_json']['groups']]
        en_ids = [g['id'] for g in en_fr['content_json']['groups']]
        assert es_ids == en_ids
        es_add_ids = [g['id'] for g in es_fr['content_json']['additionalModules']]
        en_add_ids = [g['id'] for g in en_fr['content_json']['additionalModules']]
        assert es_add_ids == en_add_ids

    def test_dark_mode_module_has_5_items_and_20_percent(self):
        """Verify dark_mode_module: 5 items, price_percent 20, not selected by default."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        dm = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'dark_mode_module')
        assert len(dm['items']) == 5
        assert dm['is_calculator_module'] is True
        assert dm['default_selected'] is False
        assert 'price_percent' not in dm
        assert dm['is_visible'] is True

    def test_live_chat_module_has_6_items_and_40_percent(self):
        """Verify live_chat_module: 6 items, price_percent 40, not selected by default."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        lc = next(g for g in fr['content_json']['additionalModules'] if g['id'] == 'live_chat_module')
        assert len(lc['items']) == 6
        assert lc['is_calculator_module'] is True
        assert lc['default_selected'] is False
        assert 'price_percent' not in lc
        assert lc['is_visible'] is True

    def test_integration_titles_have_api_postfix_es(self):
        """Verify ES integration titles include (Integración API) postfix."""
        sections = ProposalService.get_default_sections('es')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        for gid in ('integration_conversion_tracking', 'integration_electronic_invoicing',
                     'integration_international_payments', 'integration_regional_payments'):
            g = next(grp for grp in fr['content_json']['additionalModules'] if grp['id'] == gid)
            assert g['title'].endswith('(Integración API)'), f"{gid} ES title missing postfix"

    def test_integration_titles_have_api_postfix_en(self):
        """Verify EN integration titles include (API Integration) postfix."""
        sections = ProposalService.get_default_sections('en')
        fr = next(s for s in sections if s['section_type'] == 'functional_requirements')
        for gid in ('integration_conversion_tracking', 'integration_electronic_invoicing',
                     'integration_international_payments', 'integration_regional_payments'):
            g = next(grp for grp in fr['content_json']['additionalModules'] if grp['id'] == gid)
            assert g['title'].endswith('(API Integration)'), f"{gid} EN title missing postfix"

    def test_hosting_plan_uses_percentage(self):
        """Verify hosting plan uses hostingPercent instead of fixed prices."""
        sections = ProposalService.get_default_sections('es')
        inv = next(s for s in sections if s['section_type'] == 'investment')
        hp = inv['content_json']['hostingPlan']
        assert hp['hostingPercent'] == 80
        assert 'monthlyPrice' not in hp
        assert 'annualPrice' not in hp

    def test_en_hosting_plan_uses_percentage(self):
        """Verify EN hosting plan also uses hostingPercent."""
        sections = ProposalService.get_default_sections('en')
        inv = next(s for s in sections if s['section_type'] == 'investment')
        hp = inv['content_json']['hostingPlan']
        assert hp['hostingPercent'] == 80
        assert 'monthlyPrice' not in hp
        assert 'annualPrice' not in hp

    @pytest.mark.parametrize('lang', ['es', 'en'])
    def test_hosting_plan_has_nine_month_tier_at_40(self, lang):
        sections = ProposalService.get_default_sections(lang)
        inv = next(s for s in sections if s['section_type'] == 'investment')
        tiers = {t['frequency']: t for t in inv['content_json']['hostingPlan']['billingTiers']}
        assert 'nine_month' in tiers
        assert tiers['nine_month']['months'] == 9
        assert tiers['nine_month']['discountPercent'] == 40

    @pytest.mark.parametrize('lang', ['es', 'en'])
    def test_hosting_plan_has_renewal_and_free_month_notes(self, lang):
        sections = ProposalService.get_default_sections(lang)
        inv = next(s for s in sections if s['section_type'] == 'investment')
        hp = inv['content_json']['hostingPlan']
        assert hp['renewalNote'].strip()
        assert hp['coverageNote'].strip()
        assert hp['freeMonths'] == 1
        assert hp['freeMonthsVisible'] is True
        assert hp['freeMonthNote'].strip()
        # New multiplicative +8% renewal formula (not the old absolute 6% one).
        assert '8%' in hp['renewalNote']

    def test_defaults_to_es_for_unknown_language(self):
        """Unknown language code falls back to Spanish defaults."""
        sections = ProposalService.get_default_sections('fr')
        assert len(sections) == EXPECTED_DEFAULT_SECTION_COUNT


CUSTOM_SECTIONS = [
    {
        'section_type': 'greeting',
        'title': 'Custom Greeting',
        'order': 0,
        'is_wide_panel': False,
        'content_json': {'proposalTitle': '', 'clientName': '', 'inspirationalQuote': 'Custom quote'},
    },
    {
        'section_type': 'executive_summary',
        'title': 'Custom Summary',
        'order': 1,
        'is_wide_panel': True,
        'content_json': {'index': '02', 'title': 'Custom'},
    },
]


class TestGetDefaultSectionsFromDB:
    """Verify get_default_sections reads from DB when config exists."""

    def test_returns_db_config_when_exists_es(self):
        ProposalDefaultConfig.objects.create(language='es', sections_json=CUSTOM_SECTIONS)
        sections = ProposalService.get_default_sections('es')
        assert len(sections) == 2
        assert sections[0]['title'] == 'Custom Greeting'

    def test_returns_db_config_when_exists_en(self):
        ProposalDefaultConfig.objects.create(language='en', sections_json=CUSTOM_SECTIONS)
        sections = ProposalService.get_default_sections('en')
        assert len(sections) == 2
        assert sections[0]['title'] == 'Custom Greeting'

    def test_falls_back_to_hardcoded_when_no_db_config(self):
        sections = ProposalService.get_default_sections('es')
        assert len(sections) == EXPECTED_DEFAULT_SECTION_COUNT

    def test_falls_back_when_db_config_has_empty_sections(self):
        ProposalDefaultConfig.objects.create(language='es', sections_json=[])
        sections = ProposalService.get_default_sections('es')
        assert len(sections) == EXPECTED_DEFAULT_SECTION_COUNT

    def test_db_config_returns_independent_copy(self):
        ProposalDefaultConfig.objects.create(language='es', sections_json=CUSTOM_SECTIONS)
        s1 = ProposalService.get_default_sections('es')
        s2 = ProposalService.get_default_sections('es')
        s1[0]['title'] = 'MUTATED'
        assert s2[0]['title'] == 'Custom Greeting'

    def test_es_db_config_does_not_affect_en(self):
        ProposalDefaultConfig.objects.create(language='es', sections_json=CUSTOM_SECTIONS)
        en_sections = ProposalService.get_default_sections('en')
        assert len(en_sections) == EXPECTED_DEFAULT_SECTION_COUNT

    def test_get_hardcoded_defaults_always_returns_hardcoded(self):
        ProposalDefaultConfig.objects.create(language='es', sections_json=CUSTOM_SECTIONS)
        hardcoded = ProposalService.get_hardcoded_defaults('es')
        assert len(hardcoded) == EXPECTED_DEFAULT_SECTION_COUNT


class TestGetDefaultExpirationDays:
    def test_returns_21_when_no_config_exists(self):
        assert ProposalService.get_default_expiration_days('es') == 21

    def test_returns_configured_value_when_config_exists(self):
        ProposalDefaultConfig.objects.create(
            language='es',
            sections_json=[],
            expiration_days=30,
        )
        assert ProposalService.get_default_expiration_days('es') == 30


class TestSendProposal:
    def test_raises_error_without_client_email(self):
        proposal = BusinessProposal.objects.create(
            title='No Email',
            client_name='Client',
            client_email='',
        )
        with pytest.raises(ValueError, match='correo'):
            ProposalService.send_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'draft'

    @patch('content.services.proposal_snapshot_service.prepare_proposal_snapshots')
    @patch('content.utils.validate_email_domain_mx', return_value=True)
    def test_missing_email_intro_blocks_before_snapshot(
        self, mock_mx, mock_prepare,
    ):
        proposal = BusinessProposal.objects.create(
            title='Missing Message',
            client_name='Client',
            client_email='client@example.com',
            email_intro='   ',
        )

        with pytest.raises(ProposalActionError) as exc_info:
            ProposalService.send_proposal(proposal)

        assert exc_info.value.code == 'missing_email_intro'
        mock_prepare.assert_not_called()
        proposal.refresh_from_db()
        assert proposal.status == BusinessProposal.Status.DRAFT
        assert proposal.sent_at is None

    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_sets_status_to_sent(self, mock_reminder, mock_urgency):
        mock_reminder.schedule = MagicMock(return_value=None)
        mock_urgency.schedule = MagicMock(return_value=None)
        proposal = BusinessProposal.objects.create(
            title='Send Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
        )
        ProposalService.send_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'sent'
        mock_reminder.schedule.assert_called_once()

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_sets_sent_at_timestamp(self, mock_reminder, mock_urgency):
        mock_reminder.schedule = MagicMock(return_value=None)
        mock_urgency.schedule = MagicMock(return_value=None)
        proposal = BusinessProposal.objects.create(
            title='Timestamp Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
        )
        ProposalService.send_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.sent_at == datetime(2025, 6, 1, 12, 0, 0, tzinfo=dt_tz.utc)
        mock_reminder.schedule.assert_called_once()
        mock_urgency.schedule.assert_called_once()

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_schedules_both_reminder_and_urgency_tasks(self, mock_reminder, mock_urgency):
        """Both reminder (day 10) and urgency (day 15) tasks are scheduled."""
        mock_reminder.schedule = MagicMock(return_value=None)
        mock_urgency.schedule = MagicMock(return_value=None)
        proposal = BusinessProposal.objects.create(
            title='Reminder Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
            reminder_days=10,
            urgency_reminder_days=15,
        )
        ProposalService.send_proposal(proposal)
        mock_reminder.schedule.assert_called_once()
        mock_urgency.schedule.assert_called_once()
        reminder_delay = mock_reminder.schedule.call_args[1]['delay']
        assert reminder_delay == 10 * 86400
        urgency_delay = mock_urgency.schedule.call_args[1]['delay']
        assert urgency_delay == 15 * 86400

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_auto_sets_expires_at_to_21_days(self, mock_reminder, mock_urgency):
        """When expires_at is not set, send_proposal auto-sets it to 21 days."""
        mock_reminder.schedule = MagicMock(return_value=None)
        mock_urgency.schedule = MagicMock(return_value=None)
        proposal = BusinessProposal.objects.create(
            title='Auto Expiry Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
        )
        assert proposal.expires_at is None
        ProposalService.send_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.expires_at == datetime(2025, 6, 22, 12, 0, 0, tzinfo=dt_tz.utc)
        mock_reminder.schedule.assert_called_once()
        mock_urgency.schedule.assert_called_once()

    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_logs_exception_when_schedule_fails(self, mock_reminder, mock_urgency):
        """send_proposal still marks as sent even if task scheduling fails."""
        mock_reminder.schedule = MagicMock(side_effect=RuntimeError('Huey unavailable'))
        mock_urgency.schedule = MagicMock(return_value=None)
        proposal = BusinessProposal.objects.create(
            title='Exception Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
        )
        ProposalService.send_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'sent'
        mock_reminder.schedule.assert_called_once()


class TestResendProposal:
    def test_raises_error_without_client_email(self):
        """Resend should fail if no client_email is set."""
        proposal = BusinessProposal.objects.create(
            title='No Email Resend',
            client_name='Client',
            client_email='',
            status='sent',
        )
        with pytest.raises(ValueError, match='correo'):
            ProposalService.resend_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'sent'

    @patch('content.services.proposal_snapshot_service.prepare_proposal_snapshots')
    @patch('content.utils.validate_email_domain_mx', return_value=True)
    def test_blank_replacement_keeps_saved_message(
        self, mock_mx, mock_prepare,
    ):
        proposal = BusinessProposal.objects.create(
            title='Resend Guard',
            client_name='Client',
            client_email='client@example.com',
            email_intro='Mensaje anterior que sigue siendo válido.',
            status='sent',
        )

        with pytest.raises(ProposalActionError) as exc_info:
            ProposalService.resend_proposal(proposal, email_intro='   ')

        assert exc_info.value.code == 'missing_email_intro'
        mock_prepare.assert_not_called()
        proposal.refresh_from_db()
        assert proposal.email_intro == 'Mensaje anterior que sigue siendo válido.'

    @patch.object(ProposalService, '_schedule_email_tasks')
    @patch.object(
        ProposalService,
        '_send_initial_email',
        return_value={'ok': True, 'reason': 'sent', 'detail': ''},
    )
    @patch('content.services.proposal_snapshot_service.finalize_proposal_snapshots')
    @patch('content.services.proposal_snapshot_service.prepare_proposal_snapshots')
    @patch('content.utils.validate_email_domain_mx', return_value=True)
    def test_replacement_is_saved_before_delivery(
        self,
        mock_mx,
        mock_prepare,
        mock_finalize,
        mock_send,
        mock_schedule,
    ):
        snapshot = object()
        mock_prepare.return_value = [snapshot]
        proposal = BusinessProposal.objects.create(
            title='Editable Resend',
            client_name='Client',
            client_email='client@example.com',
            email_intro='Mensaje anterior.',
            status='viewed',
        )

        result = ProposalService.resend_proposal(
            proposal,
            email_intro='  Mensaje nuevo que resuelve el proceso.  ',
        )

        proposal.refresh_from_db()
        assert result['ok'] is True
        assert proposal.email_intro == 'Mensaje nuevo que resuelve el proceso.'
        mock_send.assert_called_once_with(proposal, snapshot=snapshot)
        mock_finalize.assert_called_once()
        assert ProposalChangeLog.objects.filter(
            proposal=proposal,
            field_name='email_intro',
            old_value='Mensaje anterior.',
            new_value='Mensaje nuevo que resuelve el proceso.',
        ).exists()

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_keeps_existing_expires_at(self, mock_reminder, mock_urgency):
        """Resend should not change the existing expires_at."""
        mock_reminder.schedule = MagicMock(return_value=None)
        mock_urgency.schedule = MagicMock(return_value=None)
        original_expiry = datetime(2025, 7, 1, 12, 0, 0, tzinfo=dt_tz.utc)
        proposal = BusinessProposal.objects.create(
            title='Resend Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
            status='viewed',
            expires_at=original_expiry,
        )
        ProposalService.resend_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'sent'
        assert proposal.expires_at == original_expiry
        assert proposal.reminder_sent_at is None
        assert proposal.urgency_email_sent_at is None
        mock_reminder.schedule.assert_called_once()
        mock_urgency.schedule.assert_called_once()

    @freeze_time('2025-06-01 12:00:00')
    @patch('content.tasks.send_urgency_reminder')
    @patch('content.tasks.send_proposal_reminder')
    def test_resets_email_tracking_fields(self, mock_reminder, mock_urgency):
        """Resend should reset reminder_sent_at and urgency_email_sent_at."""
        mock_reminder.schedule = MagicMock(return_value=None)
        mock_urgency.schedule = MagicMock(return_value=None)
        now = datetime(2025, 6, 1, 12, 0, 0, tzinfo=dt_tz.utc)
        proposal = BusinessProposal.objects.create(
            title='Reset Fields Test',
            client_name='Client',
            client_email='client@test.com',
            email_intro='Esta propuesta resuelve el proceso principal del cliente.',
            status='viewed',
            expires_at=now + timedelta(days=30),
            reminder_sent_at=now - timedelta(days=2),
            urgency_email_sent_at=now - timedelta(days=1),
        )
        ProposalService.resend_proposal(proposal)
        proposal.refresh_from_db()
        assert proposal.reminder_sent_at is None
        assert proposal.urgency_email_sent_at is None
        assert proposal.sent_at == now
        mock_reminder.schedule.assert_called_once()
        mock_urgency.schedule.assert_called_once()


class TestSendMultiProposalMessageGuard:
    @patch('content.services.proposal_snapshot_service.prepare_proposal_snapshots')
    @patch('content.utils.validate_email_domain_mx', return_value=True)
    def test_missing_message_blocks_every_proposal_before_snapshot(
        self, mock_mx, mock_prepare,
    ):
        ready = BusinessProposal.objects.create(
            title='Fase lista',
            client_name='Client',
            client_email='client@example.com',
            email_intro='Esta fase resuelve el registro manual.',
        )
        missing = BusinessProposal.objects.create(
            title='Fase incompleta',
            client_name='Client',
            client_email='client@example.com',
            email_intro='',
        )

        with pytest.raises(ProposalActionError) as exc_info:
            ProposalService.send_multi_proposals([ready, missing])

        assert exc_info.value.code == 'missing_email_intro'
        mock_prepare.assert_not_called()
        ready.refresh_from_db()
        missing.refresh_from_db()
        assert ready.status == BusinessProposal.Status.DRAFT
        assert missing.status == BusinessProposal.Status.DRAFT


class TestRecordView:
    def test_increments_view_count(self):
        proposal = BusinessProposal.objects.create(
            title='View Test',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
        )
        assert proposal.view_count == 0
        ProposalService.record_view(proposal)
        proposal.refresh_from_db()
        assert proposal.view_count == 1

    @freeze_time('2026-03-01 12:00:00')
    def test_sets_first_viewed_at_on_first_visit(self):
        proposal = BusinessProposal.objects.create(
            title='First View',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
        )
        assert proposal.first_viewed_at is None
        ProposalService.record_view(proposal)
        proposal.refresh_from_db()
        assert proposal.first_viewed_at is not None

    @freeze_time('2026-03-01 12:00:00')
    def test_does_not_overwrite_first_viewed_at_on_second_visit(self):
        proposal = BusinessProposal.objects.create(
            title='Second View',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
        )
        ProposalService.record_view(proposal)
        proposal.refresh_from_db()
        first_ts = proposal.first_viewed_at
        ProposalService.record_view(proposal)
        proposal.refresh_from_db()
        assert proposal.first_viewed_at == first_ts
        assert proposal.view_count == 2

    def test_updates_status_from_sent_to_viewed(self):
        proposal = BusinessProposal.objects.create(
            title='Status View',
            client_name='Client',
            client_email='client@test.com',
            status='sent',
        )
        ProposalService.record_view(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'viewed'

    def test_does_not_update_status_when_not_sent(self):
        proposal = BusinessProposal.objects.create(
            title='Draft View',
            client_name='Client',
            client_email='client@test.com',
            status='draft',
        )
        ProposalService.record_view(proposal)
        proposal.refresh_from_db()
        assert proposal.status == 'draft'


class TestSendInitialEmailExceptionPath:
    @patch(
        'content.services.proposal_email_service.ProposalEmailService.send_proposal_to_client',
        side_effect=Exception('SMTP error'),
    )
    def test_exception_in_send_initial_email_is_caught(self, mock_send):
        """Exception in _send_initial_email is caught and logged, not raised."""
        proposal = BusinessProposal.objects.create(
            title='Email Error', client_name='Client',
            client_email='client@test.com', status='sent',
        )
        ProposalService._send_initial_email(proposal)
        assert mock_send.call_count == 1
        mock_send.assert_called_once_with(proposal, snapshot=None)


class TestCheckExpiration:
    @freeze_time('2026-03-01 12:00:00')
    def test_returns_true_for_expired_proposal(self):
        proposal = BusinessProposal.objects.create(
            title='Expired',
            client_name='Client',
            client_email='c@test.com',
            expires_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=dt_tz.utc),
        )
        assert ProposalService.check_expiration(proposal) is True

    @freeze_time('2026-03-01 12:00:00')
    def test_returns_false_for_active_proposal(self):
        proposal = BusinessProposal.objects.create(
            title='Active',
            client_name='Client',
            client_email='c@test.com',
            expires_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=dt_tz.utc),
        )
        assert ProposalService.check_expiration(proposal) is False


class TestNormalizeHostingPlan:
    """Helper must make model fields the source of truth, with JSON as fallback."""

    def _proposal(self, **overrides):
        p = MagicMock()
        p.language = overrides.get('language', 'es')
        p.is_active = overrides.get('is_active', True)
        p.status = overrides.get('status', 'draft')
        p.hosting_percent = overrides.get('hosting_percent', 40)
        p.hosting_discount_nine_month = overrides.get(
            'hosting_discount_nine_month', 40,
        )
        p.hosting_discount_semiannual = overrides.get(
            'hosting_discount_semiannual', 25,
        )
        p.hosting_discount_quarterly = overrides.get(
            'hosting_discount_quarterly', 15,
        )
        return p

    def test_model_percent_overrides_json(self):
        result = normalize_hosting_plan(
            self._proposal(hosting_percent=40),
            {'hostingPercent': 30},
        )
        assert result['hostingPercent'] == 40

    def test_model_discounts_override_tier_discounts(self):
        result = normalize_hosting_plan(
            self._proposal(
                hosting_discount_semiannual=25,
                hosting_discount_quarterly=15,
            ),
            {'billingTiers': [
                {'frequency': 'semiannual', 'discountPercent': 20, 'months': 6},
                {'frequency': 'quarterly', 'discountPercent': 10, 'months': 3},
            ]},
        )
        tiers = {t['frequency']: t for t in result['billingTiers']}
        assert tiers['semiannual']['discountPercent'] == 25
        assert tiers['quarterly']['discountPercent'] == 15
        # Nine-month is guaranteed even though the input lacked it.
        assert tiers['nine_month']['discountPercent'] == 40
        assert 'monthly' not in tiers

    def test_monthly_tier_is_dropped_and_nine_month_guaranteed(self):
        # A legacy proposal that only stored a monthly tier is reconciled to the
        # canonical offered set [nine-month, semiannual, quarterly].
        result = normalize_hosting_plan(
            self._proposal(),
            {'billingTiers': [
                {'frequency': 'monthly', 'discountPercent': 0, 'months': 1},
            ]},
        )
        freqs = [t['frequency'] for t in result['billingTiers']]
        assert freqs == ['nine_month', 'semiannual', 'quarterly']

    def test_missing_model_percent_falls_back_to_json(self):
        p = self._proposal(hosting_percent=0)
        result = normalize_hosting_plan(p, {'hostingPercent': 25})
        assert result['hostingPercent'] == 25

    def test_missing_model_percent_defaults_to_80_when_json_also_empty(self):
        p = self._proposal(hosting_percent=0)
        result = normalize_hosting_plan(p, {})
        assert result['hostingPercent'] == 80

    def test_empty_billing_tiers_returns_canonical_offering(self):
        result = normalize_hosting_plan(self._proposal(), {})
        assert [tier['frequency'] for tier in result['billingTiers']] == [
            'nine_month', 'semiannual', 'quarterly',
        ]

    def test_malformed_tier_is_skipped(self):
        result = normalize_hosting_plan(
            self._proposal(),
            {'billingTiers': [
                None,
                'not-a-dict',
                {'frequency': 'monthly', 'months': 1, 'discountPercent': 0},
            ]},
        )
        # Malformed entries are ignored; the result is the canonical offered set.
        freqs = [t['frequency'] for t in result['billingTiers']]
        assert freqs == ['nine_month', 'semiannual', 'quarterly']

    def test_none_billing_tiers_returns_canonical_offering(self):
        result = normalize_hosting_plan(
            self._proposal(), {'billingTiers': None},
        )
        assert [tier['frequency'] for tier in result['billingTiers']] == [
            'nine_month', 'semiannual', 'quarterly',
        ]

    def test_closed_proposal_preserves_annual_snapshot(self):
        stored = [
            {
                'frequency': 'annual', 'months': 12,
                'discountPercent': 40, 'label': 'Anual',
            },
        ]
        result = normalize_hosting_plan(
            self._proposal(status='accepted'), {'billingTiers': stored},
        )

        assert result['billingTiers'] == stored

    def test_presentation_fields_preserved(self):
        result = normalize_hosting_plan(
            self._proposal(),
            {
                'title': 'Cloud', 'description': 'Managed.',
                'specs': [{'label': 'SSL', 'value': 'included'}],
                'hostingPercent': 30,
            },
        )
        assert result['title'] == 'Cloud'
        assert result['description'] == 'Managed.'
        assert result['specs'] == [{'label': 'SSL', 'value': 'included'}]


class TestNormalizeHostingPlanFreeMonths:
    """The free-month gift block: explicit visibility flag + resolved copy.

    This is the single read-time hook the panel form, the public view and the
    PDF all share, so what it returns is what the three of them show.
    """

    def _proposal(self, **overrides):
        p = MagicMock()
        p.language = overrides.get('language', 'es')
        p.is_active = overrides.get('is_active', True)
        p.status = overrides.get('status', 'draft')
        p.hosting_percent = overrides.get('hosting_percent', 40)
        p.hosting_discount_nine_month = 40
        p.hosting_discount_semiannual = 20
        p.hosting_discount_quarterly = 10
        return p

    # --- visibility ---

    def test_explicit_false_hides_block_even_with_months(self):
        """The checkbox wins: the count no longer decides visibility."""
        result = normalize_hosting_plan(
            self._proposal(),
            {'freeMonths': 3, 'freeMonthsVisible': False},
        )
        assert result['freeMonthsVisible'] is False

    def test_explicit_true_shows_block_with_zero_months(self):
        result = normalize_hosting_plan(
            self._proposal(),
            {'freeMonths': 0, 'freeMonthsVisible': True},
        )
        assert result['freeMonthsVisible'] is True

    @pytest.mark.parametrize(
        ('stored_months', 'expected'),
        [(1, True), (3, True), ('2', True), (0, False), ('0', False),
         ('', False), (None, False)],
    )
    def test_missing_flag_falls_back_to_the_old_count_rule(
        self, stored_months, expected,
    ):
        """Content written before the flag keeps the appearance it has today."""
        result = normalize_hosting_plan(
            self._proposal(), {'freeMonths': stored_months},
        )
        assert result['freeMonthsVisible'] is expected

    def test_hosting_plan_without_any_free_month_key_stays_hidden(self):
        result = normalize_hosting_plan(self._proposal(), {'title': 'Cloud'})
        assert result['freeMonthsVisible'] is False

    def test_closed_proposal_also_gets_the_flag_resolved(self):
        """The early-return branch for historical terms must resolve it too."""
        result = normalize_hosting_plan(
            self._proposal(is_active=False, status='accepted'),
            {'freeMonths': 1},
        )
        assert result['freeMonthsVisible'] is True

    # --- copy ---

    @pytest.mark.parametrize(
        ('lang', 'fragment'),
        [('es', 'hosting es gratis'), ('en', 'hosting is free')],
    )
    def test_empty_note_is_filled_with_the_language_default(self, lang, fragment):
        result = normalize_hosting_plan(
            self._proposal(language=lang), {'freeMonths': 1, 'freeMonthNote': ''},
        )
        assert fragment in result['freeMonthNote']

    def test_blank_note_counts_as_empty(self):
        result = normalize_hosting_plan(
            self._proposal(), {'freeMonths': 1, 'freeMonthNote': '   '},
        )
        assert result['freeMonthNote'].strip()

    def test_custom_note_is_never_overwritten(self):
        result = normalize_hosting_plan(
            self._proposal(),
            {'freeMonths': 1, 'freeMonthNote': 'Tres meses de regalo.'},
        )
        assert result['freeMonthNote'] == 'Tres meses de regalo.'


class TestAdminPinnedCalculatorGroupIds:
    """admin_pinned_calculator_group_ids: visible calc modules with selected is True."""

    def _fr(self, *modules):
        return {'groups': [], 'additionalModules': list(modules)}

    def test_includes_only_explicitly_selected_visible_calc_modules(self):
        from content.services.proposal_service import admin_pinned_calculator_group_ids

        fr = self._fr(
            {'id': 'ai', 'is_calculator_module': True, 'selected': True, 'is_visible': True},
            {'id': 'pwa', 'is_calculator_module': True, 'selected': False, 'is_visible': True},
            {'id': 'branding', 'is_calculator_module': True, 'default_selected': True,
             'selected': False, 'is_visible': True},
            {'id': 'hidden_ai', 'is_calculator_module': True, 'selected': True, 'is_visible': False},
            {'id': 'not_calc', 'is_calculator_module': False, 'selected': True, 'is_visible': True},
            {'id': '', 'is_calculator_module': True, 'selected': True, 'is_visible': True},
            'not-a-dict',
        )
        assert admin_pinned_calculator_group_ids(fr) == {'ai'}

    def test_reads_both_groups_and_additional_modules(self):
        from content.services.proposal_service import admin_pinned_calculator_group_ids

        fr = {
            'groups': [{'id': 'g1', 'is_calculator_module': True, 'selected': True, 'is_visible': True}],
            'additionalModules': [{'id': 'm1', 'is_calculator_module': True, 'selected': True, 'is_visible': True}],
        }
        assert admin_pinned_calculator_group_ids(fr) == {'g1', 'm1'}

    def test_non_dict_input_returns_empty_set(self):
        from content.services.proposal_service import admin_pinned_calculator_group_ids

        assert admin_pinned_calculator_group_ids(None) == set()
        assert admin_pinned_calculator_group_ids([]) == set()


class TestAdminDefaultCalculatorGroupIds:
    """admin_default_calculator_group_ids: `selected` is the source of truth; `default_selected` is only a fallback when `selected` is absent."""

    def _fr(self, *modules):
        return {'groups': [], 'additionalModules': list(modules)}

    def test_selected_true_included_selected_false_excluded(self):
        from content.services.proposal_service import admin_default_calculator_group_ids

        fr = self._fr(
            {'id': 'ai', 'is_calculator_module': True, 'selected': True, 'is_visible': True},
            {'id': 'pwa', 'is_calculator_module': True, 'selected': False, 'is_visible': True},
        )
        assert admin_default_calculator_group_ids(fr) == {'ai'}

    def test_explicit_selected_false_overrides_default_selected_true(self):
        from content.services.proposal_service import admin_default_calculator_group_ids

        fr = self._fr(
            {'id': 'branding', 'is_calculator_module': True, 'selected': False,
             'default_selected': True, 'is_visible': True},
        )
        assert admin_default_calculator_group_ids(fr) == set()

    def test_default_selected_true_used_when_selected_absent(self):
        from content.services.proposal_service import admin_default_calculator_group_ids

        fr = self._fr(
            {'id': 'legacy', 'is_calculator_module': True, 'default_selected': True, 'is_visible': True},
        )
        assert admin_default_calculator_group_ids(fr) == {'legacy'}

    def test_hidden_and_non_calc_and_blank_ignored(self):
        from content.services.proposal_service import admin_default_calculator_group_ids

        fr = self._fr(
            {'id': 'hidden', 'is_calculator_module': True, 'selected': True, 'is_visible': False},
            {'id': 'not_calc', 'is_calculator_module': False, 'selected': True, 'is_visible': True},
            {'id': '', 'is_calculator_module': True, 'selected': True, 'is_visible': True},
            'not-a-dict',
        )
        assert admin_default_calculator_group_ids(fr) == set()

    def test_non_dict_input_returns_empty_set(self):
        from content.services.proposal_service import admin_default_calculator_group_ids

        assert admin_default_calculator_group_ids(None) == set()
