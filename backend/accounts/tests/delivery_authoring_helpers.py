"""Real signed sources for focused delivery authoring behavior tests."""
import copy
import io
import zipfile

from django.core.files.base import ContentFile
from reportlab.pdfgen.canvas import Canvas
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import ContractAmendment, ProjectContract
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import RECORDED_AT, build_delivery_context, prepare_prompt, version
from content.models import Document

CONTRACT_TEXT = 'Contract includes creating records.'


def pdf_bytes(text=CONTRACT_TEXT):
    stream = io.BytesIO()
    canvas = Canvas(stream, invariant=1)
    canvas.drawString(30, 700, text)
    canvas.save()
    return stream.getvalue()


def docx_bytes():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Original DOCX reference.</w:t></w:r></w:p></w:body></w:document>')
    return stream.getvalue()


def proposal_source(context, body, filename):
    from accounts.models import ProjectPhase
    from content.models import BusinessProposal, ProposalDocument
    proposal = BusinessProposal.objects.create(title='Selected project proposal', client_name='Cliente')
    ProjectPhase.objects.create(project=context.project, business_proposal=proposal, order=1)
    return ProposalDocument.objects.create(proposal=proposal, title='Selected original file',
                                            file=ContentFile(body, name=filename))


def build_authoring_context():
    context = build_delivery_context()
    context.document.generated_file.save('contract.pdf', ContentFile(pdf_bytes()), save=True)
    return context


def source_document(context, text='Selected additional text.', **overrides):
    fields = {'project': context.project, 'client_user': context.client,
              'title': 'Additional source', 'content_markdown': text,
              'include_portada': False, 'include_subportada': False, 'include_contraportada': False}
    fields.update(overrides)
    return Document.objects.create(**fields)


def other_contract(context):
    document = source_document(context, 'OTHER_CONTRACT_SCOPE')
    return ProjectContract.objects.create(project=context.project, key='other-contract',
                                          title='Other contract', document=document)


def signed_amendment(context, contract=None, *, key='amendment', text='Amendment adds editing records.'):
    document = source_document(context, text, requires_signature=True, signed_by=context.client,
                               signed_at=RECORDED_AT, signature_name='Cliente')
    document.generated_file.save('amendment.pdf', ContentFile(pdf_bytes(text)), save=True)
    return ContractAmendment.objects.create(contract=contract or context.contract, key=key,
                                            title='Selected amendment', document=document, client_visible=True)


def reference(document, *, role='reference'):
    return {'document_id': document.pk, 'role': role, 'applicability_note': 'Selected explicitly for this review.'}


def additional_references(context, count, *, characters=30):
    return [reference(source_document(context, 'Reference text ' + 'x' * characters)) for _ in range(count)]


def citation(prepared):
    source = prepared['sources'][0]
    return {'source_key': source['source_key'], 'locator': source['fragments'][0]['locator'],
            'quote': CONTRACT_TEXT}


def guides_payload(prepared):
    return copy.deepcopy(prepared['template'])


def guide_leaf(payload):
    return payload['scopes'][0]['phases'][0]['stages'][0]['requirements'][0]


def malformed_guides(prepared, kind):
    payload = guides_payload(prepared)
    scope = payload['scopes'][0]
    if kind == 'phase':
        scope['phases'] = [None]
    elif kind == 'stages':
        scope['phases'][0]['stages'] = 'invalid'
    else:
        scope['phases'][0]['stages'][0]['requirements'] = None
    return payload


def manual_payload(prepared):
    payload = guides_payload(prepared)
    payload['schema_version'] = 1
    payload.pop('context_id')
    guide_leaf(payload).pop('source_references')
    return payload


def trace_first(context, prepared):
    delivery.mutate_node(context.project.pk, context.admin, 'requirements', {
        'expected_version': version(context), 'context_id': prepared['id'],
        'source_references': [citation(prepared)],
    }, context.first.pk)
    context.first.refresh_from_db()


def existing_tree_payload(context, prepared):
    payload = guides_payload(prepared)
    scope = payload['scopes'][0]
    scope.update(key=context.scope.key, title=context.scope.title, description=context.scope.description)
    phase = scope['phases'][0]
    phase.update(key=context.phase.key, title=context.phase.title)
    stage = phase['stages'][0]
    stage.update(key=context.stage.key, title=context.stage.title)
    guide_leaf(payload).update(key=context.first.key, title=context.first.title,
                               description=context.first.description, guide=context.first.guide)
    return payload


def reply_payload(prepared, *, classification='inside_scope'):
    return {'schema_version': 2, 'context_id': prepared['id'],
            'response_text': 'We will complete the pending validation instructions.',
            'classifications': [{'request': 'Add a missing creation step.', 'classification': classification,
                                 'rationale': 'The selected agreement describes record creation.',
                                 'citations': [citation(prepared)]}]}


def captured_citation(prepared, role):
    source = next(source for source in prepared['sources'] if source['role'] == role)
    fragment = source['fragments'][0]
    return {'source_key': source['source_key'], 'locator': fragment['locator'], 'quote': fragment['text']}


def reply_message(context, prepared, **overrides):
    payload = reply_payload(prepared)
    values = {'expected_version': version(context), 'request_id': 'share-reviewed-response',
              'level': 'stage', 'target_id': context.stage.pk, 'message': payload['response_text'],
              'context_id': prepared['id'], 'source_references': [citation(prepared)],
              'classifications': payload['classifications'], 'human_reviewed': True}
    values.update(overrides)
    return values


def api_for(actor):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(actor).access_token}')
    return api


def endpoint(context, path):
    return f'/api/accounts/projects/{context.project.pk}/delivery/{path}'
