"""Immutable private documents supporting a recorded client decision."""
import hashlib
import io

from rest_framework.exceptions import NotFound

from accounts.models import DeliveryReviewDocumentEvidence, RequirementReview
from accounts.services.delivery_access import fail, is_admin, project_for_actor
from accounts.services.delivery_documents import (
    _raw_pdf, document_can_be_shared, store_private_pdf, validated_pdf_bytes,
)


def capture_review_documents(review, documents):
    """Copy proof within the workflow's database transaction/artifact scope."""
    project = review.publication.stage.phase.scope.contract.project
    documents = list(documents)
    for document in documents:
        if (document.is_archived or document.project_id not in (None, project.pk)
                or document.client_user_id not in (None, project.client_id)
                or (document.project_id is None and document.client_user_id != project.client_id)):
            fail('El respaldo pertenece a otro proyecto o cliente.', 'document_context')
        if not document_can_be_shared(project, document):
            fail('El respaldo está asociado a una guía que todavía no se ha publicado.', 'document_not_published')
    existing = {evidence.document_id: evidence for evidence in review.document_evidence.all()}
    result = []
    for document in documents:
        evidence = existing.get(document.pk)
        if evidence is None:
            pdf = validated_pdf_bytes(io.BytesIO(_raw_pdf(document)))
            evidence = DeliveryReviewDocumentEvidence(
                review=review, document=document, title=document.title,
                sha256=hashlib.sha256(pdf).hexdigest(),
            )
            store_private_pdf(evidence, pdf, 'approval-evidence.pdf')
            evidence.save()
            existing[document.pk] = evidence
        result.append(evidence)
    return result


def evidence_data(evidence, project_id):
    """Serialize a prefetched proof after the caller authorizes its review."""
    return {
        'id': evidence.pk, 'review_id': evidence.review_id,
        'document_id': evidence.document_id, 'title': evidence.title,
        'sha256': evidence.sha256, 'created_at': evidence.created_at.isoformat(),
        'pdf_url': (f'/api/accounts/projects/{project_id}/delivery/reviews/'
                    f'{evidence.review_id}/evidence/{evidence.pk}/pdf/'),
    }


def _review_for_actor(project_id, actor, review_id):
    project = project_for_actor(project_id, actor)
    review = RequirementReview.objects.filter(
        pk=review_id, publication__stage__phase__scope__contract__project=project,
    ).select_related(
        'publication__stage__phase__scope__contract',
        'publication__stage__phase__scope__amendment',
    ).prefetch_related('document_evidence').first()
    if review is None:
        raise NotFound('Revisión no disponible.')
    if not is_admin(actor):
        scope = review.publication.stage.phase.scope
        if (not scope.contract.client_visible
                or (scope.amendment_id and not scope.amendment.client_visible)
                or not any(item.get('id') == review.requirement_id
                           for item in review.publication.payload.get('requirements', []))):
            raise NotFound('Revisión no publicada.')
    return review


def list_review_evidence(project_id, actor, review_id):
    review = _review_for_actor(project_id, actor, review_id)
    return {'documents': [evidence_data(evidence, project_id) for evidence in review.document_evidence.all()]}


def review_evidence_pdf(project_id, actor, review_id, evidence_id):
    review = _review_for_actor(project_id, actor, review_id)
    evidence = next((item for item in review.document_evidence.all() if item.pk == evidence_id), None)
    if evidence is None:
        raise NotFound('Respaldo no disponible.')
    try:
        with evidence.file.open('rb') as source:
            return source.read(), evidence.title
    except (OSError, ValueError):
        raise NotFound('El respaldo registrado no está disponible.') from None
