"""Tests for ProposalPdfService.

Covers: _strip_emoji, _safe helpers, drawing helpers,
section renderers, generate() happy/error paths,
_merge_with_covers, generate_to_file.
"""
import io
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from freezegun import freeze_time
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.pdfgen import canvas

from content.models import (
    BusinessProposal,
    ProposalChangeLog,
    ProposalSection,
)
from content.services.pdf_utils import _draw_green_bar
from content.services.proposal_pdf_service import (
    CONTENT_W,
    ESMERALD,
    LEMON,
    MARGIN_B,
    MARGIN_L,
    MARGIN_T,
    PAGE_H,
    SECTION_RENDERERS,
    ProposalPdfService,
    _clean_inline_bold,
    _clean_url_display,
    _draw_banner_box,
    _draw_bullet_list,
    _draw_footer,
    _draw_line_with_links,
    _draw_paragraphs,
    _draw_pill,
    _draw_section_header,
    _draw_sidebar_box,
    _draw_subtitle,
    _font,
    _format_cop,
    _parse_markdown_lines,
    _register_fonts,
    _render_context_diagnostic,
    _render_creative_support,
    _render_design_ux,
    _render_executive_summary,
    _render_linked_requirements,
    _render_raw_text,
    _replace_urls_with_placeholders,
    _safe,
    _strip_emoji,
    default_selected_modules_from_content,
)

pytestmark = pytest.mark.django_db


# ── Data builders ─────────────────────────────────────────────

_HOSTING_PLAN_WITH_SPECS = {
    'title': 'Cloud Pro',
    'description': 'Full managed hosting.',
    'specs': [
        {'label': 'Storage', 'value': '50 GB'},
        {'label': 'Bandwidth', 'value': 'Unlimited'},
        {'label': 'SSL', 'value': 'Included'},
    ],
    'monthlyPrice': '$150.000',
    'monthlyLabel': 'por mes',
    'annualPrice': '$1.500.000',
    'annualLabel': 'pago anual',
    'coverageNote': 'Hosting covers domain, SSL, and CDN.',
}


def _investment_content_json(**overrides):
    """Build investment section content_json with sensible defaults."""
    base = {
        'index': '4', 'title': 'Inversión',
        'introText': 'Total:',
        'totalInvestment': '$5,000,000', 'currency': 'COP',
        'whatsIncluded': [],
        'paymentOptions': [],
        'hostingPlan': {'title': 'Cloud', 'description': 'Included.'},
        'modules': [],
        'valueReasons': [],
    }
    base.update(overrides)
    return base


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def pdf_canvas():
    """A ReportLab canvas backed by an in-memory buffer."""
    _register_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c._test_buf = buf
    return c


@pytest.fixture
def proposal_with_sections(db):
    """Proposal with all 12 section types enabled."""
    p = BusinessProposal.objects.create(
        title='PDF Test Proposal',
        client_name='Test Client',
        client_email='test@example.com',
        language='es',
        total_investment=Decimal('5000000'),
        currency='COP',
        status='sent',
        expires_at=timezone.now() + timezone.timedelta(days=20),
    )
    sections_data = [
        ('greeting', 'Saludo', 0, {
            'clientName': 'Test Client',
            'inspirationalQuote': 'Design is how it works.',
        }),
        ('executive_summary', 'Resumen ejecutivo', 1, {
            'index': '1', 'title': 'Resumen ejecutivo',
            'paragraphs': ['Primera línea.', 'Segunda línea.'],
            'highlightsTitle': 'Puntos clave',
            'highlights': ['Diseño', 'Desarrollo'],
        }),
        ('context_diagnostic', 'Contexto', 2, {
            'index': '2', 'title': 'Contexto y diagnóstico',
            'paragraphs': ['Análisis del cliente.'],
            'issuesTitle': 'Problemas', 'issues': ['SEO débil'],
            'opportunityTitle': 'Oportunidad', 'opportunity': 'Crecer.',
        }),
        ('conversion_strategy', 'Estrategia', 3, {
            'index': '3', 'title': 'Estrategia de conversión',
            'intro': 'Se construirá una página.',
            'steps': [{'title': 'Paso 1', 'bullets': ['Acción A']}],
            'resultTitle': 'Resultado', 'result': 'Más clientes.',
        }),
        ('design_ux', 'Diseño UX', 4, {
            'index': '4', 'title': 'Diseño Visual',
            'paragraphs': ['El sitio será moderno.'],
            'focusTitle': 'Enfoque', 'focusItems': ['Mobile first'],
            'objectiveTitle': 'Objetivo', 'objective': 'Impactar.',
        }),
        ('creative_support', 'Soporte Creativo', 5, {
            'index': '5', 'title': 'Acompañamiento Creativo',
            'paragraphs': ['Acompañamiento cercano.'],
            'includesTitle': 'Incluye', 'includes': ['Revisiones'],
            'closing': 'Estamos aquí para ti.',
        }),
        ('development_stages', 'Etapas', 6, {
            'title': 'Etapas de Desarrollo',
            'stages': [
                {'title': 'Propuesta', 'description': 'Etapa inicial.', 'current': True},
                {'title': 'Desarrollo', 'description': 'Construcción.', 'current': False},
            ],
        }),
        ('functional_requirements', 'Requerimientos', 7, {
            'index': '7', 'title': 'Requerimientos Funcionales',
            'intro': 'Detalle de requerimientos.',
            'groups': [
                {
                    'title': 'Vistas',
                    'description': 'Pantallas del sitio.',
                    'items': [{'name': 'Home', 'description': 'Página de inicio.'}],
                },
            ],
            'additionalModules': [],
        }),
        ('timeline', 'Cronograma', 8, {
            'index': '8', 'title': 'Cronograma',
            'introText': 'Fases del proyecto.',
            'totalDuration': '1 mes',
            'phases': [{
                'title': 'Diseño', 'duration': '1 semana',
                'description': 'Diseño visual.',
                'tasks': ['Wireframes', 'Mockups'],
                'milestone': 'Aprobación de diseño',
            }],
        }),
        ('investment', 'Inversión', 9, {
            'index': '9', 'title': 'Inversión',
            'introText': 'La inversión total es:',
            'totalInvestment': '$5,000,000', 'currency': 'COP',
            'whatsIncluded': [
                {'icon': '🎨', 'title': 'Diseño', 'description': 'UX/UI'},
            ],
            'paymentOptions': [
                {'label': '50% inicio', 'description': '$2,500,000 COP'},
            ],
            'hostingPlan': {'title': 'Cloud 1', 'description': 'Hosting incluido.'},
            'valueReasons': ['Calidad', 'Soporte'],
        }),
        ('final_note', 'Nota Final', 10, {
            'index': '10', 'title': 'Nota Final',
            'message': 'Gracias por considerar nuestra propuesta.',
            'personalNote': 'Es un placer trabajar contigo.',
            'teamName': 'Project App', 'teamRole': 'CEO',
            'contactEmail': 'team@projectapp.co',
            'commitmentBadges': [
                {'icon': '🤝', 'title': 'Calidad', 'description': 'Garantizada'},
            ],
        }),
        ('next_steps', 'Próximos pasos', 11, {
            'index': '11', 'title': 'Próximos pasos',
            'introMessage': 'Estamos listos.',
            'steps': [
                {'title': 'Revisión', 'description': 'Revisar propuesta.'},
            ],
            'ctaMessage': 'Agenda una llamada.',
            'contactMethods': [
                {'icon': '📧', 'title': 'Email', 'value': 'team@projectapp.co'},
            ],
        }),
    ]
    for stype, title, order, content in sections_data:
        ProposalSection.objects.create(
            proposal=p, section_type=stype,
            title=title, order=order,
            is_enabled=True, content_json=content,
        )
    return p


# ── _strip_emoji tests ───────────────────────────────────────

class TestStripEmoji:
    def test_removes_standard_emoji(self):
        """Standard emoji characters are stripped from the string."""
        assert _strip_emoji('Hello 🎨 World') == 'Hello  World'

    def test_removes_multiple_emojis(self):
        result = _strip_emoji('✅ Done 🚀 Launch 🎯 Target')
        assert '✅' not in result
        assert '🚀' not in result
        assert '🎯' not in result

    def test_preserves_plain_latin_text(self):
        """Plain ASCII text passes through unchanged."""
        assert _strip_emoji('Hello World') == 'Hello World'

    def test_preserves_accented_characters(self):
        """Accented Latin characters are preserved."""
        assert _strip_emoji('Diseño gráfico') == 'Diseño gráfico'

    def test_returns_empty_for_none(self):
        """None input returns None."""
        assert _strip_emoji(None) is None

    def test_returns_empty_for_empty_string(self):
        """Empty string returns empty string."""
        assert _strip_emoji('') == ''

    def test_removes_variation_selectors(self):
        result = _strip_emoji('⚙️ Settings')
        assert 'Settings' in result

    def test_removes_geometric_shapes(self):
        result = _strip_emoji('■ Square ● Circle')
        assert '■' not in result
        assert '●' not in result

    def test_br_tag_replaced_with_space(self):
        """HTML <br> tags are replaced with a space."""
        assert _strip_emoji('Line one<br>Line two') == 'Line one Line two'

    def test_br_self_closing_replaced_with_space(self):
        """Self-closing <br/> tags are replaced with a space."""
        assert _strip_emoji('A<br/>B') == 'A B'

    def test_br_with_space_replaced(self):
        """Self-closing <br /> tags with space are replaced."""
        assert _strip_emoji('A<br />B') == 'A B'

    def test_br_case_insensitive(self):
        """Uppercase <BR> tags are replaced with a space."""
        assert _strip_emoji('A<BR>B') == 'A B'

    def test_bold_html_converted_to_markdown(self):
        """HTML <b> tags are converted to ** markdown bold markers."""
        assert _strip_emoji('una <b>exigencia</b> clara') == 'una **exigencia** clara'

    def test_italic_html_tags_stripped(self):
        """HTML <i> and </i> italic tags are stripped from text."""
        assert _strip_emoji('texto <i>importante</i> aquí') == 'texto importante aquí'

    def test_mixed_html_bold_preserved_others_stripped(self):
        """Bold <b> tags become ** markers; other HTML tags are stripped."""
        assert _strip_emoji('<b>bold</b> and <i>italic</i>') == '**bold** and italic'


# ── _safe tests ───────────────────────────────────────────────

class TestSafe:
    def test_returns_value_for_existing_key(self):
        """Existing key with a truthy value is returned."""
        assert _safe({'name': 'Alice'}, 'name') == 'Alice'

    def test_returns_default_for_missing_key(self):
        """Missing key falls back to the provided default."""
        assert _safe({}, 'name', 'Unknown') == 'Unknown'

    def test_returns_default_for_none_value(self):
        """None value falls back to the default."""
        assert _safe({'name': None}, 'name', 'Default') == 'Default'

    def test_returns_default_for_empty_string_value(self):
        """Empty string value falls back to the default."""
        assert _safe({'name': ''}, 'name', 'Default') == 'Default'

    def test_returns_empty_string_default(self):
        """No explicit default returns empty string."""
        assert _safe({}, 'name') == ''

    def test_returns_default_for_non_dict(self):
        """Non-dict input falls back to the default."""
        assert _safe('not_a_dict', 'key', 'fallback') == 'fallback'

    def test_returns_list_default(self):
        """List default is returned for missing key."""
        assert _safe({}, 'items', []) == []

    def test_returns_existing_list(self):
        """Existing list value is returned over the default."""
        assert _safe({'items': [1, 2]}, 'items', []) == [1, 2]


_INVESTMENT_DATA = {
    'index': '9', 'title': 'Investment',
    'introText': 'Total:',
    'totalInvestment': '$5,000,000', 'currency': 'COP',
    'whatsIncluded': [{'title': 'Design', 'description': 'UX'}],
    'paymentOptions': [{'label': '50%', 'description': '$2.5M'}],
    'hostingPlan': {'title': 'Cloud', 'description': 'Included.'},
    'valueReasons': ['Quality'],
}

_FINAL_NOTE_DATA = {
    'index': '10', 'title': 'Final Note',
    'message': 'Thank you.',
    'personalNote': 'A pleasure.',
    'teamName': 'Team', 'teamRole': 'CEO',
    'contactEmail': 'team@test.com',
    'commitmentBadges': [{'title': 'Quality', 'description': 'Guaranteed'}],
}


def _calculator_module_group(**overrides):
    """Build an optional proposal module group with sensible defaults."""
    base = {
        'id': 'pwa_module', 'title': 'PWA',
        'is_calculator_module': True,
        'is_always_included': False,
        'default_selected': False,
        'is_visible': True,
        'description': 'Progressive Web App.',
        'items': [{'name': 'Offline', 'description': 'Works offline.'}],
    }
    base.update(overrides)
    return base


def _fr_section_content_json(groups=None, **overrides):
    """Build functional_requirements section content_json."""
    base = {
        'index': '1', 'title': 'Requirements',
        'intro': '',
        'groups': groups or [],
        'additionalModules': [],
    }
    base.update(overrides)
    return base


def _final_note_data(**overrides):
    """Build final note section data with sensible defaults."""
    base = dict(_FINAL_NOTE_DATA)
    base.update(overrides)
    return base


# ── Drawing helper tests ─────────────────────────────────────

class TestDrawGreenBar:
    def test_draws_without_error(self, pdf_canvas):
        ops_before = len(pdf_canvas._code)
        _draw_green_bar(pdf_canvas)
        assert len(pdf_canvas._code) > ops_before


class TestDrawFooter:
    def test_draws_footer_without_error(self, pdf_canvas):
        ops_before = len(pdf_canvas._code)
        _draw_footer(pdf_canvas, 1, 10, 'Test Client')
        assert len(pdf_canvas._code) > ops_before

    def test_draws_footer_with_empty_client_name(self, pdf_canvas):
        ops_before = len(pdf_canvas._code)
        _draw_footer(pdf_canvas, 1, 5, '')
        assert len(pdf_canvas._code) > ops_before


class TestDrawPill:
    def test_returns_right_x_and_bottom_y(self, pdf_canvas):
        right_x, bottom_y = _draw_pill(
            pdf_canvas, MARGIN_L, PAGE_H - 100, 'Test Badge',
        )
        assert right_x > MARGIN_L
        assert bottom_y < PAGE_H - 100

    def test_custom_colors(self, pdf_canvas):
        right_x, _ = _draw_pill(
            pdf_canvas, MARGIN_L, PAGE_H - 100, 'COP',
            bg_color=LEMON, text_color=ESMERALD, font_size=8,
        )
        assert right_x > MARGIN_L


class TestDrawBannerBox:
    def test_returns_lower_y(self, pdf_canvas):
        start_y = PAGE_H - 100
        end_y = _draw_banner_box(
            pdf_canvas, MARGIN_L, start_y, CONTENT_W,
            'Test banner text', icon_text='Info:',
        )
        assert end_y < start_y


class TestDrawSectionHeader:
    def test_returns_lower_y_after_drawing(self, pdf_canvas):
        start_y = PAGE_H - 50
        end_y = _draw_section_header(pdf_canvas, start_y, '1', 'Test Title')
        assert end_y < start_y

    def test_wraps_long_title(self, pdf_canvas):
        start_y = PAGE_H - 50
        long_title = 'A' * 100
        end_y = _draw_section_header(pdf_canvas, start_y, '1', long_title)
        assert end_y < start_y - 30

    def test_draws_without_index(self, pdf_canvas):
        start_y = PAGE_H - 50
        end_y = _draw_section_header(pdf_canvas, start_y, '', 'No Index')
        assert end_y < start_y


class TestDrawParagraphs:
    def test_returns_lower_y_after_drawing(self, pdf_canvas):
        start_y = 500
        end_y = _draw_paragraphs(pdf_canvas, start_y, ['Test paragraph.'])
        assert end_y < start_y

    def test_skips_empty_paragraphs(self, pdf_canvas):
        start_y = 500
        end_y = _draw_paragraphs(pdf_canvas, start_y, ['', None, 'Valid'])
        assert end_y < start_y

    def test_handles_empty_list(self, pdf_canvas):
        start_y = 500
        end_y = _draw_paragraphs(pdf_canvas, start_y, [])
        assert end_y == start_y

    def test_br_tags_not_rendered_as_text(self, pdf_canvas):
        """Paragraph containing <br> tags renders without literal tag text."""
        start_y = 500
        end_y = _draw_paragraphs(
            pdf_canvas, start_y, ['First line<br>Second line'],
        )
        assert end_y < start_y

    def test_bold_html_tags_not_rendered_as_text(self, pdf_canvas):
        """Paragraph containing <b> tags renders without literal tag text."""
        start_y = 500
        end_y = _draw_paragraphs(
            pdf_canvas, start_y,
            ['una <b>exigencia regulatoria</b> y una <b>oportunidad</b>'],
        )
        assert end_y < start_y

    def test_stops_at_page_bottom(self, pdf_canvas):
        end_y = _draw_paragraphs(pdf_canvas, MARGIN_B + 10, ['Text'])
        assert end_y == MARGIN_B + 10


class TestDrawBulletList:
    def test_returns_lower_y_after_drawing(self, pdf_canvas):
        start_y = 400
        end_y = _draw_bullet_list(pdf_canvas, start_y, ['Item A', 'Item B'])
        assert end_y < start_y

    def test_handles_empty_list(self, pdf_canvas):
        start_y = 400
        end_y = _draw_bullet_list(pdf_canvas, start_y, [])
        assert end_y == start_y

    def test_br_tags_not_rendered_as_text(self, pdf_canvas):
        """Bullet item containing <br> tags renders without literal tag text."""
        start_y = 400
        end_y = _draw_bullet_list(
            pdf_canvas, start_y, ['Item with<br>line break'],
        )
        assert end_y < start_y


class TestDrawSidebarBox:
    def test_returns_box_bottom_y(self, pdf_canvas):
        box_y = _draw_sidebar_box(
            pdf_canvas, 500, 'Test', ['Item 1', 'Item 2'],
        )
        assert box_y < 500

    def test_handles_empty_items(self, pdf_canvas):
        box_y = _draw_sidebar_box(pdf_canvas, 500, 'Empty', [])
        assert box_y < 500


class TestDrawSubtitle:
    def test_leaves_space_before_next_paragraph(self, pdf_canvas):
        end_y = _draw_subtitle(pdf_canvas, 400, 'Subtitle')
        _draw_paragraphs(pdf_canvas, end_y, ['Following paragraph'])
        rendered = []
        reader = PdfReader(io.BytesIO(pdf_canvas.getpdfdata()))

        reader.pages[0].extract_text(visitor_text=lambda text, cm, tm, font, size: rendered.append((text, tm[5])))

        title_y = next(y for text, y in rendered if 'Subtitle' in text)
        paragraph_y = next(y for text, y in rendered if 'Following paragraph' in text)
        assert title_y - paragraph_y >= 24


# ── Section renderer tests ───────────────────────────────────

class TestSectionRenderers:
    def test_greeting_renders_without_error(self, pdf_canvas, proposal):
        data = {'clientName': 'Test', 'inspirationalQuote': 'Be great.'}
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['greeting'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_greeting_renders_with_long_name(self, pdf_canvas, proposal):
        data = {'clientName': 'A' * 50, 'inspirationalQuote': ''}
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['greeting'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_executive_summary_renders(self, pdf_canvas, proposal):
        data = {
            'index': '1', 'title': 'Summary',
            'paragraphs': ['Paragraph one.'],
            'highlightsTitle': 'Key', 'highlights': ['Point'],
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['executive_summary'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_context_diagnostic_renders(self, pdf_canvas, proposal):
        data = {
            'index': '2', 'title': 'Context',
            'paragraphs': ['Analysis.'],
            'issuesTitle': 'Issues', 'issues': ['SEO'],
            'opportunityTitle': 'Opportunity', 'opportunity': 'Growth.',
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['context_diagnostic'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_conversion_strategy_renders(self, pdf_canvas, proposal):
        data = {
            'index': '3', 'title': 'Strategy',
            'intro': 'Build trust.',
            'steps': [{'title': 'Step 1', 'bullets': ['A']}],
            'resultTitle': 'Result', 'result': 'More clients.',
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['conversion_strategy'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_design_ux_renders(self, pdf_canvas, proposal):
        data = {
            'index': '4', 'title': 'Design',
            'paragraphs': ['Modern.'],
            'focusTitle': 'Focus', 'focusItems': ['Mobile'],
            'objectiveTitle': 'Objective', 'objective': 'Impact.',
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['design_ux'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_creative_support_renders(self, pdf_canvas, proposal):
        data = {
            'index': '5', 'title': 'Support',
            'paragraphs': ['Guidance.'],
            'includesTitle': 'Includes', 'includes': ['Reviews'],
            'closing': 'We are here.',
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['creative_support'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_development_stages_renders(self, pdf_canvas, proposal):
        data = {
            'title': 'Stages',
            'stages': [
                {'title': 'Phase 1', 'description': 'Start.', 'current': True},
                {'title': 'Phase 2', 'description': 'Build.', 'current': False},
            ],
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['development_stages'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_functional_requirements_returns_y_and_stores_groups(self, pdf_canvas, proposal):
        """functional_requirements returns a y-position and stores groups in ps."""
        ps = {'num': 1, 'client': 'Test'}
        data = {
            'index': '7', 'title': 'Requirements',
            'intro': 'Details.',
            'groups': [{'title': 'Views', 'description': 'Pages.', 'items': []}],
            'additionalModules': [],
        }
        result = SECTION_RENDERERS['functional_requirements'](
            pdf_canvas, data, proposal, ps=ps,
        )
        assert isinstance(result, (int, float))
        assert result < PAGE_H - 50
        assert '_func_req_groups' in ps
        assert len(ps['_func_req_groups']) >= 1

    def test_timeline_renders(self, pdf_canvas, proposal):
        """Timeline section renders phases without error."""
        data = {
            'index': '8', 'title': 'Timeline',
            'introText': 'Phases.',
            'totalDuration': '1 month',
            'phases': [{
                'title': 'Design', 'duration': '1 week',
                'description': 'Visual design.',
                'tasks': ['Wireframes'],
                'milestone': 'Approval',
            }],
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['timeline'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_investment_renders(self, pdf_canvas, proposal):
        """Investment section renders pricing info without error."""
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['investment'](pdf_canvas, _INVESTMENT_DATA, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_final_note_renders(self, pdf_canvas, proposal):
        """Final note section renders team info without error."""
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['final_note'](pdf_canvas, _FINAL_NOTE_DATA, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_next_steps_renders(self, pdf_canvas, proposal):
        data = {
            'index': '11', 'title': 'Next Steps',
            'introMessage': 'Ready.',
            'steps': [{'title': 'Review', 'description': 'Check.'}],
            'ctaMessage': 'Call us.',
            'contactMethods': [{'title': 'Email', 'value': 'team@test.com'}],
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['next_steps'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before


class TestRenderRawText:
    def test_renders_paste_mode_section(self, pdf_canvas, proposal):
        data = {
            'index': '12', 'title': 'Custom',
            'rawText': 'Custom content from paste mode.',
        }
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_renders_markdown_headings(self, pdf_canvas, proposal):
        data = {
            'index': '1', 'title': 'Markdown Test',
            'rawText': '# Heading 1\n## Heading 2\n### Heading 3\nParagraph.',
        }
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_renders_markdown_bullets(self, pdf_canvas, proposal):
        data = {
            'index': '1', 'title': 'Bullets',
            'rawText': '- Item one\n- Item two\n* Item three',
        }
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_renders_numbered_list(self, pdf_canvas, proposal):
        data = {
            'index': '1', 'title': 'Numbered',
            'rawText': '1. First\n2. Second\n3. Third',
        }
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_renders_bold_lines(self, pdf_canvas, proposal):
        data = {
            'index': '1', 'title': 'Bold',
            'rawText': '**Bold line**\nNormal text with **inline bold** here.',
        }
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_handles_empty_raw_text(self, pdf_canvas, proposal):
        data = {'index': '1', 'title': 'Empty', 'rawText': ''}
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_br_tags_in_raw_text_converted(self, pdf_canvas, proposal):
        """Raw text with <br> tags renders correctly without literal tags."""
        data = {
            'index': '1', 'title': 'BR Test',
            'rawText': 'First line<br>Second line<br/>Third line',
        }
        page_before = pdf_canvas.getPageNumber()
        _render_raw_text(pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before


class TestParseMarkdownLines:
    def test_parses_headings(self):
        tokens = _parse_markdown_lines('# H1\n## H2\n### H3\n#### H4')
        assert tokens == [
            ('h1', 'H1'), ('h2', 'H2'), ('h3', 'H3'), ('h4', 'H4'),
        ]

    def test_parses_bullets(self):
        tokens = _parse_markdown_lines('- Apple\n* Banana')
        assert tokens == [('bullet', 'Apple'), ('bullet', 'Banana')]

    def test_parses_numbered_list(self):
        tokens = _parse_markdown_lines('1. First\n2. Second')
        assert tokens == [('numbered', 'First'), ('numbered', 'Second')]

    def test_parses_bold_line(self):
        tokens = _parse_markdown_lines('**Bold Title**')
        assert tokens == [('bold_line', 'Bold Title')]

    def test_parses_paragraph(self):
        tokens = _parse_markdown_lines('Just a normal line.')
        assert tokens == [('paragraph', 'Just a normal line.')]

    def test_parses_blank_lines(self):
        tokens = _parse_markdown_lines('Line 1\n\nLine 2')
        assert tokens == [
            ('paragraph', 'Line 1'), ('blank', ''), ('paragraph', 'Line 2'),
        ]

    def test_returns_empty_for_none(self):
        """None input returns an empty token list."""
        assert _parse_markdown_lines(None) == []

    def test_returns_empty_for_empty_string(self):
        """Empty string returns an empty token list."""
        assert _parse_markdown_lines('') == []

    def test_br_tags_converted_to_newlines(self):
        """HTML <br> tags are converted to newlines producing separate tokens."""
        tokens = _parse_markdown_lines('Line one<br>Line two')
        assert tokens == [
            ('paragraph', 'Line one'),
            ('paragraph', 'Line two'),
        ]

    def test_br_self_closing_converted(self):
        """Self-closing <br/> tags produce separate paragraph tokens."""
        tokens = _parse_markdown_lines('Alpha<br/>Beta')
        assert tokens == [
            ('paragraph', 'Alpha'),
            ('paragraph', 'Beta'),
        ]

    def test_bold_html_converted_to_markdown_bold(self):
        """HTML <b> tags are converted to ** markers in paragraph tokens."""
        tokens = _parse_markdown_lines('una <b>exigencia regulatoria</b> clara')
        assert tokens == [
            ('paragraph', 'una **exigencia regulatoria** clara'),
        ]


class TestCleanInlineBold:
    def test_removes_bold_markers(self):
        """Double-asterisk bold markers are stripped."""
        assert _clean_inline_bold('Use **bold** text') == 'Use bold text'

    def test_handles_multiple_bold(self):
        result = _clean_inline_bold('**A** and **B**')
        assert result == 'A and B'

    def test_preserves_non_bold_text(self):
        """Text without bold markers passes through unchanged."""
        assert _clean_inline_bold('No bold here') == 'No bold here'

    def test_removes_italic_markers(self):
        """Single-asterisk italic markers are stripped."""
        assert _clean_inline_bold('Use *italic* text') == 'Use italic text'

    def test_removes_bold_italic_markers(self):
        """Triple-asterisk bold-italic markers are stripped."""
        assert _clean_inline_bold('Use ***bold-italic*** text') == 'Use bold-italic text'

    def test_removes_mixed_markers(self):
        """Bold, italic, and bold-italic markers all stripped in one pass."""
        result = _clean_inline_bold('***A*** **B** *C* plain')
        assert result == 'A B C plain'


class TestSectionRenderersMap:
    def test_contains_all_section_types(self):
        expected = {
            'greeting', 'executive_summary', 'context_diagnostic',
            'conversion_strategy', 'design_ux', 'creative_support',
            'development_stages', 'process_methodology',
            'functional_requirements',
            'timeline', 'investment', 'value_added_modules',
            'commercial_conditions', 'roi_projection',
            'final_note', 'next_steps',
        }
        assert set(SECTION_RENDERERS.keys()) == expected


# ── ProposalPdfService.generate tests ─────────────────────────

class TestGenerate:
    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_returns_pdf_bytes(self, mock_back, mock_cover, proposal_with_sections):
        """Generate produces valid PDF bytes for a proposal with sections."""
        result = ProposalPdfService.generate(proposal_with_sections)

        assert result is not None
        assert isinstance(result, bytes)
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_generates_multiple_pages(self, mock_back, mock_cover, proposal_with_sections):
        """Multiple sections produce at least 2 PDF pages."""
        from pypdf import PdfReader

        pdf_bytes = ProposalPdfService.generate(proposal_with_sections)
        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 2
        mock_cover.exists.assert_called()

    @patch('content.services.proposal_pdf_service.canvas.Canvas')
    def test_returns_none_on_exception(self, mock_canvas_cls, proposal):
        mock_canvas_cls.side_effect = RuntimeError('Canvas error')

        result = ProposalPdfService.generate(proposal)

        assert result is None

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_handles_proposal_with_no_sections(self, mock_back, mock_cover, proposal):
        """Proposal with zero sections still produces valid PDF bytes."""
        result = ProposalPdfService.generate(proposal)

        assert result is not None
        assert isinstance(result, bytes)
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @freeze_time('2026-06-01T12:00:00')
    def test_commercial_pdf_excludes_technical_document_section(
        self, mock_back, mock_cover, db,
    ):
        """Commercial PDF must not embed technical_document body text."""
        p = BusinessProposal.objects.create(
            title='Tech exclusion test',
            client_name='Client',
            client_email='c@example.com',
            language='es',
            total_investment=Decimal('1000000'),
            currency='COP',
            status='sent',
            expires_at=timezone.now() + timezone.timedelta(days=10),
        )
        ProposalSection.objects.create(
            proposal=p,
            section_type='greeting',
            title='Hi',
            order=0,
            is_enabled=True,
            content_json={
                'clientName': 'Client',
                'inspirationalQuote': 'Q',
            },
        )
        marker = 'UNIQUE_TECH_PDF_MARKER_Z9y8x7w6'
        ProposalSection.objects.create(
            proposal=p,
            section_type='technical_document',
            title='Technical',
            order=1,
            is_enabled=True,
            content_json={'purpose': marker},
        )

        pdf_bytes = ProposalPdfService.generate(p)
        assert pdf_bytes is not None
        latin = pdf_bytes.decode('latin-1', errors='ignore')
        assert marker not in latin
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_handles_raw_text_section(self, mock_back, mock_cover, proposal):
        """Unknown section type with rawText falls back to raw text rendering."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='unknown_type',
            title='Custom Section',
            order=0,
            is_enabled=True,
            content_json={'rawText': 'Custom content.', 'title': 'Custom'},
        )

        result = ProposalPdfService.generate(proposal)

        assert result is not None
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_paste_mode_overrides_form_renderer(self, mock_back, mock_cover, proposal):
        """Known section type with _editMode='paste' should use rawText, not form renderer."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='executive_summary',
            title='Resumen ejecutivo',
            order=0,
            is_enabled=True,
            content_json={
                '_editMode': 'paste',
                'rawText': '# Resumen\n\nEsta es la propuesta.\n\n- Punto 1\n- Punto 2',
                'index': '1',
                'title': 'Resumen ejecutivo',
                'paragraphs': [],
                'highlights': [],
            },
        )

        result = ProposalPdfService.generate(proposal)

        assert result is not None
        assert isinstance(result, bytes)
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_form_mode_uses_form_renderer(self, mock_back, mock_cover, proposal):
        """Known section type with _editMode='form' should use the form renderer."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='executive_summary',
            title='Resumen ejecutivo',
            order=0,
            is_enabled=True,
            content_json={
                '_editMode': 'form',
                'index': '1',
                'title': 'Resumen ejecutivo',
                'paragraphs': ['Primer párrafo.'],
                'highlights': ['Diseño'],
            },
        )

        result = ProposalPdfService.generate(proposal)

        assert result is not None
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_paste_mode_requirement_group(self, mock_back, mock_cover, proposal):
        """Functional requirement group in paste mode should render rawText."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Requerimientos',
            order=0,
            is_enabled=True,
            content_json={
                'index': '7',
                'title': 'Requerimientos Funcionales',
                'intro': 'Detalle.',
                'groups': [{
                    'title': 'Vistas',
                    'description': 'Pantallas.',
                    '_editMode': 'paste',
                    'rawText': '## Vistas\n- Home\n- About\n- Contact',
                    'items': [],
                }],
                'additionalModules': [],
            },
        )

        result = ProposalPdfService.generate(proposal)

        assert result is not None
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_selected_modules_passed_to_investment_renderer(
        self, mock_back, mock_cover, proposal,
    ):
        """selected_modules list is forwarded through ps dict to _render_investment."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inversión',
            order=0,
            is_enabled=True,
            content_json=_investment_content_json(modules=[
                {'id': 'web', 'name': 'Sitio Web', 'price': 3000000, 'included': True},
                {'id': 'seo', 'name': 'SEO', 'price': 500000, 'included': False},
            ]),
        )

        result = ProposalPdfService.generate(
            proposal, selected_modules=['web'],
        )

        assert result is not None
        assert isinstance(result, bytes)
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_selected_modules_none_renders_all(
        self, mock_back, mock_cover, proposal,
    ):
        """When selected_modules is None, all modules are rendered normally."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inversión',
            order=0,
            is_enabled=True,
            content_json=_investment_content_json(modules=[
                {'id': 'web', 'name': 'Sitio Web', 'price': 3000000, 'included': True},
                {'id': 'seo', 'name': 'SEO', 'price': 500000, 'included': False},
            ]),
        )

        result = ProposalPdfService.generate(
            proposal, selected_modules=None,
        )

        assert result is not None
        assert isinstance(result, bytes)
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_selected_modules_empty_list_renders_without_error(
        self, mock_back, mock_cover, proposal,
    ):
        """Empty selected_modules list produces valid PDF without errors."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inversión',
            order=0,
            is_enabled=True,
            content_json=_investment_content_json(modules=[
                {'id': 'web', 'name': 'Sitio Web', 'price': 3000000, 'included': True},
            ]),
        )

        result = ProposalPdfService.generate(
            proposal, selected_modules=[],
        )

        assert result is not None
        assert isinstance(result, bytes)
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()


# ── _merge_with_covers tests ─────────────────────────────────

class TestMergeWithCovers:
    def _make_pdf_bytes(self, num_pages=1):
        """Create minimal valid PDF bytes."""
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        for i in range(num_pages):
            c.drawString(100, 400, f'Page {i + 1}')
            c.showPage()
        c.save()
        return buf.getvalue()

    @patch('content.services.pdf_utils.COVER_PDF')
    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    def test_returns_content_when_no_covers(self, mock_back, mock_cover):
        """Without cover PDFs, merge returns the original content unchanged."""
        mock_cover.exists.return_value = False
        mock_back.exists.return_value = False

        content = self._make_pdf_bytes(2)
        result = ProposalPdfService._merge_with_covers(content)

        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 2
        mock_cover.exists.assert_called()
        mock_back.exists.assert_called()

    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    @patch('content.services.pdf_utils.COVER_PDF')
    def test_adds_cover_when_exists(self, mock_cover, mock_back):
        """When a cover PDF exists, it is prepended to the content pages."""
        cover_bytes = self._make_pdf_bytes(1)
        cover_path = Path('/tmp/test_cover.pdf')
        cover_path.write_bytes(cover_bytes)

        mock_cover.exists.return_value = True
        mock_cover.__str__ = MagicMock(return_value=str(cover_path))
        mock_back.exists.return_value = False

        content = self._make_pdf_bytes(2)
        result = ProposalPdfService._merge_with_covers(content)

        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 3  # 1 cover + 2 content
        mock_cover.exists.assert_called()
        mock_back.exists.assert_called()

        cover_path.unlink(missing_ok=True)

    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    @patch('content.services.pdf_utils.COVER_PDF')
    def test_handles_corrupt_cover_gracefully(self, mock_cover, mock_back):
        """Corrupt cover PDF is skipped, returning only the content pages."""
        corrupt_path = Path('/tmp/test_corrupt.pdf')
        corrupt_path.write_bytes(b'not a pdf')

        mock_cover.exists.return_value = True
        mock_cover.__str__ = MagicMock(return_value=str(corrupt_path))
        mock_back.exists.return_value = False

        content = self._make_pdf_bytes(1)
        result = ProposalPdfService._merge_with_covers(content)

        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 1  # only content, corrupt cover skipped
        mock_cover.exists.assert_called()

        corrupt_path.unlink(missing_ok=True)

    def _make_letter_cover_path(self):
        """Create a LETTER-size cover PDF on disk and return its path."""
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=LETTER)
        c.drawString(100, 400, 'Cover page in Letter size')
        c.showPage()
        c.save()
        path = Path('/tmp/test_cover_letter.pdf')
        path.write_bytes(buf.getvalue())
        return path

    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    @patch('content.services.pdf_utils.COVER_PDF')
    def test_letter_cover_merged_produces_two_pages(self, mock_cover, mock_back):
        """A Letter-size cover merges with 1 content page → 2 pages total."""
        cover_path = self._make_letter_cover_path()
        mock_cover.exists.return_value = True
        mock_cover.__str__ = MagicMock(return_value=str(cover_path))
        mock_back.exists.return_value = False

        result = ProposalPdfService._merge_with_covers(self._make_pdf_bytes(1))
        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 2
        mock_cover.exists.assert_called()
        mock_back.exists.assert_called()

        cover_path.unlink(missing_ok=True)

    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    @patch('content.services.pdf_utils.COVER_PDF')
    def test_letter_cover_scaled_to_a4_dimensions(self, mock_cover, mock_back):
        """scale_to normalises Letter-size cover page to A4 (≈595×842 pt)."""
        cover_path = self._make_letter_cover_path()
        mock_cover.exists.return_value = True
        mock_cover.__str__ = MagicMock(return_value=str(cover_path))
        mock_back.exists.return_value = False

        result = ProposalPdfService._merge_with_covers(self._make_pdf_bytes(1))
        cover_page = PdfReader(io.BytesIO(result)).pages[0]
        assert abs(float(cover_page.mediabox.width) - 595.0) < 2
        assert abs(float(cover_page.mediabox.height) - 842.0) < 2
        mock_cover.exists.assert_called()

        cover_path.unlink(missing_ok=True)


# ── generate_to_file tests ───────────────────────────────────

class TestGenerateToFile:
    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_saves_pdf_to_specified_path(self, mock_back, mock_cover, proposal_with_sections, tmp_path):
        """generate_to_file writes a valid PDF to the specified output path."""
        out = tmp_path / 'output.pdf'

        result = ProposalPdfService.generate_to_file(
            proposal_with_sections, output_path=str(out),
        )

        assert result == str(out)
        assert out.exists()
        assert out.read_bytes()[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_saves_to_temp_path_when_no_output_path(self, mock_back, mock_cover, proposal_with_sections):
        """Without output_path, generate_to_file creates a temp file."""
        result = ProposalPdfService.generate_to_file(proposal_with_sections)

        assert result is not None
        assert Path(result).exists()
        assert Path(result).read_bytes()[:5] == b'%PDF-'
        mock_cover.exists.assert_called()
        Path(result).unlink(missing_ok=True)

    @patch.object(ProposalPdfService, 'generate', return_value=None)
    def test_returns_none_when_generate_fails(self, mock_gen, proposal):
        """generate_to_file returns None when generate() returns None."""
        result = ProposalPdfService.generate_to_file(proposal)

        assert result is None
        mock_gen.assert_called_once_with(proposal)


# ── _format_cop tests ────────────────────────────────────────

class TestFormatCop:
    def test_formats_integer_with_dots(self):
        """Integer value is formatted as $X.XXX.XXX."""
        assert _format_cop(5000000) == '$5.000.000'

    def test_formats_string_integer(self):
        """String-numeric value is formatted correctly."""
        assert _format_cop('1490000') == '$1.490.000'

    def test_returns_string_for_non_numeric(self):
        """Non-numeric input is returned as-is string."""
        assert _format_cop('N/A') == 'N/A'

    def test_returns_string_for_none(self):
        """None input returns 'None' string."""
        assert _format_cop(None) == 'None'

    def test_formats_zero(self):
        """Zero formats to $0."""
        assert _format_cop(0) == '$0'


# ── _clean_url_display tests ─────────────────────────────────

class TestCleanUrlDisplay:
    def test_strips_scheme_from_https_url(self):
        """HTTPS scheme is removed, returning domain + path."""
        result = _clean_url_display('https://example.com/path')
        assert result == 'example.com/path'

    def test_strips_www_prefix(self):
        """Www prefix is removed from display label."""
        result = _clean_url_display('https://www.example.com')
        assert result == 'example.com'

    def test_handles_bare_domain(self):
        """Bare domain without scheme gets https:// prepended internally."""
        result = _clean_url_display('example.com')
        assert result == 'example.com'

    def test_strips_trailing_slash(self):
        """Trailing slash on root path is removed."""
        result = _clean_url_display('https://example.com/')
        assert result == 'example.com'

    def test_preserves_meaningful_path(self):
        """Non-root path segments are preserved."""
        result = _clean_url_display('https://docs.example.com/api/v2')
        assert result == 'docs.example.com/api/v2'

    def test_handles_invalid_url_gracefully(self):
        """Malformed input returns the original string."""
        result = _clean_url_display('')
        assert isinstance(result, str)


# ── _replace_urls_with_placeholders tests ─────────────────────

class TestReplaceUrlsWithPlaceholders:
    def test_replaces_full_url_with_display_label(self):
        """Full https URL is replaced with domain+path label."""
        text = 'Visit https://example.com/docs for details.'
        result, links = _replace_urls_with_placeholders(text)
        assert 'https://' not in result
        assert len(links) >= 1
        assert links[0][1] == 'https://example.com/docs'

    def test_replaces_bare_domain(self):
        """Bare domain like example.com is detected and replaced."""
        text = 'See example.com for info.'
        result, links = _replace_urls_with_placeholders(text)
        assert len(links) >= 1
        assert links[0][1].startswith('https://')

    def test_no_urls_returns_empty_links(self):
        """Text with no URLs returns empty links list."""
        text = 'No URLs here.'
        result, links = _replace_urls_with_placeholders(text)
        assert result == text
        assert links == []

    def test_multiple_urls(self):
        """Multiple URLs are all detected and replaced."""
        text = 'Visit https://a.com/page and https://b.com/page today.'
        result, links = _replace_urls_with_placeholders(text)
        assert len(links) >= 2


# ── _draw_line_with_links tests ──────────────────────────────

class TestDrawLineWithLinks:
    def test_draws_plain_text_without_error(self, pdf_canvas):
        """Plain text line draws without raising."""
        _register_fonts()
        ops_before = len(pdf_canvas._code)
        _draw_line_with_links(
            pdf_canvas, 50, 500, 'Hello world',
            _font('regular'), 10, ESMERALD,
        )
        assert len(pdf_canvas._code) > ops_before

    def test_draws_text_with_link(self, pdf_canvas):
        """Text containing a domain renders with link styling."""
        _register_fonts()
        ops_before = len(pdf_canvas._code)
        _draw_line_with_links(
            pdf_canvas, 50, 500, 'Visit example.com today',
            _font('regular'), 10, ESMERALD,
        )
        assert len(pdf_canvas._code) > ops_before

    def test_draws_full_url_as_link(self, pdf_canvas):
        """Full URL in text renders with clickable link."""
        _register_fonts()
        ops_before = len(pdf_canvas._code)
        _draw_line_with_links(
            pdf_canvas, 50, 500, 'See https://example.com/path here',
            _font('regular'), 10, ESMERALD,
        )
        assert len(pdf_canvas._code) > ops_before

    def test_draws_bold_segments(self, pdf_canvas):
        """Text with **bold** markers renders with bold font segments."""
        _register_fonts()
        ops_before = len(pdf_canvas._code)
        _draw_line_with_links(
            pdf_canvas, 50, 500, 'normal **bold text** normal',
            _font('regular'), 10, ESMERALD,
        )
        assert len(pdf_canvas._code) > ops_before

    def test_draws_bold_and_link_combined(self, pdf_canvas):
        """Text with both **bold** and URL renders both styles."""
        _register_fonts()
        ops_before = len(pdf_canvas._code)
        _draw_line_with_links(
            pdf_canvas, 50, 500, '**important** see example.com',
            _font('regular'), 10, ESMERALD,
        )
        assert len(pdf_canvas._code) > ops_before


# ── _font fallback tests ────────────────────────────────────

class TestFontFallback:
    def test_returns_string_for_regular(self):
        """Regular style returns a valid font name string."""
        result = _font('regular')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_string_for_unknown_style(self):
        """Unknown style falls back to Ubuntu/Helvetica."""
        result = _font('nonexistent_style')
        assert isinstance(result, str)

    def test_returns_fallback_for_bold(self):
        """Bold style returns a valid font name."""
        result = _font('bold')
        assert isinstance(result, str)


# ── Section renderer edge cases (no-sidebar branches) ────────

class TestSectionRendererEdgeCases:
    @pytest.fixture
    def proposal(self, db):
        return BusinessProposal.objects.create(
            title='Edge Case Proposal',
            client_name='Test',
            client_email='t@t.com',
            language='es',
            total_investment=Decimal('1000000'),
            currency='COP',
            status='sent',
        )

    def test_exec_summary_no_highlights_renders(self, pdf_canvas, proposal):
        """Fails if empty highlights cause the summary paragraph to disappear."""
        data = {
            'index': '1', 'title': 'Summary',
            'paragraphs': ['Test paragraph.'],
            'highlightsTitle': '', 'highlights': [],
        }
        y = _render_executive_summary(pdf_canvas, data, proposal)
        draw_ops = '\n'.join(pdf_canvas._code)
        assert y < PAGE_H - MARGIN_T
        assert 'Summary' in draw_ops
        assert 'Test paragraph' in draw_ops

    def test_context_diagnostic_no_issues_renders(self, pdf_canvas, proposal):
        """Context diagnostic with no issues renders paragraphs and opportunity."""
        data = {
            'index': '2', 'title': 'Context',
            'paragraphs': ['Analysis.'],
            'issuesTitle': '', 'issues': [],
            'opportunityTitle': 'Opportunity', 'opportunity': 'Growth potential.',
        }
        y = _render_context_diagnostic(pdf_canvas, data, proposal)
        assert isinstance(y, (int, float))

    def test_context_diagnostic_no_issues_no_opportunity(self, pdf_canvas, proposal):
        """Context with neither issues nor opportunity renders just paragraphs."""
        data = {
            'index': '2', 'title': 'Context',
            'paragraphs': ['Analysis.'],
            'issuesTitle': '', 'issues': [],
            'opportunityTitle': '', 'opportunity': '',
        }
        y = _render_context_diagnostic(pdf_canvas, data, proposal)
        assert isinstance(y, (int, float))

    def test_design_ux_no_focus_items_renders(self, pdf_canvas, proposal):
        """Design UX with no focus items renders paragraphs and objective."""
        data = {
            'index': '4', 'title': 'Design',
            'paragraphs': ['Modern design.'],
            'focusTitle': '', 'focusItems': [],
            'objectiveTitle': 'Objective', 'objective': 'Impact.',
        }
        y = _render_design_ux(pdf_canvas, data, proposal)
        assert isinstance(y, (int, float))

    def test_design_ux_no_focus_no_objective(self, pdf_canvas, proposal):
        """Design UX with no focus items and no objective."""
        data = {
            'index': '4', 'title': 'Design',
            'paragraphs': ['Modern design.'],
            'focusTitle': '', 'focusItems': [],
            'objectiveTitle': '', 'objective': '',
        }
        y = _render_design_ux(pdf_canvas, data, proposal)
        assert isinstance(y, (int, float))

    def test_creative_support_no_includes_renders(self, pdf_canvas, proposal):
        """Creative support with no includes renders paragraphs and closing."""
        data = {
            'index': '5', 'title': 'Support',
            'paragraphs': ['Guidance.'],
            'includesTitle': '', 'includes': [],
            'closing': 'We are here for you.',
        }
        y = _render_creative_support(pdf_canvas, data, proposal)
        assert isinstance(y, (int, float))

    def test_creative_support_no_includes_no_closing(self, pdf_canvas, proposal):
        """Creative support with no includes and no closing."""
        data = {
            'index': '5', 'title': 'Support',
            'paragraphs': ['Guidance.'],
            'includesTitle': '', 'includes': [],
            'closing': '',
        }
        y = _render_creative_support(pdf_canvas, data, proposal)
        assert isinstance(y, (int, float))

    def test_exec_summary_low_y_no_sidebar(self, pdf_canvas, proposal):
        """Executive summary starting at low y triggers no-sidebar branch."""
        data = {
            'index': '1', 'title': 'Summary',
            'paragraphs': ['Short.'],
            'highlightsTitle': 'Key', 'highlights': ['A', 'B'],
        }
        y = _render_executive_summary(pdf_canvas, data, proposal, y=MARGIN_B + 150)
        assert isinstance(y, (int, float))

    def test_context_diagnostic_low_y_no_sidebar(self, pdf_canvas, proposal):
        """Context diagnostic starting at low y triggers no-sidebar branch."""
        data = {
            'index': '2', 'title': 'Context',
            'paragraphs': ['Analysis.'],
            'issuesTitle': 'Issues', 'issues': ['SEO'],
            'opportunityTitle': 'Opportunity', 'opportunity': 'Growth.',
        }
        y = _render_context_diagnostic(pdf_canvas, data, proposal, y=MARGIN_B + 150)
        assert isinstance(y, (int, float))

    def test_creative_support_low_y_no_sidebar(self, pdf_canvas, proposal):
        """Creative support starting at low y triggers no-sidebar branch."""
        data = {
            'index': '5', 'title': 'Support',
            'paragraphs': ['Guidance.'],
            'includesTitle': 'Includes', 'includes': ['Reviews'],
            'closing': 'We are here.',
        }
        y = _render_creative_support(pdf_canvas, data, proposal, y=MARGIN_B + 150)
        assert isinstance(y, (int, float))


# ── Back cover merge test ────────────────────────────────────

class TestBackCoverMerge(TestMergeWithCovers):
    @patch('content.services.pdf_utils.COVER_PDF')
    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    def test_adds_back_cover_when_exists(self, mock_back, mock_cover):
        """When a back cover PDF exists, it is appended after content pages."""
        back_bytes = self._make_pdf_bytes(1)
        back_path = Path('/tmp/test_back_cover.pdf')
        back_path.write_bytes(back_bytes)

        mock_cover.exists.return_value = False
        mock_back.exists.return_value = True
        mock_back.__str__ = MagicMock(return_value=str(back_path))

        content = self._make_pdf_bytes(2)
        result = ProposalPdfService._merge_with_covers(content)

        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 3  # 2 content + 1 back
        mock_back.exists.assert_called()

        back_path.unlink(missing_ok=True)

    @patch('content.services.pdf_utils.COVER_PDF')
    @patch('content.services.pdf_utils.BACK_COVER_PDF')
    def test_corrupt_back_cover_skipped(self, mock_back, mock_cover):
        """Corrupt back cover PDF is skipped gracefully."""
        corrupt_path = Path('/tmp/test_corrupt_back.pdf')
        corrupt_path.write_bytes(b'not a pdf')

        mock_cover.exists.return_value = False
        mock_back.exists.return_value = True
        mock_back.__str__ = MagicMock(return_value=str(corrupt_path))

        content = self._make_pdf_bytes(1)
        result = ProposalPdfService._merge_with_covers(content)

        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) == 1  # only content
        mock_back.exists.assert_called()

        corrupt_path.unlink(missing_ok=True)


# ── Investment hosting edge cases ────────────────────────────

class TestInvestmentHostingEdgeCases:
    def test_investment_with_hosting_specs_and_pricing(self, pdf_canvas, proposal):
        """Investment section with hosting specs grid and pricing renders."""
        data = _investment_content_json(
            index='9', title='Investment',
            totalInvestment='$5,000,000',
            whatsIncluded=[{'title': 'Design', 'description': 'UX'}],
            paymentOptions=[{'label': '50%', 'description': '$2.5M'}],
            hostingPlan=_HOSTING_PLAN_WITH_SPECS,
            valueReasons=['Quality', 'Support'],
        )
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['investment'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_investment_with_billing_tiers_and_badge(self, pdf_canvas, proposal):
        """Billing tiers render badge, monthly price, and plural period total text."""
        data = _investment_content_json(
            index='9',
            title='Investment',
            totalInvestment='$5,000,000',
            hostingPlan={
                'title': 'Scale',
                'description': 'Managed hosting.',
                'hostingPercent': 12,
                'billingTiers': [
                    {'label': 'Mensual', 'months': 1, 'discountPercent': 0},
                    {'label': 'Semestral', 'months': 6, 'discountPercent': 10, 'badge': 'Ahorra'},
                ],
            },
        )
        ps = {
            'num': 1,
            'client': 'Test',
            'total': None,
            'selected_modules': None,
            'base_weeks': 0,
        }
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['investment'](pdf_canvas, data, proposal, ps=ps)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_investment_with_monthly_price_only(self, pdf_canvas, proposal):
        """Investment hosting with only monthly price renders."""
        data = _investment_content_json(
            index='9', title='Investment',
            totalInvestment='$1,000,000',
            hostingPlan={
                'title': 'Basic',
                'description': 'Basic hosting.',
                'monthlyPrice': '$50.000',
                'annualPrice': '',
            },
        )
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['investment'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before

    def test_investment_with_annual_price_only(self, pdf_canvas, proposal):
        """Legacy annual-only hosting pricing renders without monthlyPrice."""
        data = _investment_content_json(
            index='9',
            title='Investment',
            totalInvestment='$1,000,000',
            hostingPlan={
                'title': 'Annual',
                'description': 'Annual hosting.',
                'monthlyPrice': '',
                'annualPrice': '$500.000',
            },
        )
        page_before = pdf_canvas.getPageNumber()
        SECTION_RENDERERS['investment'](pdf_canvas, data, proposal)
        assert pdf_canvas.getPageNumber() >= page_before


# ── Generate with FR items and selected_modules ──────────────

class TestGenerateWithConfigurableScope:
    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_configurable_items_filtered_by_selected_modules(
        self, mock_back, mock_cover, proposal,
    ):
        """Configurable requirements follow the persisted proposal scope."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='greeting',
            title='Hi', order=0, is_enabled=True,
            content_json={'clientName': 'Test', 'inspirationalQuote': ''},
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Reqs', order=1, is_enabled=True,
            content_json={
                'index': '7', 'title': 'Requirements',
                'intro': 'Details.',
                'groups': [{
                    'id': 'views', 'title': 'Views',
                    'description': 'Pages.',
                    'items': [
                        {'name': 'Home', 'description': 'Landing.', 'is_required': True},
                        {'name': 'Blog', 'description': 'Blog.', 'is_required': False, 'price': 500000},
                        {'name': 'Gallery', 'description': 'Photos.', 'price': 300000},
                    ],
                }],
                'additionalModules': [],
            },
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inv', order=2, is_enabled=True,
            content_json=_investment_content_json(
                index='9', title='Investment',
                totalInvestment='$2,000,000', hostingPlan={},
            ),
        )

        result = ProposalPdfService.generate(
            proposal, selected_modules=['fr-views-blog'],
        )

        assert result is not None
        assert result[:5] == b'%PDF-'
        text = '\n'.join(
            page.extract_text() or ''
            for page in PdfReader(io.BytesIO(result)).pages
        )
        assert 'Home' in text
        assert 'Blog' in text
        assert 'Gallery' not in text
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_greeting_not_first_section_triggers_page_break(
        self, mock_back, mock_cover, proposal,
    ):
        """Greeting section that isn't the first content triggers a page break."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='executive_summary',
            title='Summary', order=0, is_enabled=True,
            content_json={
                'index': '1', 'title': 'Summary',
                'paragraphs': ['P1.'], 'highlightsTitle': '',
                'highlights': [],
            },
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='greeting',
            title='Hi', order=1, is_enabled=True,
            content_json={'clientName': 'Test', 'inspirationalQuote': ''},
        )

        result = ProposalPdfService.generate(proposal)

        assert result is not None
        assert result[:5] == b'%PDF-'
        reader = PdfReader(io.BytesIO(result))
        assert len(reader.pages) >= 2
        mock_cover.exists.assert_called()


# ── Phase 2a: Helper edge cases ──────────────────────────────

class TestRegisterFontsException:
    def test_font_registration_exception_is_handled(self, monkeypatch):
        """TTFont raising an exception is caught and font registration continues."""
        import content.services.pdf_utils as pdf_mod

        monkeypatch.setattr(pdf_mod, '_fonts_registered', False)

        original_ttfont = pdf_mod.TTFont
        call_count = {'n': 0}

        def _exploding_ttfont(name, path):
            call_count['n'] += 1
            if call_count['n'] == 1:
                raise RuntimeError('Font load error')
            return original_ttfont(name, path)

        monkeypatch.setattr(pdf_mod, 'TTFont', _exploding_ttfont)
        _register_fonts()
        assert pdf_mod._fonts_registered is True


class TestFontFallbackKeyError:
    def test_returns_helvetica_when_primary_not_registered(self, monkeypatch):
        """_font returns the Helvetica fallback when pdfmetrics.getFont raises KeyError."""
        from reportlab.pdfbase import pdfmetrics as pm

        original_get = pm.getFont

        def _always_raise(name):
            raise KeyError(name)

        monkeypatch.setattr(pm, 'getFont', _always_raise)
        _font.cache_clear()  # clear cached result from prior tests in suite
        result = _font('regular')
        assert result == 'Helvetica'
        _font.cache_clear()  # restore fresh state for subsequent tests
        monkeypatch.setattr(pm, 'getFont', original_get)


class TestCleanUrlDisplayException:
    def test_returns_input_on_parse_failure(self, monkeypatch):
        """_clean_url_display returns the original string when urlparse raises."""
        def _exploding_parse(url):
            raise ValueError('bad url')

        monkeypatch.setattr('urllib.parse.urlparse', _exploding_parse)
        result = _clean_url_display(':::bad')
        assert result == ':::bad'


# ── Phase 2b: Pagination early-return paths ──────────────────

class TestDrawParagraphsNoPs:
    def test_returns_early_when_y_below_margin_without_ps(self, pdf_canvas):
        """_draw_paragraphs returns y unchanged when below margin and no ps."""
        start_y = MARGIN_B + 5
        end_y = _draw_paragraphs(
            pdf_canvas, start_y,
            ['Long paragraph that would normally wrap multiple lines.'],
        )
        assert end_y <= start_y


class TestDrawBulletListNoPs:
    def test_returns_early_when_y_below_margin_without_ps(self, pdf_canvas):
        """_draw_bullet_list returns y unchanged when below margin and no ps."""
        start_y = MARGIN_B + 5
        end_y = _draw_bullet_list(
            pdf_canvas, start_y,
            ['Long bullet item that would normally wrap.'],
        )
        assert end_y <= start_y


# ── Phase 2c: Section renderer no-ps break paths ─────────────

class TestSectionRendererNoPsBreaks:
    @pytest.fixture
    def proposal_obj(self, db):
        return BusinessProposal.objects.create(
            title='NoPsBreak', client_name='Test',
            client_email='t@t.com', language='es',
            total_investment=Decimal('1000000'), currency='COP',
            status='sent',
        )

    def test_conversion_strategy_renders_all_steps_without_page_state(
        self, pdf_canvas, proposal_obj,
    ):
        """Fails if no-page-state rendering drops configured strategy steps."""
        data = {
            'index': '3', 'title': 'Strategy',
            'intro': 'Build.',
            'steps': [
                {'title': f'Step {i}', 'bullets': [f'Action {i}']}
                for i in range(20)
            ],
            'resultTitle': 'Result', 'result': 'More.',
        }
        SECTION_RENDERERS['conversion_strategy'](
            pdf_canvas, data, proposal_obj, y=MARGIN_B + 60,
        )
        draw_ops = '\n'.join(pdf_canvas._code)
        assert 'Strategy' in draw_ops
        assert 'Step 0' in draw_ops
        assert 'Step 19' in draw_ops

    def test_development_stages_breaks_at_low_y_without_ps(self, pdf_canvas, proposal_obj):
        """Development stages loop breaks when y is below margin and no ps."""
        data = {
            'title': 'Stages',
            'stages': [
                {'title': f'Phase {i}', 'description': f'Work {i}.', 'current': False}
                for i in range(20)
            ],
        }
        y = SECTION_RENDERERS['development_stages'](
            pdf_canvas, data, proposal_obj, y=MARGIN_B + 60,
        )
        assert isinstance(y, (int, float))

    def test_timeline_breaks_at_low_y_without_ps(self, pdf_canvas, proposal_obj):
        """Timeline phases loop breaks when y is below margin and no ps."""
        data = {
            'index': '8', 'title': 'Timeline',
            'introText': 'Phases.',
            'totalDuration': '',
            'phases': [
                {'title': f'P{i}', 'duration': '1w', 'description': f'D{i}.',
                 'tasks': [], 'milestone': ''}
                for i in range(20)
            ],
        }
        y = SECTION_RENDERERS['timeline'](
            pdf_canvas, data, proposal_obj, y=MARGIN_B + 60,
        )
        assert isinstance(y, (int, float))

    def test_next_steps_breaks_at_low_y_without_ps(self, pdf_canvas, proposal_obj):
        """Next steps loop breaks when y is below margin and no ps."""
        data = {
            'index': '11', 'title': 'Next Steps',
            'introMessage': 'Ready.',
            'steps': [
                {'title': f'S{i}', 'description': f'D{i}.'}
                for i in range(20)
            ],
            'ctaMessage': '', 'contactMethods': [],
        }
        y = SECTION_RENDERERS['next_steps'](
            pdf_canvas, data, proposal_obj, y=MARGIN_B + 50,
        )
        assert isinstance(y, (int, float))

    def test_functional_requirements_card_break_at_low_y(self, pdf_canvas, proposal_obj):
        """FR overview cards break when y is too low for the next card."""
        data = {
            'index': '7', 'title': 'Reqs',
            'intro': '',
            'groups': [
                {'title': f'Group {i}', 'description': f'Desc {i}.',
                 'items': [{'name': f'Item {j}', 'description': f'D{j}.'} for j in range(3)]}
                for i in range(30)
            ],
            'additionalModules': [],
        }
        y = SECTION_RENDERERS['functional_requirements'](
            pdf_canvas, data, proposal_obj, y=MARGIN_B + 80,
        )
        assert isinstance(y, (int, float))


# ── Phase 2d: Investment with selected_modules ────────────────

class TestInvestmentManualTotalWithScope:
    @pytest.fixture
    def proposal_obj(self, db):
        return BusinessProposal.objects.create(
            title='InvSelMod', client_name='Test',
            client_email='t@t.com', language='es',
            total_investment=Decimal('5000000'), currency='COP',
            status='sent',
        )

    def test_selected_module_preserves_manual_payment_amounts(
        self, pdf_canvas, proposal_obj,
    ):
        from content.services.proposal_pdf_service import _render_investment

        ps = {
            'num': 1, 'client': 'Test',
            'selected_modules': ['web'],
            'base_weeks': 0,
        }
        data = _investment_content_json(
            totalInvestment='$5.000.000',
            paymentOptions=[
                {'label': '50% inicio', 'description': '$2.500.000'},
                {'label': '50% final', 'description': '$2.500.000'},
            ],
            modules=[
                {'id': 'web', 'name': 'Web'},
                {'id': 'seo', 'name': 'SEO'},
            ],
        )
        y = _render_investment(pdf_canvas, data, proposal_obj, ps=ps)
        draw_ops = '\n'.join(pdf_canvas._code)
        assert y < PAGE_H - MARGIN_T
        assert '50% inicio' in draw_ops
        assert '$2.500.000' in draw_ops
        assert '$1.500.000' not in draw_ops


# ── Helper unit tests ─────────────────────────────────────────

class TestPaymentPillDesc:
    """Direct unit tests for the _payment_pill_desc helper.

    Mirrors the frontend Investment.vue ``computedPaymentOptions`` contract:
    derive the amount from the percentage in the label times the live total,
    not from whatever amount was previously stored in ``description``.
    """

    def test_uses_label_pct_against_display_num(self):
        from content.services.proposal_pdf_service import _payment_pill_desc

        # The stored description can be stale; derive 40% from the manual
        # proposal total supplied as display_num.
        pill = _payment_pill_desc(
            label='40% al firmar el contrato',
            desc='$1.728.000 COP',
            display_num=4_320_000,
        )
        assert '$1.728.000' in pill
        assert pill.endswith('COP')

    def test_falls_back_to_label_only_amount_when_desc_has_no_money(self):
        from content.services.proposal_pdf_service import _payment_pill_desc

        pill = _payment_pill_desc(
            label='30% al desplegar',
            desc='al desplegar la plataforma',
            display_num=4_320_000,
        )
        assert pill.startswith('$')
        assert '1.296.000' in pill

    def test_returns_desc_unchanged_when_label_has_no_percent(self):
        from content.services.proposal_pdf_service import _payment_pill_desc

        pill = _payment_pill_desc(
            label='Pago contra entrega',
            desc='$1.000.000 COP',
            display_num=4_320_000,
        )
        assert pill == '$1.000.000 COP'

    def test_returns_desc_unchanged_when_display_num_is_zero(self):
        from content.services.proposal_pdf_service import _payment_pill_desc

        pill = _payment_pill_desc(
            label='40% al firmar',
            desc='$0',
            display_num=0,
        )
        assert pill == '$0'


class TestInvestmentPaymentsUseManualTotal:
    """Payment milestones derive from the proposal's manually agreed total."""

    @pytest.fixture
    def proposal_obj(self, db):
        return BusinessProposal.objects.create(
            title='Eff', client_name='Test',
            client_email='t@t.com', language='es',
            total_investment=Decimal('3200000'), currency='COP',
            status='sent',
        )

    def test_payment_amounts_match_manual_total(self, pdf_canvas, proposal_obj):
        from content.services import proposal_pdf_service as svc

        data = _investment_content_json(
            totalInvestment='$3.200.000',
            paymentOptions=[
                {'label': '40% al firmar', 'description': '$1.728.000 COP'},
                {'label': '30% al aprobar', 'description': '$1.296.000 COP'},
                {'label': '30% al desplegar', 'description': '$1.296.000 COP'},
            ],
        )
        ps = {'num': 1, 'client': 'Test'}
        svc._render_investment(pdf_canvas, data, proposal_obj, ps=ps)
        pdf_canvas.save()
        text = '\n'.join(
            page.extract_text() or ''
            for page in PdfReader(pdf_canvas._test_buf).pages
        )

        assert '$3.200.000' in text
        assert '$1.280.000' in text
        assert text.count('$960.000') == 2
        assert '$1.728.000' not in text
        assert '$1.296.000' not in text


class TestRenderInvestmentEndToEndAdminDefaults:
    """Render admin-owned scope without changing the agreed investment."""

    @pytest.fixture
    def proposal_obj(self, db):
        return BusinessProposal.objects.create(
            title='InvSelMod', client_name='Test',
            client_email='t@t.com', language='es',
            total_investment=Decimal('5000000'), currency='COP',
            status='sent',
        )

    def test_default_selected_module_preserves_manual_investment(self, db):
        from content.services.proposal_pdf_service import (
            ProposalPdfService,
            default_selected_modules_from_content,
        )

        proposal = BusinessProposal.objects.create(
            title='AdminDefault', client_name='Test',
            client_email='t@t.com', language='es',
            total_investment=Decimal('6000000'), currency='COP',
            status='sent',
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='FR', order=1, is_enabled=True,
            content_json=_fr_section_content_json(additionalModules=[
                _calculator_module_group(
                    id='branding', default_selected=True,
                ),
            ]),
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inv', order=2, is_enabled=True,
            content_json=_investment_content_json(
                totalInvestment='$6.000.000',
                paymentOptions=[
                    {'label': '40% al firmar', 'description': '$2.400.000 COP'},
                    {'label': '60% al desplegar', 'description': '$3.600.000 COP'},
                ],
            ),
        )

        sel = default_selected_modules_from_content(proposal)
        assert 'module-branding' in sel

        pdf = ProposalPdfService.generate(proposal, selected_modules=sel)
        assert len(pdf) > 1000

        import io as _io

        from pypdf import PdfReader
        text = '\n'.join(
            (page.extract_text() or '')
            for page in PdfReader(_io.BytesIO(pdf)).pages
        )
        assert '$6.000.000' in text
        assert '$2.400.000' in text
        assert '$3.600.000' in text
        assert '$8.100.000' not in text

    def test_explicit_selected_false_excludes_module_from_scope(self, db):
        from content.services.proposal_pdf_service import (
            ProposalPdfService,
            default_selected_modules_from_content,
        )

        proposal = BusinessProposal.objects.create(
            title='HiddenAndExcluded', client_name='Test',
            client_email='t@t.com', language='es',
            total_investment=Decimal('6000000'), currency='COP',
            status='sent',
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='FR', order=1, is_enabled=True,
            content_json=_fr_section_content_json(additionalModules=[
                _calculator_module_group(
                    id='branding',
                    title='Identidad Visual',
                    default_selected=True, selected=False,
                ),
            ]),
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inv', order=2, is_enabled=True,
            content_json=_investment_content_json(
                totalInvestment='$6.000.000',
                paymentOptions=[
                    {'label': '40% al firmar', 'description': '$2.400.000 COP'},
                    {'label': '60% al desplegar', 'description': '$3.600.000 COP'},
                ],
            ),
        )

        sel = default_selected_modules_from_content(proposal)
        assert 'module-branding' not in sel

        pdf = ProposalPdfService.generate(proposal, selected_modules=sel)
        import io as _io

        from pypdf import PdfReader
        text = '\n'.join(
            (page.extract_text() or '')
            for page in PdfReader(_io.BytesIO(pdf)).pages
        )
        assert 'Identidad Visual' not in text

    def test_manual_duration_renders_when_modules_deselected(
        self, pdf_canvas, proposal_obj,
    ):
        from content.services.proposal_pdf_service import _render_investment

        ps = {
            'num': 1, 'client': 'Test',
            'selected_modules': [],
            'base_weeks': 12,
        }
        data = _investment_content_json(
            totalInvestment='$5.000.000',
            paymentOptions=[],
            modules=[
                {'id': 'mod1', 'name': 'Mod'},
                {'id': 'mod2', 'name': 'Mod2'},
            ],
        )
        y = _render_investment(pdf_canvas, data, proposal_obj, ps=ps)
        draw_ops = '\n'.join(pdf_canvas._code)
        assert y < PAGE_H - MARGIN_T
        assert '12 semanas' in draw_ops
        assert '9 semanas' not in draw_ops
        assert 'reducido de 12' not in draw_ops


# ── Generate with optional proposal scope ─

class TestGenerateContentModes:
    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_selected_optional_module_renders_in_pdf(
        self, mock_back, mock_cover, proposal,
    ):
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Reqs', order=0, is_enabled=True,
            content_json=_fr_section_content_json(
                groups=[_calculator_module_group()],
            ),
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='investment',
            title='Inv', order=1, is_enabled=True,
            content_json=_investment_content_json(
                totalInvestment='$10.000.000',
            ),
        )
        result = ProposalPdfService.generate(
            proposal, selected_modules=['module-pwa_module'],
        )

        assert result is not None
        assert result[:5] == b'%PDF-'
        text = '\n'.join(
            page.extract_text() or ''
            for page in PdfReader(io.BytesIO(result)).pages
        )
        assert 'PWA' in text
        assert 'Offline' in text
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_paste_mode_greeting_renders(
        self, mock_back, mock_cover, proposal,
    ):
        """Greeting with _editMode=paste uses rawText renderer."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='greeting',
            title='Hi', order=0, is_enabled=True,
            content_json={
                '_editMode': 'paste',
                'rawText': '# Welcome\nHello client.',
                'clientName': 'Test',
            },
        )

        result = ProposalPdfService.generate(proposal)

        assert result is not None
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_fr_configurable_items_filtered_with_selected_modules(
        self, mock_back, mock_cover, proposal,
    ):
        """FR groups with configurable items are filtered by selected_modules."""
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Reqs', order=0, is_enabled=True,
            content_json={
                'index': '1', 'title': 'Requirements',
                'intro': 'Details.',
                'groups': [
                    {
                        'id': 'views', 'title': 'Views',
                        'is_visible': True,
                        'description': 'Pages.',
                        'items': [
                            {'name': 'Home', 'description': 'Landing.', 'is_required': True},
                            {'name': 'Blog', 'description': 'Blog.', 'is_required': False, 'price': 500000},
                            {'name': 'Gallery', 'description': 'Photos.', 'price': 300000},
                        ],
                    },
                    {
                        'id': 'hidden_group', 'title': 'Hidden',
                        'is_visible': False,
                        'description': 'Should not appear.',
                        'items': [{'name': 'X', 'description': 'Y.'}],
                    },
                ],
                'additionalModules': [],
            },
        )

        result = ProposalPdfService.generate(
            proposal,
            selected_modules=['fr-views-home', 'fr-views-blog'],
        )

        assert result is not None
        assert result[:5] == b'%PDF-'
        mock_cover.exists.assert_called()


# ── Phase 2f: Badge overflow + bold_line ──────────────────────

class TestFinalNoteBadgeOverflow:
    def test_badge_pills_wrap_to_next_row(self, pdf_canvas, proposal):
        """Fails if overflowing badge pills stay on their original row."""
        many_badges = [
            {'title': f'Very Long Badge Title Number {i}'} for i in range(10)
        ]
        data = _final_note_data(personalNote='', commitmentBadges=many_badges)
        ps = {'num': 1, 'client': 'Test', 'total': None}
        SECTION_RENDERERS['final_note'](pdf_canvas, data, proposal, ps=ps)
        first_badge_op = next(
            op for op in pdf_canvas._code
            if '(Very Long Badge Title Number 0)' in op
        )
        wrapped_badge_op = next(
            op for op in pdf_canvas._code
            if '(Very Long Badge Title Number 3)' in op
        )
        assert float(wrapped_badge_op.split()[6]) < float(first_badge_op.split()[6])


class TestRenderRawTextBoldLine:
    def test_bold_line_type_renders_at_low_y_with_ps(self, pdf_canvas, proposal):
        """Fails if markdown bold-line and heading tokens are omitted from the PDF."""
        data = {
            'index': '1', 'title': 'Test',
            'rawText': '**Bold Title Line**\n\nSome paragraph.\n\n### H3 Heading\n\n#### H4 Heading',
        }
        ps = {'num': 1, 'client': 'Test', 'total': None}
        _render_raw_text(pdf_canvas, data, proposal, ps=ps, y=MARGIN_B + 100)
        pdf_canvas.save()
        rendered_text = '\n'.join(
            page.extract_text() or ''
            for page in PdfReader(pdf_canvas._test_buf).pages
        )
        assert ps['num'] >= 2
        assert 'Bold Title Line' in rendered_text
        assert 'H3 Heading' in rendered_text
        assert 'H4 Heading' in rendered_text


class TestInvestmentHostingRenewalContent:
    """Verify renewal content in the generated investment PDF.

    The tests assert rendered copy instead of merely checking PDF creation.
    """

    def _proposal_with_investment(self, hosting_plan):
        p = BusinessProposal.objects.create(
            title='Renewal PDF Test',
            client_name='Renewal Client', client_email='renewal@test.com',
            language='es', currency='COP', status='sent',
            total_investment=Decimal('5000000'),
            expires_at=timezone.now() + timezone.timedelta(days=20),
        )
        ProposalSection.objects.create(
            proposal=p, section_type='investment',
            title='Inversión', order=4, is_enabled=True,
            content_json=_investment_content_json(hostingPlan=hosting_plan),
        )
        return p

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_custom_renewal_note_text_appears_in_generated_pdf(self, _mock_back, _mock_cover):  # quality: disable unverified_mock (file-path stubs prevent real disk I/O; PDF content is the contract)  # noqa: PT019
        """Render an admin-written renewal note in the renewal callout.

        The maximal hosting payload also retains its specs and tier table.
        """
        proposal = self._proposal_with_investment(_HOSTING_PLAN_WITH_SPECS | {
            'renewalNote': 'La renovación cada nueve meses queda fija en $987.654 COP durante el primer trienio.',
        })

        pdf_bytes = ProposalPdfService.generate(proposal)

        assert pdf_bytes is not None
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)

        assert 'RENOVACIONES' in text
        assert 'La renovación cada nueve meses queda fija en $987.654 COP durante el primer trienio.' in text
        assert 'Storage' in text
        assert '$150.000' in text
        assert '$1.350.000' in text
        assert 'Hosting covers domain, SSL, and CDN.' in text

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_default_smlmv_renewal_formula_appears_when_note_missing(self, _mock_back, _mock_cover):  # quality: disable unverified_mock (file-path stubs prevent real disk I/O; PDF content is the contract)  # noqa: PT019
        """Render the default SMLMV formula when no custom note exists.

        A hosting title without renewalNote still produces useful copy.
        """
        proposal = self._proposal_with_investment({
            'title': 'Starter',
            'description': 'Basic hosting.',
        })

        pdf_bytes = ProposalPdfService.generate(proposal)

        assert pdf_bytes is not None
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)

        assert 'RENOVACIONES' in text
        assert (
            'Renovaciones para cada año de renovación (a partir del segundo año)'
            in text
        )
        assert 'Costo de renovación = Costo del año anterior' in text

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_legacy_pricing_fields_render_current_tiers(self, _mock_back, _mock_cover):  # quality: disable unverified_mock (file-path stubs prevent real disk I/O; PDF content is the contract)  # noqa: PT019
        """Normalize legacy hosting fields to the current billing tiers.

        Active proposals render 9/6/3 terms instead of obsolete labels.
        """
        proposal = self._proposal_with_investment({
            'title': 'Starter',
            'description': 'Basic hosting.',
            'specs': [],
            'monthlyPrice': '$50.000',
            'annualPrice': '',
        })

        pdf_bytes = ProposalPdfService.generate(proposal)

        assert pdf_bytes is not None
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)

        assert 'Cada 9 meses' in text
        assert '$150.000' in text
        assert '$1.350.000' in text
        assert 'por mes' not in text
        assert 'pago anual' not in text


class TestRequirementGroupEmptyItems:
    def test_group_with_no_items_returns_y(self, pdf_canvas):
        """Fails if an empty requirement group omits its configured heading."""
        from content.services.proposal_pdf_service import _render_requirement_group_page

        grp = {'title': 'Empty Group', 'description': '', 'items': []}
        y = _render_requirement_group_page(pdf_canvas, grp)
        draw_ops = '\n'.join(pdf_canvas._code)
        assert y < PAGE_H - MARGIN_T
        assert 'Empty Group' in draw_ops


# ── Phase 2g: Remaining uncovered lines ──────────────────────

class TestDrawLineWithLinksEmptyPart:
    def test_empty_part_from_split_is_skipped(self, pdf_canvas):
        """Line starting with a domain produces empty first part that is skipped (L230)."""
        _register_fonts()
        ops_before = len(pdf_canvas._code)
        _draw_line_with_links(
            pdf_canvas, 50, 500, 'example.com is a site',
            _font('regular'), 10, ESMERALD,
        )
        assert len(pdf_canvas._code) > ops_before


class TestDrawParagraphsNewPageWithPs:
    def test_multi_line_paragraph_at_low_y_triggers_new_page(self, pdf_canvas):
        """Multi-line paragraph near bottom with ps triggers _new_page (L368)."""
        ps = {'num': 1, 'client': 'Test'}
        long_text = 'A very long paragraph. ' * 20
        _draw_paragraphs(
            pdf_canvas, MARGIN_B + 15, [long_text], ps=ps,
        )
        assert ps['num'] >= 2


class TestDrawBulletListNewPageWithPs:
    def test_multi_line_bullet_at_low_y_triggers_new_page(self, pdf_canvas):
        """Multi-line bullet item near bottom with ps triggers _new_page (L394)."""
        ps = {'num': 1, 'client': 'Test'}
        long_item = 'A bullet item with lots of text. ' * 15
        _draw_bullet_list(
            pdf_canvas, MARGIN_B + 15, [long_item], ps=ps,
        )
        assert ps['num'] >= 2


class TestDrawBannerBoxEmptyText:
    def test_empty_text_still_renders_box(self, pdf_canvas):
        """_draw_banner_box with empty text produces a single empty-line box (L502)."""
        start_y = PAGE_H - 200
        end_y = _draw_banner_box(
            pdf_canvas, MARGIN_L, start_y, CONTENT_W, '',
            icon_text='Info:',
        )
        assert end_y < start_y


class TestFinalNoteEmptyBadgeTitle:
    def test_badge_with_empty_title_is_skipped(self, pdf_canvas, proposal):
        """Badge with empty/None title is skipped in the loop."""
        mixed_badges = [{'title': ''}, {'title': None}, {'title': 'Valid Badge'}]
        data = _final_note_data(
            message='Thanks.', personalNote='',
            contactEmail='e@t.com', commitmentBadges=mixed_badges,
        )
        ps = {'num': 1, 'client': 'Test'}
        y = SECTION_RENDERERS['final_note'](pdf_canvas, data, proposal, ps=ps)
        assert isinstance(y, (int, float))


class TestNextStepsEmptyContactTitle:
    def test_contact_method_with_empty_title_is_skipped(self, pdf_canvas, proposal):
        """Fails if a blank contact title is emitted or Email is skipped."""
        from content.services.proposal_pdf_service import _render_next_steps

        data = {
            'index': '11', 'title': 'Next Steps',
            'introMessage': 'Ready.',
            'steps': [],
            'ctaMessage': '',
            'contactMethods': [
                {'title': '', 'value': 'skip@test.com'},
                {'title': 'Email', 'value': 'team@test.com'},
            ],
        }
        ps = {'num': 1, 'client': 'Test'}
        y = _render_next_steps(pdf_canvas, data, proposal, ps=ps)
        draw_ops = '\n'.join(pdf_canvas._code)
        assert y < PAGE_H - MARGIN_T
        assert 'Email' in draw_ops
        assert 'team@test.com' in draw_ops
        assert 'skip@test.com' not in draw_ops


# ── default_selected_modules_from_content tests ─────────────

class TestDefaultSelectedModulesFromContent:
    """Regression coverage for the PDF module-selection fallback.

    When the PDF endpoint receives no ``?selected_modules=`` query
    param, it must derive the default selection from the current
    ``content_json`` — not from the stale ``BusinessProposal.selected_modules``
    field — so admin edits to ``additionalModules[i].selected`` propagate
    to the PDF immediately.
    """

    def _make_proposal(
        self,
        fr_content=None,
        investment_content=None,
        persisted=None,
        confirmed=False,
    ):
        proposal = BusinessProposal.objects.create(
            title='Selection Defaults',
            client_name='Client',
            client_email='client@test.com',
            language='es',
            total_investment=Decimal('5000000'),
            currency='COP',
            status='sent',
            expires_at=timezone.now() + timezone.timedelta(days=15),
            selected_modules=persisted or [],
        )
        if fr_content is not None:
            ProposalSection.objects.create(
                proposal=proposal,
                section_type='functional_requirements',
                title='FR', order=1, is_enabled=True,
                content_json=fr_content,
            )
        if investment_content is not None:
            ProposalSection.objects.create(
                proposal=proposal,
                section_type='investment',
                title='Inversión', order=2, is_enabled=True,
                content_json=investment_content,
            )
        if confirmed:
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type=ProposalChangeLog.ChangeType.CALCULATOR_CONFIRMED,
            )
        return proposal

    def test_includes_calc_module_when_selected_true(self):
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=True),
            ]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'module-pwa' in result

    def test_excludes_calc_module_when_selected_false(self):
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=False),
            ]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'module-pwa' not in result

    def test_explicit_selected_false_excludes_even_with_default_selected_true(self):
        """``selected`` is the source of truth: an explicit ``selected=False`` keeps the module out of the PDF scope even if ``default_selected=True`` — the admin unchecked it in the panel. (The ``selected``-absent fallback is covered by ``test_falls_back_to_default_selected_when_selected_absent``.)."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(
                    id='branding', default_selected=True, selected=False,
                ),
            ]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'module-branding' not in result

    def test_excludes_group_when_is_visible_false(self):
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='hidden', selected=True, is_visible=False),
            ]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'module-hidden' not in result

    def test_confirmed_persisted_selected_modules_wins_over_content_json(self):
        """A legacy confirmed scope snapshot overrides older admin defaults."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=False),
            ]),
            persisted=['module-pwa'],
            confirmed=True,
        )

        result = default_selected_modules_from_content(proposal)

        assert result == ['module-pwa']

    def test_confirmed_persisted_bare_ids_are_normalized_to_canonical_prefixed_form(self):
        """Legacy bare IDs normalize to the canonical PDF scope identifiers."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=False),
            ]),
            persisted=['pwa'],
            confirmed=True,
        )

        result = default_selected_modules_from_content(proposal)

        assert result == ['module-pwa']

    def test_confirmed_empty_selection_does_not_leak_default_selected_modules(self):
        """A legacy confirmed empty scope does not restore admin defaults."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(
                    id='pwa', default_selected=True, selected=False,
                ),
            ]),
            persisted=[],
            confirmed=True,
        )

        result = default_selected_modules_from_content(proposal)

        assert result == []

    def test_confirmed_empty_selection_still_includes_admin_pinned_modules(self):
        """An admin pin remains in scope over a legacy confirmed empty list."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=True),
            ]),
            persisted=[],
            confirmed=True,
        )

        result = default_selected_modules_from_content(proposal)

        assert result == ['module-pwa']

    def test_confirmed_unions_persisted_with_admin_pinned_modules(self):
        """PDF scope combines legacy confirmed IDs with admin pins."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=False),
                _calculator_module_group(id='ai', selected=True),
            ]),
            persisted=['module-pwa'],
            confirmed=True,
        )

        result = default_selected_modules_from_content(proposal)

        assert set(result) == {'module-pwa', 'module-ai'}

    def test_unconfirmed_empty_persisted_falls_back_to_content_json(self):
        """Without a confirmation log, the admin's content_json defaults drive the PDF — the selected_modules field is ignored."""
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', selected=True),
            ]),
            persisted=[],
        )

        result = default_selected_modules_from_content(proposal)

        assert 'module-pwa' in result

    def test_includes_all_investment_modules_by_default(self):
        proposal = self._make_proposal(
            investment_content=_investment_content_json(modules=[
                {'id': 'mod-a', 'name': 'A', 'price': 100},
                {'id': 'mod-b', 'name': 'B', 'price': 200},
            ]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'mod-a' in result
        assert 'mod-b' in result

    def test_includes_regular_group_as_group_prefix(self):
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(groups=[{
                'id': 'views', 'title': 'Vistas',
                'is_visible': True, 'is_calculator_module': False,
                'items': [],
            }]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'group-views' in result

    def test_falls_back_to_default_selected_when_selected_absent(self):
        proposal = self._make_proposal(
            fr_content=_fr_section_content_json(additionalModules=[
                _calculator_module_group(id='pwa', default_selected=True),
            ]),
        )

        result = default_selected_modules_from_content(proposal)

        assert 'module-pwa' in result

    def test_returns_empty_list_for_proposal_without_sections(self):
        proposal = self._make_proposal()

        result = default_selected_modules_from_content(proposal)

        assert result == []


# ── Hosting: model fields override content_json ───────────────

class TestInvestmentHostingModelOverride:
    """BusinessProposal.hosting_* fields must override content_json.hostingPlan in the PDF (mirrors the public UI in frontend/pages/proposal/[uuid]/index.vue). Prevents regression of the stale-hosting bug introduced by d793ac79."""

    def test_model_hosting_percent_and_discount_override_content_json(  # quality: disable test_too_long (verifies full investment rendering cycle across hosting, discount, and tax fields)
        self, pdf_canvas, db,
    ):
        from content.services.proposal_pdf_service import _render_investment

        proposal = BusinessProposal.objects.create(
            title='Hosting override',
            client_name='Test', client_email='t@t.co',
            language='es', currency='COP', status='sent',
            total_investment=Decimal('6000000'),
            hosting_percent=40,
            hosting_discount_nine_month=40,
            hosting_discount_semiannual=25,
            hosting_discount_quarterly=15,
        )
        data = _investment_content_json(
            totalInvestment='$6.000.000',
            hostingPlan={
                'title': 'Cloud', 'description': 'Managed.',
                'hostingPercent': 30,
                'billingTiers': [
                    {'frequency': 'semiannual', 'months': 6,
                     'discountPercent': 20, 'label': 'Semestral'},
                    {'frequency': 'quarterly', 'months': 3,
                     'discountPercent': 10, 'label': 'Trimestral'},
                    {'frequency': 'monthly', 'months': 1,
                     'discountPercent': 0, 'label': 'Mensual'},
                ],
            },
        )

        drawn = []
        original_draw = pdf_canvas.drawString

        def _spy(x, y, text):
            drawn.append(text)
            return original_draw(x, y, text)

        pdf_canvas.drawString = _spy

        _render_investment(pdf_canvas, data, proposal)

        monthly_strings = [t for t in drawn if '/mes' in t]
        assert any('/9 meses' in t for t in drawn)
        assert not any('/año' in t for t in drawn)
        # Model values: 6_000_000 × 40% / 12 = 200_000 monthly base. The offered
        # tiers are nine-month/semiannual/quarterly (monthly is not offered):
        #   nine-month (40%): 120_000, semiannual (25%): 150_000, quarterly (15%): 170_000
        assert any('$120.000' in t for t in monthly_strings), (
            f'Expected nine-month tier $120.000/mes from model discount=40; '
            f'got: {monthly_strings}'
        )
        # Monthly is no longer an offered tier.
        assert not any('$200.000 /mes' in t for t in monthly_strings), (
            f'Monthly tier should no longer be rendered; got: {monthly_strings}'
        )
        assert any('$170.000' in t for t in monthly_strings), (
            f'Expected quarterly tier $170.000/mes from model discount=15; '
            f'got: {monthly_strings}'
        )
        assert any('$150.000' in t for t in monthly_strings), (
            f'Expected semiannual tier $150.000/mes from model discount=25; '
            f'got: {monthly_strings}'
        )
        # Stale JSON (30% × 10% quarterly = $135.000/mes; 30% monthly base =
        # $125.000/mes) must not leak. $150.000 is excluded because it
        # collides with the model's semiannual value.
        assert not any('$135.000 /mes' in t for t in monthly_strings), (
            'Stale content_json quarterly discount leaked into PDF'
        )
        assert not any('$125.000 /mes' in t for t in monthly_strings), (
            'Stale content_json hostingPercent leaked into PDF'
        )


# ── value_added_modules: dedicated "Sin costo adicional" section ──

class TestInvestmentModelTotalOverride:
    """BusinessProposal.total_investment and .currency must override content_json mirrors in the PDF, matching the frontend override in pages/proposal/[uuid]/index.vue. Prevents the staleness bug reported for proposal id=41 (PDF showed JSON total, UI showed model total)."""

    def test_model_total_investment_overrides_content_json(
        self, pdf_canvas, db,
    ):
        from content.services.proposal_pdf_service import _render_investment

        proposal = BusinessProposal.objects.create(
            title='Total override', client_name='Client',
            client_email='c@c.co', language='es', currency='COP',
            status='sent',
            total_investment=Decimal('7500000'),
        )
        data = _investment_content_json(
            totalInvestment='$2.000.000',  # stale JSON
            currency='USD',                 # stale JSON
        )

        drawn = []

        def _wrap(method_name):
            original = getattr(pdf_canvas, method_name)

            def _spy(x, y, text, *a, **kw):
                drawn.append(text)
                return original(x, y, text, *a, **kw)

            setattr(pdf_canvas, method_name, _spy)

        for name in ('drawString', 'drawRightString', 'drawCentredString'):
            _wrap(name)

        _render_investment(pdf_canvas, data, proposal)

        joined = '\n'.join(drawn)
        assert '$7.500.000' in joined, (
            f'Expected model total $7.500.000 in PDF; '
            f'got drawn strings: {drawn}'
        )
        assert '$2.000.000' not in joined, (
            'Stale content_json total leaked into PDF'
        )


class TestValueAddedModulesSection:
    """The PDF renders courtesy modules separately from optional scope."""

    def _proposal_with_value_added(self, *, selected_modules=None):
        p = BusinessProposal.objects.create(
            title='Value Added',
            client_name='Client', client_email='c@c.co',
            language='es', currency='COP', status='sent',
            total_investment=Decimal('5000000'),
            expires_at=timezone.now() + timezone.timedelta(days=20),
        )
        ProposalSection.objects.create(
            proposal=p, section_type='functional_requirements',
            title='FR', order=9, is_enabled=True,
            content_json={
                'index': '9', 'title': 'Requerimientos',
                'intro': 'Detalle.',
                'groups': [
                    {
                        'id': 'admin_module', 'title': 'Panel administrativo',
                        'icon': '🛠', 'is_visible': True,
                        'is_always_included': True,
                        'description': 'Panel para gestionar contenido.',
                        'items': [],
                    },
                    {
                        'id': 'analytics_dashboard', 'title': 'Dashboard analítico',
                        'icon': '📊', 'is_visible': True,
                        'is_always_included': True,
                        'description': 'Métricas de comportamiento.',
                        'items': [],
                    },
                ],
                'additionalModules': [
                    {
                        'id': 'pwa_module', 'title': 'Aplicación PWA',
                        'icon': '📱', 'is_visible': True,
                        'is_calculator_module': True,
                        'is_always_included': False,
                        'description': 'Convierte el sitio en PWA.',
                        'items': [],
                    },
                ],
            },
        )
        ProposalSection.objects.create(
            proposal=p, section_type='value_added_modules',
            title='Incluido sin costo', order=10, is_enabled=True,
            content_json={
                'index': '10',
                'title': 'Incluido sin costo adicional',
                'intro': 'Módulos que ya están cotizados dentro del precio.',
                'module_ids': ['admin_module', 'analytics_dashboard'],
                'justifications': {
                    'admin_module': 'Para independencia editorial del cliente.',
                    'analytics_dashboard': 'Para decisiones basadas en datos.',
                },
                'footer_note': 'Total adicional: $0.',
            },
        )
        return p, selected_modules

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_value_added_section_renders_justifications(self, _mock_back, _mock_cover):  # quality: disable unverified_mock (file-path stubs prevent real disk I/O; PDF content is the contract)  # noqa: PT019
        proposal, _ = self._proposal_with_value_added()
        pdf_bytes = ProposalPdfService.generate(proposal)

        assert pdf_bytes is not None
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)

        assert 'Panel administrativo' in text
        assert 'Dashboard analítico' in text
        assert 'Para independencia editorial del cliente.' in text
        assert 'Para decisiones basadas en datos.' in text
        assert 'Total adicional: $0.' in text

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_functional_requirements_excludes_value_added_ids(self, _mock_back, _mock_cover):  # quality: disable unverified_mock (file-path stubs prevent real disk I/O; PDF content is the contract)  # noqa: PT019
        proposal, _ = self._proposal_with_value_added()
        pdf_bytes = ProposalPdfService.generate(proposal)

        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)

        # Each value-added title should appear exactly once: in the dedicated
        # section, not duplicated inside the functional requirements overview.
        assert text.count('Panel administrativo') == 1
        assert text.count('Dashboard analítico') == 1

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_unselected_optional_module_absent_from_pdf(self, _mock_back, _mock_cover):  # quality: disable unverified_mock (file-path stubs prevent real disk I/O; PDF content is the contract)  # noqa: PT019
        proposal, _ = self._proposal_with_value_added()
        pdf_bytes = ProposalPdfService.generate(proposal, selected_modules=[])

        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)

        assert 'Aplicación PWA' not in text


# ── Item ↔ technical requirement traceability in group detail pages ──

class TestGenerateWithLinkedItemRequirements:
    def _create_sections(self, proposal, with_links=True):
        item = {'name': 'Registro de usuario', 'description': 'Alta de usuarios.'}
        if with_links:
            item['id'] = 'item-views-registro-de-usuario'
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Reqs', order=1, is_enabled=True,
            content_json={
                'index': '7', 'title': 'Requerimientos',
                'intro': 'Detalle.',
                'groups': [{
                    'id': 'views', 'title': 'Vistas',
                    'description': 'Páginas.',
                    'items': [item],
                }],
                'additionalModules': [],
            },
        )
        epic_req = {
            'flowKey': 'req-registro',
            'title': 'Registro con verificacion de email',
            'description': 'Formulario con validacion en tiempo real.',
            'priority': 'high',
        }
        if with_links:
            epic_req['linked_item_ids'] = ['item-views-registro-de-usuario']
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='technical_document',
            title='Detalle técnico', order=2, is_enabled=True,
            content_json={'epics': [{
                'epicKey': 'views', 'title': 'Vistas',
                'requirements': [epic_req],
            }]},
        )

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_linked_requirements_rendered_under_item(
        self, mock_back, mock_cover, proposal,
    ):
        self._create_sections(proposal, with_links=True)
        result = ProposalPdfService.generate(proposal)
        assert result is not None
        reader = PdfReader(io.BytesIO(result))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        assert 'Registro con verificacion de email' in text
        assert 'Alta' in text

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_legacy_proposal_without_ids_renders_unchanged(
        self, mock_back, mock_cover, proposal,
    ):
        self._create_sections(proposal, with_links=False)
        result = ProposalPdfService.generate(proposal)
        assert result is not None
        reader = PdfReader(io.BytesIO(result))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        # The item itself renders, but no linked technical requirement appears
        assert 'Registro de usuario' in text
        assert 'Registro con verificacion de email' not in text

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_deselected_module_requirements_excluded(
        self, mock_back, mock_cover, proposal,
    ):
        """Exclude requirements for a deselected optional module.

        Linked technical copy must not leak into the group detail pages.
        """
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Reqs', order=1, is_enabled=True,
            content_json={
                'index': '7', 'title': 'Requerimientos',
                'groups': [{
                    'id': 'views', 'title': 'Vistas', 'description': 'Páginas.',
                    'items': [{'name': 'Home', 'description': 'Landing.',
                               'id': 'item-views-home'}],
                }],
                'additionalModules': [{
                    'id': 'billing_module', 'title': 'Facturación',
                    'is_calculator_module': True,
                    'is_always_included': False,
                    'items': [{'name': 'Factura DIAN', 'description': 'Emisión.',
                               'id': 'item-billing_module-factura-dian'}],
                }],
            },
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='technical_document',
            title='Detalle técnico', order=2, is_enabled=True,
            content_json={'epics': [{
                'epicKey': 'billing', 'title': 'Facturación',
                'linked_module_ids': ['module-billing_module'],
                'requirements': [{
                    'flowKey': 'req-dian',
                    'title': 'Emision electronica DIAN',
                    'priority': 'critical',
                    'linked_module_ids': ['module-billing_module'],
                    'linked_item_ids': ['item-billing_module-factura-dian'],
                }],
            }]},
        )
        # Empty selection → module not contracted
        result = ProposalPdfService.generate(proposal, selected_modules=[])
        assert result is not None
        reader = PdfReader(io.BytesIO(result))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        assert 'Emision electronica DIAN' not in text

    @patch(
        'content.services.proposal_pdf_service.COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    @patch(
        'content.services.proposal_pdf_service.BACK_COVER_PDF',
        new_callable=lambda: MagicMock(exists=MagicMock(return_value=False)),
    )
    def test_messy_whitespace_and_bold_markers_normalized(
        self, mock_back, mock_cover, proposal,
    ):
        """Normalize whitespace and bold markers in linked content.

        Drawing does not leak .notdef glyphs or literal asterisks.
        """
        item = {'name': 'Registro\tde\nusuario', 'description': 'Alta.',
                'id': 'item-views-registro-de-usuario'}
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='functional_requirements',
            title='Reqs', order=1, is_enabled=True,
            content_json={
                'index': '7', 'title': 'Requerimientos', 'intro': 'Detalle.',
                'groups': [{'id': 'views', 'title': 'Vistas',
                            'description': 'Páginas.', 'items': [item]}],
                'additionalModules': [],
            },
        )
        ProposalSection.objects.create(
            proposal=proposal,
            section_type='technical_document',
            title='Detalle técnico', order=2, is_enabled=True,
            content_json={'epics': [{
                'epicKey': 'views', 'title': 'Vistas',
                'requirements': [{
                    'flowKey': 'req-registro',
                    'title': '**Registro** con <b>verificacion</b> de email',
                    'description': 'Formulario validado.',
                    'priority': 'high',
                    'linked_item_ids': ['item-views-registro-de-usuario'],
                }],
            }]},
        )
        result = ProposalPdfService.generate(proposal)
        assert result is not None
        reader = PdfReader(io.BytesIO(result))
        text = '\n'.join(p.extract_text() or '' for p in reader.pages)
        assert 'Registro de usuario' in text
        assert 'Registro con verificacion de email' in text
        assert '**' not in text


class _SpyCanvas:
    """Delegating canvas that records filled rects and roundRects."""

    def __init__(self, real):
        self._real = real
        self.round_rects = []   # (x, y, w, h)
        self.rects = []

    def roundRect(self, x, y, w, h, r, **kw):
        self.round_rects.append((x, y, w, h))
        return self._real.roundRect(x, y, w, h, r, **kw)

    def rect(self, x, y, w, h, **kw):
        self.rects.append((x, y, w, h))
        return self._real.rect(x, y, w, h, **kw)

    def __getattr__(self, name):
        return getattr(self._real, name)


class TestLinkedRequirementsGeometry:
    """DB-free geometry contract for the linked-requirement sub-rows."""

    ROW_Y = 700  # high enough that _check_y never breaks the page

    def _render(self, req):
        _register_fonts()
        real = canvas.Canvas(io.BytesIO(), pagesize=A4)
        c = _SpyCanvas(real)
        ps = {'_item_requirements_map': {'i1': [req]}, '_pdf_lang': 'es'}
        end_y = _render_linked_requirements(
            c, {'id': 'i1', 'name': 'Ítem'}, ps, self.ROW_Y)
        return c, end_y

    def test_pill_stays_inside_content_and_row(self):
        c, _ = self._render({
            'title': 'Registro e inicio de sesión con verificación de correo '
                     'y recuperación de contraseña para todos los perfiles',
            'description': 'Formulario validado.',
            'priority': 'critical',
        })
        assert len(c.round_rects) == 1
        x, y, w, h = c.round_rects[0]
        assert x + w <= MARGIN_L + CONTENT_W
        assert y + h <= self.ROW_Y  # never paints into the parent row above

    def test_band_spans_full_table_width(self):
        c, end_y = self._render({
            'title': 'Registro', 'description': 'Alta.', 'priority': 'high',
        })
        bands = [r for r in c.rects if r[0] == MARGIN_L and r[2] == CONTENT_W]
        assert bands, 'expected a full-width background band'
        assert end_y == bands[0][1]  # returned row_y is the band bottom

    def test_no_priority_draws_no_pill(self):
        c, _ = self._render({
            'title': 'Registro', 'description': 'Alta.', 'priority': '',
        })
        assert c.round_rects == []
        assert any(r[0] == MARGIN_L and r[2] == CONTENT_W for r in c.rects)
