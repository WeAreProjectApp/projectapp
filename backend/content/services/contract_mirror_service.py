"""The Document-manager window onto the one contract.

The default ``ContractTemplate`` is the only contract. It changes through
versioned data migrations and nowhere else. The document linked through
``ContractTemplate.mirror_document`` stores no copy of its own: every reader
(panel detail, PDF download, email attachment, MCP) renders the contract
live, exactly as the client sees it in the proposal's legal view and in its
draft download. That is why the document is read-only everywhere: an edit
made there would have nowhere to go but a second, drifting copy.
"""

from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist

CONTRACT_MIRROR_BLOCKER = 'contract_mirror'
CONTRACT_MIRROR_CODE = 'contract_mirror_read_only'
CONTRACT_MIRROR_MESSAGE = (
    'Este documento es el contrato vigente: se consulta y se descarga aquí, '
    'pero no se edita, duplica, archiva ni elimina. El contrato se modifica '
    'únicamente por migración de la plantilla del contrato.'
)
MIRROR_TITLE = 'Contrato de prestación de servicios — borrador vigente'

# The draft never carries a proposal's data: every field is masked.
_ANY_PROPOSAL = SimpleNamespace(contract_params={}, pk=None)


def is_contract_mirror(document):
    """True when *document* is the Document-manager window onto the contract."""
    if document is None or getattr(document, 'pk', None) is None:
        return False
    try:
        return document.contract_template is not None
    except ObjectDoesNotExist:
        return False


def mirror_markdown():
    """The complete draft contract as Markdown, or None without a default.

    Title, parties, every clause and the signature block, masked with
    XXX-XXX-XXX — the same text the contract PDF is drawn from.
    """
    from content.models import ContractTemplate
    from content.services.contract_pdf_service import resolve_contract_content

    if not ContractTemplate.get_default():
        return None
    content = resolve_contract_content(_ANY_PROPOSAL, draft=True, force_default=True)
    return content['snapshot'] or None


def mirror_pdf():
    """The draft contract PDF the client downloads, or None on failure."""
    from content.models import ContractTemplate
    from content.services.contract_pdf_service import generate_contract_pdf
    from content.services.pdf_utils import add_watermark_to_pdf

    if not ContractTemplate.get_default():
        return None
    pdf_bytes = generate_contract_pdf(_ANY_PROPOSAL, draft=True, force_default=True)
    return add_watermark_to_pdf(pdf_bytes) if pdf_bytes else None


def mirror_placeholder_markdown():
    """What the row stores: a pointer, never contract text that could drift."""
    return (
        f'# {MIRROR_TITLE}\n\n'
        'Este documento muestra en vivo el contrato vigente de ProjectApp, el '
        'mismo que ven los clientes en la sección legal de su propuesta. Su '
        'contenido no se guarda aquí.\n'
    )
