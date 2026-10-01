"""Ticket PDFs reuse delivery storage and checks, without publishing source links."""
import hashlib

from django.db.models import Q
from rest_framework.exceptions import NotFound

from accounts.models import ContractAmendment, DeliveryDocumentLink, IssueAttachment, ProjectContract
from accounts.services.delivery_access import fail, is_admin
from accounts.services.delivery_documents import MAX_PDF_BYTES, PortalDocumentIndex, _raw_pdf, store_private_pdf
from accounts.services.issue_context import original_context
from content.models import Document


def allowed_documents(project, actor, ticket=None, *, public=False, contract=None):
    docs = Document.objects.filter(is_archived=False).exclude(
        document_type__code='collection_account',
    ).filter(Q(project=project) | Q(project__isnull=True, client_user=project.client)).filter(
        Q(client_user__isnull=True) | Q(client_user=project.client),
    ).select_related('project').order_by('title', 'pk')
    context = original_context(ticket) if ticket else {}
    if contract and not context.get('contract_id'):
        context = {**context, 'contract_id': contract.pk}
    bindings = list(DeliveryDocumentLink.objects.filter(document_id__in=docs.values('pk')).select_related(
        'contract', 'amendment', 'scope', 'phase__scope', 'stage__phase__scope',
        'requirement__stage__phase__scope',
    ))
    excluded = set()
    for document_id, contract_id, project_id in ProjectContract.objects.filter(
        document_id__in=docs.values('pk'),
    ).values_list('document_id', 'pk', 'project_id'):
        if project_id != project.pk or contract_id != context.get('contract_id'):
            excluded.add(document_id)
    for document_id, contract_id, amendment_id, project_id in ContractAmendment.objects.filter(
        document_id__in=docs.values('pk'),
    ).values_list('document_id', 'contract_id', 'pk', 'contract__project_id'):
        if project_id != project.pk or contract_id != context.get('contract_id') or (
            context.get('scope_id') and amendment_id != context.get('amendment_id')
        ):
            excluded.add(document_id)
    for link in bindings:
        if link.project_id != project.pk:
            excluded.add(link.document_id)
            continue
        if link.level == 'project':
            continue
        contract_id = link.contract_id
        scope_id = link.scope_id
        amendment_id = link.amendment_id
        if link.level == 'amendment':
            contract_id = link.amendment.contract_id
        if link.level in ('scope', 'phase', 'stage', 'requirement'):
            scope = (link.scope if link.level == 'scope' else link.phase.scope if link.level == 'phase'
                     else link.stage.phase.scope if link.level == 'stage' else link.requirement.stage.phase.scope)
            contract_id, scope_id, amendment_id = scope.contract_id, scope.pk, scope.amendment_id
        if not context.get('contract_id') or contract_id != context['contract_id']:
            excluded.add(link.document_id)
        elif scope_id and context.get('scope_id') and scope_id != context['scope_id']:
            excluded.add(link.document_id)
        elif amendment_id and context.get('scope_id') and amendment_id != context.get('amendment_id'):
            excluded.add(link.document_id)
        elif link.phase_id and context.get('phase_id') and link.phase_id != context['phase_id']:
            excluded.add(link.document_id)
        elif link.stage_id and context.get('stage_id') and link.stage_id != context['stage_id']:
            excluded.add(link.document_id)
        elif link.requirement_id and context.get('requirement_id') and link.requirement_id != context['requirement_id']:
            excluded.add(link.document_id)
    candidates = list(docs.exclude(pk__in=excluded))
    portal = PortalDocumentIndex(project.client, candidates)
    result = []
    for doc in candidates:
        if not is_admin(actor) and not portal.visible(doc):
            continue
        if public and not all(portal.index.visible(link) for link in portal.index.by_document[doc.pk]):
            continue
        result.append(doc)
    return result


def attach_documents(project, actor, ticket, document_ids, *, public, contract=None, **target):
    if not document_ids:
        return []
    available = {doc.pk: doc for doc in allowed_documents(project, actor, ticket, public=public, contract=contract)}
    if len(set(document_ids)) != len(document_ids) or any(pk not in available for pk in document_ids):
        fail('Documento no disponible para el contexto de este ticket.', 'issue_document_context')
    portal = PortalDocumentIndex(project.client, list(available.values()))
    origin = original_context(ticket)
    result = []
    for document_id in document_ids:
        doc = available[document_id]
        snapshots = [snapshot for link in portal.index.by_document[doc.pk]
                     for snapshot in portal.index.snapshots[link.pk]
                     if snapshot.publication_id == origin.get('publication_id')]
        snapshot = snapshots[0] if snapshots else portal.snapshot(doc) if public else None
        if snapshot:
            with snapshot.file.open('rb') as source:
                pdf = source.read(MAX_PDF_BYTES + 1)
            title = getattr(snapshot, 'title', doc.title)
        else:
            pdf, title = _raw_pdf(doc), doc.title
        if len(pdf) > MAX_PDF_BYTES:
            fail('El PDF supera el límite de 10 MB.', 'issue_pdf_too_large')
        attachment = IssueAttachment(document=doc, title=title, sha256=hashlib.sha256(pdf).hexdigest(), **target)
        store_private_pdf(attachment, pdf, f'issue-{ticket.pk}-document-{doc.pk}.pdf')
        attachment.save()
        result.append(attachment)
    return result


def attachment_for_actor(attachment_id, actor):
    item = IssueAttachment.objects.select_related(
        'response__bug_report__project', 'response__change_request__project',
        'bug_comment__bug_report__project', 'change_comment__change_request__project',
    ).filter(pk=attachment_id).first()
    if item is None:
        raise NotFound('Adjunto no encontrado.')
    message = item.response or item.bug_comment or item.change_comment
    ticket = (message.bug_report or message.change_request) if item.response_id else (
        message.bug_report if item.bug_comment_id else message.change_request
    )
    if not is_admin(actor) and (
        message.is_internal or ticket.is_archived or ticket.project.client_id != actor.pk
    ):
        raise NotFound('Adjunto no encontrado.')
    return item
