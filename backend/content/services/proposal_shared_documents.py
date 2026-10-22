"""Shared document identities; reads never provision and approved bytes never change."""
from copy import deepcopy
from django.db import transaction
from rest_framework.exceptions import ValidationError
from content.models import Document, DocumentFolder, ProposalApprovalPackage, ProposalDocument, ProposalDocumentBinding
from content.services.project_document_folder_service import require_project_folder


def binding_for(document):
    try:
        return document.proposal_binding
    except ProposalDocumentBinding.DoesNotExist:
        return None


def latest_package(proposal):
    return proposal.approval_packages.order_by('-number').first()


def folders_for(project):
    from content.services.project_document_folder_service import ProjectFolderReconciliationRequired
    try:
        root = require_project_folder(project)
    except ProjectFolderReconciliationRequired as exc:
        raise ValidationError({'project_id': str(exc)}) from exc
    from content.models.document_folder import lock_document_folder_mutations
    lock_document_folder_mutations()
    result = {}
    for key, name in [('contracts', 'Contratos'), ('annexes', 'Anexos')]:
        system_key = f'approval:project:{project.pk}:{key}'
        if not DocumentFolder.objects.filter(system_key=system_key).exists():
            matches = list(root.children.select_for_update().filter(name__iexact=name))
            if matches:
                if len(matches) != 1 or matches[0].is_archived or matches[0].system_key or matches[0].project_id != project.pk or matches[0].client_user_id != project.client_id:
                    raise ValidationError({'folder': f'Revisa la carpeta existente «{name}» antes de confirmar; no se creará un duplicado.'})
                matches[0].system_key = system_key
                matches[0].save(update_fields=['system_key'])
        folder, _ = DocumentFolder.objects.get_or_create(
            system_key=system_key,
            defaults={'name': name, 'parent': root, 'project': project, 'client_user_id': project.client_id,
                      'creation_source': 'system', 'creation_operation': 'proposal_approval'},
        )
        if folder.parent_id != root.pk or folder.is_archived or folder.project_id != project.pk or folder.client_user_id != project.client_id:
            raise ValidationError({'folder': 'La carpeta del cierre cambió. Revisa su organización antes de confirmar.'})
        result[key] = folder
    return root, result


def file_source(proposal, key):
    if key.startswith('original-'):
        return proposal.proposal_documents.filter(pk=int(key.removeprefix('original-'))).first()
    if key in ('contract', 'contract_product', 'contract_service'):
        return proposal.proposal_documents.filter(document_type=key, is_archived=False).order_by('-pk').first()
    return None


def create_package(proposal, *, actor, request_id, payload_hash, source_hash, written_rows, manifest):
    previous = latest_package(proposal)
    package = ProposalApprovalPackage.objects.create(
        proposal=proposal, number=previous.number + 1 if previous else 1,
        request_id=request_id, payload_hash=payload_hash, source_hash=source_hash,
        manifest=deepcopy(manifest), created_by=actor,
    )
    root = bind_package_files(proposal, package, written_rows, actor=actor)
    package.manifest['files'] = [{'id': row.pk, 'source_key': row.source_key, 'sha256': row.sha256, 'size': row.size} for row in written_rows]
    package.save(update_fields=['manifest'])
    return package, root


def bind_package_files(proposal, package, written_rows, *, actor):
    project = proposal.deliverable.project
    root, folders = folders_for(project)
    proposal.document_bindings.update(is_current=False)
    for row in written_rows:
        source = file_source(proposal, row.source_key)
        key = row.source_key
        if key.startswith('custom-') and row.document_type in ProposalDocument.CONTRACT_DOC_TYPES:
            key = f'custom-{row.document_type}'
        binding = proposal.document_bindings.filter(source_key=key).first()
        if binding is None:
            folder = folders['contracts' if row.document_type in ProposalDocument.CONTRACT_DOC_TYPES else 'annexes']
            from content.models import DocumentType
            kind, _ = DocumentType.objects.get_or_create(code='markdown', defaults={'name': 'Documento'})
            document = Document.objects.create(document_type=kind, title=row.title[:255], folder=folder, project=project,
                client_user_id=project.client_id, deliverable=proposal.deliverable,
                created_by=actor, updated_by=actor, language=proposal.language, source_proposal=proposal,
                metadata={'proposal_approval': True})
            binding = ProposalDocumentBinding.objects.create(document=document, proposal=proposal,
                source_key=key, source_document=source)
        if binding.document.title != row.title[:255]:
            binding.document.title = row.title[:255]
            binding.document.updated_by = actor
            binding.document.save(update_fields=['title', 'updated_by', 'updated_at'])
        row.package = package
        row.binding = binding
        row.save(update_fields=['package', 'binding'])
        binding.current_file = row
        binding.is_current = True
        binding.save(update_fields=['current_file', 'is_current'])
    return root


def can_replace_binary(binding):
    return binding.is_current and (binding.source_key.startswith('custom-') or bool(
        binding.source_document_id and not binding.source_document.is_generated
        and binding.source_document.document_type not in ProposalDocument.CONTRACT_DOC_TYPES))


def summary(binding, *, package=None, current_hash=None):
    from content.services.proposal_approval_service import source_hash
    package = package or latest_package(binding.proposal)
    current_hash = current_hash or source_hash(binding.proposal)
    cache = getattr(binding, '_prefetched_objects_cache', {})
    revisions = cache.get('revisions')
    if revisions is None:
        revisions = binding.revisions.select_related('package').order_by('-pk')
    return {
        'can_replace_binary': can_replace_binary(binding),
        'proposal_id': binding.proposal_id, 'document_id': binding.document_id,
        'source_key': binding.source_key, 'is_current': binding.is_current,
        'package_number': package.number if package else None,
        'current_file_id': binding.current_file_id,
        'source_hash': current_hash,
        'has_pending_changes': bool(package and package.source_hash != current_hash),
        'source_editor_url': f'/panel/proposals/{binding.proposal_id}/edit?tab=' + ('technical' if binding.source_key == 'technical' else 'sections' if binding.source_key == 'commercial' else 'documents'),
        'api_url': f'/api/documents/{binding.document_id}/proposal-source/',
        'history': [{'id': row.pk, 'package_number': row.package.number if row.package_id else None,
                     'title': row.title, 'sha256': row.sha256, 'filename': row.filename,
                     'download_url': f'/api/proposals/{binding.proposal_id}/approval/files/{row.pk}/'}
                    for row in revisions],
    }


@transaction.atomic
def reconfirm(proposal_id, payload, *, actor, files=()):
    from content.models import BusinessProposal, ProposalApprovalFile
    from content.services.proposal_approval_service import ApprovalConflict, _packet, source_hash, _read_file
    from content.serializers.proposal_approval import ProposalApprovalSerializer
    from django.core.files.base import ContentFile
    import hashlib
    import json
    proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
    previous = latest_package(proposal)
    if not previous:
        raise ValidationError({'detail': 'Confirma primero el cierre inicial.'})
    if not proposal.deliverable_id or not proposal.deliverable.project_id:
        raise ApprovalConflict({'detail': 'Reasigna primero el proyecto conservado.', 'code': 'retained_project'})
    if not isinstance(payload.get('request_id'), str) or not payload['request_id'] or len(payload['request_id']) > 100:
        raise ValidationError({'request_id': 'Indica un identificador estable de hasta 100 caracteres.'})
    hasher = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode())
    for file in files:
        hasher.update(_read_file(file))
    digest = hasher.hexdigest()
    existing = proposal.approval_packages.filter(request_id=payload['request_id']).first()
    if existing:
        if existing.payload_hash != digest:
            raise ApprovalConflict({'detail': 'Ese identificador ya confirmó otro contenido.', 'code': 'idempotency_conflict'})
        return existing
    current_hash = source_hash(proposal)
    if payload.get('source_hash') != current_hash:
        raise ApprovalConflict({'detail': 'Los documentos cambiaron. Revisa nuevamente.', 'code': 'stale_source'})
    list(proposal.sections.select_for_update().values_list('pk', flat=True))
    list(proposal.proposal_documents.select_for_update().values_list('pk', flat=True))
    data = dict(payload, action='confirm', accept_proposal=False,
                client_profile_id=proposal.client_id, project_id=proposal.deliverable.project_id)
    data.setdefault('use_proposal_contracts', previous.manifest.get('use_proposal_contracts', True))
    data.pop('new_client', None)
    data.pop('new_project', None)
    serializer = ProposalApprovalSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    # Custom contracts remain the chosen source unless explicitly replaced.
    retained = []
    if not files and not data['use_proposal_contracts'] and not previous.manifest.get('use_proposal_contracts', True):
        data['use_proposal_contracts'] = False
        from content.services.contract_variants import approved_doc_types
        required = approved_doc_types(proposal)
        retained = [row for row in previous.files.filter(source_key__startswith='custom-')
                    if row.document_type not in ProposalDocument.CONTRACT_DOC_TYPES or row.document_type in required]
        data['custom_documents'] = [{'title': row.title, 'document_type': row.document_type,
            **({'resource_id': row.source_key.removeprefix('custom-')} if row.document_type not in ProposalDocument.CONTRACT_DOC_TYPES else {})} for row in retained]
        from django.core.files.uploadedfile import SimpleUploadedFile
        files = []
        for row in retained:
            binding = row.binding
            file = binding.draft_file if binding and binding.draft_file else row.file
            filename = binding.draft_filename if binding and binding.draft_file else row.filename
            with file.open('rb') as stream:
                files.append(SimpleUploadedFile(filename, stream.read()))
    packet = _packet(proposal, data, files, profile=proposal.client)
    written, rows = [], []
    try:
        for key, title, kind, filename, content in packet:
            row = ProposalApprovalFile(proposal=proposal, project=proposal.deliverable.project,
                deliverable=proposal.deliverable, source_key=key, title=title, document_type=kind,
                filename=filename[:255], sha256=hashlib.sha256(content).hexdigest(), size=len(content), created_by=actor)
            # Reuse unchanged private revisions: only new content writes a new file.
            old = previous.files.filter(binding__source_key=key, sha256=row.sha256).first()
            draft = proposal.document_bindings.filter(source_key=key, draft_sha256=row.sha256).first()
            if old:
                row.file.name = old.file.name
            elif draft and draft.draft_file:
                row.file.name = draft.draft_file.name
            else:
                row.file.save(filename[:255], ContentFile(content), save=False)
                written.append((row.file.storage, row.file.name))
            row.save()
            rows.append(row)
        if source_hash(proposal) != current_hash:
            raise ApprovalConflict({'detail': 'La fuente cambió durante la generación.', 'code': 'stale_source'})
        from content.services.proposal_approval_service import _commercial_summary, _client_summary
        from accounts.services.technical_resources_sync import filtered_technical_doc_for_sync
        section = proposal.sections.filter(section_type='technical_document', is_enabled=True).first()
        manifest = dict(previous.manifest, use_proposal_contracts=data['use_proposal_contracts'],
            service_contract_approved=proposal.service_contract_approved,
            commercial_summary=_commercial_summary(proposal), client=_client_summary(proposal.client),
            technical_content=filtered_technical_doc_for_sync(proposal, section.content_json) if section else {})
        package, _root = create_package(proposal, actor=actor, request_id=data['request_id'],
            payload_hash=digest, source_hash=current_hash, written_rows=rows, manifest=manifest)
        if payload.get('accept_proposal') is True and proposal.status != BusinessProposal.Status.ACCEPTED:
            from content.services.proposal_status_service import change_status
            change_status(proposal, BusinessProposal.Status.ACCEPTED, source='approval_review', acting_user_id=actor.pk)
            package.source_hash = source_hash(proposal)
            package.save(update_fields=['source_hash'])
        return package
    except Exception:
        for storage, name in written:
            storage.delete(name)
        raise


@transaction.atomic
def replace_binary_source(binding_id, payload, upload, *, actor):
    """Replace a live binary source, preserving its identity and approved revision."""
    from django.core.files.base import ContentFile
    from content.models import BusinessProposal
    from content.services.proposal_approval_service import ApprovalConflict, source_hash
    binding = ProposalDocumentBinding.objects.get(pk=binding_id)
    proposal = BusinessProposal.objects.select_for_update().get(pk=binding.proposal_id)
    binding = ProposalDocumentBinding.objects.select_for_update().get(pk=binding_id)
    if not can_replace_binary(binding):
        raise ValidationError({'file': 'Este documento se genera desde datos estructurados. Edita su fuente.'})
    if payload.get('source_hash') != source_hash(proposal):
        raise ApprovalConflict({'detail': 'La fuente cambió. Conserva tu archivo y revisa nuevamente.', 'code': 'stale_source'})
    if not upload:
        raise ValidationError({'file': 'Adjunta el archivo que sustituirá al borrador.'})
    # Reuse the approval binary validator, including signatures and Office ZIP checks.
    from content.services.proposal_approval_service import _validate_custom_file
    filename, content = _validate_custom_file(upload)
    import hashlib
    old_name = binding.draft_file.name
    binding.draft_file.save(filename, ContentFile(content), save=False)
    storage, name = binding.draft_file.storage, binding.draft_file.name
    binding.draft_filename = filename[:255]
    binding.draft_sha256 = hashlib.sha256(content).hexdigest()
    try:
        binding.save(update_fields=['draft_file', 'draft_filename', 'draft_sha256'])
    except Exception:
        if name != old_name:
            storage.delete(name)
        raise
    return binding


def resolved_source_document(document):
    """Read adapter for legacy proposal/formalization consumers of a binary draft."""
    from copy import copy
    if hasattr(document, '_shared_binding'):
        binding = document._shared_binding
    else:
        binding = ProposalDocumentBinding.objects.filter(source_document=document).exclude(draft_file='').first()
    if binding is None or not binding.draft_file:
        return document
    resolved = copy(document)
    resolved.file = binding.draft_file
    return resolved
