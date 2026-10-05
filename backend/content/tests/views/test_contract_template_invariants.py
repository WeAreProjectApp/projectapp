"""High-risk atomicity invariants for versioned contract templates."""
from io import BytesIO

import pytest
from pypdf import PdfReader

from content.models import ContractTemplateVersion, McpActionIntent
from content.services.contract_template_service import read_template

from content.tests.contract_template_fixtures import rpc_call

pytestmark = pytest.mark.django_db


def _content(result):
    return result['structuredContent']


def _confirm(api_client, token, confirmation_id):
    return rpc_call(api_client, token, 'confirm_action', {'confirmation_id': confirmation_id}, msg_id=2)


def _four_year_warranty(template):
    old = 'garantía por un periodo de tres (3) años'
    new = 'garantía por un periodo de cuatro (4) años'
    markdown = template['markdown']
    assert markdown.count(old) == 1
    return markdown.replace(old, new, 1)


def _pdf_text(raw_pdf):
    return ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(BytesIO(bytes(raw_pdf))).pages).split())


def test_inconsistent_combined_warranty_change_creates_no_confirmation_intent(
    api_client, coherent_template, proposals_mcp,
):
    """Falla si un cambio real de garantía en combined puede eludir la variante product."""
    token, credential = proposals_mcp
    combined = read_template('combined')
    before_intents = McpActionIntent.objects.filter(credential=credential).count()

    result = rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': _four_year_warranty(combined),
        'if_match': combined['etag'], 'change_note': 'Cambio aislado que debe bloquearse.',
    })

    assert result['isError'] is True
    assert _content(result)['error']['code'] == 'TEMPLATES_INCONSISTENT'
    assert McpActionIntent.objects.filter(credential=credential).count() == before_intents
    assert read_template('combined')['markdown'] == combined['markdown']


def test_coordinated_warranty_update_syncs_both_current_pdfs(
    api_client, initialized_contract_mirrors, proposals_mcp,
):
    """Falla si un lote coherente confirma texto nuevo pero conserva el PDF anterior en un espejo."""
    token, _ = proposals_mcp
    combined = read_template('combined')
    product = read_template('product')

    preview = _content(rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': _four_year_warranty(combined),
        'if_match': combined['etag'], 'change_note': 'Garantía coordinada a cuatro años.',
        'related_updates': [{
            'variant': 'product', 'markdown': _four_year_warranty(product),
            'if_match': product['etag'],
        }],
    }))
    confirmed = _content(_confirm(api_client, token, preview['confirmation_id']))['result']
    combined_mirror = initialized_contract_mirrors.mirrors.get(variant='combined')
    product_mirror = initialized_contract_mirrors.mirrors.get(variant='product')
    combined_mirror.refresh_from_db()
    product_mirror.refresh_from_db()

    assert [row['variant'] for row in confirmed['results']] == ['combined', 'product']
    assert combined_mirror.revision.version == 2
    assert product_mirror.revision.version == 2
    assert 'cuatro (4) años' in combined_mirror.revision.markdown
    assert 'cuatro (4) años' in product_mirror.revision.markdown
    assert 'cuatro (4) años' in _pdf_text(combined_mirror.pdf_content)
    assert 'cuatro (4) años' in _pdf_text(product_mirror.pdf_content)


def test_replaying_a_confirmed_template_update_does_not_duplicate_a_revision_or_note(
    api_client, initialized_contract_mirrors, proposals_mcp,
):
    """Falla si repetir confirm_action vuelve a guardar una versión o una nota contractual."""
    token, _ = proposals_mcp
    combined = read_template('combined')
    preview = _content(rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': combined['markdown'] + '\n',
        'if_match': combined['etag'], 'change_note': 'Una sola confirmación debe bastar.',
    }))
    confirmation_id = preview['confirmation_id']
    _confirm(api_client, token, confirmation_id)
    mirror = initialized_contract_mirrors.mirrors.get(variant='combined')
    versions_after_first_confirmation = ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='combined',
    ).count()
    notes_after_first_confirmation = mirror.document.document_notes.filter(
        title='Plantilla combinada — versión 2',
    ).count()

    replay = _content(_confirm(api_client, token, confirmation_id))

    assert replay['replayed'] is True
    assert ContractTemplateVersion.objects.filter(
        template=initialized_contract_mirrors, variant='combined',
    ).count() == versions_after_first_confirmation == 2
    assert mirror.document.document_notes.filter(
        title='Plantilla combinada — versión 2',
    ).count() == notes_after_first_confirmation == 1


def test_missing_if_match_is_rejected_before_creating_a_confirmation_intent(
    api_client, coherent_template, proposals_mcp,
):
    """Falla si el MCP agenda un cambio sensible sin precondición de concurrencia."""
    token, credential = proposals_mcp
    combined = read_template('combined')
    before_intents = McpActionIntent.objects.filter(credential=credential).count()

    result = rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': combined['markdown'] + '\n',
        'change_note': 'No debe poder previsualizarse sin etag.',
    })

    assert result['isError'] is True
    assert _content(result)['error']['code'] == 'PRECONDITION_REQUIRED'
    assert McpActionIntent.objects.filter(credential=credential).count() == before_intents
