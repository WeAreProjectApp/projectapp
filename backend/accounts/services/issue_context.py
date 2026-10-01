"""Read delivery evidence and freeze a ticket's original context without writes."""
from copy import deepcopy

from accounts.models import DeliveryPublication, IssueContext, Requirement, RequirementReview
from accounts.services.delivery_access import DeliveryConflict, fail, is_admin


def capture_context(project, actor, values):
    requirement_id = values.get('source_requirement_id')
    if not requirement_id:
        if values.get('source_publication_id') or values.get('source_requirement_version') is not None:
            fail('Selecciona el requerimiento de la entrega.', 'issue_source_required')
        return None, {'origin_kind': 'general', 'project_id': project.pk}
    requirement = Requirement.objects.select_related(
        'stage__phase__scope__contract', 'stage__phase__scope__amendment',
    ).filter(pk=requirement_id, stage__phase__scope__contract__project=project).first()
    if requirement is None:
        fail('Requerimiento no encontrado en este proyecto.', 'issue_source_invalid')
    stage = requirement.stage
    phase, scope = stage.phase, stage.phase.scope
    if not is_admin(actor) and (
        not scope.contract.client_visible
        or (scope.amendment_id and not scope.amendment.client_visible)
    ):
        fail('La entrega no está disponible.', 'issue_source_invalid')
    publications = DeliveryPublication.objects.filter(stage=stage).order_by('-round')
    if values.get('source_publication_id'):
        publications = publications.filter(pk=values['source_publication_id'])
    publication = publications.first()
    row = next((row for row in publication.payload.get('requirements', [])
                if row['id'] == requirement_id), None) if publication else None
    if row is None:
        fail('El requerimiento no consta en la publicación elegida.', 'issue_source_invalid')
    if values.get('source_requirement_version') is not None and row['version'] != values['source_requirement_version']:
        raise DeliveryConflict('La versión de la guía cambió. Selecciona la publicación original.')
    approved_review = RequirementReview.objects.filter(
        requirement=requirement, requirement_version=row['version'], decision='approved',
    ).order_by('created_at', 'pk').first()
    snapshot = {
        'origin_kind': 'published', 'project_id': project.pk,
        'contract_id': scope.contract_id, 'contract_title': scope.contract.title,
        'amendment_id': scope.amendment_id,
        'amendment_title': scope.amendment.title if scope.amendment_id else None,
        'scope_id': scope.pk, 'scope_title': scope.title,
        'phase_id': phase.pk, 'phase_title': phase.title,
        'stage_id': stage.pk, 'stage_title': publication.payload.get('title', stage.title),
        'stage_version': publication.payload.get('version'),
        'publication_id': publication.pk, 'publication_round': publication.round,
        'requirement_id': requirement.pk, 'requirement_title': row['title'],
        'requirement_version': row['version'], 'requirement': deepcopy(row),
        'approved_publication_id': approved_review.publication_id if approved_review else None,
        'approved_review_id': approved_review.pk if approved_review else None,
    }
    return publication, snapshot


def save_context(ticket, kind, publication, snapshot):
    return IssueContext.objects.create(
        project_id=ticket.project_id, publication=publication, snapshot=snapshot,
        **{'bug_report' if kind == 'bug' else 'change_request': ticket},
    )


def original_context(ticket):
    context = getattr(ticket, 'issue_context', None)
    return context.snapshot if context else {
        'origin_kind': 'legacy_unknown', 'project_id': ticket.project_id,
    }
