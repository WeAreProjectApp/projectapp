"""Explicit delivery authoring uses real MCP transport and retained source files."""
from copy import deepcopy
import hashlib
import io
import json

import pytest
from django.core.files.base import ContentFile
from reportlab.pdfgen.canvas import Canvas

from accounts.models import (
    ContractSignatureEvidence, DeliveryMessage, DeliveryPromptContext,
    Project, ProjectContract, Requirement,
)
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import RECORDED_AT
from content.models import Document, McpUpload
from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects, confirm, current_version, draft as draft,
)


pytestmark = pytest.mark.django_db
AGREEMENT_TEXT = 'The agreement includes creating and editing a customer record.'
REPLY_TEXT = 'Revisaremos el guardado descrito en el contrato y la observación de esta etapa.'


def agreement_pdf(text):
    output = io.BytesIO()
    canvas = Canvas(output, invariant=1)
    canvas.drawString(40, 760, text)
    canvas.save()
    return output.getvalue()


AGREEMENT_PDF = agreement_pdf(AGREEMENT_TEXT)


@pytest.fixture
def selected_project(draft, superuser):
    draft.document.generated_file.save('agreement.pdf', ContentFile(AGREEMENT_PDF), save=True)
    ContractSignatureEvidence.objects.create(
        contract=draft.contract, file=ContentFile(AGREEMENT_PDF, name='signed-agreement.pdf'),
        sha256=hashlib.sha256(AGREEMENT_PDF).hexdigest(), method='external',
        signer_name='Cliente titular', signed_at=RECORDED_AT,
        attestation='Copia firmada recibida del cliente.', attested_by=superuser,
    )
    return draft


@pytest.fixture
def published_project(selected_project, superuser):
    delivery.publish_stage(selected_project.project.pk, superuser, selected_project.stage.pk, {
        'expected_version': delivery.overview(selected_project.project.pk, superuser)['version'],
        'request_id': 'authoring-publication',
    })
    return selected_project


def prepare_guides(call, project, request_id='guide-context', **selection):
    return call('create_delivery_guide_prompt', {
        'project_id': project.project.pk, 'contract_id': project.contract.pk,
        'expected_version': current_version(call, project.project),
        'request_id': request_id, **selection,
    })


def prepare_reply(call, project, request_id='reply-context', **selection):
    return call('create_delivery_reply_prompt', {
        'project_id': project.project.pk, 'stage_id': project.stage.pk,
        'expected_version': current_version(call, project.project),
        'request_id': request_id, **selection,
    })


def citation(context):
    source = context['sources'][0]
    return {'source_key': source['source_key'], 'locator': source['fragments'][0]['locator'],
            'quote': AGREEMENT_TEXT}


def reply_payload(context, classification='inside_scope'):
    return {
        'schema_version': 2, 'context_id': context['id'], 'response_text': REPLY_TEXT,
        'classifications': [{
            'request': 'El registro de prueba no se guarda.', 'classification': classification,
            'rationale': 'La cláusula seleccionada contempla crear y editar registros.',
            'citations': [citation(context)],
        }],
    }


def message_arguments(call, project, context, *, human_reviewed=True, request_id='reviewed-reply'):
    payload = reply_payload(context)
    return {
        'project_id': project.project.pk, 'level': 'stage', 'target_id': project.stage.pk,
        'expected_version': current_version(call, project.project), 'request_id': request_id,
        'message': payload['response_text'], 'context_id': context['id'],
        'source_references': [citation(context)], 'classifications': payload['classifications'],
        'human_reviewed': human_reviewed,
    }


def reference_document(project, markdown):
    return Document.objects.create(
        project=project.project, client_user=project.client, title='Referencia elegida',
        content_markdown=markdown, content_json={'blocks': []},
    )


def source_selection(document):
    return [{'document_id': document.pk, 'role': 'reference',
             'applicability_note': 'Material de consulta; no amplía el alcance contractual.'}]


def test_mcp_guide_prompt_excludes_unselected_contracts(call_projects, selected_project):
    """Falla si preparar guías vuelve a mezclar el texto de contratos hermanos."""
    sibling = reference_document(selected_project, '# Otro contrato\nSIBLING SECRET TERMS')
    ProjectContract.objects.create(
        project=selected_project.project, key='sibling', title='Otro contrato', document=sibling,
    )

    context = prepare_guides(call_projects, selected_project)

    assert context['mode'] == 'guides'
    assert [source['source_key'] for source in context['sources']] == [f'contract-{selected_project.contract.pk}']
    assert AGREEMENT_TEXT in context['prompt']
    assert 'SIBLING SECRET TERMS' not in context['prompt']


def test_mcp_reply_prompt_excludes_internal_messages(call_projects, published_project):
    """Falla si una nota privada se convierte en conversación pública para responder."""
    DeliveryMessage.objects.create(
        project=published_project.project, actor=published_project.client, level='stage',
        target_id=published_project.stage.pk, message='INTERNAL REVIEW NOTE', is_internal=True,
    )

    context = prepare_reply(call_projects, published_project)

    assert context['mode'] == 'reply'
    assert context['stage_id'] == published_project.stage.pk
    assert context['conversation']['publication_id'] == published_project.stage.publications.get().pk
    assert context['conversation']['messages'] == []
    assert 'INTERNAL REVIEW NOTE' not in context['prompt']


def test_mcp_prompt_retry_keeps_one_retained_context(call_projects, selected_project):
    """Falla si un reintento duplica la captura o cambia la versión de entrega."""
    version = current_version(call_projects, selected_project.project)
    first = prepare_guides(call_projects, selected_project, 'retained-once')

    retried = prepare_guides(call_projects, selected_project, 'retained-once')

    history = call_projects('list_delivery_prompt_contexts', {'project_id': selected_project.project.pk})
    assert retried['id'] == first['id']
    assert [row['id'] for row in history['contexts']] == [first['id']]
    assert DeliveryPromptContext.objects.filter(project=selected_project.project).count() == 1
    assert current_version(call_projects, selected_project.project) == version


def test_mcp_prompt_capture_rejects_a_stale_version(call_projects, selected_project):
    """Falla si se captura un contrato con una selección basada en otra versión."""
    arguments = {
        'project_id': selected_project.project.pk, 'contract_id': selected_project.contract.pk,
        'expected_version': current_version(call_projects, selected_project.project) + 1,
        'request_id': 'stale-context',
    }

    error = call_projects('create_delivery_guide_prompt', arguments, expect_error=True)

    assert error['code'] == 'CONFLICT'
    assert DeliveryPromptContext.objects.filter(project=selected_project.project).count() == 0


def test_mcp_context_reopen_preserves_the_captured_prompt(call_projects, selected_project):
    """Falla si reabrir una captura incorpora cambios posteriores del documento."""
    captured = prepare_guides(call_projects, selected_project)
    selected_project.document.content_markdown = '# Edited\nLIVE REPLACEMENT TERMS'
    selected_project.document.save(update_fields=['content_markdown'])

    reopened = call_projects('get_delivery_prompt_context', {
        'project_id': selected_project.project.pk, 'context_id': captured['id'],
    })

    assert reopened['prompt'] == captured['prompt']
    assert reopened['manifest_sha256'] == captured['manifest_sha256']
    assert 'LIVE REPLACEMENT TERMS' not in reopened['prompt']


def test_mcp_context_read_rejects_another_project(call_projects, selected_project):
    """Falla si un UUID de captura permite leer fuentes desde un proyecto ajeno."""
    captured = prepare_guides(call_projects, selected_project)
    other = Project.objects.create(name='Otra selección', client=selected_project.client)

    error = call_projects('get_delivery_prompt_context', {
        'project_id': other.pk, 'context_id': captured['id'],
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'


def test_mcp_source_download_preserves_the_exact_signed_pdf(call_projects, selected_project):
    """Falla si descargar una fuente devuelve el PDF editorial reemplazado."""
    captured = prepare_guides(call_projects, selected_project)
    selected_project.document.generated_file.save(
        'replacement.pdf', ContentFile(agreement_pdf('LIVE REPLACEMENT PDF')), save=True,
    )

    result = call_projects('download_delivery_prompt_source', {
        'project_id': selected_project.project.pk, 'context_id': captured['id'],
        'source_key': captured['sources'][0]['source_key'],
    })

    artifact = McpUpload.objects.get(pk=result['asset_id'])
    with artifact.file.open('rb') as stream:
        assert stream.read() == AGREEMENT_PDF
    assert result['content_type'] == 'application/pdf'
    assert result['sha256'] == hashlib.sha256(AGREEMENT_PDF).hexdigest()
    assert artifact.credential.connector.slug == 'projects'
    assert 'file' not in result


def test_mcp_source_download_keeps_the_original_non_pdf_format(call_projects, selected_project):
    """Falla si una fuente Markdown retenida se anuncia incorrectamente como PDF."""
    document = reference_document(selected_project, '# Referencia\nPasos para preparar datos.')
    context = prepare_guides(call_projects, selected_project, sources=source_selection(document))

    result = call_projects('download_delivery_prompt_source', {
        'project_id': selected_project.project.pk, 'context_id': context['id'],
        'source_key': f'document-{document.pk}',
    })

    artifact = McpUpload.objects.get(pk=result['asset_id'])
    with artifact.file.open('rb') as stream:
        retained = json.loads(stream.read())
    assert retained == {'markdown': '# Referencia\nPasos para preparar datos.', 'content_json': {'blocks': []}}
    assert result['filename'] == 'source-content.json'
    assert result['content_type'] == 'application/json'


def test_mcp_source_download_rejects_a_foreign_context(call_projects, selected_project):
    """Falla si un contexto ajeno genera un artefacto privado para otra selección."""
    context = prepare_guides(call_projects, selected_project)
    other = Project.objects.create(name='Otro proyecto de consulta', client=selected_project.client)

    error = call_projects('download_delivery_prompt_source', {
        'project_id': other.pk, 'context_id': context['id'],
        'source_key': context['sources'][0]['source_key'],
    }, expect_error=True)

    assert error['code'] == 'NOT_FOUND'
    assert McpUpload.objects.count() == 0


def test_mcp_reply_cannot_exclude_scope_with_missing_sources(call_projects, published_project):
    """Falla si faltar un anexo permite concluir definitivamente fuera del alcance."""
    context = prepare_reply(call_projects, published_project, missing_sources=['Anexo de alcance firmado'])

    error = call_projects('preview_delivery_reply', {
        'project_id': published_project.project.pk, 'payload': reply_payload(context, 'outside_scope'),
    }, expect_error=True)

    assert context['complete'] is False
    assert error['code'] == 'SCOPE_INDETERMINATE'
    assert DeliveryMessage.objects.count() == 0


def test_mcp_reply_cannot_exclude_scope_after_partial_extraction(call_projects, published_project):
    """Falla si un límite de extracción se trata como lectura contractual completa."""
    document = reference_document(published_project, '# Texto extenso\n' + 'Una línea extensa. ' * 4000)
    context = prepare_reply(call_projects, published_project, sources=source_selection(document))

    error = call_projects('preview_delivery_reply', {
        'project_id': published_project.project.pk, 'payload': reply_payload(context, 'outside_scope'),
    }, expect_error=True)

    assert context['sources'][1]['status'] == 'partial'
    assert error['code'] == 'SCOPE_INDETERMINATE'
    assert DeliveryMessage.objects.count() == 0


def test_mcp_reply_preview_validates_citations_without_sharing(call_projects, published_project):
    """Falla si validar una respuesta la publica o pierde las citas verificadas."""
    context = prepare_reply(call_projects, published_project)
    version = current_version(call_projects, published_project.project)

    result = call_projects('preview_delivery_reply', {
        'project_id': published_project.project.pk, 'payload': reply_payload(context),
        'expected_version': version,
    })

    assert result['valid'] is True
    assert result['source_references'] == [citation(context)]
    assert result['response_text'] == REPLY_TEXT
    assert result['human_review_required'] is True
    assert DeliveryMessage.objects.count() == 0
    assert current_version(call_projects, published_project.project) == version


def test_mcp_reply_preview_rejects_an_invented_quote(call_projects, published_project):
    """Falla si basta citar una fuente válida para introducir una cláusula inexistente."""
    context = prepare_reply(call_projects, published_project)
    payload = reply_payload(context)
    payload['classifications'][0]['citations'][0]['quote'] = 'The client agreed to unlimited integrations.'

    error = call_projects('preview_delivery_reply', {
        'project_id': published_project.project.pk, 'payload': payload,
    }, expect_error=True)

    assert error['code'] == 'CITATION_QUOTE'
    assert DeliveryMessage.objects.count() == 0


def test_mcp_reply_preview_rejects_a_guide_context(call_projects, selected_project):
    """Falla si una selección para guías puede responder sin capturar la etapa."""
    context = prepare_guides(call_projects, selected_project)

    error = call_projects('preview_delivery_reply', {
        'project_id': selected_project.project.pk, 'payload': reply_payload(context),
    }, expect_error=True)

    assert error['code'] == 'CONTEXT_MODE'


def test_mcp_reply_sharing_requires_human_review(call_projects, published_project):
    """Falla si un borrador citado puede compartirse sin revisión humana explícita."""
    context = prepare_reply(call_projects, published_project)

    error = confirm(call_projects, 'add_delivery_message', message_arguments(
        call_projects, published_project, context, human_reviewed=False,
    ), expect_error=True)

    assert error['code'] == 'HUMAN_REVIEW_REQUIRED'
    assert DeliveryMessage.objects.count() == 0


def test_mcp_reviewed_reply_preserves_its_provenance(call_projects, published_project):
    """Falla si compartir manualmente descarta el contexto y fundamento de la respuesta."""
    context = prepare_reply(call_projects, published_project)

    confirm(call_projects, 'add_delivery_message', message_arguments(call_projects, published_project, context))

    message = DeliveryMessage.objects.get(project=published_project.project)
    assert str(message.context_id) == context['id']
    assert message.message == REPLY_TEXT
    assert message.source_references == [citation(context)]
    assert message.reply_classifications == reply_payload(context)['classifications']
    assert message.actor.first_name == 'MCP'


def test_mcp_reply_sharing_rejects_changed_observations(call_projects, published_project):
    """Falla si una respuesta usa una conversación capturada antes de otra observación."""
    context = prepare_reply(call_projects, published_project)
    confirm(call_projects, 'add_delivery_message', {
        'project_id': published_project.project.pk, 'level': 'stage',
        'target_id': published_project.stage.pk,
        'expected_version': current_version(call_projects, published_project.project),
        'request_id': 'new-observation', 'message': 'Nueva observación: el listado aparece vacío.',
    })

    error = confirm(call_projects, 'add_delivery_message', message_arguments(
        call_projects, published_project, context,
    ), expect_error=True)

    assert error['code'] == 'CONFLICT'
    assert list(DeliveryMessage.objects.values_list('message', flat=True)) == ['Nueva observación: el listado aparece vacío.']


def test_mcp_cited_guide_import_retains_its_context(call_projects, selected_project):
    """Falla si aplicar JSON v2 guarda guías sin su copia contractual y citas."""
    context = prepare_guides(call_projects, selected_project)
    payload = deepcopy(context['template'])

    confirm(call_projects, 'apply_delivery_import', {
        'project_id': selected_project.project.pk, 'payload': payload,
        'expected_version': current_version(call_projects, selected_project.project),
        'request_id': 'import-cited-guides',
    })

    requirement = Requirement.objects.get(key='validacion-1')
    assert str(requirement.context_id) == context['id']
    assert requirement.source_references == payload['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]['source_references']
    assert requirement.review_status == 'pending'


def test_mcp_cited_guide_import_requires_normative_citations(call_projects, selected_project):
    """Falla si declarar JSON v2 permite crear una guía con fundamento vacío."""
    context = prepare_guides(call_projects, selected_project)
    payload = deepcopy(context['template'])
    payload['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]['source_references'] = []

    error = call_projects('preview_delivery_import', {
        'project_id': selected_project.project.pk, 'payload': payload,
        'expected_version': current_version(call_projects, selected_project.project),
    }, expect_error=True)

    assert error['code'] == 'CITATION_NORMATIVE'
    assert Requirement.objects.filter(key='validacion-1').count() == 0


def test_mcp_cited_requirement_cannot_remove_its_context(call_projects, selected_project):
    """Falla si editar una guía trazada la convierte en una guía manual sin fuentes."""
    context = prepare_guides(call_projects, selected_project)
    selected_project.requirement.context_id = context['id']
    selected_project.requirement.source_references = [citation(context)]
    selected_project.requirement.save(update_fields=['context', 'source_references'])

    error = call_projects('update_delivery_requirement', {
        'project_id': selected_project.project.pk, 'node_id': selected_project.requirement.pk,
        'expected_version': current_version(call_projects, selected_project.project),
        'data': {'context_id': None, 'source_references': []},
    }, expect_error=True)

    selected_project.requirement.refresh_from_db()
    assert error['code'] == 'CONTEXT_REQUIRED'
    assert str(selected_project.requirement.context_id) == context['id']
    assert selected_project.requirement.source_references == [citation(context)]
