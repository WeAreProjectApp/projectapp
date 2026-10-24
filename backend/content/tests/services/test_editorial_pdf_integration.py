"""Integration coverage for editorial rich text in generated PDF bytes."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from content.services.document_pdf_service import DocumentPdfService
from content.services.editorial_pdf import draw_editorial_source
from content.services.pdf_utils import MARGIN_B, MARGIN_T, PAGE_H


def pdf_text(pdf_bytes):
    return '\n'.join(page.extract_text() or '' for page in PdfReader(BytesIO(pdf_bytes)).pages)


def test_draw_editorial_source_draws_list_table_and_colored_text():
    """Falla si el dibujador editorial deja de convertir listas, tablas o texto coloreado en PDF."""
    source = (
        '<p style="text-align:center"><span style="color:#ff0000">Rojo</span></p>\n'
        '<ul><li>Alcance</li><li>Entrega</li></ul>\n'
        '<table><thead><tr><th>Fase</th><th>Estado</th></tr></thead>'
        '<tbody><tr><td>Diseño</td><td>Listo</td></tr></tbody></table>'
    )
    output = BytesIO()
    pdf_canvas = canvas.Canvas(output, pagesize=A4, pageCompression=0)

    remaining_y = draw_editorial_source(pdf_canvas, 700, source, width=460, x=60)
    pdf_canvas.save()
    pdf_bytes = output.getvalue()

    assert remaining_y < 700
    assert pdf_bytes[:4] == b'%PDF'
    assert 'Rojo' in pdf_text(pdf_bytes)
    assert 'Alcance' in pdf_text(pdf_bytes)
    assert 'Diseño' in pdf_text(pdf_bytes)


def test_document_pdf_service_renders_rich_html_block_without_persisting_document():
    """Falla si el PDF de un documento omite un bloque editorial aunque el contenido sea válido."""
    document = SimpleNamespace(
        id=1,
        title='Acta editorial',
        client_name='Cliente',
        cover_type='generic',
        language='es',
        include_portada=False,
        include_subportada=False,
        include_contraportada=False,
        template_style='professional',
        content_markdown='',
        content_json={
            'meta': {'client_name': 'Cliente'},
            'blocks': [{
                'type': 'rich_html',
                'html': '<p style="text-align:right"><strong>Aprobación final</strong></p>',
            }],
        },
    )

    pdf_bytes = DocumentPdfService.generate(document)

    assert pdf_bytes[:4] == b'%PDF'
    assert 'Aprobación final' in pdf_text(pdf_bytes)


def test_editorial_pdf_uses_bold_font_for_bold_content():
    """Falla si negrita se dibuja con la fuente regular aunque el texto exista."""
    output = BytesIO()
    pdf_canvas = canvas.Canvas(output, pagesize=A4)

    draw_editorial_source(pdf_canvas, 700, '**Negrita visible**', width=460, x=60)
    pdf_canvas.save()
    page = PdfReader(BytesIO(output.getvalue())).pages[0]
    fonts = [str(item.get_object().get('/BaseFont', '')) for item in page['/Resources']['/Font'].values()]

    assert any('Ubuntu-Bold' in font for font in fonts)


def test_editorial_pdf_moves_content_to_the_next_page():
    """Falla si un bloque sin espacio al pie desaparece en vez de pasar a la página siguiente."""
    output = BytesIO()
    pdf_canvas = canvas.Canvas(output, pagesize=A4)
    page_state = {'num': 1, 'client': 'Cliente de prueba'}

    draw_editorial_source(
        pdf_canvas, MARGIN_B + 12, '<p>Contenido transferido íntegro</p>',
        width=460, x=60, ps=page_state,
    )
    pdf_canvas.save()
    pages = PdfReader(BytesIO(output.getvalue())).pages

    assert len(pages) == 2
    assert 'Contenido transferido íntegro' not in pages[0].extract_text()
    assert 'Contenido transferido íntegro' in pages[1].extract_text()


def test_editorial_pdf_preserves_the_tail_of_a_split_paragraph():
    """Falla si dividir un párrafo entre páginas omite el final del contenido original."""
    output = BytesIO()
    pdf_canvas = canvas.Canvas(output, pagesize=A4)
    page_state = {'num': 1, 'client': 'Cliente de prueba'}
    source = '<p>Inicio estable<br>' + 'Continuación<br>' * 48 + 'Final íntegro</p>'

    draw_editorial_source(pdf_canvas, 700, source, width=460, x=60, ps=page_state)
    pdf_canvas.save()
    pages = PdfReader(BytesIO(output.getvalue())).pages

    assert len(pages) == 2
    assert 'Inicio estable' in pages[0].extract_text()
    assert 'Final íntegro' in pages[1].extract_text()


def test_editorial_pdf_rejects_a_table_row_taller_than_a_page():
    """Falla si una fila indivisible demasiado alta provoca páginas vacías sin terminar."""
    output = BytesIO()
    pdf_canvas = canvas.Canvas(output, pagesize=A4)
    page_state = {'num': 1, 'client': 'Cliente de prueba'}
    source = '<table><tr><td><p>' + 'Detalle<br>' * 80 + '</p></td></tr></table>'

    with pytest.raises(ValueError, match='El bloque editorial excede el área imprimible'):
        draw_editorial_source(
            pdf_canvas, PAGE_H - MARGIN_T, source, width=460, x=60, ps=page_state,
        )
