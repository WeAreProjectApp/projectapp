"""Only explicit, retained source selections ground delivery authoring."""
import hashlib
import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from freezegun import freeze_time
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import (
    ContractSignatureEvidence, DeliveryPromptContext, DeliveryPromptSource,
    DeliveryWorkspace, Project, ProjectContract, ProjectPhase,
)
from accounts.services import delivery_authoring as authoring
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_authoring_helpers import (
    additional_references, build_authoring_context, other_contract, pdf_bytes, proposal_source, reference,
    signed_amendment, source_document,
)
from accounts.tests.delivery_helpers import RECORDED_AT, prepare_prompt, version
from content.models import BusinessProposal, DocumentType, ProposalDocument

pytestmark = pytest.mark.django_db


@pytest.fixture
def context():
    with freeze_time(RECORDED_AT):
        yield build_authoring_context()


def private_files():
    return sorted(path for path in Path(settings.PRIVATE_MEDIA_ROOT).rglob('*') if path.is_file())


def signed_annex_proof(context):
    amendment = signed_amendment(context)
    prepare_prompt(context, amendment_ids=[amendment.pk], request_id='retain-annex-proof')
    return amendment, amendment.signature_evidence.get()


def original_annex_citation(amendment):
    return {'source_key': f'document-{amendment.document_id}', 'locator': 'Página 1',
            'quote': 'Amendment adds editing records.'}


def test_guides_capture_without_a_stage(context):
    """Fails if preparing contractual guides requires an existing delivery stage."""
    prepared = prepare_prompt(context)

    assert prepared['stage_id'] is None
    assert prepared['scope_id'] is None
    assert prepared['sources'][0]['sha256'] == hashlib.sha256(pdf_bytes()).hexdigest()
    assert prepared['sources'][0]['date'] == RECORDED_AT.isoformat()
    assert DeliveryWorkspace.objects.count() == 0


def test_capture_excludes_unselected_contracts(context):
    """Fails if a capture silently mixes text from contracts the administrator did not select."""
    other_contract(context)
    signed_amendment(context, key='unselected', text='UNSELECTED_AMENDMENT_SCOPE')

    prepared = prepare_prompt(context)

    assert len(prepared['sources']) == 1
    assert 'OTHER_CONTRACT_SCOPE' not in prepared['prompt']
    assert 'UNSELECTED_AMENDMENT_SCOPE' not in prepared['prompt']
    assert context.second.title not in prepared['prompt']


def test_selected_amendment_retains_its_signed_copy(context):
    """Fails if an applicable amendment uses mutable text instead of its signed evidence."""
    amendment = signed_amendment(context)

    prepared = prepare_prompt(context, amendment_ids=[amendment.pk])

    assert prepared['amendment_ids'] == [amendment.pk]
    assert prepared['sources'][1]['role'] == 'amendment'
    assert prepared['sources'][1]['fragments'][0]['text'] == 'Amendment adds editing records.'
    assert prepared['complete'] is True


def test_amendment_from_another_contract_is_rejected(context):
    """Fails if an unrelated amendment can change the selected contractual context."""
    amendment = signed_amendment(context, other_contract(context))

    with pytest.raises(ValidationError, match='otro contrato'):
        prepare_prompt(context, amendment_ids=[amendment.pk])

    assert DeliveryPromptContext.objects.count() == 0


def test_scope_requires_its_applicable_amendment(context):
    """Fails if a scope is captured without the amendment that defines it."""
    amendment = signed_amendment(context)
    context.scope.amendment = amendment
    context.scope.save(update_fields=['amendment'])

    with pytest.raises(ValidationError, match='otrosí'):
        prepare_prompt(context, scope_id=context.scope.pk)

    assert DeliveryPromptContext.objects.count() == 0


def test_annex_association_preserves_legal_uncertainty(context):
    """Fails if an administrative annex association is presented as proven contractual incorporation."""
    document = source_document(context, 'Administrative annex text.')

    prepared = prepare_prompt(context, sources=[reference(document, role='contractual_annex')])

    assert prepared['sources'][1]['applicability_note'] == 'Selected explicitly for this review.'
    assert prepared['sources'][1]['role'] == 'contractual_annex'
    assert prepared['complete'] is False
    assert 'asociación es administrativa' in prepared['uncertainties'][0]


def test_other_contract_cannot_be_attached_as_an_annex(context):
    """Fails if another contract can be disguised as an annex to the selected agreement."""
    other = other_contract(context)

    with pytest.raises(ValidationError, match='otro contrato'):
        prepare_prompt(context, sources=[reference(other.document, role='contractual_annex')])

    assert DeliveryPromptSource.objects.count() == 0
    assert ContractSignatureEvidence.objects.count() == 0


def test_other_contract_reference_is_explicitly_non_normative(context):
    """Fails if a deliberately selected outside reference becomes normative evidence."""
    other = other_contract(context)

    prepared = prepare_prompt(context, sources=[reference(other.document)])

    assert prepared['sources'][1]['role'] == 'reference'
    assert 'OTHER_CONTRACT_SCOPE' in prepared['prompt']
    assert 'no se usará como fundamento' in ' '.join(prepared['sources'][1]['warnings'])


def test_unlinked_contract_document_cannot_be_an_annex(context):
    """Fails if an unlinked contractual document bypasses the annex ownership rule."""
    kind = DocumentType.objects.create(code='contract', name='Contrato')
    document = source_document(context, document_type=kind)

    with pytest.raises(ValidationError, match='referencia no normativa'):
        prepare_prompt(context, sources=[reference(document, role='contractual_annex')])

    assert DeliveryPromptContext.objects.count() == 0


def test_proposal_attachment_requires_project_ownership(context):
    """Fails if an attachment from another project enters the selected context."""
    proposal = BusinessProposal.objects.create(title='Foreign proposal', client_name='Other client')
    source = ProposalDocument.objects.create(proposal=proposal, title='Foreign annex',
                                             file=ContentFile(pdf_bytes(), name='annex.pdf'))

    with pytest.raises(ValidationError, match='no pertenece'):
        prepare_prompt(context, sources=[{'proposal_document_id': source.pk, 'role': 'reference',
                                         'applicability_note': 'Explicit foreign proposal.'}])

    assert DeliveryPromptContext.objects.count() == 0


def test_proposal_source_keeps_an_explicit_unknown_version(context):
    """Fails if the platform invents a digital version for an original proposal attachment."""
    proposal = BusinessProposal.objects.create(title='Project proposal', client_name='Cliente')
    ProjectPhase.objects.create(project=context.project, business_proposal=proposal, order=1)
    source = ProposalDocument.objects.create(proposal=proposal, title='Selected file',
                                             file=ContentFile(pdf_bytes('Proposal reference.'), name='reference.pdf'))

    prepared = prepare_prompt(context, sources=[{'proposal_document_id': source.pk, 'role': 'reference',
                                                'applicability_note': 'Reference for this project.'}])

    assert prepared['sources'][1]['version'] is None
    assert prepared['sources'][1]['version_kind'] == 'unknown'
    assert 'versión digital' in ' '.join(prepared['sources'][1]['warnings'])


def test_retained_source_survives_a_live_document_edit(context):
    """Fails if later document edits change retained contractual excerpts or exact source bytes."""
    document = source_document(context, 'Original selected note.')
    prepared = prepare_prompt(context, sources=[reference(document)])
    document.content_markdown = 'Changed private working note.'
    document.save(update_fields=['content_markdown'])

    recovered = authoring.get_prompt_context(context.project.pk, context.admin, prepared['id'])
    raw, filename, mime = authoring.prompt_source_file(context.project.pk, context.admin, prepared['id'], f'document-{document.pk}')

    assert recovered['sources'] == prepared['sources']
    assert json.loads(raw)['markdown'] == 'Original selected note.'
    assert filename == 'source-content.json'
    assert mime == 'application/json'


def test_client_cannot_read_private_authoring_context(context):
    """Fails if a client can read private contractual drafting sources."""
    prepared = prepare_prompt(context)

    with pytest.raises(PermissionDenied):
        authoring.get_prompt_context(context.project.pk, context.client, prepared['id'])


def test_client_cannot_download_private_source_bytes(context):
    """Fails if a client can download a private drafting capture."""
    prepared = prepare_prompt(context)

    with pytest.raises(PermissionDenied):
        authoring.prompt_source_file(context.project.pk, context.client, prepared['id'], prepared['sources'][0]['source_key'])


def test_context_id_is_bound_to_its_project(context):
    """Fails if a context identifier bypasses the project authorization boundary."""
    prepared = prepare_prompt(context)
    other = Project.objects.create(name='Other project', client=context.client)

    with pytest.raises(NotFound):
        authoring.get_prompt_context(other.pk, context.admin, prepared['id'])


def test_preparation_replay_returns_the_same_capture(context):
    """Fails if replaying an identical preparation creates duplicate retained evidence."""
    first = prepare_prompt(context)

    replayed = prepare_prompt(context)

    assert replayed == first
    assert DeliveryPromptContext.objects.count() == 1
    assert DeliveryPromptSource.objects.count() == 1
    assert version(context) == 0


def test_reused_request_rejects_a_changed_selection(context):
    """Fails if an idempotency key silently changes the selected contractual sources."""
    prepared = prepare_prompt(context)

    with pytest.raises(DeliveryConflict, match='otra preparación'):
        prepare_prompt(context, instructions='Changed instructions.')

    assert str(DeliveryPromptContext.objects.get().pk) == prepared['id']


def test_stale_preparation_writes_no_sources(context):
    """Fails if stale preparation creates sources despite a workspace version conflict."""
    with pytest.raises(DeliveryConflict):
        prepare_prompt(context, expected_version=1)

    assert DeliveryPromptContext.objects.count() == 0
    assert DeliveryPromptSource.objects.count() == 0


def test_captured_context_cannot_be_overwritten(context):
    """Fails if a saved drafting context can be rewritten after capture."""
    prepared = prepare_prompt(context)
    record = DeliveryPromptContext.objects.get(pk=prepared['id'])
    record.prompt = 'Replacement text.'

    with pytest.raises(ValueError, match='cannot be edited'):
        record.save()

    record.refresh_from_db()
    assert record.prompt == prepared['prompt']


def test_oversized_context_rolls_back_its_private_copies(context):
    """Fails if rejecting an oversized context leaves partial rows or private copies."""
    references = additional_references(context, 8, characters=15_000)
    original_files = private_files()

    with pytest.raises(ValidationError, match='100 KB'):
        prepare_prompt(context, sources=references)

    assert DeliveryPromptContext.objects.count() == 0
    assert DeliveryPromptSource.objects.count() == 0
    assert ContractSignatureEvidence.objects.count() == 0
    assert private_files() == original_files


def test_missing_signed_original_produces_an_incomplete_capture(context):
    """Fails if a lost signed original is replaced by live text or presented as retained proof."""
    context.document.generated_file.storage.delete(context.document.generated_file.name)

    prepared = prepare_prompt(context)

    source = prepared['sources'][0]
    assert prepared['complete'] is False
    assert (source['status'], source['sha256'], source['download_url']) == ('unreadable', None, None)
    assert source['fragments'] == []
    assert 'no está disponible' in ' '.join(source['warnings'])
    assert 'Alcance acordado.' not in prepared['prompt']
    assert ContractSignatureEvidence.objects.count() == 0


def test_oversized_contract_original_never_retains_a_prefix_hash(context):
    """Fails if an original above 15 MB creates a partial backup or a hash of truncated bytes."""
    body = pdf_bytes()
    original = proposal_source(context, body + b' ' * (15 * 1024 * 1024 + 1 - len(body)), 'oversized-contract.pdf')
    contract = ProjectContract.objects.create(project=context.project, key='oversized-original',
                                              title='Contract with oversized original', proposal_document=original)

    prepared = prepare_prompt(context, contract_id=contract.pk)

    source = prepared['sources'][0]
    assert prepared['complete'] is False
    assert (source['status'], source['sha256'], source['download_url']) == ('unreadable', None, None)
    assert source['fragments'] == []
    assert 'supera 15 MB' in ' '.join(source['warnings'])
    assert DeliveryPromptSource.objects.get(context_id=prepared['id']).file.name == ''


def test_tampered_signed_annex_cannot_supply_a_verified_quote(context):
    """Fails if altered signed annex bytes remain usable as captured contractual quotations."""
    amendment, evidence = signed_annex_proof(context)
    with evidence.file.open('wb') as stream:
        stream.write(pdf_bytes('Replacement annex content.'))

    prepared = prepare_prompt(context, request_id='tampered-annex',
                              sources=[reference(amendment.document, role='contractual_annex')])

    source = prepared['sources'][1]
    assert prepared['complete'] is False
    assert (source['status'], source['sha256'], source['download_url']) == ('unreadable', None, None)
    assert source['fragments'] == []
    assert 'no coincide con su hash' in ' '.join(source['warnings'])
    with pytest.raises(ValidationError, match='fuente capturada legible'):
        authoring.validate_references(DeliveryPromptContext.objects.get(pk=prepared['id']),
                                      [original_annex_citation(amendment)], normative=True)


def test_missing_signed_annex_cannot_supply_a_verified_quote(context):
    """Fails if a missing signed annex falls back to its live original or validates an unsupported quote."""
    amendment, evidence = signed_annex_proof(context)
    evidence.file.storage.delete(evidence.file.name)

    prepared = prepare_prompt(context, request_id='missing-annex',
                              sources=[reference(amendment.document, role='contractual_annex')])

    source = prepared['sources'][1]
    assert prepared['complete'] is False
    assert (source['status'], source['sha256'], source['download_url']) == ('unreadable', None, None)
    assert source['fragments'] == []
    assert 'No se pudo leer la copia de origen.' in source['warnings']
    assert 'Amendment adds editing records.' not in prepared['prompt']
    with pytest.raises(ValidationError, match='fuente capturada legible'):
        authoring.validate_references(DeliveryPromptContext.objects.get(pk=prepared['id']),
                                      [original_annex_citation(amendment)], normative=True)
