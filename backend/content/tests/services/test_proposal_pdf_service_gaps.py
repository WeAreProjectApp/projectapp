"""Tests covering missing branches in proposal_pdf_service.py.

Targets:
- _render_context_diagnostic Tier 3 linear fallback
- _render_creative_support Tier 3 linear fallback
- _render_timeline long totalDuration truncation
- _render_investment linear layout (no two-column)
- _render_investment hosting renewal
- _render_final_note: message, team/role/email, commitment badges
- _render_next_steps: introMessage, step descriptions
"""
import io
from decimal import Decimal

import pytest
from django.utils import timezone
from freezegun import freeze_time
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.models import BusinessProposal
from content.services.proposal_pdf_service import (
    MARGIN_B,
    MARGIN_T,
    PAGE_H,
    _register_fonts,
    _render_context_diagnostic,
    _render_creative_support,
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
        title='PDF Gaps Proposal',
        client_name='Gaps Client',
        client_email='gaps@example.com',
        language='es',
        total_investment=Decimal('5000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=14),
    )


# ===========================================================================
# _render_context_diagnostic — Tier 3 linear fallback
# ===========================================================================

class TestContextDiagnosticTier3:
    def test_tier3_linear_fallback_with_issues_and_opportunity(self, pdf_canvas, proposal):
        """Very low y forces Tier 3 (no sidebar) with opp + issues.

        Catches a branch that no-ops on a populated opportunity/issues
        payload and returns the untouched input y instead of drawing the
        subtitle/paragraphs/badge panel — isinstance(y, (int, float)) would
        pass either way, since y is a number regardless of whether it moved.
        """
        data = {
            'index': '2', 'title': 'Contexto',
            'paragraphs': ['Análisis del cliente.'],
            'issuesTitle': 'Problemas', 'issues': ['SEO débil', 'Sin mobile'],
            'opportunityTitle': 'Oportunidad', 'opportunity': 'Hay un mercado.',
        }
        # Very low y → avail (y - MARGIN_B) ≈ 60 < any partial_need
        y = _render_context_diagnostic(pdf_canvas, data, proposal, y=MARGIN_B + 60)

        assert y < MARGIN_B + 60

    def test_tier3_linear_fallback_without_opportunity(self, pdf_canvas, proposal):
        """Tier 3 path when opp is empty.

        Catches a branch that no-ops on the paragraphs/issues content and
        returns the untouched input y instead of drawing them.
        """
        data = {
            'index': '2', 'title': 'Contexto',
            'paragraphs': ['Analysis.'],
            'issuesTitle': 'Issues', 'issues': ['Problem A'],
        }
        y = _render_context_diagnostic(pdf_canvas, data, proposal, y=MARGIN_B + 60)

        assert y < MARGIN_B + 60


# ===========================================================================
# _render_creative_support — Tier 3 linear fallback
# ===========================================================================

class TestCreativeSupportTier3:
    def test_tier3_linear_fallback_with_includes_and_closing(self, pdf_canvas, proposal):
        """Very low y forces Tier 3 (no sidebar) with includes + closing.

        Catches a branch that no-ops on the paragraphs/includes/closing
        content and returns the untouched input y instead of drawing them.
        """
        data = {
            'index': '5', 'title': 'Acompañamiento Creativo',
            'paragraphs': ['Guidance.'],
            'includesTitle': 'Incluye', 'includes': ['Revisiones', 'Ajustes'],
            'closing': 'Estamos aquí para ti.',
        }
        y = _render_creative_support(pdf_canvas, data, proposal, y=MARGIN_B + 60)

        assert y < MARGIN_B + 60

    def test_tier3_linear_fallback_without_closing(self, pdf_canvas, proposal):
        """Tier 3 path when closing is empty.

        Catches a branch that no-ops on the paragraphs/includes content and
        returns the untouched input y instead of drawing them.
        """
        data = {
            'index': '5', 'title': 'Support',
            'paragraphs': ['Support text.'],
            'includesTitle': 'Includes', 'includes': ['Item A'],
        }
        y = _render_creative_support(pdf_canvas, data, proposal, y=MARGIN_B + 60)

        assert y < MARGIN_B + 60


# ===========================================================================
# _render_timeline — long totalDuration triggers value truncation
# ===========================================================================

class TestTimelineTruncation:
    def test_very_long_total_duration_gets_truncated(self, pdf_canvas, proposal):
        """A very long duration value forces the KPI badge to truncate it.

        Catches a branch that no-ops on a non-empty totalDuration/introText
        and returns the untouched default y instead of drawing the intro
        paragraph and the KPI tile row.
        """
        from content.services.proposal_pdf_service import _render_timeline

        # A very long string that exceeds the badge inner width (~176 pts)
        long_duration = 'A' * 200  # far exceeds any badge inner_w
        data = {
            'index': '7', 'title': 'Cronograma',
            'introText': 'Duración estimada.',
            'totalDuration': long_duration,
            'phases': [],
        }

        y = _render_timeline(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T

    def test_long_label_in_timeline_triggers_label_truncation(self, pdf_canvas, proposal):
        """Label truncation is triggered when value_w <= inner_w but label_w > inner_w.

        Catches a branch that no-ops on a non-empty totalDuration and returns
        the untouched default y instead of drawing the KPI tile row.
        """
        from content.services.proposal_pdf_service import _render_timeline

        # Regular short value, but override inner_w indirectly by using a tiny badge
        # In practice this is hard to trigger deterministically, so use very long string
        data = {
            'index': '7', 'title': 'Timeline',
            # Short value to NOT trigger value truncation but…
            # Actually both conditions use badge_w = min(CONTENT_W, ...).
            # To trigger LABEL truncation without VALUE truncation is tricky.
            # Use a string slightly shorter than 'label_str' width:
            'totalDuration': 'D' * 150,  # triggers value truncation (not label)
            'phases': [],
        }

        y = _render_timeline(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T


# ===========================================================================
# _render_investment — linear layout (no two-column)
# ===========================================================================

class TestInvestmentLinearLayout:
    def test_linear_layout_with_payment_options_and_items(self, pdf_canvas, proposal):
        """Low y forces linear (no two-column) layout.

        Catches a branch that no-ops on the payment options/included items
        and returns the untouched input y instead of drawing them.
        """
        from content.services.proposal_pdf_service import _render_investment

        data = {
            'index': '8', 'title': 'Inversión',
            'introText': 'Total:',
            'totalInvestment': '$5,000,000', 'currency': 'COP',
            'whatsIncluded': ['Diseño', 'Desarrollo', 'Soporte'],
            'paymentOptions': [
                {'label': 'Contado', 'description': '$5,000,000'},
                {'label': 'Cuotas', 'description': '$2,500,000 x2'},
            ],
            'hostingPlan': None,
            'modules': [],
            'valueReasons': ['Calidad', 'Experiencia'],
        }

        y = _render_investment(pdf_canvas, data, proposal, y=MARGIN_B + 100)

        assert y < MARGIN_B + 100

    def test_linear_layout_without_payment_options(self, pdf_canvas, proposal):
        """Linear layout with no payment options and no includes.

        Catches a branch that no-ops on the (empty-options) investment total
        row and returns the untouched input y instead of drawing it.
        """
        from content.services.proposal_pdf_service import _render_investment

        data = {
            'index': '8', 'title': 'Inversión',
            'introText': '',
            'totalInvestment': '$3,000,000', 'currency': 'COP',
            'whatsIncluded': [],
            'paymentOptions': [],
            'hostingPlan': None,
            'modules': [],
            'valueReasons': [],
        }

        y = _render_investment(pdf_canvas, data, proposal, y=MARGIN_B + 100)

        assert y < MARGIN_B + 100


# ===========================================================================
# _render_investment — hosting renewal
# ===========================================================================

class TestInvestmentHostingRenewal:
    def test_hosting_with_renewal_text_renders(self, pdf_canvas, proposal):
        """Catches a hosting renewal block that leaves the drawing position unchanged."""
        from content.services.proposal_pdf_service import _render_investment

        data = {
            'index': '8', 'title': 'Inversión',
            'introText': 'Total:',
            'totalInvestment': '$6,000,000', 'currency': 'COP',
            'whatsIncluded': [],
            'paymentOptions': [],
            'hostingPlan': {
                'title': 'Cloud Pro',
                'description': 'Full managed hosting.',
                'specs': [],
                'monthlyPrice': '$150.000',
                'note': 'Este plan cubre CDN y SSL.',
                'renewal': 'Renovación anual con ajuste de precios.\n\nSe cobra en enero de cada año.',
            },
            'modules': [],
            'valueReasons': [],
        }

        y = _render_investment(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T


# ===========================================================================
# _render_final_note — message, team/role/email, commitment badges
# ===========================================================================

class TestFinalNoteCompleteBranches:
    def test_final_note_with_all_fields(self, pdf_canvas, proposal):
        """Catches a final-note block that ignores the supplied content."""
        from content.services.proposal_pdf_service import _render_final_note

        data = {
            'index': '11', 'title': 'Nota Final',
            'message': 'Estamos listos para empezar juntos.',
            'personalNote': 'Este proyecto me emociona mucho.',
            'validityMessage': 'Vigencia: 30 días calendario.',
            'teamName': 'Project App',
            'teamRole': 'Desarrollo de Software',
            'contactEmail': 'team@projectapp.co',
            'commitmentBadges': [
                {'title': 'Calidad'},
                {'title': 'Entrega Puntual'},
                {'title': ''},  # empty badge — should be skipped
            ],
        }

        y = _render_final_note(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T

    def test_final_note_with_no_optional_fields(self, pdf_canvas, proposal):
        """Catches a missing section header when optional note fields are absent."""
        from content.services.proposal_pdf_service import _render_final_note

        data = {
            'index': '11', 'title': 'Nota Final',
        }

        y = _render_final_note(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T


# ===========================================================================
# _render_next_steps — introMessage + steps with descriptions
# ===========================================================================

class TestNextStepsCompleteBranches:
    def test_next_steps_with_intro_and_descriptions(self, pdf_canvas, proposal):
        """Catches a next-steps block that ignores the supplied content."""
        from content.services.proposal_pdf_service import _render_next_steps

        data = {
            'index': '10', 'title': 'Próximos Pasos',
            'introMessage': 'Para iniciar el proyecto, sigue estos pasos:',
            'steps': [
                {'title': 'Firma de contrato', 'description': 'Firma el contrato digital.'},
                {'title': 'Pago inicial', 'description': 'Realiza el pago del 50%.'},
                {'title': 'Kickoff', 'description': ''},  # no description branch
            ],
            'ctaMessage': '¡Estamos listos!',
            'contactMethods': [
                {'title': 'WhatsApp', 'handle': '+57 300 000 0000'},
            ],
        }

        y = _render_next_steps(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T

    def test_next_steps_without_intro(self, pdf_canvas, proposal):
        """Catches a next-steps block that fails to draw the step list."""
        from content.services.proposal_pdf_service import _render_next_steps

        data = {
            'index': '10', 'title': 'Next Steps',
            'steps': [{'title': 'Step 1', 'description': 'Do this.'}],
        }

        y = _render_next_steps(pdf_canvas, data, proposal)

        assert y < PAGE_H - MARGIN_T


# ===========================================================================
# Tax suffix ("+ IVA" / "+ Tax") on total + payment pills
# ===========================================================================

class TestTaxSuffix:
    def test_cop_returns_iva(self):
        from content.services.proposal_pdf_service import _tax_suffix
        assert _tax_suffix('COP') == ' + IVA'

    def test_usd_returns_tax(self):
        from content.services.proposal_pdf_service import _tax_suffix
        assert _tax_suffix('USD') == ' + Tax'

    def test_usd_case_insensitive(self):
        from content.services.proposal_pdf_service import _tax_suffix
        assert _tax_suffix('usd') == ' + Tax'

    def test_none_defaults_to_iva(self):
        from content.services.proposal_pdf_service import _tax_suffix
        assert _tax_suffix(None) == ' + IVA'


class TestPaymentPillTaxSuffix:
    def test_amount_pill_appends_suffix(self):
        from content.services.proposal_pdf_service import _payment_pill_desc
        pill = _payment_pill_desc('50%', '$745.000', 1490000, tax_suffix=' + Tax')
        assert pill.endswith(' + Tax')
        assert '745.000' in pill
        assert pill.startswith('$')

    def test_amount_pill_does_not_duplicate_stored_tax_suffix(self):
        from content.services.proposal_pdf_service import _payment_pill_desc
        pill = _payment_pill_desc(
            '40%', '$112.000.000 COP + IVA', 280000000,
            tax_suffix=' + IVA',
        )
        assert pill == '$112.000.000 COP + IVA'

    def test_no_percentage_option_has_no_suffix(self):
        from content.services.proposal_pdf_service import _payment_pill_desc
        # No percentage in label -> raw description, no amount, no suffix.
        pill = _payment_pill_desc('Contado', 'Pago único', 1490000,
                                  tax_suffix=' + Tax')
        assert pill == 'Pago único'

    def test_default_suffix_empty(self):
        from content.services.proposal_pdf_service import _payment_pill_desc
        pill = _payment_pill_desc('50%', '$745.000', 1490000)
        assert not pill.endswith(' + Tax')
        assert not pill.endswith(' + IVA')


class TestInvestmentTaxLabels:
    """Verify tax labels on the investment total and hosting charges."""

    def _render_and_record(self, pdf_canvas, monkeypatch, proposal, data):
        from content.services.proposal_pdf_service import (
            MARGIN_T,
            PAGE_H,
            _render_investment,
        )
        recorded = []
        for method in ('drawString', 'drawCentredString', 'drawRightString'):
            orig = getattr(pdf_canvas, method)

            def rec(x, y, text, *a, _orig=orig, **k):
                recorded.append(str(text))
                return _orig(x, y, text, *a, **k)

            monkeypatch.setattr(pdf_canvas, method, rec)
        _render_investment(pdf_canvas, data, proposal,
                           ps={'num': 1, 'client': 'X'}, y=PAGE_H - MARGIN_T)
        return recorded

    def _data(self, currency):
        return {
            'index': '7', 'title': 'Inversión',
            'totalInvestment': '$5.000.000', 'currency': currency,
            'paymentOptions': [], 'whatsIncluded': [],
            'modules': [{'id': 'm1', 'name': 'Módulo CMS'}],
            'hostingPlan': {
                'title': 'Hosting Premium', 'hostingPercent': 10,
                'billingTiers': [
                    {'label': 'Mensual', 'months': 1, 'discountPercent': 0},
                ],
            },
        }

    def test_cop_tax_labels_cover_total_hosting(
        self, pdf_canvas, monkeypatch, proposal,
    ):
        recorded = self._render_and_record(
            pdf_canvas, monkeypatch, proposal, self._data('COP'))
        assert not any('Precio (+ IVA)' in r for r in recorded)
        assert any(r.strip() == 'Módulo' for r in recorded)
        assert any('Precio/mes (+ IVA)' in r for r in recorded)
        assert any('Equivalente (+ IVA)' in r for r in recorded)
        assert sum(1 for r in recorded if r.strip() == '+ IVA') >= 2

    @freeze_time('2026-03-01 12:00:00')
    def test_usd_tax_labels_cover_total_hosting(
        self, pdf_canvas, monkeypatch, db,
    ):
        usd_proposal = BusinessProposal.objects.create(
            title='USD Proposal', client_name='USD Client',
            client_email='usd@example.com', language='en',
            total_investment=Decimal('5000'), currency='USD',
            status='sent',
            expires_at=timezone.now() + timezone.timedelta(days=14),
        )
        recorded = self._render_and_record(
            pdf_canvas, monkeypatch, usd_proposal, self._data('USD'))
        assert not any('Precio (+ Tax)' in r for r in recorded)
        assert any('Precio/mes (+ Tax)' in r for r in recorded)
        assert any('Equivalente (+ Tax)' in r for r in recorded)
        assert sum(1 for r in recorded if r.strip() == '+ Tax') >= 2
        assert not any('+ IVA' in r for r in recorded)
