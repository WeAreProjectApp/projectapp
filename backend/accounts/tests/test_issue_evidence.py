"""Ticket evidence retains its original publication and object permissions."""
import hashlib

import pytest
from django.core.files.base import ContentFile
from rest_framework.exceptions import APIException
from rest_framework.test import APIClient

from accounts.models import (
    DeliveryDocumentSnapshot, DeliveryPhase, DeliveryScope, DeliveryStage,
    IssueAttachment, IssueResponse, Project, ProjectContract,
)
from accounts.services import delivery_workflow as delivery
from accounts.services import issue_reports as issues
from accounts.services.delivery_documents import MAX_PDF_BYTES
from accounts.services.issue_evidence import allowed_documents
from accounts.tests._issue_evidence_helpers import (
    amendment, context as context, evidence_document,
    memory_only_mail as memory_only_mail, pdf_bytes,
)
from accounts.tests.delivery_helpers import publish, version

pytestmark = pytest.mark.django_db


def source_ticket(context):
    return issues.create_ticket(context.project.pk, context.client, 'bug', {
        'title': 'Falla al guardar', 'source_requirement_id': context.first.pk,
    })


def link_document(context, document, level, target):
    return delivery.link_document(context.project.pk, context.admin, {
        'expected_version': version(context), 'level': level,
        'target_id': target.pk, 'document_id': document.pk,
    })


def original_target(context, level):
    if level == 'amendment':
        item = amendment(context)
        context.scope.amendment = item
        context.scope.save(update_fields=['amendment'])
        return item
    return {'project': context.project, 'contract': context.contract,
            'scope': context.scope, 'phase': context.phase,
            'stage': context.stage, 'requirement': context.first}[level]


def another_contract(context):
    source = evidence_document(context, title='Segundo contrato')
    return ProjectContract.objects.create(
        project=context.project, document=source, key='second', title='Segundo contrato', client_visible=True,
    )


def another_scope(context):
    return DeliveryScope.objects.create(contract=context.contract, key='second', title='Segundo alcance')


def another_phase(context):
    return DeliveryPhase.objects.create(scope=context.scope, key='second', title='Segunda fase')


def another_stage(context):
    return DeliveryStage.objects.create(phase=context.phase, key='second', title='Segunda etapa')


def another_requirement(context):
    return context.second


def another_amendment(context):
    return amendment(context, key='different')


@pytest.mark.parametrize('level', ['project', 'contract', 'amendment', 'scope', 'phase', 'stage', 'requirement'])
def test_original_hierarchy_document_is_captured(context, level):
    """Falla si la respuesta rechaza evidencia que pertenece al origen contractual congelado."""
    document = evidence_document(context)
    link_document(context, document, level, original_target(context, level))
    publish(context)
    ticket = source_ticket(context)

    issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
        'admin_response': 'Diagnóstico de la entrega original.', 'document_ids': [document.pk],
    })

    attachment = IssueAttachment.objects.get(document=document)
    assert attachment.file.read() == pdf_bytes()
    assert attachment.title == 'Evidencia del ticket'
    assert attachment.sha256 == hashlib.sha256(pdf_bytes()).hexdigest()


@pytest.mark.parametrize('level,target_builder', [
    ('contract', another_contract), ('amendment', another_amendment),
    ('scope', another_scope), ('phase', another_phase),
    ('stage', another_stage), ('requirement', another_requirement),
])
def test_other_hierarchy_document_is_rejected(context, level, target_builder):
    """Falla si una respuesta mezcla contrato, otrosí, alcance, fase, etapa o guía ajenos al origen."""
    publish(context)
    ticket = source_ticket(context)
    document = evidence_document(context)
    link_document(context, document, level, target_builder(context))

    with pytest.raises(APIException) as error:
        issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
            'status': 'resolved', 'admin_response': 'Evidencia equivocada.', 'document_ids': [document.pk],
        })

    assert error.value.status_code == 400
    assert error.value.detail['code'] == 'issue_document_context'
    assert IssueAttachment.objects.count() == 0
    assert IssueResponse.objects.count() == 0
    ticket.refresh_from_db()
    assert ticket.status == 'reported'


def test_global_client_document_bound_to_another_project_is_absent(context):
    """Falla si un PDF global del mismo cliente hereda acceso desde el proyecto equivocado."""
    other = Project.objects.create(name='Otro proyecto', client=context.client)
    document = evidence_document(context)
    document.project = None
    document.save(update_fields=['project'])
    delivery.link_document(other.pk, context.admin, {
        'expected_version': 0, 'level': 'project', 'target_id': other.pk, 'document_id': document.pk,
    })

    available = allowed_documents(context.project, context.admin, public=False)

    assert [item.pk for item in available] == []


def test_client_cannot_select_an_unlinked_private_document(context):
    """Falla si el selector de documentos del cliente ofrece notas privadas sin publicación."""
    document = evidence_document(context)
    document.is_client_visible = False
    document.save(update_fields=['is_client_visible'])

    available = allowed_documents(context.project, context.client, public=True)

    assert [item.pk for item in available] == []


def test_public_reply_cannot_release_a_draft_document(context):
    """Falla si responder públicamente comparte un PDF ligado a una etapa sin publicar."""
    ticket = issues.create_ticket(context.project.pk, context.client, 'bug', {'title': 'General'})
    document = evidence_document(context)
    link_document(context, document, 'stage', context.stage)

    with pytest.raises(APIException) as error:
        issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
            'admin_response': 'PDF del borrador.', 'contract_id': context.contract.pk,
            'document_ids': [document.pk],
        })

    assert error.value.status_code == 400
    assert error.value.detail['code'] == 'issue_document_context'
    assert IssueAttachment.objects.count() == 0
    assert IssueResponse.objects.count() == 0


def test_ticket_attachment_uses_its_original_round_snapshot(context):
    """Falla si un ticket antiguo recibe los bytes o título del PDF de una ronda posterior."""
    document = evidence_document(context)
    original = pdf_bytes()
    link_document(context, document, 'stage', context.stage)
    publish(context)
    ticket = source_ticket(context)
    document.title = 'Título de la ronda nueva'
    document.generated_file.save('new-round.pdf', ContentFile(original + b'\n% later round'))
    document.save(update_fields=['title'])
    publish(context, request_id='publish-2')

    issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
        'admin_response': 'Revisión de la primera ronda.', 'document_ids': [document.pk],
    })

    attachment = IssueAttachment.objects.get(document=document)
    assert attachment.title == 'Evidencia del ticket'
    assert attachment.file.read() == original
    assert attachment.sha256 == hashlib.sha256(original).hexdigest()


def test_oversized_published_evidence_rolls_back_the_reply(context):
    """Falla si una copia publicada que excede el límite crea una respuesta o adjunto parcial."""
    document = evidence_document(context)
    link_document(context, document, 'stage', context.stage)
    publish(context)
    ticket = source_ticket(context)
    snapshot = DeliveryDocumentSnapshot.objects.get(link__document=document)
    snapshot.file.save('oversized.pdf', ContentFile(b'%PDF-' + b'x' * MAX_PDF_BYTES))

    with pytest.raises(APIException) as error:
        issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
            'admin_response': 'Evidencia demasiado grande.', 'document_ids': [document.pk],
        })

    assert error.value.status_code == 400
    assert error.value.detail['code'] == 'issue_pdf_too_large'
    assert IssueAttachment.objects.count() == 0
    assert IssueResponse.objects.count() == 0


def test_duplicate_document_ids_do_not_create_duplicate_evidence(context):
    """Falla si repetir un documento crea copias o deja una respuesta parcial."""
    ticket = issues.create_ticket(context.project.pk, context.client, 'bug', {'title': 'General'})
    document = evidence_document(context)

    with pytest.raises(APIException) as error:
        issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
            'admin_response': 'Documento repetido.', 'document_ids': [document.pk, document.pk],
        })

    assert error.value.status_code == 400
    assert error.value.detail['code'] == 'issue_document_context'
    assert IssueAttachment.objects.count() == 0
    assert IssueResponse.objects.count() == 0


@pytest.mark.parametrize('actor_name,status', [
    ('client', 200), ('admin', 200), ('outsider', 404), ('anonymous', 401),
])
def test_response_attachment_download_preserves_object_permissions(context, actor_name, status):
    """Falla si conocer la URL da acceso a otro cliente o rompe la descarga privada del dueño."""
    ticket = issues.create_ticket(context.project.pk, context.client, 'bug', {'title': 'General'})
    document = evidence_document(context)
    issues.evaluate_ticket(context.project.pk, context.admin, 'bug', ticket.pk, {
        'admin_response': 'Diagnóstico público.', 'document_ids': [document.pk],
    })
    attachment = IssueAttachment.objects.get()
    actors = {'client': context.client, 'admin': context.admin,
              'outsider': context.outsider, 'anonymous': None}
    api = APIClient()
    api.force_authenticate(user=actors[actor_name])

    response = api.get(f'/api/accounts/issue-reports/attachments/{attachment.pk}/')

    assert response.status_code == status
    response.close()


@pytest.mark.parametrize('kind', ['bug', 'change'])
def test_comment_attachment_download_retains_frozen_bytes(context, kind):
    """Falla si los adjuntos de comentarios existentes pierden contenido o dejan de ser privados."""
    publish(context)
    ticket = issues.create_ticket(context.project.pk, context.client, kind, {
        'title': 'Desde la entrega', 'source_requirement_id': context.first.pk,
    })
    document = evidence_document(context)
    issues.comment_ticket(context.project.pk, context.client, kind, ticket.pk, {
        'content': 'Adjunto evidencia del problema.', 'document_ids': [document.pk],
    })
    attachment = IssueAttachment.objects.get()
    api = APIClient()
    api.force_authenticate(user=context.client)

    response = api.get(f'/api/accounts/issue-reports/attachments/{attachment.pk}/')

    assert response.status_code == 200
    assert b''.join(response.streaming_content) == pdf_bytes()
    assert response['Cache-Control'] == 'private, no-store'
    assert response['X-Content-Type-Options'] == 'nosniff'
    assert response['Content-Type'] == 'application/pdf'
    response.close()


def test_missing_attachment_download_returns_404(context):
    """Falla si una referencia inexistente filtra detalles o termina como error del servidor."""
    api = APIClient()
    api.force_authenticate(user=context.client)

    response = api.get('/api/accounts/issue-reports/attachments/999999/')

    assert response.status_code == 404


@pytest.mark.parametrize('stored', [
    ['Private legacy prompt'],
    {'public': ['Private legacy prompt'], 'private': {'source_references': ['Private citation']}},
])
def test_legacy_reply_json_redacts_private_material(context, stored):
    """Falla si JSON legado de forma inesperada publica prompts o referencias privadas."""
    ticket = issues.create_ticket(context.project.pk, context.client, 'bug', {'title': 'General'})
    IssueResponse.objects.create(
        bug_report=ticket, actor=context.admin, message='Respuesta legada.', review_evidence=stored,
    )
    api = APIClient()
    api.force_authenticate(user=context.client)

    response = api.get(f'/api/accounts/projects/{context.project.pk}/bug-reports/{ticket.pk}/')

    assert response.status_code == 200
    assert response.data['responses'][0]['review_evidence'] == {}
    assert 'Private legacy prompt' not in str(response.data)
    assert 'Private citation' not in str(response.data)
