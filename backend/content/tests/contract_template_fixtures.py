"""Fixtures for versioned contract-template integration tests."""
from pathlib import Path

import pytest
from django.core.management import call_command

from content.models import (
    ContractTemplate,
    ContractTemplateVersion,
    Document,
    DocumentFolder,
    DocumentType,
    McpConnector,
)
from content.services.contract_template_rollout import approved_adjustments
from content.services.contract_template_validation import TEXT_FIELDS, VARIANTS


@pytest.fixture
def source_237_markdown():
    """Approved source text used to establish a coherent three-template baseline."""
    return (Path(__file__).parent / 'fixtures' / 'contract_template_document237.md').read_text()


@pytest.fixture
def coherent_template(source_237_markdown):
    """Default template with the approved, mutually consistent first-use texts."""
    template = ContractTemplate.get_default()
    assert template is not None, 'Las migraciones deben conservar la plantilla predeterminada.'
    original = {key: getattr(template, field) for key, field in TEXT_FIELDS.items()}
    adjusted = approved_adjustments(original, source_237_markdown)

    template.versions.all().delete()
    for key, field in TEXT_FIELDS.items():
        setattr(template, field, adjusted[key])
    template.save(update_fields=list(TEXT_FIELDS.values()))
    ContractTemplateVersion.objects.bulk_create([
        ContractTemplateVersion(
            template=template,
            variant=key,
            version=1,
            markdown=adjusted[key],
            author_label='Prueba de baseline',
            change_note='Baseline coherente para pruebas.',
        )
        for key in VARIANTS
    ])
    return template


@pytest.fixture
def initialized_contract_mirrors(coherent_template, superuser):
    """Run the real initializer so update tests exercise PDF and note pipelines."""
    markdown_type, _ = DocumentType.objects.get_or_create(
        code='markdown', defaults={'name': 'Markdown'},
    )
    folder = DocumentFolder.objects.create(name='Contratos')
    combined_document = Document.objects.create(
        title='Contrato combinado anterior', document_type=markdown_type,
        folder=folder, content_markdown='Borrador anterior combinado.',
    )
    service_document = Document.objects.create(
        title='Contrato de servicio anterior', document_type=markdown_type,
        folder=folder, content_markdown='Borrador anterior de servicio.',
    )
    coherent_template.mirror_document = combined_document
    coherent_template.save(update_fields=['mirror_document'])

    call_command(
        'initialize_contract_template_mirrors', '--apply',
        '--folder-id', str(folder.pk),
        '--service-document-id', str(service_document.pk),
        '--actor-id', str(superuser.pk),
    )
    coherent_template.refresh_from_db()
    return coherent_template


@pytest.fixture
def proposals_mcp(superuser):
    """A proposal connector credential whose confirmed writes have an auditable actor."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='proposals', defaults={'name': 'Gestor de Propuestas'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    credential = connector.credential_for_token(token)
    credential.actor = superuser
    credential.save(update_fields=['actor', 'updated_at'])
    return token, credential


def proposal_mcp_url(token):
    return f'/api/mcp/proposals/{token}/'


def rpc_call(api_client, token, name, arguments, *, msg_id=1):
    """Call one real MCP tool without automatically accepting sensitive previews."""
    response = api_client.post(
        proposal_mcp_url(token),
        {
            'jsonrpc': '2.0', 'id': msg_id, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        },
        format='json',
    )
    return response.data['result']
