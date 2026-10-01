"""Shared helpers for seed/demo management commands.

The leading underscore keeps Django's command loader from treating this as a
runnable management command.
"""

from django.db import models

from accounts.models import ProjectPhase


def ensure_phase(project):
    """Return a ProjectPhase for the project, creating one if needed.

    This is the commercial proposal/hosting phase, separate from delivery
    reviews. Reuse a proposal tied to the client, or create a placeholder.
    """
    phase = ProjectPhase.objects.filter(project=project).order_by('order').first()
    if phase:
        return phase

    from content.models import BusinessProposal

    client = project.client
    proposal = None
    if client is not None:
        proposal = (
            BusinessProposal.objects.filter(client_email__iexact=client.email)
            .order_by('id').first()
        )
    proposal = proposal or BusinessProposal.objects.order_by('id').first()
    if proposal is None:
        proposal = BusinessProposal.objects.create(
            title=f'Proyecto {project.name}',
            client_name=getattr(client, 'get_full_name', lambda: '')() or project.name,
            client_email=getattr(client, 'email', '') or '',
        )
    return ProjectPhase.objects.create(project=project, business_proposal=proposal, order=0)


def ensure_delivery_stage(project, *, context, actor=None):
    """Create a fake signed contract and independently authored delivery stages."""
    from django.contrib.auth import get_user_model
    from django.core.files.base import ContentFile
    from accounts.models import (
        ContractAmendment, ContractSignatureEvidence, DeliveryPhase,
        DeliveryScope, DeliveryStage, DeliveryWorkspace, ProjectContract,
    )
    from content.fake_data import ensure_fake_data_allowed
    from content.models import Document
    import hashlib

    ensure_fake_data_allowed('delivery_seed_helpers')
    anchor_now = context.anchor_now
    document_key = f'delivery:{project.client.email}:{project.name}:demo-contract'
    actor = actor or get_user_model().objects.filter(profile__role='admin').first() or project.client
    contract = ProjectContract.objects.filter(project=project, key='demo-contract').first()
    if contract is None:
        document = Document.objects.create(
            uuid=context.uuid(document_key),
            title=f'[Seed] Contrato — {project.name}'[:255], project=project,
            client_user=project.client, created_by=actor,
            is_client_visible=True, requires_signature=True,
            signed_by=project.client, signed_at=anchor_now,
            signature_name=project.client.get_full_name() or project.client.email,
            content_markdown='# Contrato de demostración\n\nDocumento ficticio para pruebas.',
        )
        document.generated_file.save('demo-contract.pdf', ContentFile(_demo_pdf(document.title)), save=True)
        contract = ProjectContract.objects.create(
            project=project, key='demo-contract', title='Contrato inicial de demostración',
            document=document, client_visible=True,
        )
    amendment = ContractAmendment.objects.filter(contract=contract, key='demo-amendment').first()
    if amendment is None:
        document = Document.objects.create(
            uuid=context.uuid(f'{document_key}:demo-amendment'),
            title=f'[Seed] Otrosí — {project.name}'[:255], project=project,
            client_user=project.client, created_by=actor, is_client_visible=True,
            content_markdown='# Otrosí de demostración\n\nAmpliación ficticia para pruebas.',
        )
        payload = _demo_pdf(document.title)
        document.generated_file.save('demo-amendment.pdf', ContentFile(payload), save=True)
        amendment = ContractAmendment.objects.create(
            contract=contract, key='demo-amendment', title='Otrosí de demostración',
            document=document, client_visible=True,
        )
        evidence = ContractSignatureEvidence.objects.create(
            amendment=amendment, sha256=hashlib.sha256(payload).hexdigest(),
            signer_name=project.client.get_full_name() or project.client.email,
            signed_at=anchor_now, attestation='Evidencia externa ficticia, exclusiva del ambiente de prueba.',
            attested_by=actor,
        )
        evidence.file.save('demo-signed-amendment.pdf', ContentFile(payload), save=True)
    original, _ = DeliveryScope.objects.get_or_create(
        contract=contract, key='demo-original', defaults={
            'title': 'Alcance inicial', 'is_current': False,
            'description': 'Alcance anterior, conservado como referencia contractual.',
        },
    )
    scope, _ = DeliveryScope.objects.get_or_create(
        contract=contract, key='demo-current', defaults={
            'title': 'Alcance vigente', 'amendment': amendment,
            'description': 'Alcance autorizado por el contrato y su otrosí.',
        },
    )
    commercial_phase = ensure_phase(project)
    phase, _ = DeliveryPhase.objects.get_or_create(
        scope=scope, key='demo-validation', defaults={
            'title': 'Fase 1: validación del producto', 'order': 0,
            'commercial_phase': commercial_phase,
        },
    )
    draft_phase, _ = DeliveryPhase.objects.get_or_create(
        scope=scope, key='demo-next', defaults={
            'title': 'Fase 2: siguiente entrega', 'order': 1,
            'commercial_phase': commercial_phase,
        },
    )
    stage, _ = DeliveryStage.objects.get_or_create(
        phase=phase, key='demo-review', defaults={'title': 'Etapa 1: revisión del cliente'},
    )
    DeliveryStage.objects.get_or_create(
        phase=draft_phase, key='demo-draft', defaults={'title': 'Etapa 2: preparación interna'},
    )
    DeliveryWorkspace.objects.get_or_create(project=project)
    return stage


def _demo_pdf(title):
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    stream = BytesIO()
    canvas = Canvas(stream, invariant=1)
    canvas.drawString(40, 780, title[:100])
    canvas.drawString(40, 750, 'Documento ficticio para pruebas. Sin validez contractual.')
    canvas.save()
    return stream.getvalue()


def seed_validation_guides(project, specs, *, context, actor=None):
    """Seed partial reviews and draft guides without inferring real approvals."""
    from accounts.models import DeliveryMessage, DeliveryStage, Requirement, RequirementReview

    anchor_now = context.anchor_now
    stage = ensure_delivery_stage(project, context=context, actor=actor)
    draft_stage = DeliveryStage.objects.get(
        phase__scope=stage.phase.scope, key='demo-draft',
    )
    for index, spec in enumerate(specs):
        target = draft_stage if spec.get('draft') else stage
        Requirement.objects.get_or_create(
            stage=target, key=spec.get('key', f'demo-{index + 1:03d}'), defaults={
                'title': spec['title'], 'description': spec.get('description', ''),
                'order': index,
                'guide': {
                    'role': spec.get('role', 'Cliente responsable de validar.'),
                    'environment': 'Ambiente de pruebas con datos ficticios.',
                    'preparation': 'Entrar con una cuenta de prueba del rol indicado.',
                    'data': 'Utilizar registros de demostración; no usar información real.',
                    'steps': spec.get('steps', ['Abrir la vista y ejecutar la acción descrita.']),
                    'expected_result': spec.get('expected_result', 'La acción descrita termina y muestra el resultado esperado.'),
                    'failure_signals': 'Si aparece un error o falta el resultado, reportar el paso y una captura.',
                },
                'review_status': 'pending' if spec.get('draft') else spec.get('review_status', 'in_review'),
            },
        )
    refresh_seed_publication(stage, actor=actor)
    publication = stage.publications.first()
    for requirement in stage.requirements.exclude(review_status__in=['pending', 'in_review']):
        RequirementReview.objects.get_or_create(
            publication=publication, requirement=requirement, defaults={
                'actor': project.client, 'requirement_version': requirement.version,
                'content_snapshot': _guide_snapshot(requirement),
                'decision': requirement.review_status,
                'message': '[Seed] Respuesta ficticia del cliente para probar conformidades parciales.',
                'environment': 'Ambiente de pruebas',
                'original_reviewer': project.client.get_full_name() or project.client.email,
                'reviewed_at': anchor_now,
            },
        )
    message, _ = DeliveryMessage.objects.get_or_create(
        project=project, level='stage', target_id=stage.pk,
        message='[Seed] Reporte de revisión parcial: lo aprobado conserva su conformidad.',
        defaults={'actor': project.client},
    )
    message.requirements.set(stage.requirements.exclude(review_status='in_review'))
    _seed_stage_document(stage, context=context, actor=actor)
    _seed_stage_document(draft_stage, context=context, actor=actor)
    refresh_seed_publication(stage, actor=actor)
    return stage


def _guide_snapshot(requirement):
    return {name: getattr(requirement, name) for name in (
        'id', 'key', 'title', 'description', 'guide', 'version', 'review_status',
    )}


def refresh_seed_publication(stage, *, actor=None):
    """Only fake-data commands may rebuild their synthetic publication fixture."""
    from accounts.models import DeliveryPublication, DeliveryStage
    from content.fake_data import ensure_fake_data_allowed

    ensure_fake_data_allowed('delivery_seed_helpers')
    actor = actor or stage.project.client
    DeliveryPublication.objects.update_or_create(
        stage=stage, round=1, defaults={
            'published_by': actor,
            'payload': {
                'id': stage.pk, 'key': stage.key, 'title': stage.title, 'version': stage.version,
                'requirements': [_guide_snapshot(req) for req in stage.requirements.all()],
            },
        },
    )
    stage.editorial_status = DeliveryStage.EditorialStatus.PUBLISHED
    stage.save(update_fields=['editorial_status', 'updated_at'])
    from accounts.models import DeliveryDocumentSnapshot
    from django.core.files.base import ContentFile
    import hashlib

    publication = stage.publications.get(round=1)
    for link in stage.document_links.select_related('document'):
        if not DeliveryDocumentSnapshot.objects.filter(publication=publication, link=link).exists():
            payload = _demo_pdf(link.document.title)
            snapshot = DeliveryDocumentSnapshot.objects.create(
                publication=publication, link=link, title=link.document.title,
                sha256=hashlib.sha256(payload).hexdigest(),
            )
            snapshot.file.save('demo-review-guide.pdf', ContentFile(payload), save=True)


def _seed_stage_document(stage, *, context, actor=None):
    from accounts.models import DeliveryDocumentLink
    from content.models import Document
    from django.core.files.base import ContentFile

    if stage.document_links.exists():
        return
    project = stage.project
    scope = stage.phase.scope
    document_key = (
        f'delivery:{project.client.email}:{project.name}:{scope.contract.key}:'
        f'{scope.key}:{stage.phase.key}:{stage.key}:guide'
    )
    actor = actor or project.client
    document = Document.objects.create(
        uuid=context.uuid(document_key),
        title=f'[Seed] Guía — {project.name} — {stage.title}'[:255],
        project=project, client_user=project.client, created_by=actor,
        # Delivery publication is authoritative even when this old flag is true.
        is_client_visible=True,
        content_markdown='# Guía de validación\n\nUsar datos ficticios en el ambiente de pruebas.',
    )
    document.generated_file.save('demo-guide.pdf', ContentFile(_demo_pdf(document.title)), save=True)
    DeliveryDocumentLink.objects.create(
        project=project, document=document, level='stage', stage=stage, created_by=actor,
    )


def clear_fake_delivery(projects):
    """Dissolve protected review evidence only during an authorized fake reset."""
    from accounts.models import DeliveryPromptContext, DeliveryPromptSource
    from content.fake_data import ensure_fake_data_allowed
    from django.core.management.base import CommandError
    from django.db import transaction
    from django.db.models.deletion import ProtectedError

    ensure_fake_data_allowed('delivery_seed_helpers')
    project_ids = list(projects.values_list('pk', flat=True))
    foreign_sources = DeliveryPromptSource.objects.exclude(context__project_id__in=project_ids).filter(
        models.Q(signature_evidence__contract__project_id__in=project_ids)
        | models.Q(signature_evidence__amendment__contract__project_id__in=project_ids),
    )
    foreign_contexts = DeliveryPromptContext.objects.exclude(project_id__in=project_ids).filter(
        models.Q(contract__project_id__in=project_ids)
        | models.Q(scope__contract__project_id__in=project_ids)
        | models.Q(stage__phase__scope__contract__project_id__in=project_ids),
    )
    if foreign_sources.exists() or foreign_contexts.exists():
        raise CommandError('Otro proyecto conserva referencias a esta evidencia. No se borraron datos ni archivos; incluye todos los proyectos afectados o conserva esta evidencia.')
    try:
        with transaction.atomic():
            files = _clear_fake_delivery_rows(project_ids)
            transaction.on_commit(lambda: _delete_delivery_files(files))
    except ProtectedError as error:
        raise CommandError('La evidencia sigue referenciada fuera del reinicio autorizado. No se borraron datos ni archivos.') from error


def _delete_delivery_files(files):
    for storage, name in files:
        storage.delete(name)


def _clear_fake_delivery_rows(project_ids):
    from accounts.models import (
        ContractAmendment, ContractSignatureEvidence, DeliveryDocumentLink,
        DeliveryDocumentSnapshot, DeliveryMessage, DeliveryOperation, DeliveryPhase,
        DeliveryPublication, DeliveryReviewDocumentEvidence, DeliveryScope,
        DeliveryStage, DeliveryWorkspace, DeliveryPromptContext, DeliveryPromptSource,
        ProjectContract, Requirement, RequirementReview,
    )
    files = []
    for source in DeliveryPromptSource.objects.filter(context__project_id__in=project_ids):
        if source.file:
            files.append((source.file.storage, source.file.name))
        source.delete()
    for evidence in DeliveryReviewDocumentEvidence.objects.filter(
        review__publication__stage__phase__scope__contract__project_id__in=project_ids,
    ):
        if evidence.file:
            files.append((evidence.file.storage, evidence.file.name))
        evidence.delete()
    RequirementReview.objects.filter(requirement__stage__phase__scope__contract__project_id__in=project_ids).delete()
    for snapshot in DeliveryDocumentSnapshot.objects.filter(publication__stage__phase__scope__contract__project_id__in=project_ids):
        if snapshot.file:
            files.append((snapshot.file.storage, snapshot.file.name))
        snapshot.delete()
    evidence = ContractSignatureEvidence.objects.filter(
        models.Q(contract__project_id__in=project_ids) | models.Q(amendment__contract__project_id__in=project_ids),
    )
    for row in evidence:
        if row.file:
            files.append((row.file.storage, row.file.name))
        row.delete()
    DeliveryPublication.objects.filter(stage__phase__scope__contract__project_id__in=project_ids).delete()
    DeliveryMessage.objects.filter(project_id__in=project_ids).delete()
    DeliveryDocumentLink.objects.filter(project_id__in=project_ids).delete()
    Requirement.objects.filter(stage__phase__scope__contract__project_id__in=project_ids).delete()
    DeliveryPromptContext.objects.filter(project_id__in=project_ids).delete()
    DeliveryStage.objects.filter(phase__scope__contract__project_id__in=project_ids).delete()
    DeliveryPhase.objects.filter(scope__contract__project_id__in=project_ids).delete()
    DeliveryScope.objects.filter(contract__project_id__in=project_ids).delete()
    ContractAmendment.objects.filter(contract__project_id__in=project_ids).delete()
    ProjectContract.objects.filter(project_id__in=project_ids).delete()
    DeliveryWorkspace.objects.filter(project_id__in=project_ids).delete()
    DeliveryOperation.objects.filter(project_id__in=project_ids).delete()
    return files
