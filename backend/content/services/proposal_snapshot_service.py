"""Persist immutable proposal PDFs before the corresponding email is sent."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

from content.models import (
    BusinessProposal,
    Document,
    DocumentState,
    DocumentStateEpisode,
    DocumentStateGroup,
)
from content.services.document_state_service import ensure_initial_state, open_state
from content.services.entity_history import historical_write
from content.services.document_type_utils import (
    get_commercial_proposal_document_type,
)
from content.services.generated_document_filing_service import (
    file_proposal_snapshot,
    proposal_snapshot_title,
)
from content.utils import safe_slug, today_bogota

logger = logging.getLogger(__name__)


class ProposalSnapshotError(ValueError):
    """A proposal version could not be generated or stored safely."""


@dataclass(frozen=True)
class PreparedProposalSnapshot:
    proposal_id: int
    document: Document
    pdf_bytes: bytes
    attachment_name: str


def _proposal_project(proposal):
    deliverable = getattr(proposal, 'deliverable', None)
    return getattr(deliverable, 'project', None) if deliverable else None


def _proposal_client_user(proposal):
    profile = getattr(proposal, 'client', None)
    return getattr(profile, 'user', None) if profile else None


def _next_version(proposal):
    latest = (
        Document.objects.filter(source_proposal=proposal)
        .aggregate(value=Max('source_version'))['value']
        or 0
    )
    return latest + 1


def _delete_stored_files(files):
    for storage, name in files:
        try:
            storage.delete(name)
        except Exception:
            logger.exception('Could not remove rolled-back proposal snapshot %s', name)


@historical_write
def prepare_proposal_snapshots(proposals, *, acting_user=None):
    """Generate and store one new version per proposal.

    All PDFs are generated before the first ``Document`` row or file is
    written.  Proposal rows are locked in a stable order so concurrent sends
    allocate distinct monotonically increasing versions.
    """
    proposal_ids = [proposal.pk for proposal in proposals]
    if not proposal_ids or any(proposal_id is None for proposal_id in proposal_ids):
        raise ProposalSnapshotError('No hay propuestas válidas para archivar.')
    if len(set(proposal_ids)) != len(proposal_ids):
        raise ProposalSnapshotError('Una propuesta no puede repetirse en el mismo envío.')

    stored_files = []
    try:
        with transaction.atomic():
            locked = {
                proposal.pk: proposal
                for proposal in (
                    BusinessProposal.objects.select_for_update()
                    .select_related('client__user', 'deliverable__project__client')
                    .prefetch_related('sections')
                    .filter(pk__in=sorted(proposal_ids))
                    .order_by('pk')
                )
            }
            if len(locked) != len(proposal_ids):
                raise ProposalSnapshotError('Una de las propuestas ya no existe.')

            from content.services.proposal_pdf_service import ProposalPdfService

            generated = {}
            for proposal_id in proposal_ids:
                proposal = locked[proposal_id]
                try:
                    from content.services.requirement_package_service import freeze_proposal_packages
                    freeze_proposal_packages(proposal)
                    pdf_bytes = ProposalPdfService.generate(proposal)
                except Exception as exc:
                    logger.exception(
                        'Commercial PDF generation failed for proposal %s',
                        proposal.uuid,
                    )
                    raise ProposalSnapshotError(
                        f'No se pudo generar el PDF de «{proposal.title}». '
                        'No se envió ninguna propuesta.',
                    ) from exc
                if not pdf_bytes:
                    raise ProposalSnapshotError(
                        f'El PDF de «{proposal.title}» quedó vacío. '
                        'No se envió ninguna propuesta.',
                    )
                generated[proposal_id] = bytes(pdf_bytes)

            document_type = get_commercial_proposal_document_type()
            business_date = today_bogota()
            prepared = []
            for proposal_id in proposal_ids:
                proposal = locked[proposal_id]
                pdf_bytes = generated[proposal_id]
                version = _next_version(proposal)
                project = _proposal_project(proposal)
                client_user = _proposal_client_user(proposal)
                from content.services.entity_history_registry import snapshot_entity
                history_snapshot, _, _ = snapshot_entity('proposal', proposal.pk)
                document = Document.objects.create(
                    document_type=document_type,
                    source_proposal=proposal,
                    source_version=version,
                    issue_date=business_date,
                    title=proposal_snapshot_title(proposal, business_date, version),
                    project=project,
                    client_user=client_user,
                    client_name=proposal.client_name or '',
                    language=proposal.language,
                    status=Document.Status.DRAFT,
                    metadata={
                        'generated_source': 'commercial_proposal_email',
                        'proposal_id': proposal.pk,
                        'source_version': version,
                        'sha256': hashlib.sha256(pdf_bytes).hexdigest(),
                        'delivery': {'status': 'pending'},
                    },
                    created_by=acting_user,
                    updated_by=acting_user,
                )
                from content.models.entity_history import EntityHistory, EntityRevision
                history_head, _ = EntityHistory.objects.get_or_create(entity_type='proposal', object_id=proposal.pk)
                attachment_name = (
                    f'Propuesta_Comercial_'
                    f'{safe_slug(proposal.client_name, "Cliente")}_v{version:02d}.pdf'
                )
                try:
                    document.generated_file.save(
                        attachment_name,
                        ContentFile(pdf_bytes),
                        save=True,
                    )
                except Exception as exc:
                    raise ProposalSnapshotError(
                        f'No se pudo guardar el PDF de «{proposal.title}». '
                        'No se envió ninguna propuesta.',
                    ) from exc
                stored_files.append((
                    document.generated_file.storage,
                    document.generated_file.name,
                ))
                history_snapshot['archived_pdf'] = document.generated_file.name
                EntityRevision.objects.create(history=history_head, snapshot=history_snapshot,
                    action='prepared_version', source='proposal_email', source_key=f'proposal_prepared:{document.pk}')
                file_proposal_snapshot(document)
                ensure_initial_state(document, actor=acting_user)
                prepared.append(PreparedProposalSnapshot(
                    proposal_id=proposal.pk,
                    document=document,
                    pdf_bytes=pdf_bytes,
                    attachment_name=attachment_name,
                ))
            return prepared
    except Exception:
        _delete_stored_files(stored_files)
        raise


def _state_for(system_key):
    return DocumentState.objects.filter(
        catalog=DocumentStateGroup.Catalog.DOCUMENTS,
        system_key=system_key,
        is_active=True,
    ).first()


@historical_write
@transaction.atomic
def finalize_proposal_snapshots(prepared, delivery, *, acting_user=None):
    """Reflect the email outcome without rewriting the stored PDF."""
    success = bool(delivery.get('ok'))
    target_key = 'sent' if success else 'needs_fix'
    state = _state_for(target_key)
    for snapshot in prepared:
        document = snapshot.document
        metadata = dict(document.metadata or {})
        metadata['delivery'] = {
            'status': 'sent' if success else 'failed',
            'reason': str(delivery.get('reason') or ''),
            'detail': str(delivery.get('detail') or ''),
        }
        document.metadata = metadata
        document.updated_by = acting_user
        document.save(update_fields=['metadata', 'updated_by', 'updated_at'])
        from content.models.entity_history import EntityRevision
        prepared_history = EntityRevision.objects.filter(source_key=f'proposal_prepared:{document.pk}').first()
        if success and prepared_history:
            from content.models.entity_history import EntityHistory, EntityRevision
            from content.services.entity_history import append_revision
            head, _ = EntityHistory.objects.get_or_create(entity_type='proposal', object_id=snapshot.proposal_id)
            head = EntityHistory.objects.select_for_update().get(pk=head.pk)
            evidence_key = f'proposal_pdf:{document.pk}'
            if not EntityRevision.objects.filter(source_key=evidence_key).exists():
                head.object_label = prepared_history.snapshot.get('title', document.title)
                append_revision(head, snapshot=prepared_history.snapshot, secrets={},
                    action='sent_version', changes=[], evidence=[evidence_key], source_key=evidence_key,
                    identity={'actor_id_snapshot': getattr(acting_user, 'pk', None),
                              'actor_label': (acting_user.get_full_name() or acting_user.username) if acting_user else 'Sistema',
                              'source': 'proposal_email'})
        if state is not None:
            open_state(
                document,
                state,
                actor=acting_user,
                origin=DocumentStateEpisode.Origin.EMAIL,
                idempotent=True,
            )
