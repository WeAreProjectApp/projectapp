"""Compatibility helpers for confirmed platform packages and safe empty teardown.

Commercial acceptance never creates clients/projects. New bindings are reviewed
through the shared proposal approval service; legacy tasks require that manifest.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Deliverable, Project, UserProfile
from accounts.services.technical_resources_sync import (
    sync_technical_resources_for_deliverable,
)

logger = logging.getLogger(__name__)

User = get_user_model()

Source = Literal['client_response', 'admin_panel']


def _acting_user_for_sync(acting_user):
    if acting_user is not None and getattr(acting_user, 'is_authenticated', False):
        return acting_user
    return User.objects.filter(is_staff=True, is_active=True).order_by('id').first()


def _find_client_user_by_email(email: str):
    if not (email or '').strip():
        return None
    return User.objects.filter(email__iexact=email.strip()).select_related('profile').first()


def ensure_deliverable_for_accepted_proposal(
    proposal,
    acting_user,
) -> Deliverable | None:
    """Existing association only: neither acceptance nor old tasks create projects."""
    return proposal.deliverable if proposal.deliverable_id else None


class PlatformRelaunchConflict(ValidationError):
    status_code = 409


@transaction.atomic
def teardown_platform_for_proposal(proposal, *, acting_user=None) -> None:
    """Retire only an empty onboarding graph, preserving all business data."""
    if not proposal.deliverable_id:
        return
    from content.services.project_deletion_service import (
        ProjectDeleteBlocked, delete_empty_project, ensure_unused_onboarding_project,
    )

    deliverable_id = proposal.deliverable_id
    project_id = Deliverable.objects.get(pk=deliverable_id).project_id
    project = Project.objects.select_for_update().get(pk=project_id)
    locked_proposal = type(proposal).objects.select_for_update().get(pk=proposal.pk)
    if locked_proposal.deliverable_id != deliverable_id:
        raise PlatformRelaunchConflict({
            'detail': 'La vinculación de la propuesta cambió. Actualiza la página antes de continuar.',
        })
    deliverable = Deliverable.objects.select_for_update().get(
        pk=deliverable_id, project=project,
    )
    try:
        ensure_unused_onboarding_project(
            project, proposal=locked_proposal, deliverable=deliverable,
        )
        actor = acting_user or deliverable.uploaded_by
        locked_proposal.deliverable = None
        locked_proposal.platform_onboarding_completed_at = None
        locked_proposal.save(update_fields=['deliverable_id', 'platform_onboarding_completed_at'])
        deliverable.delete()
        delete_empty_project(project.pk, actor=actor)
    except ProjectDeleteBlocked as exc:
        raise PlatformRelaunchConflict({
            'detail': 'Este proyecto tiene información relacionada. Gestiona la entrega desde Platform sin reiniciar el proyecto.',
            'code': 'project_delete_blocked',
            'blockers': exc.preview['blockers'],
        }) from exc


def handle_proposal_accepted_for_platform(
    proposal,
    *,
    source: Source = 'client_response',
    acting_user=None,
    send_email: bool = True,
) -> dict[str, Any]:
    """Synchronize only an explicitly confirmed frozen package; never send mail."""
    if not proposal.deliverable_id or not proposal.platform_approval_manifest:
        return {'skipped': True, 'reason': 'review_required'}
    from content.services.proposal_approval_service import _sync
    actor = _acting_user_for_sync(acting_user)
    if actor is None:
        raise ValidationError('No hay un administrador disponible para sincronizar.')
    _sync(proposal, actor)
    return {'skipped': False, 'deliverable_id': proposal.deliverable_id}


def _ensure_project_stages(proposal) -> None:
    """
    Create empty `ProposalProjectStage` rows for the proposal if missing,
    so the Cronograma admin tab has rows to populate. Delegates to
    `ProposalStageTracker.ensure_stages` for the canonical stage catalog.
    """
    from content.services.proposal_stage_tracker import ProposalStageTracker

    try:
        ProposalStageTracker.ensure_stages(proposal)
    except Exception:
        logger.exception(
            'Failed to ensure project stages for proposal %s', proposal.pk,
        )


def _sync_proposal_documents_to_deliverable(proposal, deliverable, acting_user):
    """
    Copy ProposalDocument files and generated PDFs to the deliverable.
    Maps document types to Deliverable categories.
    """
    from accounts.models import Deliverable, DeliverableFile
    from content.models import ProposalDocument
    from content.services.contract_variants import active_doc_types
    from content.services.pdf_utils import safe_pdf_filename
    from django.core.files.base import ContentFile

    TYPE_TO_CATEGORY = {
        ProposalDocument.DOC_TYPE_CONTRACT: Deliverable.CATEGORY_CONTRACT,
        ProposalDocument.DOC_TYPE_CONTRACT_PRODUCT: Deliverable.CATEGORY_CONTRACT,
        ProposalDocument.DOC_TYPE_CONTRACT_SERVICE: Deliverable.CATEGORY_CONTRACT,
        ProposalDocument.DOC_TYPE_AMENDMENT: Deliverable.CATEGORY_AMENDMENT,
        ProposalDocument.DOC_TYPE_LEGAL_ANNEX: Deliverable.CATEGORY_LEGAL_ANNEX,
        ProposalDocument.DOC_TYPE_CLIENT_DOCUMENT: Deliverable.CATEGORY_OTHER,
        ProposalDocument.DOC_TYPE_OTHER: Deliverable.CATEGORY_OTHER,
    }
    # Only the contracts of the chosen closing modality belong to the project;
    # the other modality's documents are kept on the proposal but not current.
    inactive_contracts = ProposalDocument.CONTRACT_DOC_TYPES - active_doc_types(proposal)

    # 1. Sync existing proposal documents (contract PDF, uploaded files)
    for doc in proposal.proposal_documents.all():
        if doc.document_type in inactive_contracts:
            continue
        if doc.file:
            DeliverableFile.objects.create(
                deliverable=deliverable,
                file=doc.file,
                title=doc.title,
                category=TYPE_TO_CATEGORY.get(doc.document_type, Deliverable.CATEGORY_OTHER),
                uploaded_by=acting_user,
            )

    # 2. Generate and attach commercial proposal PDF
    date_str = (proposal.created_at or timezone.now()).strftime('%Y-%m-%d')
    try:
        from content.services.proposal_pdf_service import ProposalPdfService
        commercial_bytes = ProposalPdfService.generate(proposal)
        if commercial_bytes:
            filename = safe_pdf_filename(
                'Propuesta_Comercial',
                proposal.title or proposal.client_name,
                date_str,
            )
            df = DeliverableFile.objects.create(
                deliverable=deliverable,
                title=f'Propuesta comercial — {proposal.title or proposal.client_name}',
                category=Deliverable.CATEGORY_DOCUMENTS,
                uploaded_by=acting_user,
            )
            df.file.save(filename, ContentFile(commercial_bytes), save=True)
    except Exception:
        logger.exception('Failed to generate commercial PDF for deliverable sync')

    # 3. Generate and attach technical detail PDF
    try:
        from content.services.technical_document_pdf import generate_technical_document_pdf
        technical_bytes = generate_technical_document_pdf(proposal)
        if technical_bytes:
            filename = safe_pdf_filename(
                'Detalle_Tecnico',
                proposal.title or proposal.client_name,
                date_str,
            )
            df = DeliverableFile.objects.create(
                deliverable=deliverable,
                title=f'Detalle técnico — {proposal.title or proposal.client_name}',
                category=Deliverable.CATEGORY_DOCUMENTS,
                uploaded_by=acting_user,
            )
            df.file.save(filename, ContentFile(technical_bytes), save=True)
    except Exception:
        logger.exception('Failed to generate technical PDF for deliverable sync')
