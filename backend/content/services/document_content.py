"""Canonical ``content_json`` construction for markdown documents.

``Document.content_json`` is not derived automatically — no signal, no
``save()`` hook — so every writer has to build it. Keeping that dict in one
place is the point of this module: the shape used to be copy-pasted across the
panel views, the MCP tools and the management commands, and the one writer that
forgot the copy (``create_estimate_document``) shipped documents whose PDF
download answered 400 while their markdown was perfectly fine.
"""

from content.services.markdown_parser import markdown_to_blocks


def build_content_json(document, markdown_text=None):
    """Build the ``{meta, blocks}`` payload the PDF stage reads.

    Args:
        document: Document instance (saved or not) the meta is read from.
        markdown_text: Markdown to parse. Defaults to the document's own
            ``content_markdown``.

    Returns:
        dict: ``{'meta': {...}, 'blocks': [...]}``.
    """
    text = document.content_markdown if markdown_text is None else markdown_text
    return {
        'meta': {
            'title': document.title,
            'client_name': document.client_name,
            'cover_type': document.cover_type,
            'template_style': document.template_style,
            'include_portada': document.include_portada,
            'include_subportada': document.include_subportada,
            'include_contraportada': document.include_contraportada,
        },
        'blocks': markdown_to_blocks(text or '', editorial=(getattr(document, 'text_formats', {}) or {}).get('/content_markdown') == 'markdown_html_v1'),
    }


def resolve_blocks(document):
    """Return the document's blocks, deriving them from markdown when absent.

    The persisted ``content_json`` wins when it has blocks. Falling back to the
    markdown keeps a document readable even if whatever created it skipped the
    parsing step; the markdown is the source of truth every writer parses.

    Nothing is persisted here on purpose — this runs inside GET requests.

    Returns:
        list: Block dicts, empty when the document has no content at all.
    """
    if (getattr(document, 'text_formats', {}) or {}).get('/content_markdown') == 'markdown_html_v1':
        return markdown_to_blocks(document.content_markdown or '', editorial=True)
    blocks = (document.content_json or {}).get('blocks')
    if blocks:
        return blocks
    return markdown_to_blocks(document.content_markdown or '')
