"""Verifiable delivery sources read through the real isolated file parsers."""
from html import escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image
from pypdf import PdfReader, PdfWriter
import pytest
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from accounts.services.delivery_source_extraction import (
    MAX_JSON_DEPTH, MAX_JSON_LOCATOR_CHARACTERS, MAX_JSON_NODES,
    extract_prompt_source,
)
from content.services.attachment_markdown import (
    MAX_FILE_BYTES, MAX_PDF_PAGES, MAX_SOURCE_CHARACTERS, MAX_SOURCE_FRAGMENTS,
)


def _pdf_bytes(pages):
    image_bytes = BytesIO()
    Image.new('RGB', (10, 10), color='black').save(image_bytes, format='PNG')
    output = BytesIO()
    canvas = Canvas(output, invariant=1)
    for text in pages:
        if text is None:
            canvas.drawImage(ImageReader(BytesIO(image_bytes.getvalue())), 72, 650, width=100, height=100)
        else:
            canvas.drawString(72, 720, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def _docx_bytes(paragraphs):
    body = ''.join(
        '<w:p>' + ('<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>' if heading else '')
        + '<w:r><w:t>' + escape(text) + '</w:t></w:r></w:p>'
        for heading, text in paragraphs
    )
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
          <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
          <Default Extension="xml" ContentType="application/xml"/>
          <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
        </Types>''')
        archive.writestr('_rels/.rels', '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
        </Relationships>''')
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')
    return output.getvalue()


def test_pdf_source_locates_actual_pages():
    """Every excerpt identifies the real page containing its quoted text."""
    result = extract_prompt_source(_pdf_bytes(['Alcance inicial', 'Condiciones de pago']), 'contrato.pdf')

    assert result['status'] == 'included'
    assert result['fragments'] == [
        {'locator': 'Página 1', 'text': 'Alcance inicial'},
        {'locator': 'Página 2', 'text': 'Condiciones de pago'},
    ]
    assert result['limits']['pdf_pages_total'] == 2
    assert result['limits']['pdf_pages_examined'] == 2


def test_pdf_source_marks_scanned_page_as_unavailable():
    """A scan between readable pages preserves actual numbering and declares the gap."""
    result = extract_prompt_source(_pdf_bytes(['Primera condición', None, 'Tercera condición']), 'contrato.pdf')

    assert result['status'] == 'partial'
    assert result['fragments'] == [
        {'locator': 'Página 1', 'text': 'Primera condición'},
        {'locator': 'Página 3', 'text': 'Tercera condición'},
    ]
    assert 'Página 2 sin texto extraíble' in ' '.join(result['warnings'])
    assert 'No se aplicó OCR' in ' '.join(result['warnings'])


def test_pdf_source_is_unreadable_when_only_scanned():
    """An image-only signed PDF cannot provide invented contractual excerpts."""
    result = extract_prompt_source(_pdf_bytes([None]), 'firmado.pdf')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert 'escaneo' in ' '.join(result['warnings'])


def test_pdf_source_rejects_encrypted_evidence():
    """Encrypted evidence produces a controlled warning rather than empty success."""
    writer = PdfWriter()
    writer.add_page(PdfReader(BytesIO(_pdf_bytes(['Condición privada']))).pages[0])
    writer.encrypt('fixture-password')
    content = BytesIO()
    writer.write(content)

    result = extract_prompt_source(content.getvalue(), 'firmado.pdf')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert 'protegido' in ' '.join(result['warnings'])


def test_pdf_source_marks_page_limit_as_partial():
    """Readable pages beyond the cap are omitted with an explicit count."""
    data = _pdf_bytes([f'Condición {number}' for number in range(1, MAX_PDF_PAGES + 2)])

    result = extract_prompt_source(data, 'largo.pdf')

    assert result['status'] == 'partial'
    assert len(result['fragments']) == MAX_PDF_PAGES
    assert result['fragments'][-1] == {'locator': 'Página 100', 'text': 'Condición 100'}
    assert result['limits']['pdf_pages_total'] == 101
    assert result['limits']['pdf_pages_examined'] == MAX_PDF_PAGES
    assert 'primeras 100' in ' '.join(result['warnings'])


def test_pdf_source_marks_character_limit_as_partial():
    """A real long PDF page cannot silently lose characters from its evidence."""
    result = extract_prompt_source(_pdf_bytes(['X' * (MAX_SOURCE_CHARACTERS + 1)]), 'largo.pdf')

    assert result['status'] == 'partial'
    assert result['fragments'][0]['locator'] == 'Página 1'
    assert len(result['fragments'][0]['text']) == MAX_SOURCE_CHARACTERS
    assert result['limits']['characters_returned'] == MAX_SOURCE_CHARACTERS
    assert '60.000 caracteres' in ' '.join(result['warnings'])


def test_signed_pdf_source_does_not_fall_back_to_live_markdown():
    """Failure to read supplied bytes must never substitute mutable portal text."""
    result = extract_prompt_source(
        b'not a valid PDF', '/private/storage/firmado.pdf',
        markdown='Contenido vivo diferente', content_json={'blocks': [{'text': 'Otra versión'}]},
    )

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert '/private/storage' not in str(result)


def test_docx_source_locates_sections_by_paragraph():
    """DOCX references keep blank-paragraph positions without claiming PDF pages."""
    data = _docx_bytes([(True, 'Alcance'), (False, ''), (False, 'Alta [v1]'), (True, 'Pago'), (False, 'Confirmar cuota')])

    result = extract_prompt_source(data, 'anexo.docx')

    assert result['status'] == 'included'
    assert result['fragments'] == [
        {'locator': 'Documento · sección «Alcance» · párrafo 1', 'text': 'Alcance'},
        {'locator': 'Documento · sección «Alcance» · párrafo 3', 'text': 'Alta [v1]'},
        {'locator': 'Documento · sección «Pago» · párrafo 4', 'text': 'Pago'},
        {'locator': 'Documento · sección «Pago» · párrafo 5', 'text': 'Confirmar cuota'},
    ]


def test_docx_source_is_unreadable_without_text():
    """A valid empty office package has no textual contractual evidence."""
    result = extract_prompt_source(_docx_bytes([(False, '')]), 'vacio.docx')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert 'no contiene texto extraíble' in ' '.join(result['warnings'])


def test_markdown_source_locates_original_section_lines():
    """Locators identify real source line ranges instead of generated paragraph numbers."""
    result = extract_prompt_source(None, '', markdown='# Alcance\n\nValidar el pedido.\n\n## Pago\nElegir cuenta.')

    assert result['status'] == 'included'
    assert result['fragments'] == [
        {'locator': 'Sección «Alcance» · líneas 1–1', 'text': '# Alcance'},
        {'locator': 'Sección «Alcance» · líneas 3–3', 'text': 'Validar el pedido.'},
        {'locator': 'Sección «Pago» · líneas 5–6', 'text': '## Pago\nElegir cuenta.'},
    ]


def test_markdown_source_preserves_headings_inside_code_as_text():
    """A code comment cannot become a false contract section locator."""
    result = extract_prompt_source(None, '', markdown='# Alcance\n\n```python\n# Comentario\n```')

    assert result['fragments'][-1] == {
        'locator': 'Sección «Alcance» · líneas 3–5', 'text': '```python\n# Comentario\n```',
    }


def test_json_source_excludes_private_metadata_from_block_paths():
    """Only visible block values enter excerpts; internal notes and storage never enter prompts."""
    result = extract_prompt_source(None, '', content_json={
        'meta': {'private_notes': 'nota privada', 'storage_path': '/private/meta'},
        'blocks': [
            {'type': 'heading', 'text': 'Cobros', 'internal_notes': 'secreto del equipo'},
            {'type': 'paragraph', 'text': 'Se paga al aprobar.', 'file_path': '/private/archivo'},
        ],
    })

    assert result['status'] == 'included'
    assert result['fragments'] == [
        {'locator': 'Bloque $.blocks[0].text', 'text': 'Cobros'},
        {'locator': 'Bloque $.blocks[1].text', 'text': 'Se paga al aprobar.'},
    ]
    assert 'privada' not in str(result)
    assert 'secreto' not in str(result)
    assert '/private/' not in str(result)


def test_json_source_locates_nested_business_values():
    """A document without Markdown still supplies independently citable JSON paths."""
    result = extract_prompt_source(None, '', content_json={
        'scope': {'requirements': [{'description': 'Crear pedido', 'amount': 200}]},
    })

    assert result['fragments'] == [
        {'locator': 'Bloque $.scope.requirements[0].description', 'text': 'Crear pedido'},
        {'locator': 'Bloque $.scope.requirements[0].amount', 'text': '200'},
    ]


def test_markdown_source_is_unreadable_when_blank():
    """Existing whitespace-only content cannot count as a reviewed source."""
    result = extract_prompt_source(None, '', markdown=' \n\t')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []


def test_json_source_replaces_whitespace_only_markdown():
    """Blank live text cannot hide the actual structured source content."""
    result = extract_prompt_source(b'', '', markdown=' \n', content_json={
        'blocks': [{'text': 'Alcance estructurado'}],
    })

    assert result['status'] == 'included'
    assert result['fragments'] == [{'locator': 'Bloque $.blocks[0].text', 'text': 'Alcance estructurado'}]


def test_source_is_missing_without_content():
    """A missing source is distinguished from an existing file with unreadable text."""
    result = extract_prompt_source(None, 'contrato.pdf')

    assert result['status'] == 'missing'
    assert result['fragments'] == []
    assert result['limits']['max_characters'] == MAX_SOURCE_CHARACTERS


def test_empty_file_bytes_allow_portal_snapshot_text():
    """The caller can explicitly provide a portal text snapshot without an attachment."""
    result = extract_prompt_source(b'', '', markdown='Alcance firmado en portal')

    assert result['status'] == 'included'
    assert result['fragments'][0]['text'] == 'Alcance firmado en portal'


def test_corrupt_docx_returns_controlled_unreadable_source():
    """An invalid office archive cannot leak parser exceptions or internal filenames."""
    result = extract_prompt_source(b'broken archive', '/private/files/documento.docx')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert '/private/files' not in str(result)


def test_raw_json_source_precedes_current_portal_content():
    """Supplied attachment bytes provide the source version even when live text differs."""
    result = extract_prompt_source(b'{"scope":"Alcance anterior"}', 'anexo.json', markdown='Alcance vigente')

    assert result['fragments'] == [{'locator': 'Bloque $.scope', 'text': 'Alcance anterior'}]


def test_raw_markdown_source_keeps_file_line_references():
    """The author receives the attachment's actual text and line locators, without live-text substitution."""
    data = '# Alcance\n\nRevisar conexión.'.encode('utf-8-sig')

    result = extract_prompt_source(data, 'contrato.md', markdown='Versión viva diferente')

    assert result['status'] == 'included'
    assert result['warnings'] == []
    assert result['fragments'] == [
        {'locator': 'Sección «Alcance» · líneas 1–1', 'text': '# Alcance'},
        {'locator': 'Sección «Alcance» · líneas 3–3', 'text': 'Revisar conexión.'},
    ]


def test_unsupported_attachment_requires_original_review():
    """An unsupported image warns the author to review the original instead of claiming empty evidence is complete."""
    image = BytesIO()
    Image.new('RGB', (10, 10), color='black').save(image, format='PNG')

    result = extract_prompt_source(image.getvalue(), 'contrato.png', markdown='Versión viva diferente')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert result['warnings'] == [
        'El formato no admite extracción de texto verificable; requiere revisión del original.',
    ]


def test_invalid_json_attachment_reports_unreadable_source():
    """Malformed JSON receives a clear warning and cannot substitute mutable text as contractual evidence."""
    result = extract_prompt_source(
        b'{"scope":', 'contrato.json', markdown='Versión viva diferente',
        content_json={'scope': 'Contenido no respaldado por el archivo'},
    )

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert result['warnings'] == [
        'No se pudo leer la fuente; puede estar dañada o usar una codificación no admitida.',
    ]


@pytest.mark.parametrize('kwargs', [
    {'markdown': 'X' * (MAX_SOURCE_CHARACTERS + 1)},
    {'content_json': {'blocks': [{'text': 'X' * (MAX_SOURCE_CHARACTERS + 1)}]}},
], ids=['markdown', 'json'])
def test_source_limits_mark_character_cut_as_partial(kwargs):
    """Text sources declare character clipping as incomplete contractual context."""
    result = extract_prompt_source(None, '', **kwargs)

    assert result['status'] == 'partial'
    assert result['limits']['characters_returned'] == MAX_SOURCE_CHARACTERS
    assert '60.000 caracteres' in ' '.join(result['warnings'])


def test_source_limits_mark_fragment_cut_as_partial():
    """Many tiny JSON values cannot evade the independently declared fragment budget."""
    result = extract_prompt_source(None, '', content_json=['texto'] * (MAX_SOURCE_FRAGMENTS + 1))

    assert result['status'] == 'partial'
    assert len(result['fragments']) == MAX_SOURCE_FRAGMENTS
    assert result['limits']['max_fragments'] == MAX_SOURCE_FRAGMENTS
    assert '1.000 fragmentos' in ' '.join(result['warnings'])


def test_source_limits_mark_json_depth_cut_as_partial():
    """Deep JSON does not silently hide a clause beyond the supported nesting depth."""
    nested = {'text': 'Condición demasiado profunda'}
    for _ in range(MAX_JSON_DEPTH + 1):
        nested = {'child': nested}

    result = extract_prompt_source(None, '', content_json={'visible': 'Condición disponible', 'nested': nested})

    assert result['status'] == 'partial'
    assert result['fragments'] == [{'locator': 'Bloque $.visible', 'text': 'Condición disponible'}]
    assert result['limits']['max_json_depth'] == MAX_JSON_DEPTH
    assert '32 niveles JSON' in ' '.join(result['warnings'])


@pytest.mark.parametrize('omitted_structure', [
    {'empty_nodes': [{}] * (MAX_JSON_NODES + 1)},
    {f'private_{index}': '' for index in range(MAX_JSON_NODES + 1)},
], ids=['empty_nodes', 'private_fields'])
def test_source_limits_mark_json_node_cut_as_partial(omitted_structure):
    """Empty structures cannot force an unbounded walk while the available clause remains usable."""
    result = extract_prompt_source(None, '', content_json={
        'visible': 'Condición disponible', **omitted_structure,
    })

    assert result['status'] == 'partial'
    assert result['fragments'] == [{'locator': 'Bloque $.visible', 'text': 'Condición disponible'}]
    assert result['limits']['json_nodes_examined'] == MAX_JSON_NODES
    assert '5.000 elementos JSON' in ' '.join(result['warnings'])


def test_source_limits_reject_oversized_file_bytes():
    """An oversized signed attachment must not substitute the smaller mutable text."""
    result = extract_prompt_source(b'X' * (MAX_FILE_BYTES + 1), 'firmado.pdf', markdown='Versión viva')

    assert result['status'] == 'unreadable'
    assert result['fragments'] == []
    assert result['limits']['max_file_bytes'] == MAX_FILE_BYTES
    assert '15 MB' in ' '.join(result['warnings'])


@pytest.mark.parametrize(('filename', 'raw_bytes', 'markdown'), [
    ('', None, '# ' + 'X' * 201),
    ('titulo.docx', _docx_bytes([(True, 'X' * 201)]), ''),
], ids=['markdown', 'docx'])
def test_source_limits_mark_shortened_section_reference_as_partial(filename, raw_bytes, markdown):
    """Even a shortened section label is declared while its original text stays available."""
    result = extract_prompt_source(raw_bytes, filename, markdown=markdown)

    assert result['status'] == 'partial'
    assert '…' in result['fragments'][0]['locator']
    assert 'X' * 201 in result['fragments'][0]['text']
    assert result['limits']['max_section_title_characters'] == 200
    assert 'referencia se abrevia' in ' '.join(result['warnings'])


def test_source_limits_mark_oversized_json_locator_as_partial():
    """An unbounded property name is omitted without inventing a shortened JSON path."""
    result = extract_prompt_source(None, '', content_json={
        'visible': 'Condición disponible', 'X' * (MAX_JSON_LOCATOR_CHARACTERS + 1): 'Condición sin referencia acotada',
    })

    assert result['status'] == 'partial'
    assert result['fragments'] == [{'locator': 'Bloque $.visible', 'text': 'Condición disponible'}]
    assert result['limits']['max_json_locator_characters'] == MAX_JSON_LOCATOR_CHARACTERS
    assert 'referencia JSON supera' in ' '.join(result['warnings'])
