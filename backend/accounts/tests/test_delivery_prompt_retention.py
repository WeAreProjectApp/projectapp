"""Retained proof stays private, bounded and readable without loading other sources."""
import json

import pytest
from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.db import connection
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext, override_settings
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, ValidationError

from accounts.management.commands._seed_helpers import clear_fake_delivery
from accounts.models import ContractSignatureEvidence, DeliveryPromptContext, DeliveryPromptSource, DeliveryScope, Project, ProjectContract, Requirement
from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_authoring_helpers import (
    additional_references, api_for, build_authoring_context, citation, docx_bytes,
    endpoint, pdf_bytes, proposal_source, reference, signed_amendment, source_document,
)
from accounts.tests.delivery_helpers import RECORDED_AT, prepare_prompt, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


def captured_queries(call):
    with CaptureQueriesContext(connection) as captured:
        result = call()
    return result, len(captured), [query['sql'] for query in captured.captured_queries]


def other_project_capture(context, **overrides):
    project = Project.objects.create(name='Preserved project', client=context.client)
    document = source_document(context, 'Preserved contractual source.', project=project)
    contract = ProjectContract.objects.create(project=project, key='preserved', title='Preserved contract', document=document)
    values = {
        'expected_version': 0, 'request_id': 'preserved-context', 'mode': 'guides', 'contract_id': contract.pk,
    }
    values.update(overrides)
    return authoring.create_prompt_context(project.pk, context.admin, values)


def retained_proof_state(context):
    proofs = [*DeliveryPromptSource.objects.order_by('pk'), *ContractSignatureEvidence.objects.order_by('pk')]
    files = {}
    for file in [*[proof.file for proof in proofs], context.document.generated_file]:
        with file.open('rb') as stream:
            files[file.name] = stream.read()
    return {
        'contexts': list(DeliveryPromptContext.objects.order_by('pk').values('id', 'manifest_sha256', 'contract_id')),
        'sources': list(DeliveryPromptSource.objects.order_by('pk').values('id', 'context_id', 'signature_evidence_id', 'sha256')),
        'signatures': list(ContractSignatureEvidence.objects.order_by('pk').values('id', 'sha256')),
        'requirements': list(Requirement.objects.order_by('pk').values('id', 'title', 'version')),
        'files': files,
    }


def test_capture_read_query_cost_is_constant_for_twenty_sources(context):
    """Fails if reading captured sources introduces one database query per source."""
    small = prepare_prompt(context)
    large = prepare_prompt(context, request_id='twenty-sources', sources=additional_references(context, 19))
    first_actor = User.objects.get(pk=context.admin.pk)
    second_actor = User.objects.get(pk=context.admin.pk)

    small_data, small_count, _ = captured_queries(lambda: authoring.get_prompt_context(context.project.pk, first_actor, small['id']))
    large_data, large_count, _ = captured_queries(lambda: authoring.get_prompt_context(context.project.pk, second_actor, large['id']))

    assert len(small_data['sources']) == 1
    assert len(large_data['sources']) == 20
    assert small_count == large_count <= 4
    assert len(json.dumps(large_data).encode()) <= 256 * 1024


def test_context_history_selects_only_metadata(context):
    """Fails if context history materializes large prompts or captured source bodies."""
    prepared = prepare_prompt(context)

    result, query_count, queries = captured_queries(lambda: authoring.list_prompt_contexts(context.project.pk, context.admin))

    assert result['contexts'][0]['id'] == prepared['id']
    assert 'prompt' not in result['contexts'][0]
    assert '"accounts_deliverypromptcontext"."prompt"' not in ' '.join(queries)
    assert query_count <= 4


def test_source_download_skips_other_context_text(context):
    """Fails if downloading one source loads every other source or the full drafting prompt."""
    prepared = prepare_prompt(context, sources=additional_references(context, 19))
    actor = User.objects.get(pk=context.admin.pk)

    result, query_count, queries = captured_queries(lambda: authoring.prompt_source_file(context.project.pk, actor, prepared['id'], prepared['sources'][0]['source_key']))

    assert result[0] == pdf_bytes()
    assert query_count <= 2
    assert '"fragments"' not in ' '.join(queries)
    assert '"prompt"' not in ' '.join(queries)


def test_original_docx_download_preserves_its_mime_type(context):
    """Fails if a retained DOCX loses its original bytes, MIME type or private response headers."""
    source = proposal_source(context, docx_bytes(), 'reference.docx')
    prepared = prepare_prompt(context, sources=[{'proposal_document_id': source.pk, 'role': 'reference',
                                                'applicability_note': 'Original editable reference.'}])

    response = api_for(context.admin).get(prepared['sources'][1]['download_url'])

    assert response.status_code == 200
    assert response.content == docx_bytes()
    assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    assert response['Cache-Control'] == 'private, no-store'
    assert 'reference.docx' in response['Content-Disposition']


def test_source_download_is_bound_to_the_project_route(context):
    """Fails if a download route grants access to a different project context."""
    prepared = prepare_prompt(context)
    other = Project.objects.create(name='Other route', client=context.client)

    response = api_for(context.admin).get(f'/api/accounts/projects/{other.pk}/delivery/prompt/{prepared["id"]}/sources/{prepared["sources"][0]["source_key"]}/download/')

    assert response.status_code == 404


def test_tampered_captured_file_is_never_served(context):
    """Fails if modified retained bytes are served under the original evidence hash."""
    prepared = prepare_prompt(context)
    source = DeliveryPromptSource.objects.get(context_id=prepared['id'])
    with source.file.open('wb') as stream:
        stream.write(b'Replacement of retained bytes.')

    with pytest.raises(NotFound, match='hash original'):
        authoring.prompt_source_file(context.project.pk, context.admin, prepared['id'], source.source_key)


def test_missing_captured_file_does_not_fall_back_to_live_bytes(context):
    """Fails if missing retained evidence is silently replaced by mutable document bytes."""
    prepared = prepare_prompt(context)
    source = DeliveryPromptSource.objects.get(context_id=prepared['id'])
    source.file.storage.delete(source.file.name)

    with pytest.raises(NotFound, match='no está disponible'):
        authoring.prompt_source_file(context.project.pk, context.admin, prepared['id'], source.source_key)


def test_unknown_source_key_returns_not_found(context):
    """Fails if an unselected source key exposes an arbitrary file."""
    prepared = prepare_prompt(context)

    with pytest.raises(NotFound):
        authoring.prompt_source_file(context.project.pk, context.admin, prepared['id'], 'unselected-source')


def test_invalid_context_identifier_is_rejected_before_download(context):
    """Fails if a malformed context identifier causes an unhandled download error."""
    with pytest.raises(ValidationError):
        authoring.prompt_source_file(context.project.pk, context.admin, 'invalid-context-uuid', 'source')


def test_captured_source_cannot_be_rewritten_through_a_queryset(context):
    """Fails if a bulk update bypasses captured source immutability."""
    prepared = prepare_prompt(context)
    source = DeliveryPromptSource.objects.get(context_id=prepared['id'])

    with pytest.raises(ValueError, match='cannot be edited'):
        DeliveryPromptSource.objects.filter(pk=source.pk).update(title='Replacement source')

    source.refresh_from_db()
    assert source.title == prepared['sources'][0]['title']


def test_saved_scope_context_prevents_deleting_its_draft_scope(context):
    """Fails if deleting a draft scope destroys a retained contractual context."""
    prepared = prepare_prompt(context, scope_id=context.scope.pk)

    response = api_for(context.admin).delete(endpoint(context, f'scopes/{context.scope.pk}/'),
                                            {'expected_version': 0}, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'context_retained'
    assert DeliveryPromptContext.objects.filter(pk=prepared['id']).count() == 1
    assert DeliveryScope.objects.filter(pk=context.scope.pk).values_list('title', flat=True).get() == 'Alcance'
    assert version(context) == 0


def test_retained_reference_protects_its_original_document(context):
    """Fails if a document supporting retained drafting evidence can be deleted."""
    document = source_document(context, 'Retained original reference.')
    prepare_prompt(context, sources=[reference(document)])

    with pytest.raises(ProtectedError):
        document.delete()

    assert document.__class__.objects.get(pk=document.pk).content_markdown == 'Retained original reference.'


@override_settings(FAKE_DATA_ALLOWED=True)
def test_authorized_fake_reset_removes_context_proof_for_its_project(context, django_capture_on_commit_callbacks):
    """Fails if an authorized reset leaves private copies or removes another project's capture."""
    prepared = prepare_prompt(context, scope_id=context.scope.pk)
    source = DeliveryPromptSource.objects.get(context_id=prepared['id'], role='contract')
    preserved = other_project_capture(context)

    with django_capture_on_commit_callbacks(execute=True):
        clear_fake_delivery(Project.objects.filter(pk=context.project.pk))

    assert DeliveryPromptContext.objects.filter(pk=prepared['id']).count() == 0
    assert DeliveryPromptSource.objects.filter(context_id=prepared['id']).count() == 0
    assert source.file.storage.exists(source.file.name) is False
    assert DeliveryPromptContext.objects.filter(pk=preserved['id']).count() == 1
    assert Project.objects.get(pk=context.project.pk).name == 'Proyecto de validación'


@override_settings(FAKE_DATA_ALLOWED=False)
def test_disabled_fake_reset_preserves_captured_proof(context):
    """Fails if the disabled fake-data capability deletes a retained capture."""
    prepared = prepare_prompt(context)
    source = DeliveryPromptSource.objects.get(context_id=prepared['id'])

    with pytest.raises(CommandError, match='disabled'):
        clear_fake_delivery(Project.objects.filter(pk=context.project.pk))

    assert DeliveryPromptContext.objects.filter(pk=prepared['id']).count() == 1
    assert source.file.storage.exists(source.file.name) is True


@override_settings(FAKE_DATA_ALLOWED=True)
def test_fake_reset_rejects_evidence_retained_by_another_project(context):
    """Fails if a partial reset damages signed evidence retained as a deliberate reference elsewhere."""
    context.document.project = None
    context.document.save(update_fields=['project'])
    prepared = prepare_prompt(context)
    retained = other_project_capture(context, sources=[reference(context.document)])
    before = retained_proof_state(context)

    with pytest.raises(CommandError, match='No se borraron datos ni archivos'):
        clear_fake_delivery(Project.objects.filter(pk=context.project.pk))

    assert retained_proof_state(context) == before
    assert len(before['contexts']) == 2
    assert len(before['sources']) == 3
    assert authoring.prompt_source_file(context.project.pk, context.admin, prepared['id'], prepared['sources'][0]['source_key'])[0] == pdf_bytes()
    retained_project_id = DeliveryPromptContext.objects.get(pk=retained['id']).project_id
    assert authoring.prompt_source_file(retained_project_id, context.admin, retained['id'], retained['sources'][1]['source_key'])[0] == pdf_bytes()


def test_duplicate_source_identity_rolls_back_preparation(context):
    """Fails if the selected contract can be captured twice under different source roles."""
    with pytest.raises(ValidationError, match='No repitas una fuente'):
        prepare_prompt(context, sources=[reference(context.document)])

    assert DeliveryPromptContext.objects.count() == 0


def test_contract_annex_requires_a_nonempty_administrative_basis(context):
    """Fails if an annex is associated without explaining the administrative selection."""
    source = source_document(context)

    response = api_for(context.admin).post(endpoint(context, 'prompt/'), {
        'expected_version': 0, 'request_id': 'annex-without-basis', 'mode': 'guides',
        'contract_id': context.contract.pk,
        'sources': [{'document_id': source.pk, 'role': 'contractual_annex', 'applicability_note': ''}],
    }, format='json')

    assert response.status_code == 400
    assert DeliveryPromptContext.objects.count() == 0


def test_requirement_rejects_an_amendment_missing_from_its_context(context):
    """Fails if requirement citations omit the amendment defining their scope."""
    prepared = prepare_prompt(context)
    amendment = signed_amendment(context)
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])

    with pytest.raises(ValidationError, match='otrosí que no se capturó'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
            'expected_version': 0, 'context_id': prepared['id'], 'source_references': [citation(prepared)],
        }, context.first.pk)

    context.first.refresh_from_db()
    assert context.first.context_id is None
    assert version(context) == 0


def test_requirement_rejects_a_scope_amendment_changed_after_capture(context):
    """Fails if a requirement uses a captured scope after its defining amendment changes."""
    first = signed_amendment(context, key='first-amendment')
    second = signed_amendment(context, key='second-amendment')
    context.scope.amendment = first
    context.scope.save(update_fields=['amendment'])
    prepared = prepare_prompt(context, scope_id=context.scope.pk, amendment_ids=[first.pk, second.pk])
    context.scope.amendment = second
    context.scope.save(update_fields=['amendment'])

    with pytest.raises(ValidationError, match='alcance cambió'):
        delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
            'expected_version': 0, 'context_id': prepared['id'], 'source_references': [citation(prepared)],
        }, context.first.pk)

    context.first.refresh_from_db()
    assert context.first.context_id is None
    assert context.scope.amendment_id == second.pk


def test_prompt_discovery_skips_document_bodies(context):
    """Fails if source discovery loads private full document bodies or captured signature payloads."""
    prepared = prepare_prompt(context)

    result, _, queries = captured_queries(lambda: authoring.prompt_options(context.project.pk, context.admin))

    assert result['contracts'][0]['id'] == context.contract.pk
    assert prepared['sources'][0]['sha256'] not in json.dumps(result)
    assert '"content_markdown"' not in ' '.join(queries)
    assert '"source_snapshot"' not in ' '.join(queries)


def test_cited_import_rejects_a_scope_identity_changed_after_capture(context):
    """Fails if cited JSON reuses a context after its captured scope identity changes."""
    prepared = prepare_prompt(context, scope_id=context.scope.pk)
    context.scope.key = 'changed-scope'
    context.scope.save(update_fields=['key'])

    with pytest.raises(ValidationError, match='identidad contractual'):
        delivery.import_payload(context.project.pk, context.admin, prepared['template'], 0, apply=True, request_id='stale-scope')

    assert Requirement.objects.count() == 2
    assert version(context) == 0
