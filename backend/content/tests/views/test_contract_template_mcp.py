"""MCP behavior for versioned default contract templates."""
import pytest

from content.models import ContractTemplateVersion
from io import BytesIO
from pypdf import PdfReader
from content.services.contract_template_service import read_template

from content.tests.contract_template_fixtures import rpc_call

pytestmark = pytest.mark.django_db


def _content(result):
    return result['structuredContent']


def _confirm(api_client, token, confirmation_id):
    return rpc_call(api_client, token, 'confirm_action', {'confirmation_id': confirmation_id}, msg_id=2)


def test_mcp_reads_every_variant_with_versioned_contract_metadata(api_client, coherent_template, proposals_mcp):
    """Falla si alguna variante deja de exponer texto, campos, versión o etag al MCP."""
    token, _ = proposals_mcp

    listed = api_client.post(
        f'/api/mcp/proposals/{token}/',
        {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}, format='json',
    ).data['result']['tools']
    tools = {tool['name']: tool for tool in listed}
    service = _content(rpc_call(api_client, token, 'get_proposal_contract_template', {'variant': 'service'}))
    product = _content(rpc_call(api_client, token, 'get_proposal_contract_template', {'variant': 'product'}))
    combined = _content(rpc_call(api_client, token, 'get_proposal_contract_template', {}))

    assert {'preview_proposal_contract_template_update', 'update_proposal_contract_template',
            'list_proposal_contract_template_versions', 'restore_proposal_contract_template_version',
            'check_proposal_contract_templates_consistency'} <= set(tools)
    assert tools['update_proposal_contract_template']['annotations']['readOnlyHint'] is False
    assert {item['variant'] for item in (combined, product, service)} == {'combined', 'product', 'service'}
    assert '{service_initial_term}' in combined['placeholders']
    assert {'markdown', 'version', 'updated_at', 'etag'} <= set(service)


def test_preview_returns_diff_without_persisting_template(api_client, coherent_template, proposals_mcp):
    """Falla si una vista previa modifica el texto o crea una versión antes de confirmar."""
    token, _ = proposals_mcp
    before = read_template('combined')
    candidate = before['markdown'] + '\n'

    result = _content(rpc_call(api_client, token, 'preview_proposal_contract_template_update', {
        'variant': 'combined', 'markdown': candidate,
    }))

    assert result['changes'][0]['changed'] is True
    assert result['changes'][0]['diff']
    assert result['documents_to_sync'][0]['variant'] == 'combined'
    assert result['documents_to_sync'][0]['status'] == 'missing'
    assert read_template('combined')['markdown'] == before['markdown']
    assert ContractTemplateVersion.objects.filter(template=coherent_template, variant='combined').count() == 1


@pytest.mark.parametrize(
    ('markdown', 'fragment'),
    [
        ('# Contrato {not_known}', 'unknown'),
        ('# Contrato sin campos obligatorios', 'missing'),
    ],
)
def test_preview_rejects_invalid_placeholders(api_client, coherent_template, proposals_mcp, markdown, fragment):
    """Falla si el preview acepta campos contractuales desconocidos o requeridos ausentes."""
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'preview_proposal_contract_template_update', {
        'variant': 'combined', 'markdown': markdown,
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['details'][f'{fragment}_placeholders']


def test_preview_rejects_a_patch_without_one_exact_target(api_client, coherent_template, proposals_mcp):
    """Falla si un parche puede alterar una ubicación inexistente o ambigua."""
    token, _ = proposals_mcp

    result = rpc_call(api_client, token, 'preview_proposal_contract_template_update', {
        'variant': 'combined',
        'patches': [{'operation': 'replace', 'heading': 'CLÁUSULA INEXISTENTE', 'markdown': 'Texto'}],
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'PATCH_TARGET_ERROR'


def test_confirmed_update_synchronizes_the_auditable_contract(
    api_client, initialized_contract_mirrors, proposals_mcp,
):
    """Falla si confirmar una edición no versiona ni sincroniza el espejo vigente."""
    token, _ = proposals_mcp
    before = read_template('combined')
    product = read_template('product')
    old_term = 'garantía por un periodo de tres (3) años'
    new_term = 'garantía por un periodo de cuatro (4) años'
    candidate = before['markdown'].replace(old_term, new_term)
    preview = _content(rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': candidate,
        'if_match': before['etag'], 'change_note': 'Ajuste contractual aprobado.',
        'related_updates': [{'variant': 'product', 'markdown': product['markdown'].replace(old_term, new_term), 'if_match': product['etag']}],
    }))

    assert preview['confirmation_required'] is True
    assert read_template('combined')['version'] == 1
    confirmed = _content(_confirm(api_client, token, preview['confirmation_id']) )['result']
    mirror = initialized_contract_mirrors.mirrors.get(variant='combined')

    assert confirmed['results'][0]['version'] == 2
    assert read_template('combined')['markdown'] == candidate
    assert mirror.revision.version == 2
    pdf_text = ' '.join(' '.join(page.extract_text() for page in PdfReader(BytesIO(bytes(mirror.pdf_content))).pages).split())
    assert 'cuatro (4) años' in pdf_text
    assert mirror.document.document_notes.get(title='Plantilla combinada — versión 2').content == (
        f'Versión 2\nFecha: {mirror.synced_at.isoformat()}\nAjuste contractual aprobado.\n\n'
        'Líneas agregadas: 1; líneas retiradas: 1.'
    )


def test_sensitive_update_rejects_an_etag_that_was_stale_before_preview(
    api_client, initialized_contract_mirrors, proposals_mcp,
):
    """Falla si una edición sensible sobrescribe una revisión leída por otro operador."""
    token, _ = proposals_mcp
    current = read_template('combined')

    result = rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': current['markdown'] + '\n',
        'if_match': 'stale-etag', 'change_note': 'No debe aplicar.',
    })

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert read_template('combined')['version'] == 1


def test_confirmation_rejects_a_related_variant_changed_after_preview(
    api_client, initialized_contract_mirrors, proposals_mcp,
):
    """Falla si confirmar ignora que otra variante cambió después de la vista previa."""
    token, _ = proposals_mcp
    combined = read_template('combined')
    preview = _content(rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'combined', 'markdown': combined['markdown'] + '\n',
        'if_match': combined['etag'], 'change_note': 'Cambio que quedará obsoleto.',
    }))
    initialized_contract_mirrors.service_content_markdown += '\n'
    initialized_contract_mirrors.save(update_fields=['service_content_markdown'])

    result = _confirm(api_client, token, preview['confirmation_id'])

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert read_template('combined')['version'] == 1


def test_confirmed_restore_creates_a_new_auditable_revision(
    api_client, initialized_contract_mirrors, proposals_mcp,
):
    """Falla si restaurar reemplaza historial en vez de registrar una revisión nueva."""
    token, credential = proposals_mcp
    initial = read_template('product')
    update = _content(rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'product', 'markdown': initial['markdown'] + '\n',
        'if_match': initial['etag'], 'change_note': 'Versión temporal.',
    }))
    _confirm(api_client, token, update['confirmation_id'])
    current = read_template('product')
    versions = _content(rpc_call(api_client, token, 'list_proposal_contract_template_versions', {'variant': 'product'}))
    assert versions['versions'][0]['author'] == credential.actor.get_username()
    assert versions['versions'][0]['change_note'] == 'Versión temporal.'
    assert versions['versions'][0]['created_at']
    original = next(row for row in versions['versions'] if row['version'] == 1)
    restore = _content(rpc_call(api_client, token, 'restore_proposal_contract_template_version', {
        'variant': 'product', 'version_id': original['version_id'], 'if_match': current['etag'],
        'change_note': 'Restaurar texto inicial.',
    }))

    result = _content(_confirm(api_client, token, restore['confirmation_id']))['result']
    restored = read_template('product')

    assert result['results'][0]['version'] == 3
    assert restored['markdown'] == initial['markdown']
    assert restored['version'] == 3
    assert ContractTemplateVersion.objects.get(template=initialized_contract_mirrors, variant='product', version=3).restored_from_id == original['version_id']


def test_mcp_consistency_check_reports_the_current_contracts(api_client, coherent_template, proposals_mcp):
    token, _ = proposals_mcp

    result = _content(rpc_call(api_client, token, 'check_proposal_contract_templates_consistency', {}))

    assert result['consistent'] is True
    assert result['findings'] == []
    assert {tuple(row['variants']) for row in result['compared']} == {('combined', 'product'), ('combined', 'service')}


def test_mcp_confirmation_reports_a_mirror_sync_failure(api_client, monkeypatch, initialized_contract_mirrors, proposals_mcp):
    token, _ = proposals_mcp
    before = read_template('service')
    preview = _content(rpc_call(api_client, token, 'update_proposal_contract_template', {
        'variant': 'service', 'markdown': before['markdown'] + '\n',
        'if_match': before['etag'], 'change_note': 'Debe informar si no puede sincronizar.',
    }))
    monkeypatch.setattr('content.services.contract_mirror_service.render_mirror_pdf', lambda *_args: b'invalid PDF')

    result = _confirm(api_client, token, preview['confirmation_id'])

    assert result['isError'] is True
    assert _content(result)['error']['code'] == 'MIRROR_SYNC_FAILED'
    assert _content(result)['error']['details'] == {
        'variant': 'service', 'document_id': initialized_contract_mirrors.mirrors.get(variant='service').document_id,
        'stage': 'pdf', 'applied': False,
    }
    assert read_template('service')['version'] == 1
