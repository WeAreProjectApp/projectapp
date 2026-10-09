"""The only transactional writer of default contract text and mirror artifacts."""
import hashlib
import logging

from django.db import transaction
from django.utils import timezone

from content.models import ContractTemplate, ContractTemplateVersion, ContractTemplateMirror, Document
from content.services.contract_template_validation import (
    ContractTemplateError, TEXT_FIELDS, VARIANTS, apply_patches, markdown_diff,
    placeholders, validate_markdown, variant_key,
)

logger = logging.getLogger(__name__)

MIRROR_TITLES = {
    'combined': 'Contrato unificado de producto y servicio',
    'product': 'Contrato de producto — desarrollo e implementación de software',
    'service': 'Contrato de servicio — hosting, mantenimiento y soporte',
}


def default_template(*, lock=False):
    queryset = ContractTemplate.objects.select_for_update() if lock else ContractTemplate.objects
    template = queryset.filter(is_default=True).first()
    if template is None:
        raise ContractTemplateError('No existe una plantilla predeterminada.', code='NOT_FOUND')
    return template


def text(template, variant):
    return getattr(template, TEXT_FIELDS[variant_key(variant)])


def current_revision(template, variant):
    return template.versions.filter(variant=variant).first()


def template_etag(template, variant):
    revision = current_revision(template, variant)
    version = revision.version if revision else 0
    return hashlib.sha256(f'{template.pk}:{variant}:{version}:{text(template, variant)}'.encode()).hexdigest()


def resource_etags(_arguments=None, *, template=None):
    from content.services.document_write_service import document_etag
    template = template or default_template()
    resources = {key: template_etag(template, key) for key in VARIANTS}
    for mirror in template.mirrors.select_related('document'):
        identity = f'{mirror.pk}:{mirror.document_id}:{mirror.document.folder_id}:{mirror.revision_id}:{mirror.synced_at.isoformat()}:{document_etag(mirror.document)}'
        resources[f'mirror:{mirror.variant}'] = hashlib.sha256(identity.encode()).hexdigest()
    return resources


def read_template(variant='combined', *, template=None):
    variant_key(variant)
    template = template or default_template()
    revision = current_revision(template, variant)
    markdown = text(template, variant)
    return {
        'id': template.pk, 'name': template.name, 'variant': variant,
        'markdown': markdown, 'content_markdown': markdown,
        'placeholders': ['{' + key + '}' for key in sorted(placeholders(markdown))], 'version': revision.version if revision else 0,
        'version_id': revision.pk if revision else None,
        'updated_at': (revision.created_at if revision else template.updated_at).isoformat(),
        'etag': template_etag(template, variant),
    }


def list_versions(variant, *, offset=0, limit=20):
    variant_key(variant)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 50:
        raise ContractTemplateError('Usa offset >= 0 y limit entre 1 y 50.')
    queryset = default_template().versions.filter(variant=variant)
    return {'variant': variant, 'total': queryset.count(), 'versions': [{
        'version_id': row.pk, 'version': row.version, 'markdown': row.markdown,
        'author': row.author_label, 'created_at': row.created_at.isoformat(),
        'change_note': row.change_note, 'restored_from_version_id': row.restored_from_id,
    } for row in queryset[offset:offset + limit]]}


def mirror_metadata(document):
    from content.services.contract_mirror_service import mirror_binding
    binding = mirror_binding(document)
    if not binding:
        return {}
    template, variant, mirror = binding
    revision = mirror.revision if mirror else current_revision(template, variant)
    return {
        'contract_variant': variant, 'contract_version': revision.version if revision else 0,
        'contract_synced_at': mirror.synced_at.isoformat() if mirror else None,
    }


def list_mirrors():
    from content.mcp.document_tools import _folder_path
    from content.services.contract_mirror_service import (
        pinned_folder_state,
        pinned_mirror_folder,
    )

    template = default_template()
    folder, _source = pinned_mirror_folder(template)
    mirrors = {row.variant: row for row in template.mirrors.select_related('document__folder', 'revision')}
    rows = []
    for key in VARIANTS:
        mirror = mirrors.get(key)
        rows.append({
            'variant': key, 'document_id': mirror.document_id if mirror else None,
            'title': mirror.document.title if mirror else MIRROR_TITLES[key],
            'folder_id': mirror.document.folder_id if mirror else None,
            'folder_path': _folder_path(mirror.document.folder) if mirror and mirror.document.folder_id else None,
            'folder_movable': bool(folder and not folder.is_archived and mirror and mirror.document.folder_id == folder.pk),
            'version': mirror.revision.version if mirror else None,
            'last_synced_at': mirror.synced_at.isoformat() if mirror else None,
            'synchronized': bool(mirror and mirror.revision.markdown == text(template, key)
                and mirror.revision.template_id == template.pk and mirror.revision.variant == key
                and mirror.pdf_content and bytes(mirror.pdf_content).startswith(b'%PDF-')
                and not mirror.document.is_archived and mirror.document.folder_id
                and folder and mirror.document.folder_id == folder.pk and not folder.is_archived),
        })
    return {'mirrors': rows, 'pinned_folder': pinned_folder_state()}


def _entries(arguments, *, restore=False):
    if not isinstance(arguments, dict):
        raise ContractTemplateError('Los argumentos deben ser un objeto.')
    allowed = {'variant', 'markdown', 'patches', 'if_match', 'change_note', 'related_updates'} | ({'version_id'} if restore else set())
    if set(arguments) - allowed:
        raise ContractTemplateError('Hay argumentos desconocidos.')
    related = arguments.get('related_updates', [])
    if not isinstance(related, list) or len(related) > 2 or any(not isinstance(row, dict) for row in related):
        raise ContractTemplateError('related_updates admite hasta dos variantes adicionales.')
    entries = [{key: value for key, value in arguments.items() if key not in {'related_updates', 'change_note'}}, *related]
    seen = set()
    for row in entries:
        if set(row) - {'variant', 'markdown', 'patches', 'if_match', 'version_id'}:
            raise ContractTemplateError('Hay argumentos desconocidos en related_updates.')
        key = variant_key(row.get('variant'))
        if key in seen:
            raise ContractTemplateError('No repitas variantes en el lote.')
        seen.add(key)
        sources = [field for field in ('markdown', 'patches', 'version_id') if field in row]
        if len(sources) != 1 or (not restore and 'version_id' in row):
            raise ContractTemplateError('Indica exactamente uno de markdown o patches; para restaurar usa version_id.')
        if 'version_id' in row and (type(row['version_id']) is not int or row['version_id'] < 1):
            raise ContractTemplateError('version_id debe ser un entero positivo.')
        if restore and row is entries[0] and 'version_id' not in row:
            raise ContractTemplateError('version_id es obligatorio para restaurar.')
    return entries


def prepare_update(arguments, *, restore=False, require_match=False, template=None):
    from content.services.contract_template_consistency import check_consistency
    template = template or default_template()
    entries = _entries(arguments, restore=restore)
    note = arguments.get('change_note', '')
    if require_match and (not isinstance(note, str) or not note.strip() or len(note) > 4000):
        raise ContractTemplateError('change_note debe explicar el cambio (máximo 4000 caracteres).')
    candidate = {key: text(template, key) for key in VARIANTS}
    changes = []
    for row in entries:
        key = row['variant']
        etag = template_etag(template, key)
        if require_match and not row.get('if_match'):
            raise ContractTemplateError('if_match es obligatorio.', code='PRECONDITION_REQUIRED')
        if row.get('if_match') is not None and row['if_match'] != etag:
            raise ContractTemplateError('La plantilla cambió; vuelve a leerla.', code='STALE_VERSION', details={'variant': key, 'current_etag': etag})
        restored = None
        if 'version_id' in row:
            restored = template.versions.filter(pk=row['version_id'], variant=key).first()
            if restored is None:
                raise ContractTemplateError('La versión no pertenece a esta variante.', code='NOT_FOUND')
            markdown = restored.markdown
        elif 'markdown' in row:
            markdown = row['markdown']
        else:
            markdown = apply_patches(candidate[key], row['patches'])
        fields = validate_markdown(markdown, key)
        before = candidate[key]
        candidate[key] = markdown
        mirror = template.mirrors.filter(variant=key).select_related('document').first()
        changes.append({
            'variant': key, 'markdown': markdown, 'if_match': etag, 'placeholders': ['{' + name + '}' for name in fields],
            'diff': markdown_diff(before, markdown, key),
            'document_id': mirror.document_id if mirror else None,
            'restored_from_version_id': restored.pk if restored else None,
            'changed': before != markdown,
        })
    consistency = check_consistency(candidate)
    return {'changes': changes, 'consistency': consistency, 'change_note': note,
            'documents_to_sync': [{'variant': row['variant'], 'document_id': row['document_id'], 'status': 'ready' if row['document_id'] else 'missing'} for row in changes if row['changed']],
            'resource_etags': resource_etags(template=template)}


def _diff_summary(diff):
    lines = diff.splitlines()
    added = sum(line.startswith('+') and not line.startswith('+++') for line in lines)
    removed = sum(line.startswith('-') and not line.startswith('---') for line in lines)
    headings = [line for line in lines if line.startswith(('+##', '-##'))]
    return f'Líneas agregadas: {added}; líneas retiradas: {removed}.' + ('\n' + '\n'.join(headings[:20]) if headings else '')


def _synchronize(template, revision, mirror, *, actor, note, diff):
    from content.services.contract_mirror_service import render_mirror_pdf
    from content.services.document_note_service import create_note
    key = revision.variant
    stage = 'pdf'
    try:
        pdf = render_mirror_pdf(template, key)
        if not pdf or not pdf.startswith(b'%PDF-'):
            raise ValueError('El renderizador no produjo un PDF.')
        stage = 'mirror'
        mirror.revision = revision
        mirror.pdf_content = pdf
        mirror.synced_at = timezone.now()
        mirror.save()
        document = mirror.document
        document.save(update_fields=['updated_at'])
        stage = 'private_note'
        label = {'combined': 'combinada', 'product': 'de producto', 'service': 'de servicio'}[key]
        create_note(document, actor=actor, title=f'Plantilla {label} — versión {revision.version}',
            content=f'Versión {revision.version}\nFecha: {mirror.synced_at.isoformat()}\n{note}\n\n{_diff_summary(diff)}')
    except Exception as exc:
        logger.exception('Contract mirror synchronization failed variant=%s document_id=%s stage=%s', key, mirror.document_id, stage)
        raise ContractTemplateError('No se sincronizó el espejo; no se aplicó ningún cambio.', code='MIRROR_SYNC_FAILED',
            details={'variant': key, 'document_id': mirror.document_id, 'stage': stage, 'applied': False}) from exc


@transaction.atomic
def apply_update(arguments, *, actor, credential=None, restore=False, expected_etags=None):
    from content.services.contract_mirror_service import pinned_mirror_folder

    template = default_template(lock=True)
    mirrors = {row.variant: row for row in template.mirrors.select_for_update().select_related('document', 'document__folder', 'revision').order_by('pk')}
    documents = list(Document.objects.select_for_update().filter(pk__in=[m.document_id for m in mirrors.values()]).order_by('pk'))
    documents_by_id = {row.pk: row for row in documents}
    if expected_etags is not None and expected_etags != resource_etags(template=template):
        raise ContractTemplateError('Las plantillas cambiaron desde la vista previa.', code='STALE_VERSION')
    folder, source = pinned_mirror_folder(template)
    if source == 'unpinned':
        hint = 'Ejecuta initialize_contract_template_mirrors con --apply y --folder-id para fijar la carpeta de los espejos.'
        raise ContractTemplateError(
            f'Los espejos no tienen una carpeta fijada; no se aplicó ningún cambio. {hint}',
            code='MIRROR_SYNC_FAILED', details={'stage': 'folder_pin', 'applied': False, 'hint': hint},
        )
    prepared = prepare_update(arguments, restore=restore, require_match=True, template=template)
    if not prepared['consistency']['consistent']:
        raise ContractTemplateError('Las variantes no son coherentes; corrige el lote antes de guardar.',
            code='TEMPLATES_INCONSISTENT', details=prepared['consistency'])
    results = []
    for change in prepared['changes']:
        key = change['variant']
        mirror = mirrors.get(key)
        if mirror is None or documents_by_id[mirror.document_id].is_archived or documents_by_id[mirror.document_id].folder_id != folder.pk or folder.is_archived or mirror.revision.template_id != template.pk or mirror.revision.variant != key:
            raise ContractTemplateError('El espejo no está vinculado correctamente a esta variante en Contratos; no se aplicó ningún cambio.',
                code='MIRROR_SYNC_FAILED', details={'variant': key, 'document_id': change['document_id'], 'stage': 'mirror', 'applied': False})
        mirror.document = documents_by_id[mirror.document_id]
        if not change['changed']:
            results.append({'variant': key, 'changed': False, 'version': mirror.revision.version, 'document_id': mirror.document_id})
            continue
        previous = current_revision(template, key)
        revision = ContractTemplateVersion.objects.create(
            template=template, variant=key, version=previous.version + 1 if previous else 1,
            markdown=change['markdown'], author=actor, credential=credential,
            author_label=actor.get_username() if actor else 'Consola', change_note=prepared['change_note'],
            restored_from_id=change['restored_from_version_id'],
        )
        setattr(template, TEXT_FIELDS[key], change['markdown'])
        template.save(update_fields=[TEXT_FIELDS[key], 'updated_at'])
        _synchronize(template, revision, mirror, actor=actor, note=prepared['change_note'], diff=change['diff'])
        results.append({'variant': key, 'changed': True, 'version': revision.version, 'version_id': revision.pk,
            'document_id': mirror.document_id, 'synchronized': True, 'last_synced_at': mirror.synced_at.isoformat(),
            'etag': template_etag(template, key)})
    return {'applied': True, 'results': results, 'consistency': prepared['consistency']}
