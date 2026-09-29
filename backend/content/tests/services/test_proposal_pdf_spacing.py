"""Geometry contracts for readable proposal documents, using a real canvas."""
from io import BytesIO

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from content.services import pdf_utils as pdf
from content.services import proposal_pdf_layout as layout
from content.services.proposal_pdf_service import (
    _render_requirement_group_page, _render_value_added_modules,
)


class RecordingCanvas:
    def __init__(self):
        pdf._register_fonts()
        self.buffer = BytesIO()
        self.canvas = canvas.Canvas(self.buffer, pagesize=A4)
        self.text = []
        self.pills = []
        self.bands = []

    def drawString(self, x, y, text, *args, **kwargs):
        font, size = self.canvas._fontname, self.canvas._fontsize
        ascent, descent = pdfmetrics.getAscentDescent(font, size)
        self.text.append((str(text), self.canvas.getPageNumber(), x, y + descent,
                          x + pdfmetrics.stringWidth(str(text), font, size), y + ascent, y))
        return self.canvas.drawString(x, y, text, *args, **kwargs)

    def roundRect(self, x, y, width, height, *args, **kwargs):
        self.pills.append((self.canvas.getPageNumber(), x, y, x + width, y + height))
        return self.canvas.roundRect(x, y, width, height, *args, **kwargs)

    def rect(self, x, y, width, height, *args, **kwargs):
        self.bands.append((self.canvas.getPageNumber(), x, y, width, height))
        return self.canvas.rect(x, y, width, height, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.canvas, name)


@pytest.fixture
def drawing():
    return RecordingCanvas()


@pytest.fixture
def page_state():
    return {'num': 1, 'client': 'Spacing sample', '_pdf_lang': 'es'}


@pytest.mark.parametrize('title', [
    'Registro',
    'Registro e inicio de sesión con verificación de correo y recuperación de contraseña',
])
def test_priority_is_separated_from_requirement_title(drawing, page_state, title):
    layout._draw_requirements_table(drawing, 700, [
        {'title': title, 'priority': 'critical', 'description': 'Descripción breve.'},
    ], page_state)

    badge = drawing.pills[0]
    title_lines = [t for t in drawing.text if t[2] == pdf.MARGIN_L + 34 and t[5] < 678 and t[0] != 'Crítico']
    last_line = title_lines[-1]

    assert last_line[3] - badge[4] >= 6


def test_priority_stays_inside_its_row(drawing, page_state):
    layout._draw_requirements_table(drawing, 700, [{'title': 'Login', 'priority': 'high'}], page_state)

    badge = drawing.pills[0]
    row = [r for r in drawing.bands if r[3] == pdf.CONTENT_W][-1]

    assert badge[2] - row[2] >= 6
    assert row[2] + row[4] - badge[4] >= 6


def test_missing_priority_has_no_empty_badge(drawing, page_state):
    layout._draw_requirements_table(drawing, 700, [{'title': 'Login'}], page_state)

    assert drawing.pills == []
    assert any(t[0] == 'Login' for t in drawing.text)


@pytest.mark.parametrize(('text', 'distance'), [
    ('Primero\nSegundo', 15),
    ('Primero\n\nSegundo', 23),
    ('Primero<br>Segundo', 15),
    ('Primero<br><br>Segundo', 23),
    ('<p>Primero</p><p>Segundo</p>', 23),
])
def test_explicit_breaks_have_visible_spacing(drawing, text, distance):
    layout._draw_paragraphs(drawing, 700, [text])

    first, second = drawing.text

    assert first[0] == 'Primero'
    assert second[0] == 'Segundo'
    assert first[6] - second[6] == distance


def test_paragraph_measurement_matches_rendered_height(drawing):
    text = ['Texto largo **con negrita** ' * 15 + '\n\nOtro párrafo.', 'Cierre.']
    measured = layout._estimate_text_height(text, max_width=180)

    bottom = layout._draw_paragraphs(drawing, 700, text, max_width=180)

    assert 700 - bottom == measured


def test_other_pdf_families_keep_default_paragraph_spacing(drawing):
    bottom = pdf._draw_paragraphs(drawing, 700, ['Primero', 'Segundo'])

    assert bottom == 660
    assert drawing.text[0][6] - drawing.text[1][6] == 20


def test_long_heading_badge_stays_inside_page(drawing, page_state):
    _render_requirement_group_page(drawing, {
        'title': 'Gestión de usuarios y permisos de acceso del proyecto ' * 3,
        'items': [{'name': 'Login', 'description': 'Alta.'}],
    }, ps=page_state, y=700)

    assert max(t[4] for t in drawing.text) <= pdf.MARGIN_L + pdf.CONTENT_W + .1
    assert max(b[3] for b in drawing.pills) <= pdf.MARGIN_L + pdf.CONTENT_W + .1


def test_external_badge_has_room_before_next_paragraph(drawing, page_state):
    bottom = layout._draw_heading_badge(drawing, 700, 'Módulo', '2 requerimientos', page_state)
    layout._draw_paragraphs(drawing, bottom, ['Descripción.'], ps=page_state)

    title = next(t for t in drawing.text if t[0] == 'Módulo')
    desc = next(t for t in drawing.text if t[0] == 'Descripción.')
    badge = drawing.pills[0]

    assert title[3] - badge[4] >= 30
    assert badge[2] - desc[5] >= 30


def test_oversized_requirement_keeps_all_content_above_footer(drawing, page_state):
    description = 'Detalle verificable ' * 1300 + 'FINAL_DEL_REQUERIMIENTO'
    layout._draw_requirements_table(drawing, 700, [
        {'title': 'Acceso', 'description': description, 'priority': 'critical'},
    ], page_state)

    body = [t for t in drawing.text if 'Detalle' in t[0] or 'FINAL_DEL_REQUERIMIENTO' in t[0]]

    assert min(t[3] for t in body) >= pdf.MARGIN_B
    assert sum(t[0].count('Detalle') for t in body) == 1300
    assert sum(t[0].count('FINAL_DEL_REQUERIMIENTO') for t in body) == 1
    assert sum(t[0] == 'Requerimiento' for t in drawing.text) > 1


def test_long_title_keeps_priority_on_its_last_page(drawing, page_state):
    title = 'Título largo ' * 750 + 'FIN_TITULO'
    layout._draw_requirements_table(drawing, 700, [{'title': title, 'priority': 'high'}], page_state)

    last = next(t for t in drawing.text if 'FIN_TITULO' in t[0])

    assert drawing.pills[0][0] == last[1]
    assert last[3] - drawing.pills[0][4] >= 6


def test_badge_group_wraps_without_losing_clickable_links(drawing, page_state):
    layout._draw_badge_group(drawing, 700, [
        {'text': 'Agendar revisión ' * 12, 'link': 'https://example.com/review'},
        {'text': 'Confirmar alcance ' * 12, 'link': 'https://example.com/scope'},
    ], page_state, max_width=180)
    drawing.save()
    reader = PdfReader(drawing.buffer)

    links = [a.get_object()['/A']['/URI'] for a in reader.pages[0]['/Annots']]

    assert links == ['https://example.com/review', 'https://example.com/scope']
    assert all(b[3] <= pdf.MARGIN_L + 180 + .1 for b in drawing.pills)
    assert drawing.pills[0][2] > drawing.pills[1][4]


@pytest.mark.parametrize('font_size', [7, 9])
def test_badge_label_uses_its_measured_font(drawing, page_state, font_size):
    drawing.setFont(pdf._font('light'), 24)
    layout._draw_badge_group(drawing, 700, [
        {'text': '2 requerimientos', 'font_size': font_size},
    ], page_state)

    label = drawing.text[0]
    badge = drawing.pills[0]

    assert badge[1] < label[2] < label[4] < badge[3]
    assert badge[2] <= label[3] < label[5] <= badge[4]


def test_contact_email_keeps_its_explicit_mailto_target(drawing, page_state):
    layout._draw_contact_value(drawing, 700, 'team@example.com', 'mailto:team@example.com', page_state)
    drawing.save()
    page = PdfReader(drawing.buffer).pages[0]

    assert 'team@example.com' in page.extract_text()
    assert [a.get_object()['/A']['/URI'] for a in page['/Annots']] == ['mailto:team@example.com']


def test_oversized_included_module_keeps_closing_paragraph(drawing, page_state):
    page_state['_value_added_catalog'] = {'included': {
        'title': 'Administración',
        'description': 'Contenido de administración ' * 1000 + '\n\nCIERRE_DEL_MODULO',
    }}

    _render_value_added_modules(drawing, {'title': 'Incluido', 'module_ids': ['included']},
                                None, ps=page_state, y=700)

    closing = next(t for t in drawing.text if t[0] == 'CIERRE_DEL_MODULO')
    assert closing[1] > 1
    assert closing[3] >= pdf.MARGIN_B
