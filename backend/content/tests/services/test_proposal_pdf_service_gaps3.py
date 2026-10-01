"""Gap tests for proposal_pdf_service — targets uncovered branches.

Covers:
- default_selected_modules_from_content: non-dict group (line 161) and missing gid (line 174)
- _render_investment: forced linear layout with payment option desc recalculation
- _render_value_added_modules: y=None default (line 1460) and missing catalog entry (line 1494)
- generate(): section content_json without 'title' key (line 2021)
"""
import io
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.models import BusinessProposal
from content.models.proposal_section import ProposalSection
from content.services.proposal_pdf_service import (
    MARGIN_B,
    MARGIN_T,
    PAGE_H,
    _register_fonts,
    _render_creative_support,
    _render_investment,
    _render_value_added_modules,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pdf_canvas():
    _register_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    return c


@pytest.fixture
def proposal(db):
    return BusinessProposal.objects.create(
        title='Gaps3 Proposal',
        client_name='Gaps Client',
        client_email='gaps3@example.com',
        language='es',
        total_investment=Decimal('5000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=14),
    )


# ---------------------------------------------------------------------------
# default_selected_modules_from_content — non-dict group skipped (line 161)
# ---------------------------------------------------------------------------

class TestDefaultSelectedModulesNonDictGroup:
    def test_non_dict_entry_in_groups_is_skipped(self, proposal):
        from content.services.proposal_pdf_service import (
            default_selected_modules_from_content,
        )

        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='FR',
            order=0,
            is_enabled=True,
            content_json={
                'groups': [
                    'not-a-dict',
                    None,
                    {'id': 'grp1', 'title': 'Valid Group'},
                ],
            },
        )

        result = default_selected_modules_from_content(proposal, has_confirmed=False)

        assert isinstance(result, list)
        assert 'group-grp1' in result


# ---------------------------------------------------------------------------
# default_selected_modules_from_content — group without id skipped (line 174)
# ---------------------------------------------------------------------------

class TestDefaultSelectedModulesMissingGid:
    def test_group_without_id_is_not_added_to_selected(self, proposal):
        from content.services.proposal_pdf_service import (
            default_selected_modules_from_content,
        )

        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='FR',
            order=0,
            is_enabled=True,
            content_json={
                'groups': [
                    {'title': 'No ID Group', 'selected': True},
                ],
            },
        )

        result = default_selected_modules_from_content(proposal, has_confirmed=False)

        assert result == []


# ---------------------------------------------------------------------------
# _render_value_added_modules — y=None default (line 1460)
# ---------------------------------------------------------------------------

class TestRenderValueAddedModulesYNone:
    def test_y_none_defaults_to_page_top(self, pdf_canvas):
        """Fails if a default-y value-added section does not render its card."""
        data = {'index': '05', 'title': 'Incluido', 'module_ids': ['admin']}
        ps = {
            '_value_added_catalog': {
                'admin': {'title': 'Administración', 'items': []},
            },
            'num': 1,
            'client': 'Test',
        }

        result = _render_value_added_modules(pdf_canvas, data, None, ps=ps, y=None)

        draw_ops = '\n'.join(pdf_canvas._code)
        assert result < PAGE_H - MARGIN_T
        assert 'Incluido' in draw_ops
        assert 'Administraci' in draw_ops


# ---------------------------------------------------------------------------
# _render_value_added_modules — module not in catalog skipped (line 1494)
# ---------------------------------------------------------------------------

class TestRenderValueAddedModulesMissingCatalogEntry:
    def test_module_id_not_in_catalog_is_skipped_without_error(self, pdf_canvas):
        data = {
            'index': '05',
            'title': 'Incluido',
            'module_ids': ['missing-id-1', 'missing-id-2'],
        }
        ps = {'_value_added_catalog': {}, 'num': 1, 'client': 'Test'}
        y_in = PAGE_H - MARGIN_T

        result = _render_value_added_modules(
            pdf_canvas, data, None, ps=ps, y=y_in,
        )

        # Nothing resolved, so nothing is drawn — not even the header.
        assert result == y_in


# ---------------------------------------------------------------------------
# _render_value_added_modules — no resolvable module means no section
# ---------------------------------------------------------------------------

class TestRenderValueAddedModulesEmptyGuard:
    """Mirrors ValueAddedModules.vue: `v-if="resolvedCards.length > 0"`.

    A proposal that grants no modules (a follow-up phase, say, where they were
    already granted in the previous one) hides the section on the web. The PDF
    must not print an orphan header for it.
    """

    CATALOG_PS = {
        '_value_added_catalog': {
            'admin_module': {'title': 'Módulo Administrativo', 'items': []},
        },
        '_pdf_lang': 'es',
        '_currency': 'COP',
    }

    def test_empty_module_ids_draws_nothing(self, pdf_canvas, proposal):
        y_in = PAGE_H - MARGIN_T
        data = {
            'index': '10',
            'title': 'Incluido sin costo adicional',
            'intro': 'Estos módulos no se cobran aparte.',
            'module_ids': [],
        }

        result = _render_value_added_modules(
            pdf_canvas, data, proposal, ps=dict(self.CATALOG_PS), y=y_in,
        )

        assert result == y_in, 'cursor must not move when nothing is drawn'

    def test_resolvable_module_still_renders(self, pdf_canvas, proposal):
        """The guard must not swallow a section that does have modules."""
        y_in = PAGE_H - MARGIN_T
        data = {
            'index': '10',
            'title': 'Incluido sin costo adicional',
            'module_ids': ['admin_module'],
            'justifications': {
                'admin_module': 'Para administrar sin depender de nosotros.',
            },
        }

        result = _render_value_added_modules(
            pdf_canvas, data, proposal, ps=dict(self.CATALOG_PS), y=y_in,
        )

        assert result < y_in, 'a resolvable module must draw the section'


# ---------------------------------------------------------------------------
# _render_investment — forced linear layout with ps (lines 1042, 1050, 1082)
# ---------------------------------------------------------------------------

class TestRenderInvestmentLinearLayout:
    def test_linear_layout_with_ps_and_options_renders_without_error(
        self, pdf_canvas, proposal,
    ):
        """Fails if the linear investment layout omits its payment or included item."""
        ps = {
            'num': 1,
            'client': 'Test',
            'selected_modules': None,
            '_fr_items': [],
            '_calc_module_items': [],
            'base_weeks': 0,
        }
        data = {
            'index': '4',
            'title': 'Inversión',
            'totalInvestment': '$5.000.000',
            'currency': 'COP',
            'paymentOptions': [
                {'label': '50% Inicio', 'description': '$2.500.000'},
                {'label': '50% Final', 'description': '$2.500.000'},
            ],
            'whatsIncluded': [
                {'title': 'Diseño', 'description': 'UI/UX completo'},
            ],
            'modules': [],
        }

        # Force linear layout by using small y
        small_y = MARGIN_B + 60

        _render_investment(pdf_canvas, data, proposal, ps=ps, y=small_y)

        draw_ops = '\n'.join(pdf_canvas._code)
        assert 'Formas de Pago' in draw_ops
        assert '50% Inicio' in draw_ops
        assert 'Dise' in draw_ops

    def test_linear_layout_preserves_manual_payment_amount(
        self, pdf_canvas, proposal,
    ):
        """The linear layout derives payment from the agreed manual total."""
        ps = {
            'num': 1,
            'client': 'Test',
            'selected_modules': ['web'],
            'base_weeks': 0,
        }
        data = {
            'index': '4',
            'title': 'Inversión',
            'totalInvestment': '$5.000.000',
            'currency': 'COP',
            'paymentOptions': [
                {'label': '50% Inicio', 'description': '$2500000'},
            ],
            'whatsIncluded': [
                {'title': 'Soporte', 'description': 'Incluido'},
            ],
            'modules': [
                {'id': 'web', 'name': 'Web'},
                {'id': 'seo', 'name': 'SEO'},
            ],
        }

        small_y = MARGIN_B + 60

        _render_investment(pdf_canvas, data, proposal, ps=ps, y=small_y)

        draw_ops = '\n'.join(pdf_canvas._code)
        assert 'Formas de Pago' in draw_ops
        assert '50% Inicio' in draw_ops
        assert 'Soporte' in draw_ops
        assert '$2.500.000' in draw_ops
        assert '$1.500.000' not in draw_ops


# ---------------------------------------------------------------------------
# generate() — section content_json without 'title' key (line 2021)
# ---------------------------------------------------------------------------

class TestGenerateSectionWithoutTitleInContentJson:
    def test_section_without_title_in_content_json_falls_back_to_section_title(
        self, proposal,
    ):
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='executive_summary',
            title='Resumen Ejecutivo',
            order=1,
            is_enabled=True,
            content_json={'index': '01', 'paragraphs': ['Texto de resumen.']},
        )

        from content.services.proposal_pdf_service import ProposalPdfService

        with patch(
            'content.services.proposal_pdf_service.ProposalPdfService._merge_with_covers',
            side_effect=lambda b, **kw: b,
        ):
            result = ProposalPdfService.generate(proposal)

        assert isinstance(result, bytes)
        assert result[:4] == b'%PDF'


# ---------------------------------------------------------------------------
# _render_creative_support — Tier 2 partial two-column layout (lines 456-462)
# ---------------------------------------------------------------------------

class TestRenderCreativeSupportTier2:
    def test_tier2_partial_two_column_renders_paragraphs_then_closing_below(
        self, pdf_canvas,
    ):
        """Fails if the partial layout drops its sidebar or closing content."""
        data = {
            'index': None,
            'title': 'Soporte',
            'paragraphs': ['Visible content.'] * 7,
            'closing': 'Mensaje de cierre.',
            'includes': ['Elemento incluido'],
            'includesTitle': 'Incluye',
        }

        _render_creative_support(pdf_canvas, data, None, ps=None, y=304)

        draw_ops = '\n'.join(pdf_canvas._code)
        assert 'Soporte' in draw_ops
        assert 'Visible content' in draw_ops
        assert 'Elemento incluido' in draw_ops
        assert 'Mensaje de cierre' in draw_ops
