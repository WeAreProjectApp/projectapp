"""
When a BusinessProposal becomes accepted (client response or admin panel), provision
platform resources if needed, sync resources from technical_document, and send welcome email (via ProposalEmailService).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

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
    """
    Return deliverable linked to proposal, creating project/deliverable if needed.
    """
    if proposal.deliverable_id:
        return proposal.deliverable

    email = (proposal.client_email or '').strip()
    user = _find_client_user_by_email(email)

    if not user and getattr(settings, 'AUTO_PROVISION_CLIENT_FROM_PROPOSAL', False) and email:
        from accounts.services.onboarding import create_client

        raw = (proposal.client_name or 'Cliente').strip()
        parts = raw.split(None, 1)
        first = parts[0] if parts else 'Cliente'
        last = parts[1] if len(parts) > 1 else ''
        try:
            user, _temp_pw = create_client(
                email=email,
                first_name=first[:150],
                last_name=last[:150],
                company_name='',
            )
        except ValueError:
            logger.warning('Could not auto-provision client for proposal %s (duplicate email).', proposal.pk)
            user = _find_client_user_by_email(email)

    if not user:
        logger.info(
            'Proposal %s accepted without platform deliverable: no client user for email %s',
            proposal.pk, email or '(empty)',
        )
        return None

    profile = getattr(user, 'profile', None)
    if not profile or profile.role != UserProfile.ROLE_CLIENT:
        logger.info('Proposal %s: user %s is not a platform client; skipping auto project.', proposal.pk, user.pk)
        return None

    from accounts.views import _extract_proposal_financial_data

    payment_milestones, hosting_tiers = _extract_proposal_financial_data(proposal)

    uploader = acting_user if acting_user and getattr(acting_user, 'is_authenticated', False) else user

    project = Project.objects.create(
        name=(proposal.title or 'Nuevo proyecto')[:200],
        description='',
        client=user,
        payment_milestones=payment_milestones,
        hosting_tiers=hosting_tiers,
    )
    d = Deliverable.objects.create(
        project=project,
        category=Deliverable.CATEGORY_DOCUMENTS,
        title=(proposal.title or 'Propuesta comercial')[:300],
        description='',
        file=None,
        uploaded_by=uploader,
    )
    proposal.deliverable = d
    proposal.save(update_fields=['deliverable_id'])
    return d


def teardown_platform_for_proposal(proposal) -> None:
    """Retire an unused onboarding graph; contractual delivery evidence is retained."""
    if not proposal.deliverable_id:
        return
    deliverable = proposal.deliverable
    project = deliverable.project
    if project.delivery_contracts.exists():
        from rest_framework.exceptions import ValidationError
        raise ValidationError({
            'detail': 'Este proyecto tiene seguimiento contractual. Gestiona la nueva entrega desde Platform sin reiniciar el proyecto.',
        })
    proposal.deliverable = None
    proposal.platform_onboarding_completed_at = None
    proposal.save(update_fields=['deliverable_id', 'platform_onboarding_completed_at'])
    project.delete()


def handle_proposal_accepted_for_platform(
    proposal,
    *,
    source: Source = 'client_response',
    acting_user=None,
    send_email: bool = True,
) -> dict[str, Any]:
    """
    Idempotent: skips if platform_onboarding_completed_at is set.
    Ensures deliverable (optional), runs technical sync, sends acceptance email with PDFs.
    """
    _ = source  # reserved for logging / future policy

    if proposal.platform_onboarding_completed_at:
        return {'skipped': True, 'reason': 'already_completed'}

    d = ensure_deliverable_for_accepted_proposal(proposal, acting_user)
    proposal.refresh_from_db(fields=['deliverable_id'])
    sync_result: dict[str, Any] = {'ok': True, 'detail': 'no_deliverable_skip_sync'}

    actor = _acting_user_for_sync(acting_user)
    if d:
        from content.services.generated_document_filing_service import (
            move_proposal_snapshots_to_project,
        )

        move_proposal_snapshots_to_project(
            proposal,
            d.project,
            acting_user=actor,
        )
    if d and actor:
        sync_result = sync_technical_resources_for_deliverable(d, actor)
        if not sync_result.get('ok'):
            logger.warning(
                'Technical sync after acceptance failed for proposal %s: %s',
                proposal.pk, sync_result.get('detail'),
            )

    # Sync proposal documents (contract, uploaded annexes) to deliverable
    if d and actor:
        _sync_proposal_documents_to_deliverable(proposal, d, actor)

    if send_email:
        from content.services.proposal_email_service import ProposalEmailService

        ProposalEmailService.send_acceptance_confirmation(proposal)

    _ensure_project_stages(proposal)

    proposal.platform_onboarding_completed_at = timezone.now()
    proposal.save(update_fields=['platform_onboarding_completed_at'])

    return {
        'skipped': False,
        'deliverable_id': d.id if d else None,
        'sync': sync_result,
    }


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
