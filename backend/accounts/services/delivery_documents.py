"""Inherited delivery-document access and immutable private PDF evidence."""
import hashlib
import io
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.files.base import ContentFile
from django.db.models import Q
from pypdf import PdfReader
from rest_framework.exceptions import NotFound

from accounts.models import (
    ContractAmendment, DeliveryDocumentLink, DeliveryDocumentSnapshot,
    DeliveryPublication, ProjectContract, RequirementReview, ContractSignatureEvidence,
)
from accounts.services.delivery_access import fail, is_admin, project_for_actor, require_admin
from content.models import Document, ProposalDocument
from content.services.document_pdf_service import DocumentPdfService

MAX_PDF_BYTES = 10 * 1024 * 1024
_saved_artifacts = ContextVar('delivery_saved_artifacts', default=None)


@contextmanager
def artifact_scope():
    """Rollback private files when a database mutation fails after PDF creation."""
    artifacts = []
    token = _saved_artifacts.set(artifacts)
    try:
        yield
    except BaseException:
        for storage, name in artifacts:
            storage.delete(name)
        raise
    finally:
        _saved_artifacts.reset(token)


def store_private_pdf(instance, pdf, filename):
    instance.file.save(filename, ContentFile(pdf), save=False)
    artifacts = _saved_artifacts.get()
    if artifacts is not None:
        artifacts.append((instance.file.storage, instance.file.name))


def validated_pdf_bytes(file):
    if getattr(file, 'size', 0) > MAX_PDF_BYTES:
        fail('El PDF no puede superar 10 MB.', 'pdf_too_large')
    pdf = file.read(MAX_PDF_BYTES + 1)
    if len(pdf) > MAX_PDF_BYTES:
        fail('El PDF no puede superar 10 MB.', 'pdf_too_large')
    if not pdf.startswith(b'%PDF-'):
        fail('Adjunta un archivo PDF válido.', 'pdf_invalid')
    try:
        reader = PdfReader(io.BytesIO(pdf))
        if reader.is_encrypted or not len(reader.pages) or len(reader.pages) > 500:
            fail('Adjunta un PDF legible, sin contraseña y de hasta 500 páginas.', 'pdf_invalid')
    except Exception as exc:
        from rest_framework.exceptions import ValidationError
        if isinstance(exc, ValidationError):
            raise
        fail('No se pudo leer el PDF firmado.', 'pdf_invalid')
    return pdf


def _raw_pdf(doc):
    if doc.generated_file:
        try:
            with doc.generated_file.open('rb') as source:
                pdf = source.read(MAX_PDF_BYTES + 1)
        except (OSError, ValueError):
            fail('El PDF de origen no está disponible.', 'pdf_unavailable')
    else:
        pdf = DocumentPdfService.generate(doc)
    if not pdf:
        fail('El documento necesita contenido válido antes de publicarse.', 'pdf_unavailable')
    if len(pdf) > MAX_PDF_BYTES:
        fail('El documento supera el límite de 10 MB.', 'pdf_too_large')
    return pdf


def _snapshot_for_link(link, index=None):
    if index is not None:
        return index.snapshot(link)
    if link.level == 'requirement' and link.requirement.review_status == 'approved':
        approved = RequirementReview.objects.filter(requirement=link.requirement, decision='approved').first()
        if approved:
            snapshot = DeliveryDocumentSnapshot.objects.filter(link=link, publication_id=approved.publication_id).first()
            if snapshot:
                return snapshot
    return DeliveryDocumentSnapshot.objects.filter(link=link).select_related('publication').order_by('-publication__created_at', '-id').first()


def _link_visible(project, actor, link, index=None):
    index = index or DeliveryDocumentIndex(project, actor)
    return index.visible(link)


def _link_data(project, actor, link, index=None):
    snapshot = None if is_admin(actor) else _snapshot_for_link(link, index)
    return {
        'id': link.pk, 'document_id': link.document_id, 'uuid': str(link.document.uuid),
        'title': snapshot.title if snapshot else link.document.title,
        'level': link.level,
        'target_id': getattr(link, f'{link.level}_id') if link.level != 'project' else project.pk,
        'pdf_url': f'/api/accounts/projects/{project.pk}/delivery/documents/{link.pk}/pdf/',
        'snapshot_id': snapshot.pk if snapshot else None,
        'sha256': snapshot.sha256 if snapshot else None,
    }


def _links_qs(project=None):
    qs = DeliveryDocumentLink.objects.all()
    if project is not None:
        qs = qs.filter(project=project)
    return qs.select_related(
        'project__client', 'document', 'contract', 'amendment__contract',
        'scope__contract', 'scope__amendment', 'phase__scope__contract', 'phase__scope__amendment',
        'stage__phase__scope__contract', 'stage__phase__scope__amendment',
        'requirement__stage__phase__scope__contract', 'requirement__stage__phase__scope__amendment',
    )


class DeliveryDocumentIndex:
    """Request-local inherited access and evidence, independent of row count.

    Every attachment of a source participates in its visibility. A project
    attachment cannot bypass an unpublished stage that uses the same source.
    Published evidence remains readable when its editable source is archived.
    """

    def __init__(self, project, actor, *, publications=None, reviews=None, document_ids=None):
        self.project = project
        self.actor = actor
        self.admin = is_admin(actor)
        sources = document_ids if document_ids is not None else DeliveryDocumentLink.objects.filter(project=project).values('document_id')
        self.links = list(_links_qs().filter(document_id__in=sources))
        self.by_document = defaultdict(list)
        for link in self.links:
            self.by_document[link.document_id].append(link)
        project_ids = {link.project_id for link in self.links}
        provided = list(publications or [])
        remaining = project_ids - ({project.pk} if publications is not None else set())
        if remaining:
            provided.extend(DeliveryPublication.objects.filter(
                stage__phase__scope__contract__project_id__in=remaining,
            ).select_related('stage__phase__scope').order_by('stage_id', '-round'))
        self.latest = {}
        self.published_scopes = set()
        self.published_phases = set()
        for publication in provided:
            current = self.latest.get(publication.stage_id)
            if current is None or publication.round > current.round:
                self.latest[publication.stage_id] = publication
            self.published_phases.add(publication.stage.phase_id)
            self.published_scopes.add(publication.stage.phase.scope_id)
        self.approved_rounds = {}
        provided_reviews = list(reviews or [])
        other_requirements = {link.requirement_id for link in self.links if link.requirement_id}
        if reviews is not None:
            other_requirements = {link.requirement_id for link in self.links if link.requirement_id and link.project_id != project.pk}
        if other_requirements:
            provided_reviews.extend(RequirementReview.objects.filter(
                requirement_id__in=other_requirements, decision='approved',
            ))
        for review in provided_reviews:
            if review.decision == 'approved':
                self.approved_rounds.setdefault(review.requirement_id, review.publication_id)
        self.snapshots = defaultdict(list)
        for snapshot in DeliveryDocumentSnapshot.objects.filter(link_id__in=[link.pk for link in self.links]).select_related('publication').order_by('-publication__created_at', '-id'):
            self.snapshots[snapshot.link_id].append(snapshot)

    def snapshot(self, link):
        snapshots = self.snapshots[link.pk]
        if link.requirement_id and link.requirement.review_status == 'approved':
            approved = self.approved_rounds.get(link.requirement_id)
            exact = next((snapshot for snapshot in snapshots if snapshot.publication_id == approved), None)
            if exact:
                return exact
        return snapshots[0] if snapshots else None

    def target_visible(self, link):
        if link.project.client_id != self.actor.pk:
            return False
        level = link.level
        if level == 'project':
            return True
        target = getattr(link, level)
        if level == 'contract':
            return target.client_visible
        if level == 'amendment':
            return target.client_visible and target.contract.client_visible
        stage = target if level == 'stage' else target.stage if level == 'requirement' else None
        phase = stage.phase if stage else target if level == 'phase' else None
        scope = phase.scope if phase else target
        if not scope.contract.client_visible or (scope.amendment_id and not scope.amendment.client_visible):
            return False
        if level == 'scope':
            return target.pk in self.published_scopes
        if level == 'phase':
            return target.pk in self.published_phases
        publication = self.latest.get(stage.pk)
        return publication is not None and (level == 'stage' or any(
            item['id'] == target.pk for item in publication.payload.get('requirements', [])
        ))

    def visible(self, link):
        if link.document.is_archived and self.snapshot(link) is None:
            return False
        if self.admin:
            return True
        for sibling in self.by_document[link.document_id]:
            if not self.target_visible(sibling):
                return False
            if sibling.level in ('scope', 'phase', 'stage', 'requirement') and self.snapshot(sibling) is None:
                return False
        return True


def list_documents(project_id, actor, level=None, target_id=None, *, index=None):
    project = project_for_actor(project_id, actor)
    index = index or DeliveryDocumentIndex(project, actor)
    if level is not None:
        from accounts.services.delivery_workflow import _target, _level_visible
        if target_id is None:
            fail('Indica el elemento al que pertenece el documento.')
        target = _target(project, level, target_id)
        if not _level_visible(project, actor, level, target):
            raise NotFound('Elemento no publicado.')
    links = [link for link in index.links if link.project_id == project.pk]
    if level is not None:
        links = [link for link in links if link.level == level and (level == 'project' or getattr(link, f'{level}_id') == target_id)]
    return {'documents': [_link_data(project, actor, link, index) for link in links if index.visible(link)]}


def document_options(project_id, actor):
    require_admin(actor)
    project = project_for_actor(project_id, actor)
    documents = Document.objects.filter(is_archived=False).filter(
        Q(project=project, client_user__isnull=True) | Q(project=project, client_user_id=project.client_id)
        | Q(project__isnull=True, client_user_id=project.client_id),
    ).exclude(document_type__code='collection_account').only('id', 'uuid', 'title', 'requires_signature')
    proposal_documents = ProposalDocument.objects.filter(
        Q(proposal__project_phases__project=project) | Q(proposal__deliverable__project=project),
    ).distinct()
    from accounts.services.delivery_contract_sources import approval_file_options
    return {'documents': [{'id': doc.pk, 'uuid': str(doc.uuid), 'title': doc.title, 'requires_signature': doc.requires_signature} for doc in documents],
            'proposal_documents': list(proposal_documents.values('id', 'title', 'document_type')),
            'approval_files': approval_file_options(project)}


def document_pdf(project_id, actor, link_id):
    project = project_for_actor(project_id, actor)
    index = DeliveryDocumentIndex(project, actor)
    link = next((link for link in index.links if link.pk == link_id and link.project_id == project.pk), None)
    if link is None or not index.visible(link):
        raise NotFound('Documento no disponible.')
    snapshot = index.snapshot(link)
    if snapshot:
        try:
            with snapshot.file.open('rb') as source:
                return source.read(), snapshot.title
        except (OSError, ValueError):
            fail('La evidencia publicada no está disponible.', 'pdf_unavailable')
    return _raw_pdf(link.document), link.document.title


def contract_pdf(project_id, actor, kind, node_id):
    from accounts.services.delivery_workflow import _node, _level_visible
    project = project_for_actor(project_id, actor)
    if kind not in ('contracts', 'amendments'):
        fail('Tipo de documento contractual desconocido.')
    node = _node(project, kind, node_id)
    if not _level_visible(project, actor, 'contract' if kind == 'contracts' else 'amendment', node):
        raise NotFound('Contrato no habilitado para el cliente.')
    if node.approval_file_id:
        from accounts.services.delivery_contract_sources import approval_contract_source
        source = approval_contract_source(node)
        if source['content_type'] != 'application/pdf':
            fail('Esta fuente conserva su formato original. Descarga su copia o registra el PDF firmado.', 'contract_source_not_pdf')
        return validated_pdf_bytes(io.BytesIO(source['raw'])), node.title
    evidence = node.signature_evidence.first()
    if evidence:
        try:
            with evidence.file.open('rb') as source:
                return source.read(), node.title
        except (OSError, ValueError):
            fail('El PDF firmado no está disponible.', 'pdf_unavailable')
    if node.document_id:
        return _raw_pdf(node.document), node.title
    try:
        with node.proposal_document.file.open('rb') as source:
            pdf = source.read(MAX_PDF_BYTES + 1)
    except (OSError, ValueError):
        fail('El PDF contractual no está disponible.', 'pdf_unavailable')
    if len(pdf) > MAX_PDF_BYTES:
        fail('El documento supera el límite de 10 MB.', 'pdf_too_large')
    return pdf, node.title


def capture_publication_documents(project, stage, publication):
    scope = stage.phase.scope
    filters = (Q(level='project') | Q(contract_id=scope.contract_id) | Q(scope_id=scope.pk)
               | Q(phase_id=stage.phase_id) | Q(stage_id=stage.pk) | Q(requirement__stage=stage))
    if scope.amendment_id:
        filters |= Q(amendment_id=scope.amendment_id)
    links = _links_qs(project).filter(filters)
    for link in links:
        if link.document.is_archived:
            fail('Un documento asociado está archivado. Revísalo antes de publicar.')
        # Previously approved guides keep the PDF from the approving round.
        previous = _snapshot_for_link(link) if link.level == 'requirement' and link.requirement.review_status == 'approved' else None
        if previous:
            with previous.file.open('rb') as source:
                pdf = source.read()
            title = previous.title
        else:
            pdf = _raw_pdf(link.document)
            title = link.document.title
        snapshot = DeliveryDocumentSnapshot(publication=publication, link=link, title=title,
                                            sha256=hashlib.sha256(pdf).hexdigest())
        store_private_pdf(snapshot, pdf, 'document.pdf')
        snapshot.save()


def share_message_documents(project, actor, level, target, documents):
    """A public reply may attach evidence without changing the approved guide."""
    from accounts.services.delivery_workflow import _level_visible
    if not _level_visible(project, actor, level, target):
        return
    for doc in documents:
        fields = {'project': project, 'level': level, 'document': doc}
        if level != 'project':
            fields[level] = target
        link, _ = DeliveryDocumentLink.objects.get_or_create(**fields, defaults={'created_by': actor})
        stage = target if level == 'stage' else target.stage if level == 'requirement' else None
        if stage:
            publication = stage.publications.first()
            if publication:
                snapshot, created = DeliveryDocumentSnapshot.objects.get_or_create(
                    publication=publication, link=link,
                    defaults={'title': doc.title, 'sha256': ''},
                )
                if created:
                    pdf = _raw_pdf(doc)
                    snapshot.sha256 = hashlib.sha256(pdf).hexdigest()
                    store_private_pdf(snapshot, pdf, 'reply.pdf')
                    snapshot.save()


def visible_message_documents(project, actor, message, *, index=None):
    index = index or DeliveryDocumentIndex(project, actor)
    result = []
    for doc in message.documents.all():
        link = next((link for link in index.by_document[doc.pk] if link.project_id == project.pk and link.level == message.level and (message.level == 'project' or getattr(link, f'{message.level}_id') == message.target_id)), None)
        if link and index.visible(link):
            result.append(_link_data(project, actor, link, index))
        elif is_admin(actor):
            result.append({'document_id': doc.pk, 'title': doc.title, 'uuid': str(doc.uuid)})
    return result


def document_is_visible(actor, doc):
    """Guard every legacy portal route, including source documents flagged visible."""
    if is_admin(actor):
        return not doc.is_archived
    return PortalDocumentIndex(actor, [doc]).visible(doc)


class PortalDocumentIndex:
    """Bulk authorization and immutable titles for the global client portal."""

    def __init__(self, actor, documents):
        self.actor = actor
        ids = [doc.pk for doc in documents]
        self.index = DeliveryDocumentIndex(None, actor, document_ids=ids)
        self.contractual_ids = set(ProjectContract.objects.filter(
            document_id__in=ids, project__client=actor, client_visible=True,
        ).values_list('document_id', flat=True))
        self.contractual_ids.update(ContractAmendment.objects.filter(
            document_id__in=ids, contract__project__client=actor,
            contract__client_visible=True, client_visible=True,
        ).values_list('document_id', flat=True))
        self.signatures = {}
        signatures = ContractSignatureEvidence.objects.filter(
            Q(contract__document_id__in=ids, contract__project__client=actor, contract__client_visible=True)
            | Q(amendment__document_id__in=ids, amendment__contract__project__client=actor, amendment__client_visible=True, amendment__contract__client_visible=True),
        ).select_related('contract', 'amendment').order_by('-created_at', '-id')
        for signature in signatures:
            source_id = signature.contract.document_id if signature.contract_id else signature.amendment.document_id
            self.signatures.setdefault(source_id, signature)

    def visible(self, doc):
        actor = self.actor
        owner = (doc.client_user_id in (None, actor.pk) and (
            (doc.project_id and doc.project.client_id == actor.pk) or (doc.project_id is None and doc.client_user_id == actor.pk)
        ))
        if not owner:
            return False
        if doc.pk in self.contractual_ids:
            return not doc.is_archived or doc.pk in self.signatures
        links = self.index.by_document[doc.pk]
        if links:
            return all(self.index.visible(link) for link in links)
        return doc.is_client_visible and not doc.is_archived

    def snapshot(self, doc):
        signature = self.signatures.get(doc.pk)
        if signature:
            return signature
        snapshots = [self.index.snapshot(link) for link in self.index.by_document[doc.pk] if self.index.visible(link)]
        return max((snapshot for snapshot in snapshots if snapshot), key=lambda snapshot: snapshot.pk, default=None)


def snapshot_for_document(actor, doc):
    """Serve captured title and PDF through the global portal as well."""
    if is_admin(actor):
        return None
    return PortalDocumentIndex(actor, [doc]).snapshot(doc)


def document_can_be_shared(project, doc):
    """Public replies cannot release a source attached to another private guide."""
    index = DeliveryDocumentIndex(project, project.client, document_ids=[doc.pk])
    return all(index.visible(link) for link in index.links)


def ensure_portal_signature_capture(node, actor):
    """Capture older verified portal facts once at an authorized write boundary."""
    if node.signature_evidence.exists() or not node.document_id:
        return
    doc = node.document
    project = node.project
    if not (doc.requires_signature and doc.signed_at and doc.signed_by_id == project.client_id):
        return
    pdf = _raw_pdf(doc)
    content = {'document_id': doc.pk, 'uuid': str(doc.uuid), 'title': doc.title,
               'markdown': doc.content_markdown, 'json': doc.content_json, 'language': doc.language,
               'signed_by_id': doc.signed_by_id, 'signed_at': doc.signed_at.isoformat(),
               'signature_name': doc.signature_name, 'signature_ip': doc.signature_ip,
               'signature_user_agent': doc.signature_user_agent}
    import json
    evidence = ContractSignatureEvidence(
        **{'contract' if isinstance(node, ProjectContract) else 'amendment': node},
        method='portal', signer_name=doc.signature_name or project.client.get_full_name() or project.client.email,
        signed_at=doc.signed_at, attestation='Firma del cliente registrada en Platform.',
        attested_by=actor, source_snapshot=content,
        source_sha256=hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
        sha256=hashlib.sha256(pdf).hexdigest(),
    )
    store_private_pdf(evidence, pdf, 'portal-signed.pdf')
    evidence.save()
    DeliveryDocumentLink.objects.get_or_create(
        project=project, document=doc, level='contract' if isinstance(node, ProjectContract) else 'amendment',
        **{'contract' if isinstance(node, ProjectContract) else 'amendment': node}, defaults={'created_by': actor},
    )


def capture_document_portal_signatures(doc, actor):
    """Called in the document signing transaction after verifying exact ownership."""
    for contract in ProjectContract.objects.select_for_update().filter(document=doc, project__client=actor):
        ensure_portal_signature_capture(contract, actor)
    for amendment in ContractAmendment.objects.select_for_update().filter(document=doc, contract__project__client=actor):
        ensure_portal_signature_capture(amendment, actor)
