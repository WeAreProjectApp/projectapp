"""Restore missing Gestor identities from exact confirmed files, never drafts."""
import hashlib
import json

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError

from content.models import BusinessProposal, Document, DocumentFolder, ProposalDocument
from content.services.proposal_approval_service import ApprovalConflict, load_proposal, source_hash
from content.services.proposal_shared_documents import latest_package


def preview(proposal):
    package = latest_package(proposal)
    manifest = package.manifest if package else proposal.platform_approval_manifest
    rows = list((package.files if package else proposal.approval_files).select_related(
        'proposal__client', 'deliverable', 'package', 'binding',
    ).order_by('pk'))
    project = proposal.deliverable.project if proposal.deliverable_id else None
    blockers = []
    if not project or not manifest or not rows:
        blockers.append('Confirma primero el cierre con cliente, proyecto y archivos.')
    root = DocumentFolder.objects.filter(managed_project=project).first() if project else None
    if project and (not root or root.is_archived or root.project_id != project.pk or root.client_user_id != project.client_id):
        blockers.append('Concilia primero la carpeta raíz del proyecto.')
    bindings = {row.source_key: row for row in proposal.document_bindings.select_related('document', 'current_file')}
    files, missing = [], []
    expected = {row.get('id'): row for row in manifest.get('files', []) if isinstance(row, dict)}
    if set(expected) != {row.pk for row in rows}:
        blockers.append('Los archivos no coinciden con el manifiesto confirmado.')
    keys = [row.source_key for row in rows]
    if len(keys) != len(set(keys)):
        blockers.append('El cierre tiene identidades documentales repetidas.')
    kinds = {row.document_type for row in rows}
    if not kinds.intersection({'contract', 'contract_product'}):
        blockers.append('Falta el contrato confirmado de producto o el contrato único.')
    from accounts.services.delivery_contract_sources import _confirmed_for_project
    for row in rows:
        exact = bool(project and _confirmed_for_project(row, project))
        digest, size = hashlib.sha256(), 0
        try:
            with row.file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(65536), b''):
                    digest.update(chunk)
                    size += len(chunk)
            exact = exact and size == row.size and digest.hexdigest() == row.sha256
        except (OSError, ValueError):
            exact = False
        if not exact:
            blockers.append(f'El archivo aprobado «{row.title}» no está disponible o no coincide con su evidencia.')
        binding = bindings.get(row.source_key)
        if binding and (binding.current_file_id != row.pk or not binding.is_current
                        or binding.document.project_id != getattr(project, 'pk', None)
                        or binding.document.client_user_id != getattr(project, 'client_id', None)
                        or binding.document.is_archived or row.binding_id != binding.pk):
            blockers.append(f'Revisa el vínculo existente de «{row.title}»; no se sustituirá automáticamente.')
        if binding is None:
            if row.binding_id:
                blockers.append(f'El archivo «{row.title}» tiene otro vínculo; revisa su identidad.')
            missing.append({'source_key': row.source_key, 'title': row.title,
                            'file_id': row.pk, 'folder': 'Contratos' if row.document_type in ProposalDocument.CONTRACT_DOC_TYPES else 'Anexos'})
        files.append([row.pk, row.source_key, row.title, row.document_type, row.filename,
                      row.file.name, row.sha256, row.size, digest.hexdigest(), size, exact])
    # An older manually filed document must not silently become a second copy.
    candidates = list(Document.objects.filter(
        Q(source_proposal=proposal) | Q(metadata__proposal_id=proposal.pk),
        proposal_binding__isnull=True, source_version__isnull=True,
    ).order_by('pk').values('id', 'title', 'folder_id', 'updated_at'))
    if missing and candidates:
        blockers.append('Hay documentos anteriores sin vínculo. Revisa sus identidades antes de crear copias.')
    folders = list(DocumentFolder.objects.filter(
        Q(managed_project=project) | Q(project=project),
    ).order_by('pk').values('id', 'name', 'parent_id', 'system_key', 'project_id', 'client_user_id', 'is_archived')) if project else []
    snapshot = {'proposal_id': proposal.pk, 'package_id': package.pk if package else None,
                'source_hash': source_hash(proposal),
                'manifest': manifest, 'files': files, 'folders': folders, 'candidates': candidates,
                'bindings': [[key, value.pk, value.document_id, value.current_file_id, value.is_current,
                              value.document.folder_id, value.document.updated_at] for key, value in sorted(bindings.items())]}
    expected_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    approved_annexes = {row.source_key for row in rows if row.document_type not in ProposalDocument.CONTRACT_DOC_TYPES}
    draft_keys = {'commercial', 'technical'} | {
        f'original-{pk}' for pk in proposal.proposal_documents.filter(is_archived=False)
        .exclude(document_type__in=ProposalDocument.CONTRACT_DOC_TYPES).values_list('pk', flat=True)
    }
    return {'proposal_id': proposal.pk, 'package_number': package.number if package else None,
            'expected_hash': expected_hash, 'missing_documents': missing, 'blockers': blockers,
            'requires_new_revision': sorted(draft_keys - approved_annexes),
            'can_reconcile': not blockers, 'already_complete': bool(package and not missing and not blockers)}


@transaction.atomic
def reconcile(proposal_id, *, expected_hash, actor):
    if not actor or not actor.is_active or not actor.is_staff:
        raise PermissionDenied('Esta acción requiere acceso administrativo.')
    from accounts.models import Project
    original = load_proposal(proposal_id)
    project_id = original.deliverable.project_id if original.deliverable_id else None
    if project_id:
        Project.objects.select_for_update().get(pk=project_id)
    proposal = BusinessProposal.objects.select_for_update().get(pk=proposal_id)
    if (proposal.deliverable.project_id if proposal.deliverable_id else None) != project_id:
        raise ApprovalConflict({'detail': 'El proyecto cambió. Revisa nuevamente.', 'code': 'stale_source'})
    list(proposal.approval_packages.select_for_update())
    list(proposal.approval_files.select_for_update())
    bindings = list(proposal.document_bindings.select_for_update())
    list(Document.objects.select_for_update().filter(pk__in=[row.document_id for row in bindings]))
    from content.models.document_folder import lock_document_folder_mutations
    lock_document_folder_mutations()
    review = preview(load_proposal(proposal_id))
    if review['expected_hash'] != expected_hash:
        raise ApprovalConflict({'detail': 'El paquete o sus vínculos cambiaron. Revisa nuevamente.', 'code': 'stale_source'})
    if review['blockers']:
        raise ValidationError({'documents': review['blockers']})
    if review['already_complete']:
        return review
    package = latest_package(proposal)
    rows = list((package.files if package else proposal.approval_files).order_by('pk'))
    from content.services.proposal_shared_documents import bind_package_files, create_package
    if package:
        bind_package_files(proposal, package, rows, actor=actor)
    else:
        create_package(proposal, actor=actor, request_id=f'historical-{proposal.pk}',
                       payload_hash=expected_hash, source_hash=source_hash(load_proposal(proposal_id)),
                       written_rows=rows, manifest=proposal.platform_approval_manifest)
    from content.models import ProposalChangeLog
    ProposalChangeLog.objects.create(proposal=proposal, change_type='updated', field_name='document_bindings',
        actor_type='seller', description=f'Recuperados {len(review["missing_documents"])} vínculos de documentos ya aprobados; actor {actor.pk}.')
    return preview(load_proposal(proposal_id))
